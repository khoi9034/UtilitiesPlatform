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

from .calibration import (
    CALIBRATION_VERSION,
    CONFIG as TRACE_CALIBRATION_CONFIG,
    calibrate_trace,
    calibration_fingerprint,
)
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

            CREATE TABLE IF NOT EXISTS network_trace_calibration_runs (
                calibration_run_id TEXT PRIMARY KEY,
                trace_run_id TEXT NOT NULL,
                utility_vertical TEXT NOT NULL,
                trace_calibration_version TEXT NOT NULL,
                input_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                raw_events_read INTEGER NOT NULL DEFAULT 0,
                raw_warnings_read INTEGER NOT NULL DEFAULT 0,
                raw_blockers_read INTEGER NOT NULL DEFAULT 0,
                calibrated_events_created INTEGER NOT NULL DEFAULT 0,
                path_specific_warning_count INTEGER NOT NULL DEFAULT 0,
                background_warning_count INTEGER NOT NULL DEFAULT 0,
                primary_blocker_count INTEGER NOT NULL DEFAULT 0,
                normal_branch_count INTEGER NOT NULL DEFAULT 0,
                ambiguous_branch_count INTEGER NOT NULL DEFAULT 0,
                safe_error_code TEXT NOT NULL DEFAULT '',
                safe_error_message TEXT NOT NULL DEFAULT '',
                supersedes_calibration_run_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trace_calibration_runs
                ON network_trace_calibration_runs(utility_vertical, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_trace_calibration_reuse
                ON network_trace_calibration_runs(trace_run_id, trace_calibration_version, input_fingerprint, status);

            CREATE TABLE IF NOT EXISTS network_trace_calibrated_results (
                calibrated_result_id TEXT NOT NULL,
                calibration_run_id TEXT PRIMARY KEY,
                trace_run_id TEXT NOT NULL,
                utility_vertical TEXT NOT NULL,
                original_outcome TEXT NOT NULL,
                calibrated_outcome TEXT NOT NULL,
                original_confidence TEXT NOT NULL,
                calibrated_confidence TEXT NOT NULL,
                objective_reached INTEGER NOT NULL,
                primary_stopping_reason TEXT NOT NULL,
                primary_stopping_asset_id TEXT NOT NULL,
                primary_stopping_relationship_id TEXT NOT NULL,
                primary_issue_group_id TEXT NOT NULL,
                path_specific_blocker_count INTEGER NOT NULL,
                path_specific_warning_count INTEGER NOT NULL,
                branch_specific_warning_count INTEGER NOT NULL,
                background_warning_count INTEGER NOT NULL,
                informational_event_count INTEGER NOT NULL,
                normal_branch_count INTEGER NOT NULL,
                ambiguous_branch_count INTEGER NOT NULL,
                provisional_segment_count INTEGER NOT NULL,
                excluded_asset_count INTEGER NOT NULL,
                excluded_relationship_count INTEGER NOT NULL,
                related_raw_event_count INTEGER NOT NULL,
                confidence_reason_json TEXT NOT NULL,
                outcome_reason_json TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                recommended_edit_category TEXT NOT NULL,
                comparison_key TEXT NOT NULL,
                path_signature TEXT NOT NULL,
                branch_signature TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS network_trace_calibrated_events (
                calibration_run_id TEXT NOT NULL,
                calibrated_event_id TEXT NOT NULL,
                trace_run_id TEXT NOT NULL,
                category TEXT NOT NULL,
                scope TEXT NOT NULL,
                priority INTEGER NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_event_ids_json TEXT NOT NULL,
                path_ids_json TEXT NOT NULL,
                asset_ids_json TEXT NOT NULL,
                relationship_ids_json TEXT NOT NULL,
                issue_group_ids_json TEXT NOT NULL,
                primary_event INTEGER NOT NULL,
                repeated_count INTEGER NOT NULL,
                trace_effect TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (calibration_run_id, calibrated_event_id)
            );
            CREATE INDEX IF NOT EXISTS idx_trace_calibrated_events
                ON network_trace_calibrated_events(trace_run_id, scope, category, priority);

            CREATE TABLE IF NOT EXISTS network_trace_calibration_history (
                history_id TEXT PRIMARY KEY,
                calibration_run_id TEXT NOT NULL,
                trace_run_id TEXT NOT NULL,
                action TEXT NOT NULL,
                prior_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
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

    def calibrate(
        self,
        vertical: str,
        trace_run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._vertical(vertical)
        payload = dict(payload or {})
        if set(payload).difference({"force_recalculate"}):
            raise NetworkTraceError("Only force_recalculate is accepted for trace calibration.")
        force = payload.get("force_recalculate", False)
        if not isinstance(force, bool):
            raise NetworkTraceError("force_recalculate must be a boolean.")
        with self.connect() as connection:
            run_row = connection.execute(
                "SELECT * FROM network_trace_runs WHERE utility_vertical = ? AND trace_run_id = ?",
                (vertical, trace_run_id),
            ).fetchone()
            if not run_row:
                raise NetworkTraceError("Network trace run not found.", 404)
            run = _safe_run(dict(run_row))
            paths = self._paths(connection, trace_run_id)
            steps = self._steps(connection, trace_run_id)
            raw_events = self._events(connection, trace_run_id)
            issue_groups = self._trace_issue_groups(connection, run_row["calibration_run_id"])
            fingerprint = calibration_fingerprint(run, paths, steps, raw_events, issue_groups)
            existing = connection.execute(
                """SELECT calibration_run_id FROM network_trace_calibration_runs
                WHERE trace_run_id = ? AND trace_calibration_version = ? AND input_fingerprint = ?
                AND status = 'succeeded' ORDER BY started_at DESC LIMIT 1""",
                (trace_run_id, CALIBRATION_VERSION, fingerprint),
            ).fetchone()
            if existing and not force:
                detail = self.calibration_run(vertical, existing["calibration_run_id"], connection)
                detail.update({
                    "reused": True,
                    "message": "No trace evidence or calibration-rule changes detected",
                })
                return detail

            previous = connection.execute(
                """SELECT calibration_run_id FROM network_trace_calibration_runs
                WHERE trace_run_id = ? AND trace_calibration_version = ? AND status = 'succeeded'
                ORDER BY started_at DESC LIMIT 1""",
                (trace_run_id, CALIBRATION_VERSION),
            ).fetchone()
            calibration_run_id = str(uuid.uuid4())
            now = intake_registry_service.utc_now()
            connection.execute(
                """INSERT INTO network_trace_calibration_runs
                (calibration_run_id, trace_run_id, utility_vertical, trace_calibration_version,
                 input_fingerprint, status, started_at, supersedes_calibration_run_id, created_at)
                VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?)""",
                (
                    calibration_run_id, trace_run_id, vertical, CALIBRATION_VERSION,
                    fingerprint, now, previous["calibration_run_id"] if previous else "", now,
                ),
            )
            self._calibration_history(
                connection, calibration_run_id, trace_run_id, "calibration_started", {}, {"status": "running"},
                "Trace calibration requested for immutable evidence.",
            )
            connection.commit()
            try:
                calibrated = calibrate_trace(run, paths, steps, raw_events, issue_groups)
                self._persist_calibration(connection, calibration_run_id, run, calibrated)
            except Exception:
                completed = intake_registry_service.utc_now()
                connection.execute(
                    """UPDATE network_trace_calibration_runs SET status = 'failed', completed_at = ?,
                    safe_error_code = 'trace_calibration_failed',
                    safe_error_message = 'Trace calibration failed safely; original trace evidence was unchanged.'
                    WHERE calibration_run_id = ?""",
                    (completed, calibration_run_id),
                )
                self._calibration_history(
                    connection, calibration_run_id, trace_run_id, "calibration_failed_safely",
                    {"status": "running"}, {"status": "failed"},
                    "Controlled calibration failure; internal details suppressed.",
                )
                connection.commit()
                raise NetworkTraceError(
                    "Trace calibration failed safely; original trace evidence was unchanged.", 500,
                ) from None
            return self.calibration_run(vertical, calibration_run_id, connection)

    def calibration_status(self, vertical: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            row = connection.execute(
                """SELECT calibration_run_id FROM network_trace_calibration_runs
                WHERE utility_vertical = ? ORDER BY started_at DESC LIMIT 1""", (vertical,),
            ).fetchone()
            if not row:
                return {
                    "utility_vertical": vertical,
                    "status": "not_started",
                    "message": "Network Trace calibration has not been run for this utility vertical.",
                    "trace_calibration_version": CALIBRATION_VERSION,
                }
            return self.calibration_run(vertical, row["calibration_run_id"], connection)

    def calibration_runs(self, vertical: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            total = int(connection.execute(
                "SELECT COUNT(*) FROM network_trace_calibration_runs WHERE utility_vertical = ?", (vertical,),
            ).fetchone()[0])
            rows = connection.execute(
                """SELECT * FROM network_trace_calibration_runs WHERE utility_vertical = ?
                ORDER BY started_at DESC LIMIT ? OFFSET ?""", (vertical, limit, offset),
            ).fetchall()
        return {
            "items": [_safe_calibration_run(dict(row)) for row in rows],
            "pagination": _pagination(total, limit, offset),
        }

    def calibration_run(
        self,
        vertical: str,
        calibration_run_id: str,
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        self._vertical(vertical)
        owns_connection = connection is None
        connection = connection or self.connect()
        try:
            row = connection.execute(
                """SELECT * FROM network_trace_calibration_runs
                WHERE utility_vertical = ? AND calibration_run_id = ?""",
                (vertical, calibration_run_id),
            ).fetchone()
            if not row:
                raise NetworkTraceError("Network trace calibration run not found.", 404)
            detail = _safe_calibration_run(dict(row))
            result = connection.execute(
                """SELECT r.*, c.input_fingerprint, c.trace_calibration_version
                FROM network_trace_calibrated_results r
                JOIN network_trace_calibration_runs c ON c.calibration_run_id = r.calibration_run_id
                WHERE r.calibration_run_id = ?""", (calibration_run_id,),
            ).fetchone()
            detail["result"] = _safe_calibrated_result(dict(result)) if result else None
            detail["history"] = [
                _safe_calibration_history(dict(item))
                for item in connection.execute(
                    """SELECT * FROM network_trace_calibration_history
                    WHERE calibration_run_id = ? ORDER BY created_at, history_id""",
                    (calibration_run_id,),
                ).fetchall()
            ]
            return detail
        finally:
            if owns_connection:
                connection.close()

    def calibrated_result(self, vertical: str, trace_run_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            self._required_run(connection, vertical, trace_run_id)
            row = connection.execute(
                """SELECT r.*, c.input_fingerprint, c.trace_calibration_version
                FROM network_trace_calibrated_results r
                JOIN network_trace_calibration_runs c ON c.calibration_run_id = r.calibration_run_id
                WHERE r.trace_run_id = ? AND c.trace_calibration_version = ? AND c.status = 'succeeded'
                ORDER BY c.started_at DESC LIMIT 1""",
                (trace_run_id, CALIBRATION_VERSION),
            ).fetchone()
            if not row:
                raise NetworkTraceError("Calibrated trace result not found. Run calibration first.", 404)
            return _safe_calibrated_result(dict(row))

    def calibrated_events(
        self,
        vertical: str,
        trace_run_id: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._vertical(vertical)
        filters = filters or {}
        allowed = {
            "scope", "category", "priority", "primary", "path_id", "asset_id",
            "relationship_id", "issue_group_id", "limit", "offset",
        }
        if set(filters).difference(allowed):
            raise NetworkTraceError("Unsupported calibrated-event filter.")
        if filters.get("scope") and filters["scope"] not in TRACE_CALIBRATION_CONFIG["warning_scopes"]:
            raise NetworkTraceError("Unsupported warning scope.")
        if filters.get("category") and filters["category"] not in TRACE_CALIBRATION_CONFIG["event_categories"]:
            raise NetworkTraceError("Unsupported calibrated-event category.")
        limit = min(max(int(filters.get("limit", 100)), 1), 500)
        offset = max(int(filters.get("offset", 0)), 0)
        with self.connect() as connection:
            self._required_run(connection, vertical, trace_run_id)
            calibration = connection.execute(
                """SELECT calibration_run_id FROM network_trace_calibration_runs
                WHERE trace_run_id = ? AND trace_calibration_version = ? AND status = 'succeeded'
                ORDER BY started_at DESC LIMIT 1""",
                (trace_run_id, CALIBRATION_VERSION),
            ).fetchone()
            if not calibration:
                raise NetworkTraceError("Calibrated trace result not found. Run calibration first.", 404)
            rows = [
                _safe_calibrated_event(dict(row))
                for row in connection.execute(
                    """SELECT * FROM network_trace_calibrated_events WHERE calibration_run_id = ?
                    ORDER BY priority, category, calibrated_event_id""",
                    (calibration["calibration_run_id"],),
                ).fetchall()
            ]
        for key in ("scope", "category", "priority"):
            if filters.get(key) not in (None, ""):
                rows = [item for item in rows if str(item[key]) == str(filters[key])]
        if filters.get("primary") not in (None, ""):
            expected = str(filters["primary"]).lower() in {"1", "true", "yes"}
            rows = [item for item in rows if item["primary"] is expected]
        for key, list_key in (
            ("path_id", "path_ids"), ("asset_id", "asset_ids"),
            ("relationship_id", "relationship_ids"), ("issue_group_id", "issue_group_ids"),
        ):
            if filters.get(key):
                rows = [item for item in rows if filters[key] in item[list_key]]
        total = len(rows)
        return {
            "items": rows[offset:offset + limit],
            "calibration_run_id": calibration["calibration_run_id"],
            "pagination": _pagination(total, limit, offset),
        }

    def calibrated_safe_summary(self, vertical: str, trace_run_id: str) -> dict[str, Any]:
        result = self.calibrated_result(vertical, trace_run_id)
        run = self.run_detail(vertical, trace_run_id)
        return {
            "trace_run_id": trace_run_id,
            "calibration_run_id": result["calibration_run_id"],
            "utility_vertical": vertical,
            "trace_type": run["trace_type"],
            "trace_profile": run["trace_profile"],
            "trace_profile_version": TRACE_PROFILE_VERSION,
            "trace_calibration_version": CALIBRATION_VERSION,
            "start_asset_id": run["start_asset_id"],
            "target_asset_id": run["target_asset_id"],
            "original_outcome": result["original_outcome"],
            "calibrated_outcome": result["calibrated_outcome"],
            "original_confidence": result["original_confidence"],
            "calibrated_confidence": result["calibrated_confidence"],
            "objective_reached": result["objective_reached"],
            "primary_stopping_condition": result["primary_stopping_reason"],
            "primary_issue_group_ids": [result["primary_issue_group_id"]] if result["primary_issue_group_id"] else [],
            "normal_branches": result["normal_branch_count"],
            "ambiguous_branches": result["ambiguous_branch_count"],
            "path_specific_blockers": result["path_specific_blocker_count"],
            "path_specific_warnings": result["path_specific_warning_count"],
            "background_warning_count": result["background_warning_count"],
            "provisional_segments": result["provisional_segment_count"],
            "assets_visited": run["assets_visited"],
            "relationships_traversed": run["relationships_traversed"],
            "path_count": run["paths_evaluated"],
            "excluded_context": {
                "assets": result["excluded_asset_count"],
                "relationships": result["excluded_relationship_count"],
            },
            "recommended_next_safe_action": result["recommended_action"],
            "comparison_key": result["comparison_key"],
            "path_signature": result["path_signature"],
            "branch_signature": result["branch_signature"],
            "input_fingerprint": result["input_fingerprint"],
            "trace_started_at": run["started_at"],
            "trace_completed_at": run["completed_at"],
            "calibration_created_at": result["created_at"],
            "disclaimer": result["disclaimer"],
        }

    def _steps(self, connection: sqlite3.Connection, trace_run_id: str) -> list[dict[str, Any]]:
        return [
            dict(row) | {"qa_issue_group_ids": _load(row["qa_issue_group_ids_json"], [])}
            for row in connection.execute(
                """SELECT * FROM network_trace_steps WHERE trace_run_id = ?
                ORDER BY trace_path_id, sequence""", (trace_run_id,),
            ).fetchall()
        ]

    def _trace_issue_groups(
        self,
        connection: sqlite3.Connection,
        calibration_run_id: str,
    ) -> list[dict[str, Any]]:
        if not calibration_run_id:
            return []
        groups = []
        for row in connection.execute(
            """SELECT * FROM connectivity_qa_issue_groups
            WHERE calibration_run_id = ? AND superseded = 0 ORDER BY issue_group_id""",
            (calibration_run_id,),
        ).fetchall():
            group = dict(row)
            for field in (
                "member_finding_ids", "affected_asset_ids", "affected_relationship_ids",
                "related_rule_codes", "vendor_equivalent_hints",
            ):
                group[field] = _load(group.pop(f"{field}_json", "[]"), [])
            groups.append(group)
        return groups

    def _persist_calibration(
        self,
        connection: sqlite3.Connection,
        calibration_run_id: str,
        run: dict[str, Any],
        calibrated: dict[str, Any],
    ) -> None:
        now = intake_registry_service.utc_now()
        result = calibrated["result"]
        metrics = calibrated["metrics"]
        result_id = stable_id(
            "trace_calibrated_result", calibrated["input_fingerprint"], CALIBRATION_VERSION,
        )
        connection.execute(
            """INSERT INTO network_trace_calibrated_results
            (calibrated_result_id, calibration_run_id, trace_run_id, utility_vertical,
             original_outcome, calibrated_outcome, original_confidence, calibrated_confidence,
             objective_reached, primary_stopping_reason, primary_stopping_asset_id,
             primary_stopping_relationship_id, primary_issue_group_id,
             path_specific_blocker_count, path_specific_warning_count,
             branch_specific_warning_count, background_warning_count, informational_event_count,
             normal_branch_count, ambiguous_branch_count, provisional_segment_count,
             excluded_asset_count, excluded_relationship_count, related_raw_event_count,
             confidence_reason_json, outcome_reason_json, recommended_action,
             recommended_edit_category, comparison_key, path_signature, branch_signature,
             result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result_id, calibration_run_id, run["trace_run_id"], run["utility_vertical"],
                result["original_outcome"], result["calibrated_outcome"],
                result["original_confidence"], result["calibrated_confidence"],
                int(result["objective_reached"]), result["primary_stopping_reason"],
                result["primary_stopping_asset_id"], result["primary_stopping_relationship_id"],
                result["primary_issue_group_id"], result["path_specific_blocker_count"],
                result["path_specific_warning_count"], result["branch_specific_warning_count"],
                result["background_warning_count"], result["informational_event_count"],
                result["normal_branch_count"], result["ambiguous_branch_count"],
                result["provisional_segment_count"], result["excluded_asset_count"],
                result["excluded_relationship_count"], result["related_raw_event_count"],
                _dump(result["confidence_reason"]), _dump(result["outcome_reason"]),
                result["recommended_action"], result["recommended_edit_category"],
                result["comparison_key"], result["path_signature"], result["branch_signature"],
                _dump(result), now,
            ),
        )
        for event in calibrated["events"]:
            connection.execute(
                """INSERT INTO network_trace_calibrated_events
                (calibration_run_id, calibrated_event_id, trace_run_id, category, scope,
                 priority, title, summary, source_event_ids_json, path_ids_json, asset_ids_json,
                 relationship_ids_json, issue_group_ids_json, primary_event, repeated_count,
                 trace_effect, evidence_json, recommended_action, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    calibration_run_id, event["calibrated_event_id"], run["trace_run_id"],
                    event["category"], event["scope"], event["priority"], event["title"],
                    event["summary"], _dump(event["source_event_ids"]), _dump(event["path_ids"]),
                    _dump(event["asset_ids"]), _dump(event["relationship_ids"]),
                    _dump(event["issue_group_ids"]), int(event["primary"]),
                    event["repeated_count"], event["trace_effect"], _dump(event["evidence"]),
                    event["recommended_action"], now,
                ),
            )
        connection.execute(
            """UPDATE network_trace_calibration_runs SET status = 'succeeded', completed_at = ?,
            raw_events_read = ?, raw_warnings_read = ?, raw_blockers_read = ?,
            calibrated_events_created = ?, path_specific_warning_count = ?,
            background_warning_count = ?, primary_blocker_count = ?, normal_branch_count = ?,
            ambiguous_branch_count = ? WHERE calibration_run_id = ?""",
            (
                now, metrics["raw_events_read"], metrics["raw_warnings_read"],
                metrics["raw_blockers_read"], metrics["calibrated_events_created"],
                metrics["path_specific_warning_count"], metrics["background_warning_count"],
                metrics["primary_blocker_count"], metrics["normal_branch_count"],
                metrics["ambiguous_branch_count"], calibration_run_id,
            ),
        )
        self._calibration_history(
            connection, calibration_run_id, run["trace_run_id"], "calibration_completed",
            {"status": "running"},
            {"status": "succeeded", "calibrated_outcome": result["calibrated_outcome"]},
            "A separate interpretation was persisted; immutable trace evidence was not changed.",
        )
        connection.commit()

    def _calibration_history(
        self,
        connection: sqlite3.Connection,
        calibration_run_id: str,
        trace_run_id: str,
        action: str,
        prior: dict[str, Any],
        new: dict[str, Any],
        reason: str,
    ) -> None:
        connection.execute(
            """INSERT INTO network_trace_calibration_history
            (history_id, calibration_run_id, trace_run_id, action, prior_value, new_value,
             actor_type, actor, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'system', 'trace_calibration_v1', ?, ?)""",
            (
                str(uuid.uuid4()), calibration_run_id, trace_run_id, action,
                _dump(prior), _dump(new), reason[:1000], intake_registry_service.utc_now(),
            ),
        )

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


def _safe_calibration_run(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "calibration_run_id": row["calibration_run_id"],
        "trace_run_id": row["trace_run_id"],
        "utility_vertical": row["utility_vertical"],
        "trace_calibration_version": row["trace_calibration_version"],
        "input_fingerprint": row["input_fingerprint"],
        "status": row["status"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"] or "",
        "raw_events_read": int(row["raw_events_read"]),
        "raw_warnings_read": int(row["raw_warnings_read"]),
        "raw_blockers_read": int(row["raw_blockers_read"]),
        "calibrated_events_created": int(row["calibrated_events_created"]),
        "path_specific_warning_count": int(row["path_specific_warning_count"]),
        "background_warning_count": int(row["background_warning_count"]),
        "primary_blocker_count": int(row["primary_blocker_count"]),
        "normal_branch_count": int(row["normal_branch_count"]),
        "ambiguous_branch_count": int(row["ambiguous_branch_count"]),
        "safe_error_code": row["safe_error_code"],
        "safe_error_message": row["safe_error_message"],
        "supersedes_calibration_run_id": row["supersedes_calibration_run_id"],
        "created_at": row["created_at"],
    }


def _safe_calibrated_result(row: dict[str, Any]) -> dict[str, Any]:
    result = _load(row.get("result_json"), {})
    result.update({
        "calibrated_result_id": row["calibrated_result_id"],
        "calibration_run_id": row["calibration_run_id"],
        "trace_run_id": row["trace_run_id"],
        "utility_vertical": row["utility_vertical"],
        "trace_calibration_version": row.get("trace_calibration_version", CALIBRATION_VERSION),
        "input_fingerprint": row.get("input_fingerprint", ""),
        "objective_reached": bool(row["objective_reached"]),
        "created_at": row["created_at"],
    })
    return result


def _safe_calibrated_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "calibrated_event_id": row["calibrated_event_id"],
        "calibration_run_id": row["calibration_run_id"],
        "trace_run_id": row["trace_run_id"],
        "category": row["category"],
        "scope": row["scope"],
        "priority": int(row["priority"]),
        "title": row["title"],
        "summary": row["summary"],
        "source_event_ids": _load(row["source_event_ids_json"], []),
        "path_ids": _load(row["path_ids_json"], []),
        "asset_ids": _load(row["asset_ids_json"], []),
        "relationship_ids": _load(row["relationship_ids_json"], []),
        "issue_group_ids": _load(row["issue_group_ids_json"], []),
        "primary": bool(row["primary_event"]),
        "repeated_count": int(row["repeated_count"]),
        "trace_effect": row["trace_effect"],
        "evidence": _load(row["evidence_json"], {}),
        "recommended_action": row["recommended_action"],
        "created_at": row["created_at"],
    }


def _safe_calibration_history(row: dict[str, Any]) -> dict[str, Any]:
    row["prior_value"] = _load(row["prior_value"], {})
    row["new_value"] = _load(row["new_value"], {})
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
