from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.services import intake_registry_service
from app.services.connectivity_qa import service as connectivity_qa
from app.services.connectivity_qa.calibration import CALIBRATION_RULE_VERSION
from app.services.connectivity_qa.rules import MODEL_VERSION, RULE_VERSION, build_graph, graph_fingerprint
from app.services.utility_assets.domain import stable_fingerprint, stable_id

from .engine import trace_graph
from .models import normalize_request
from .profiles import TRACE_PROFILE_VERSION, TRACE_PROFILES, TRACE_RULE_VERSION, trace_definition, trace_types

DISCLAIMER = (
    "UtilitiesPlatform Network Trace V1 performs read-only analytical traversal of the platform's "
    "vendor-neutral canonical asset and relationship model. It is not an operational ArcFM, "
    "Smallworld, Esri Utility Network, outage-management, engineering, or telecom-provisioning trace."
)


class NetworkTraceError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


class NetworkTraceService:
    def connect(self) -> sqlite3.Connection:
        connection = connectivity_qa.connect()
        self._initialize(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS network_trace_runs (
                trace_run_id TEXT PRIMARY KEY,
                utility_vertical TEXT NOT NULL,
                trace_type TEXT NOT NULL,
                trace_profile TEXT NOT NULL,
                trace_rule_version TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                request_fingerprint TEXT NOT NULL,
                graph_fingerprint TEXT NOT NULL,
                asset_checksum TEXT NOT NULL,
                relationship_checksum TEXT NOT NULL,
                qa_run_id TEXT NOT NULL,
                calibration_run_id TEXT NOT NULL,
                status TEXT NOT NULL,
                outcome TEXT NOT NULL,
                start_asset_id TEXT NOT NULL,
                target_asset_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                lifecycle_mode TEXT NOT NULL,
                operational_mode TEXT NOT NULL,
                provisional_policy TEXT NOT NULL,
                qa_policy TEXT NOT NULL,
                request_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                assets_visited INTEGER NOT NULL DEFAULT 0,
                relationships_traversed INTEGER NOT NULL DEFAULT 0,
                paths_evaluated INTEGER NOT NULL DEFAULT 0,
                warnings_count INTEGER NOT NULL DEFAULT 0,
                blockers_count INTEGER NOT NULL DEFAULT 0,
                provisional_segments INTEGER NOT NULL DEFAULT 0,
                confidence TEXT NOT NULL,
                safe_error_code TEXT NOT NULL DEFAULT '',
                safe_error_message TEXT NOT NULL DEFAULT '',
                summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_network_trace_runs
                ON network_trace_runs(utility_vertical, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_network_trace_reuse
                ON network_trace_runs(input_fingerprint, request_fingerprint, status);

            CREATE TABLE IF NOT EXISTS network_trace_paths (
                trace_path_id TEXT PRIMARY KEY,
                trace_run_id TEXT NOT NULL,
                path_rank INTEGER NOT NULL,
                path_status TEXT NOT NULL,
                start_asset_id TEXT NOT NULL,
                end_asset_id TEXT NOT NULL,
                asset_ids_json TEXT NOT NULL,
                relationship_ids_json TEXT NOT NULL,
                hop_count INTEGER NOT NULL,
                confidence TEXT NOT NULL,
                provisional INTEGER NOT NULL,
                warnings_json TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                stopping_reason TEXT NOT NULL,
                qa_issue_group_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(trace_run_id, path_rank)
            );

            CREATE TABLE IF NOT EXISTS network_trace_steps (
                trace_step_id TEXT PRIMARY KEY,
                trace_run_id TEXT NOT NULL,
                trace_path_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                asset_id TEXT NOT NULL,
                entered_by_relationship_id TEXT NOT NULL,
                exited_by_relationship_id TEXT NOT NULL,
                step_role TEXT NOT NULL,
                operational_state TEXT NOT NULL,
                lifecycle_status TEXT NOT NULL,
                feeder_or_route_context TEXT NOT NULL,
                qa_issue_group_ids_json TEXT NOT NULL,
                trace_effect TEXT NOT NULL,
                decision TEXT NOT NULL,
                decision_reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(trace_path_id, sequence)
            );

            CREATE TABLE IF NOT EXISTS network_trace_events (
                trace_event_id TEXT PRIMARY KEY,
                trace_run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                relationship_id TEXT NOT NULL,
                issue_group_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                safe_details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS network_trace_history (
                history_id TEXT PRIMARY KEY,
                trace_run_id TEXT NOT NULL,
                action TEXT NOT NULL,
                prior_value_json TEXT NOT NULL,
                new_value_json TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.commit()

    def types(self, vertical: str | None = None) -> dict[str, Any]:
        try:
            return trace_types(vertical)
        except ValueError as exc:
            raise NetworkTraceError(str(exc), 404) from exc

    def run(self, vertical: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = dict(payload or {})
        trace_type = str(payload.get("trace_type", ""))
        try:
            definition = trace_definition(vertical, trace_type)
            payload.setdefault("direction", definition["default_direction"])
            request = normalize_request(vertical, payload, {item["trace_type"] for item in TRACE_PROFILES[vertical]["traces"]})
        except (KeyError, ValueError) as exc:
            raise NetworkTraceError(str(exc), 404 if "vertical" in str(exc).lower() else 422) from exc

        with self.connect() as connection:
            assets, all_assets, relationships = self._graph_rows(connection, vertical)
            nodes = {item["asset_id"]: item for item in assets}
            start = nodes.get(request["start_asset_id"])
            if not start:
                raise NetworkTraceError("Start asset was not found in the selected utility vertical.", 404)
            if start.get("asset_class") not in definition["start_asset_classes"]:
                allowed = ", ".join(definition["start_asset_classes"])
                raise NetworkTraceError(f"Start asset class is not allowed for this trace type. Allowed classes: {allowed}.")
            target_id = request["optional_target_asset_id"]
            if target_id and target_id not in nodes:
                raise NetworkTraceError("Target asset was not found in the selected utility vertical.", 404)

            graph_checksum, asset_checksum, relationship_checksum = graph_fingerprint(vertical, assets, relationships)
            qa_context = self._qa_context(connection, vertical)
            graph = build_graph(vertical, assets, all_assets, relationships)
            input_fingerprint = stable_fingerprint(
                vertical,
                asset_checksum,
                relationship_checksum,
                MODEL_VERSION,
                RULE_VERSION,
                qa_context["qa_run_fingerprint"],
                CALIBRATION_RULE_VERSION,
                qa_context["calibration_fingerprint"],
                qa_context["issue_group_fingerprint"],
                TRACE_PROFILE_VERSION,
                request["lifecycle_mode"],
                request["provisional_relationship_policy"],
                request["qa_policy"],
            )
            request_fingerprint = stable_fingerprint(
                request["start_asset_id"],
                request["optional_target_asset_id"],
                request["trace_type"],
                request["direction"],
                request["lifecycle_mode"],
                request["operational_mode"],
                request["provisional_relationship_policy"],
                request["qa_policy"],
                request["include_reference_relationships"],
                request["include_containment_relationships"],
                request["max_depth"],
                request["max_assets"],
            )
            if not request["force_recalculate"]:
                existing = connection.execute(
                    """SELECT trace_run_id FROM network_trace_runs
                    WHERE input_fingerprint = ? AND request_fingerprint = ? AND status = 'succeeded'
                    ORDER BY started_at DESC LIMIT 1""",
                    (input_fingerprint, request_fingerprint),
                ).fetchone()
                if existing:
                    result = self.run_detail(vertical, existing["trace_run_id"], connection)
                    result.update({
                        "reused": True,
                        "message": "No asset, relationship, QA, calibration, or trace-policy changes detected",
                    })
                    return result

            now = intake_registry_service.utc_now()
            trace_run_id = str(uuid.uuid4())
            profile_name = TRACE_PROFILES[vertical]["profile_name"]
            connection.execute(
                """INSERT INTO network_trace_runs
                (trace_run_id, utility_vertical, trace_type, trace_profile, trace_rule_version,
                 input_fingerprint, request_fingerprint, graph_fingerprint, asset_checksum,
                 relationship_checksum, qa_run_id, calibration_run_id, status, outcome,
                 start_asset_id, target_asset_id, direction, lifecycle_mode, operational_mode,
                 provisional_policy, qa_policy, request_json, started_at, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', '', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'indeterminate', ?)""",
                (
                    trace_run_id, vertical, request["trace_type"], profile_name, TRACE_RULE_VERSION,
                    input_fingerprint, request_fingerprint, graph_checksum, asset_checksum,
                    relationship_checksum, qa_context["qa_run_id"], qa_context["calibration_run_id"],
                    request["start_asset_id"], target_id, request["direction"], request["lifecycle_mode"],
                    request["operational_mode"], request["provisional_relationship_policy"], request["qa_policy"],
                    _dump(_safe_request(request)), now, now,
                ),
            )
            self._history(connection, trace_run_id, "run_started", {}, {"status": "running"}, request["requested_by"], "Read-only analytical trace requested.")
            connection.commit()

            try:
                result = trace_graph(request, definition, graph, qa_context["issue_groups"])
                self._persist_result(connection, trace_run_id, result, request)
            except Exception:
                self._fail_safely(connection, trace_run_id, request["requested_by"])
            return self.run_detail(vertical, trace_run_id, connection)

    def status(self, vertical: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT trace_run_id FROM network_trace_runs WHERE utility_vertical = ? ORDER BY started_at DESC LIMIT 1",
                (vertical,),
            ).fetchone()
            if not row:
                return {
                    "utility_vertical": vertical,
                    "status": "not_started",
                    "message": "Network Trace has not been run for this utility vertical.",
                    "disclaimer": DISCLAIMER,
                }
            return self.run_detail(vertical, row["trace_run_id"], connection)

    def runs(self, vertical: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            total = int(connection.execute(
                "SELECT COUNT(*) FROM network_trace_runs WHERE utility_vertical = ?", (vertical,),
            ).fetchone()[0])
            rows = connection.execute(
                """SELECT * FROM network_trace_runs WHERE utility_vertical = ?
                ORDER BY started_at DESC LIMIT ? OFFSET ?""", (vertical, limit, offset),
            ).fetchall()
        return {"items": [_safe_run(dict(row)) for row in rows], "pagination": _pagination(total, limit, offset)}

    def run_detail(
        self,
        vertical: str,
        trace_run_id: str,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self._vertical(vertical)
        owns_connection = connection is None
        connection = connection or self.connect()
        try:
            row = connection.execute(
                "SELECT * FROM network_trace_runs WHERE utility_vertical = ? AND trace_run_id = ?",
                (vertical, trace_run_id),
            ).fetchone()
            if not row:
                raise NetworkTraceError("Network trace run not found.", 404)
            result = _safe_run(dict(row))
            result["paths"] = self._paths(connection, trace_run_id)
            result["events"] = self._events(connection, trace_run_id)
            result["history"] = [
                {
                    **dict(item),
                    "prior_value": _load(item["prior_value_json"], {}),
                    "new_value": _load(item["new_value_json"], {}),
                }
                for item in connection.execute(
                    """SELECT history_id, action, prior_value_json, new_value_json, actor_type,
                    actor, reason, created_at FROM network_trace_history
                    WHERE trace_run_id = ? ORDER BY rowid""", (trace_run_id,),
                ).fetchall()
            ]
            for event in result["history"]:
                event.pop("prior_value_json", None)
                event.pop("new_value_json", None)
            return result
        finally:
            if owns_connection:
                connection.close()

    def paths(self, vertical: str, trace_run_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            self._required_run(connection, vertical, trace_run_id)
            return {"items": self._paths(connection, trace_run_id)}

    def steps(self, vertical: str, trace_run_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            self._required_run(connection, vertical, trace_run_id)
            rows = connection.execute(
                """SELECT s.*, a.canonical_name, a.asset_class, a.canonical_attributes_json
                FROM network_trace_steps s
                LEFT JOIN canonical_utility_assets a ON a.asset_id = s.asset_id
                WHERE s.trace_run_id = ? ORDER BY s.trace_path_id, s.sequence""", (trace_run_id,),
            ).fetchall()
        return {"items": [_safe_step(dict(row)) for row in rows]}

    def events(self, vertical: str, trace_run_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            self._required_run(connection, vertical, trace_run_id)
            return {"items": self._events(connection, trace_run_id)}

    def readiness(self, asset_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT asset_id, utility_vertical, asset_class, canonical_name, lifecycle_status,
                operational_status FROM canonical_utility_assets WHERE asset_id = ?""", (asset_id,),
            ).fetchone()
            if not row:
                raise NetworkTraceError("Asset not found.", 404)
            asset = dict(row)
            vertical = asset["utility_vertical"]
            context = self._qa_context(connection, vertical)
            relationships = connection.execute(
                """SELECT relationship_id, provisional FROM utility_asset_relationships
                WHERE from_asset_id = ? OR to_asset_id = ?""", (asset_id, asset_id),
            ).fetchall()
            relation_ids = {item["relationship_id"] for item in relationships}
            groups = [
                item for item in context["issue_groups"]
                if asset_id in item.get("affected_asset_ids", [])
                or relation_ids.intersection(item.get("affected_relationship_ids", []))
            ]
            latest = connection.execute(
                """SELECT trace_run_id, outcome, completed_at FROM network_trace_runs
                WHERE start_asset_id = ? ORDER BY started_at DESC LIMIT 1""", (asset_id,),
            ).fetchone()
            trace_count = int(connection.execute(
                "SELECT COUNT(DISTINCT trace_run_id) FROM network_trace_steps WHERE asset_id = ?", (asset_id,),
            ).fetchone()[0])
            recent_traces = [
                {
                    "trace_run_id": item["trace_run_id"],
                    "trace_type": item["trace_type"],
                    "outcome": item["outcome"],
                    "confidence": item["confidence"],
                    "completed_at": item["completed_at"],
                }
                for item in connection.execute(
                    """SELECT DISTINCT r.trace_run_id, r.trace_type, r.outcome, r.confidence, r.completed_at
                    FROM network_trace_runs r JOIN network_trace_steps s ON s.trace_run_id = r.trace_run_id
                    WHERE s.asset_id = ? ORDER BY r.started_at DESC LIMIT 10""", (asset_id,),
                ).fetchall()
            ]
            relationship_usage = {
                relation_id: {"traces_used": 0, "traces_stopped": 0}
                for relation_id in relation_ids
            }
            for path in connection.execute(
                """SELECT trace_run_id, relationship_ids_json, stopping_reason
                FROM network_trace_paths ORDER BY created_at DESC"""
            ).fetchall():
                used = set(_load(path["relationship_ids_json"], []))
                for relation_id in relation_ids.intersection(used):
                    relationship_usage[relation_id]["traces_used"] += 1
                    if path["stopping_reason"] not in {"target_reached", "source_reached", "terminal_reached"}:
                        relationship_usage[relation_id]["traces_stopped"] += 1
        eligible = [
            {"trace_type": item["trace_type"], "name": item["name"], "default_direction": item["default_direction"]}
            for item in TRACE_PROFILES[vertical]["traces"] if asset["asset_class"] in item["start_asset_classes"]
        ]
        blockers = [
            _safe_group(item) for item in groups
            if item.get("trace_impact") == "stops_trace" and item.get("review_status") not in {"false_positive", "superseded", "accepted_risk"}
        ]
        warnings = [_safe_group(item) for item in groups if item not in blockers]
        return {
            **asset,
            "eligible_trace_types": eligible,
            "trace_ready": bool(eligible),
            "qa_evaluated": bool(context["qa_run_id"]),
            "calibration_available": bool(context["calibration_run_id"]),
            "blockers": blockers,
            "warnings": warnings,
            "provisional_relationships": sum(bool(item["provisional"]) for item in relationships),
            "latest_trace": dict(latest) if latest else None,
            "trace_count": trace_count,
            "recent_traces": recent_traces,
            "relationship_trace_usage": relationship_usage,
            "confidence_notice": "Vendor-neutral analytical confidence based on canonical relationship evidence.",
            "disclaimer": DISCLAIMER,
        }

    def safe_summary(self, vertical: str, trace_run_id: str) -> dict[str, Any]:
        result = self.run_detail(vertical, trace_run_id)
        paths = result["paths"]
        warnings = [item for path in paths for item in path["warnings"]]
        blockers = [item for path in paths for item in path["blockers"]]
        return {
            "trace_run_id": result["trace_run_id"],
            "utility_vertical": result["utility_vertical"],
            "trace_type": result["trace_type"],
            "trace_profile": result["trace_profile"],
            "trace_profile_version": TRACE_PROFILE_VERSION,
            "trace_rule_version": result["trace_rule_version"],
            "input_fingerprint": result["input_fingerprint"],
            "request_fingerprint": result["request_fingerprint"],
            "start_asset_id": result["start_asset_id"],
            "target_asset_id": result["target_asset_id"],
            "outcome": result["outcome"],
            "confidence": result["confidence"],
            "assets_visited": result["assets_visited"],
            "relationships_traversed": result["relationships_traversed"],
            "path_count": result["paths_evaluated"],
            "branch_count": max(0, result["paths_evaluated"] - 1),
            "blockers": blockers,
            "warnings": warnings,
            "provisional_segments": result["provisional_segments"],
            "stopping_reasons": [path["stopping_reason"] for path in paths],
            "related_calibrated_issue_groups": sorted({
                issue_group_id for path in paths for issue_group_id in path["qa_issue_group_ids"]
            }),
            "ordered_safe_asset_ids": [path["asset_ids"] for path in paths],
            "ordered_relationship_ids": [path["relationship_ids"] for path in paths],
            "requested_options": result["request_options"],
            "started_at": result["started_at"],
            "completed_at": result["completed_at"],
            "disclaimer": DISCLAIMER,
        }

    def _graph_rows(
        self,
        connection: sqlite3.Connection,
        vertical: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        self._vertical(vertical)
        assets = [
            _json_row(dict(row), ("canonical_attributes_json", "geometry_summary_json", "evidence_json"))
            for row in connection.execute(
                "SELECT * FROM canonical_utility_assets WHERE utility_vertical = ? ORDER BY asset_id", (vertical,),
            ).fetchall()
        ]
        all_assets = [
            _json_row(dict(row), ("canonical_attributes_json", "geometry_summary_json", "evidence_json"))
            for row in connection.execute("SELECT * FROM canonical_utility_assets ORDER BY asset_id").fetchall()
        ]
        selected_ids = {row["asset_id"] for row in assets}
        relationships = [
            _json_row(dict(row), ("evidence_json",))
            for row in connection.execute("SELECT * FROM utility_asset_relationships ORDER BY relationship_id").fetchall()
            if row["from_asset_id"] in selected_ids or row["to_asset_id"] in selected_ids
        ]
        return assets, all_assets, relationships

    def _qa_context(self, connection: sqlite3.Connection, vertical: str) -> dict[str, Any]:
        qa = connection.execute(
            """SELECT qa_run_id, run_fingerprint FROM connectivity_qa_runs
            WHERE utility_vertical = ? AND status IN ('succeeded', 'partially_failed', 'blocked')
            ORDER BY started_at DESC LIMIT 1""", (vertical,),
        ).fetchone()
        calibration = connection.execute(
            """SELECT calibration_run_id, input_fingerprint FROM connectivity_qa_calibration_runs
            WHERE utility_vertical = ? AND qa_run_id = ? AND status = 'succeeded'
            ORDER BY started_at DESC LIMIT 1""", (vertical, qa["qa_run_id"] if qa else ""),
        ).fetchone()
        groups: list[dict[str, Any]] = []
        if calibration:
            groups = [
                _json_row(
                    dict(row),
                    (
                        "member_finding_ids_json", "affected_asset_ids_json",
                        "affected_relationship_ids_json", "related_rule_codes_json",
                        "vendor_equivalent_hints_json",
                    ),
                )
                for row in connection.execute(
                    """SELECT * FROM connectivity_qa_issue_groups
                    WHERE calibration_run_id = ? AND superseded = 0 ORDER BY issue_group_id""",
                    (calibration["calibration_run_id"],),
                ).fetchall()
            ]
            for group in groups:
                for field in (
                    "member_finding_ids", "affected_asset_ids", "affected_relationship_ids",
                    "related_rule_codes", "vendor_equivalent_hints",
                ):
                    group[field] = group.pop(f"{field}_json", [])
        group_fingerprint = stable_fingerprint([
            (
                item.get("issue_group_id"), item.get("trace_impact"), item.get("review_status"),
                item.get("affected_asset_ids"), item.get("affected_relationship_ids"),
            )
            for item in groups
        ])
        return {
            "qa_run_id": qa["qa_run_id"] if qa else "",
            "qa_run_fingerprint": qa["run_fingerprint"] if qa else "not_evaluated",
            "calibration_run_id": calibration["calibration_run_id"] if calibration else "",
            "calibration_fingerprint": calibration["input_fingerprint"] if calibration else "not_evaluated",
            "issue_group_fingerprint": group_fingerprint,
            "issue_groups": groups,
        }

    def _persist_result(
        self,
        connection: sqlite3.Connection,
        trace_run_id: str,
        result: dict[str, Any],
        request: dict[str, Any],
    ) -> None:
        now = intake_registry_service.utc_now()
        summary = {
            "outcome": result["outcome"],
            "confidence": result["confidence"],
            "excluded_asset_count": len(result["excluded_asset_ids"]),
            "excluded_relationship_count": len(result["excluded_relationship_ids"]),
            "truncated": result["truncated"],
            "message": _outcome_message(result["outcome"]),
            "confidence_notice": "Vendor-neutral analytical confidence based on canonical relationship evidence.",
            "limitations": [
                DISCLAIMER,
                "Only explicit canonical relationships are traversed; no geometry, source, QA, or operational state is changed.",
                "Provisional evidence and calibrated QA conditions remain candidates for human review.",
            ],
        }
        connection.execute(
            """UPDATE network_trace_runs SET status = 'succeeded', outcome = ?, completed_at = ?,
            assets_visited = ?, relationships_traversed = ?, paths_evaluated = ?, warnings_count = ?,
            blockers_count = ?, provisional_segments = ?, confidence = ?, summary_json = ?
            WHERE trace_run_id = ?""",
            (
                result["outcome"], now, result["assets_visited"], result["relationships_traversed"],
                result["paths_evaluated"], result["warnings_count"], result["blockers_count"],
                result["provisional_segments"], result["confidence"], _dump(summary), trace_run_id,
            ),
        )
        for path in result["paths"]:
            trace_path_id = stable_id("trace_path", trace_run_id, path["path_rank"])
            connection.execute(
                """INSERT INTO network_trace_paths
                (trace_path_id, trace_run_id, path_rank, path_status, start_asset_id, end_asset_id,
                 asset_ids_json, relationship_ids_json, hop_count, confidence, provisional,
                 warnings_json, blockers_json, stopping_reason, qa_issue_group_ids_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace_path_id, trace_run_id, path["path_rank"], path["path_status"],
                    path["start_asset_id"], path["end_asset_id"], _dump(path["asset_ids"]),
                    _dump(path["relationship_ids"]), path["hop_count"], path["confidence"],
                    int(path["provisional"]), _dump(path["warnings"]), _dump(path["blockers"]),
                    path["stopping_reason"], _dump(path["qa_issue_group_ids"]), now,
                ),
            )
            for step in path["steps"]:
                connection.execute(
                    """INSERT INTO network_trace_steps
                    (trace_step_id, trace_run_id, trace_path_id, sequence, asset_id,
                     entered_by_relationship_id, exited_by_relationship_id, step_role,
                     operational_state, lifecycle_status, feeder_or_route_context,
                     qa_issue_group_ids_json, trace_effect, decision, decision_reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        stable_id("trace_step", trace_path_id, step["sequence"]), trace_run_id,
                        trace_path_id, step["sequence"], step["asset_id"],
                        step["entered_by_relationship_id"], step["exited_by_relationship_id"],
                        step["step_role"], step["operational_state"], step["lifecycle_status"],
                        step["feeder_or_route_context"], _dump(step["qa_issue_group_ids"]),
                        step["trace_effect"], step["decision"], step["decision_reason"], now,
                    ),
                )
        for index, event in enumerate(result["events"]):
            connection.execute(
                """INSERT INTO network_trace_events
                (trace_event_id, trace_run_id, event_type, asset_id, relationship_id,
                 issue_group_id, severity, message, safe_details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?)""",
                (
                    stable_id("trace_event", trace_run_id, index, event["event_type"]),
                    trace_run_id, event["event_type"], event.get("asset_id", ""),
                    event.get("relationship_id", ""), event.get("issue_group_id", ""),
                    event.get("severity", "info"), event["message"][:1000], now,
                ),
            )
        self._history(
            connection, trace_run_id, "run_completed", {"status": "running"},
            {"status": "succeeded", "outcome": result["outcome"]},
            request["requested_by"], "Read-only analytical trace completed.",
        )
        connection.commit()

    def _fail_safely(self, connection: sqlite3.Connection, trace_run_id: str, actor: str) -> None:
        now = intake_registry_service.utc_now()
        summary = {
            "outcome": "failed_safely",
            "message": "The trace encountered a controlled execution problem. No asset or relationship was changed.",
            "limitations": [DISCLAIMER],
        }
        connection.execute(
            """UPDATE network_trace_runs SET status = 'failed', outcome = 'failed_safely',
            completed_at = ?, confidence = 'indeterminate', safe_error_code = 'trace_execution_failed',
            safe_error_message = 'Trace failed safely; no canonical evidence was changed.', summary_json = ?
            WHERE trace_run_id = ?""", (now, _dump(summary), trace_run_id),
        )
        self._history(
            connection, trace_run_id, "run_failed_safely", {"status": "running"},
            {"status": "failed", "outcome": "failed_safely"}, actor,
            "Controlled trace execution failure; source details suppressed.",
        )
        connection.commit()

    def _paths(self, connection: sqlite3.Connection, trace_run_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM network_trace_paths WHERE trace_run_id = ? ORDER BY path_rank", (trace_run_id,),
        ).fetchall()
        return [_safe_path(dict(row)) for row in rows]

    def _events(self, connection: sqlite3.Connection, trace_run_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            """SELECT trace_event_id, event_type, asset_id, relationship_id, issue_group_id,
            severity, message, safe_details_json, created_at FROM network_trace_events
            WHERE trace_run_id = ? ORDER BY created_at, trace_event_id""", (trace_run_id,),
        ).fetchall()
        return [
            {**dict(row), "safe_details": _load(row["safe_details_json"], {})}
            for row in rows
        ]

    def _required_run(self, connection: sqlite3.Connection, vertical: str, trace_run_id: str) -> None:
        if not connection.execute(
            "SELECT 1 FROM network_trace_runs WHERE utility_vertical = ? AND trace_run_id = ?",
            (vertical, trace_run_id),
        ).fetchone():
            raise NetworkTraceError("Network trace run not found.", 404)

    def _history(
        self,
        connection: sqlite3.Connection,
        trace_run_id: str,
        action: str,
        prior: dict[str, Any],
        new: dict[str, Any],
        actor: str,
        reason: str,
    ) -> None:
        connection.execute(
            """INSERT INTO network_trace_history
            (history_id, trace_run_id, action, prior_value_json, new_value_json,
             actor_type, actor, reason, created_at)
            VALUES (?, ?, ?, ?, ?, 'human', ?, ?, ?)""",
            (
                str(uuid.uuid4()), trace_run_id, action, _dump(prior), _dump(new),
                actor[:100], reason[:1000], intake_registry_service.utc_now(),
            ),
        )

    @staticmethod
    def _vertical(vertical: str) -> None:
        if vertical not in TRACE_PROFILES:
            raise NetworkTraceError("Unsupported utility vertical.", 404)


def _safe_request(request: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in request.items()
        if key not in {"requested_by", "request_notes", "force_recalculate", "preserve_review_decisions"}
    }


def _safe_run(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_run_id": row["trace_run_id"],
        "utility_vertical": row["utility_vertical"],
        "trace_type": row["trace_type"],
        "trace_profile": row["trace_profile"],
        "trace_rule_version": row["trace_rule_version"],
        "input_fingerprint": row["input_fingerprint"],
        "request_fingerprint": row["request_fingerprint"],
        "status": row["status"],
        "outcome": row["outcome"],
        "start_asset_id": row["start_asset_id"],
        "target_asset_id": row["target_asset_id"],
        "direction": row["direction"],
        "lifecycle_mode": row["lifecycle_mode"],
        "operational_mode": row["operational_mode"],
        "provisional_policy": row["provisional_policy"],
        "qa_policy": row["qa_policy"],
        "request_options": _load(row["request_json"], {}),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"] or "",
        "assets_visited": int(row["assets_visited"]),
        "relationships_traversed": int(row["relationships_traversed"]),
        "paths_evaluated": int(row["paths_evaluated"]),
        "warnings_count": int(row["warnings_count"]),
        "blockers_count": int(row["blockers_count"]),
        "provisional_segments": int(row["provisional_segments"]),
        "confidence": row["confidence"],
        "safe_error_code": row["safe_error_code"],
        "safe_error_message": row["safe_error_message"],
        "summary": _load(row["summary_json"], {}),
        "disclaimer": DISCLAIMER,
    }


def _safe_path(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_path_id": row["trace_path_id"],
        "trace_run_id": row["trace_run_id"],
        "path_rank": int(row["path_rank"]),
        "path_status": row["path_status"],
        "start_asset_id": row["start_asset_id"],
        "end_asset_id": row["end_asset_id"],
        "asset_ids": _load(row["asset_ids_json"], []),
        "relationship_ids": _load(row["relationship_ids_json"], []),
        "hop_count": int(row["hop_count"]),
        "confidence": row["confidence"],
        "provisional": bool(row["provisional"]),
        "warnings": _load(row["warnings_json"], []),
        "blockers": _load(row["blockers_json"], []),
        "stopping_reason": row["stopping_reason"],
        "qa_issue_group_ids": _load(row["qa_issue_group_ids_json"], []),
        "created_at": row["created_at"],
    }


def _safe_step(row: dict[str, Any]) -> dict[str, Any]:
    row["qa_issue_group_ids"] = _load(row.pop("qa_issue_group_ids_json"), [])
    attributes = _load(row.pop("canonical_attributes_json", "{}"), {})
    row["asset_context"] = {
        key: attributes.get(key)
        for key in (
            "feeder_id", "circuit_id", "phase", "nominal_voltage", "operating_voltage",
            "route_id", "cable_id", "fiber_count", "strand_start", "strand_end",
            "total_capacity", "used_capacity", "reserved_capacity", "available_capacity",
        )
        if attributes.get(key) not in (None, "")
    }
    return row


def _safe_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_group_id": group.get("issue_group_id", ""),
        "primary_rule_code": group.get("primary_rule_code", ""),
        "group_title": group.get("group_title", ""),
        "trace_impact": group.get("trace_impact", "not_evaluated"),
        "trace_impact_reason": group.get("trace_impact_reason", ""),
        "recommended_action": group.get("recommended_action", ""),
        "review_status": group.get("review_status", "open"),
    }


def _json_row(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    for field in fields:
        row[field] = _load(row.get(field), {} if not field.endswith("_ids_json") and "codes" not in field and "hints" not in field and "members" not in field else [])
    return row


def _outcome_message(outcome: str) -> str:
    return {
        "complete": "The requested terminal condition was reached using confirmed canonical evidence.",
        "complete_with_warnings": "The trace reached a terminal condition with warnings or provisional evidence.",
        "partial": "A valid partial path was found before represented evidence ended.",
        "blocked": "A calibrated or configured trace blocker prevented continuation.",
        "no_path": "No traversable canonical path exists under the selected options.",
        "ambiguous": "More than one plausible path remains without authoritative evidence to select one.",
        "failed_safely": "The trace failed safely and changed no canonical evidence.",
    }[outcome]


def _pagination(total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total}


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _load(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


service = NetworkTraceService()
