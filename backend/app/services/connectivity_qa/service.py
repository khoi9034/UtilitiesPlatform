from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.services import intake_registry_service
from app.services.utility_assets import service as utility_assets

from .rules import (
    MODEL_VERSION,
    PROFILES,
    REVIEW_STATUSES,
    RULE_VERSION,
    build_graph,
    evaluate_rule,
    graph_fingerprint,
    rule_profile,
)


class ConnectivityQaError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConnectivityQaService:
    def connect(self) -> sqlite3.Connection:
        connection = utility_assets.connect()
        self._initialize(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS connectivity_qa_runs (
                qa_run_id TEXT PRIMARY KEY,
                utility_vertical TEXT NOT NULL,
                profile_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                run_fingerprint TEXT NOT NULL,
                asset_checksum TEXT NOT NULL,
                relationship_checksum TEXT NOT NULL,
                status TEXT NOT NULL,
                force_recalculate INTEGER NOT NULL DEFAULT 0,
                asset_count INTEGER NOT NULL,
                relationship_count INTEGER NOT NULL,
                rules_executed INTEGER NOT NULL DEFAULT 0,
                rules_skipped INTEGER NOT NULL DEFAULT 0,
                findings_count INTEGER NOT NULL DEFAULT 0,
                blocking_findings_count INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                summary_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                created_by TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_connectivity_runs_vertical_started
                ON connectivity_qa_runs(utility_vertical, started_at DESC);

            CREATE TABLE IF NOT EXISTS connectivity_qa_rule_runs (
                qa_run_id TEXT NOT NULL,
                rule_code TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                status TEXT NOT NULL,
                finding_count INTEGER NOT NULL,
                error_message TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (qa_run_id, rule_code)
            );

            CREATE TABLE IF NOT EXISTS connectivity_qa_findings (
                qa_run_id TEXT NOT NULL,
                finding_id TEXT NOT NULL,
                finding_fingerprint TEXT NOT NULL,
                utility_vertical TEXT NOT NULL,
                rule_code TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                severity TEXT NOT NULL,
                blocking INTEGER NOT NULL,
                asset_id TEXT,
                related_asset_id TEXT,
                relationship_id TEXT,
                asset_class TEXT,
                short_title TEXT NOT NULL,
                explanation TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                review_status TEXT NOT NULL DEFAULT 'open',
                review_comment TEXT,
                reviewed_by TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (qa_run_id, finding_id),
                UNIQUE (qa_run_id, finding_fingerprint)
            );
            CREATE INDEX IF NOT EXISTS idx_connectivity_findings_filter
                ON connectivity_qa_findings(utility_vertical, review_status, severity, rule_code);
            CREATE INDEX IF NOT EXISTS idx_connectivity_findings_fingerprint
                ON connectivity_qa_findings(finding_fingerprint, created_at DESC);

            CREATE TABLE IF NOT EXISTS connectivity_qa_history (
                history_id TEXT PRIMARY KEY,
                qa_run_id TEXT NOT NULL,
                finding_id TEXT,
                action TEXT NOT NULL,
                prior_value_json TEXT NOT NULL,
                new_value_json TEXT NOT NULL,
                actor TEXT,
                comment TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.commit()

    def rules(self, vertical: str | None = None) -> dict[str, Any]:
        if vertical:
            rows = rule_profile(vertical)
            return {"utility_vertical": vertical, "profile_name": PROFILES[vertical], "model_version": MODEL_VERSION, "rule_version": RULE_VERSION, "items": rows}
        return {
            "profiles": {key: {"profile_name": value, "rules": rule_profile(key)} for key, value in PROFILES.items()},
            "model_version": MODEL_VERSION,
            "rule_version": RULE_VERSION,
        }

    def run(self, vertical: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        if vertical not in PROFILES:
            raise ConnectivityQaError("Unsupported utility vertical.", 404)
        force = bool(payload.get("force_recalculate", False))
        actor = str(payload.get("actor", "local_operator"))[:100]
        with self.connect() as connection:
            assets = [_json_row(dict(row), ("canonical_attributes_json", "geometry_summary_json", "evidence_json")) for row in connection.execute(
                "SELECT * FROM canonical_utility_assets WHERE utility_vertical = ? ORDER BY asset_id", (vertical,),
            ).fetchall()]
            all_assets = [_json_row(dict(row), ("canonical_attributes_json", "geometry_summary_json", "evidence_json")) for row in connection.execute(
                "SELECT * FROM canonical_utility_assets ORDER BY asset_id",
            ).fetchall()]
            selected_ids = {row["asset_id"] for row in assets}
            relationships = [_json_row(dict(row), ("evidence_json",)) for row in connection.execute(
                "SELECT * FROM utility_asset_relationships ORDER BY relationship_id",
            ).fetchall() if row["from_asset_id"] in selected_ids or row["to_asset_id"] in selected_ids]
            fingerprint, asset_checksum, relationship_checksum = graph_fingerprint(vertical, assets, relationships)
            if not force:
                existing = connection.execute(
                    """SELECT qa_run_id FROM connectivity_qa_runs
                    WHERE utility_vertical = ? AND run_fingerprint = ? AND status IN ('succeeded', 'partially_failed', 'blocked')
                    ORDER BY started_at DESC LIMIT 1""", (vertical, fingerprint),
                ).fetchone()
                if existing:
                    result = self.run_detail(vertical, existing["qa_run_id"], connection)
                    result["reused"] = True
                    return result

            now = intake_registry_service.utc_now()
            qa_run_id = str(uuid.uuid4())
            status = "running" if assets else "blocked"
            connection.execute(
                """INSERT INTO connectivity_qa_runs
                (qa_run_id, utility_vertical, profile_name, model_version, rule_version, run_fingerprint,
                 asset_checksum, relationship_checksum, status, force_recalculate, asset_count,
                 relationship_count, summary_json, started_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)""",
                (
                    qa_run_id, vertical, PROFILES[vertical], MODEL_VERSION, RULE_VERSION, fingerprint,
                    asset_checksum, relationship_checksum, status, int(force), len(assets), len(relationships), now, actor,
                ),
            )
            self._history(connection, qa_run_id, None, "run_started", {}, {"status": status}, actor, "")
            connection.commit()
            if not assets:
                completed = intake_registry_service.utc_now()
                for definition in rule_profile(vertical):
                    connection.execute(
                        """INSERT INTO connectivity_qa_rule_runs
                        (qa_run_id, rule_code, rule_version, status, finding_count, error_message, started_at, completed_at)
                        VALUES (?, ?, ?, 'skipped', 0, ?, ?, ?)""",
                        (qa_run_id, definition["rule_code"], RULE_VERSION, "No canonical assets available.", now, completed),
                    )
                summary = self._finish(connection, qa_run_id, "blocked", 0, len(rule_profile(vertical)), 0, 0, 0)
                return {**self.run_detail(vertical, qa_run_id, connection), "reused": False, "summary": summary}

            graph = build_graph(vertical, assets, all_assets, relationships)
            rules_executed = rules_skipped = error_count = finding_count = blocking_count = 0
            for definition in rule_profile(vertical):
                rule_started = intake_registry_service.utc_now()
                try:
                    findings = evaluate_rule(definition, graph)
                    status = "failed" if findings and definition["blocking"] else "warning" if findings else "passed"
                    for finding in findings:
                        review = connection.execute(
                            """SELECT review_status, review_comment, reviewed_by, reviewed_at
                            FROM connectivity_qa_findings WHERE finding_fingerprint = ?
                            ORDER BY created_at DESC LIMIT 1""", (finding["finding_fingerprint"],),
                        ).fetchone()
                        finding_now = intake_registry_service.utc_now()
                        review_values = dict(review) if review else {"review_status": "open", "review_comment": "", "reviewed_by": "", "reviewed_at": ""}
                        connection.execute(
                            """INSERT INTO connectivity_qa_findings
                            (qa_run_id, finding_id, finding_fingerprint, utility_vertical, rule_code, rule_version,
                             severity, blocking, asset_id, related_asset_id, relationship_id, asset_class,
                             short_title, explanation, recommended_action, evidence_json, review_status,
                             review_comment, reviewed_by, reviewed_at, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                qa_run_id, finding["finding_id"], finding["finding_fingerprint"], vertical,
                                definition["rule_code"], RULE_VERSION, definition["severity"], int(definition["blocking"]),
                                finding["asset_id"], finding["related_asset_id"], finding["relationship_id"],
                                finding["asset_class"], finding["short_title"], finding["explanation"],
                                finding["recommended_action"], _dump(finding["evidence_json"]),
                                review_values["review_status"], review_values["review_comment"],
                                review_values["reviewed_by"], review_values["reviewed_at"], finding_now, finding_now,
                            ),
                        )
                    rules_executed += 1
                    finding_count += len(findings)
                    blocking_count += len(findings) if definition["blocking"] else 0
                    error_message = ""
                except Exception as exc:  # A bad rule must not erase other rule results.
                    status, findings, error_message = "blocked", [], f"{type(exc).__name__}: rule execution failed safely"
                    rules_skipped += 1
                    error_count += 1
                completed = intake_registry_service.utc_now()
                connection.execute(
                    """INSERT INTO connectivity_qa_rule_runs
                    (qa_run_id, rule_code, rule_version, status, finding_count, error_message, started_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (qa_run_id, definition["rule_code"], RULE_VERSION, status, len(findings), error_message, rule_started, completed),
                )
                connection.commit()

            run_status = "partially_failed" if error_count else "succeeded"
            summary = self._finish(connection, qa_run_id, run_status, rules_executed, rules_skipped, finding_count, blocking_count, error_count)
            self._history(connection, qa_run_id, None, "run_completed", {"status": "running"}, {"status": run_status, "findings_count": finding_count}, actor, "")
            connection.commit()
            result = self.run_detail(vertical, qa_run_id, connection)
            result.update({"reused": False, "summary": summary})
            return result

    def status(self, vertical: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT qa_run_id FROM connectivity_qa_runs WHERE utility_vertical = ? ORDER BY started_at DESC LIMIT 1",
                (vertical,),
            ).fetchone()
            if not row:
                return {"utility_vertical": vertical, "status": "not_started", "message": "Connectivity QA has not been run for this utility vertical."}
            return self.run_detail(vertical, row["qa_run_id"], connection)

    def runs(self, vertical: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM connectivity_qa_runs WHERE utility_vertical = ?", (vertical,)).fetchone()[0])
            rows = connection.execute(
                """SELECT * FROM connectivity_qa_runs WHERE utility_vertical = ?
                ORDER BY started_at DESC LIMIT ? OFFSET ?""", (vertical, limit, offset),
            ).fetchall()
        return {"items": [_safe_run(dict(row)) for row in rows], "pagination": _pagination(total, limit, offset)}

    def run_detail(self, vertical: str, qa_run_id: str, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        owns_connection = connection is None
        connection = connection or self.connect()
        try:
            row = connection.execute(
                "SELECT * FROM connectivity_qa_runs WHERE utility_vertical = ? AND qa_run_id = ?",
                (vertical, qa_run_id),
            ).fetchone()
            if not row:
                raise ConnectivityQaError("Connectivity QA run not found.", 404)
            rule_rows = connection.execute(
                "SELECT rule_code, rule_version, status, finding_count, error_message, started_at, completed_at FROM connectivity_qa_rule_runs WHERE qa_run_id = ? ORDER BY rule_code",
                (qa_run_id,),
            ).fetchall()
            result = _safe_run(dict(row))
            result["rule_runs"] = [dict(item) for item in rule_rows]
            return result
        finally:
            if owns_connection:
                connection.close()

    def summary(self, vertical: str) -> dict[str, Any]:
        latest = self.status(vertical)
        return latest.get("summary", latest)

    def findings(self, vertical: str, filters: dict[str, Any]) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            qa_run_id = str(filters.get("qa_run_id") or "")
            if not qa_run_id:
                row = connection.execute(
                    "SELECT qa_run_id FROM connectivity_qa_runs WHERE utility_vertical = ? ORDER BY started_at DESC LIMIT 1",
                    (vertical,),
                ).fetchone()
                if not row:
                    return {"items": [], "pagination": _pagination(0, int(filters.get("limit", 100)), int(filters.get("offset", 0))), "message": "Connectivity QA has not been run."}
                qa_run_id = row["qa_run_id"]
            clauses = ["f.utility_vertical = ?", "f.qa_run_id = ?"]
            values: list[Any] = [vertical, qa_run_id]
            for field in ("severity", "review_status", "rule_code", "asset_class", "asset_id"):
                if filters.get(field):
                    clauses.append(f"f.{field} = ?")
                    values.append(str(filters[field]))
            if filters.get("blocking") is not None:
                clauses.append("f.blocking = ?")
                values.append(int(bool(filters["blocking"])))
            where = " AND ".join(clauses)
            limit, offset = int(filters.get("limit", 100)), int(filters.get("offset", 0))
            total = int(connection.execute(f"SELECT COUNT(*) FROM connectivity_qa_findings f WHERE {where}", values).fetchone()[0])
            rows = connection.execute(
                f"""SELECT f.*, a.canonical_name asset_name, a.lifecycle_status asset_lifecycle_status,
                r.canonical_name related_asset_name
                FROM connectivity_qa_findings f
                LEFT JOIN canonical_utility_assets a ON a.asset_id = f.asset_id
                LEFT JOIN canonical_utility_assets r ON r.asset_id = f.related_asset_id
                WHERE {where}
                ORDER BY CASE f.severity WHEN 'critical' THEN 0 WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                         f.blocking DESC, f.rule_code, f.asset_id
                LIMIT ? OFFSET ?""", (*values, limit, offset),
            ).fetchall()
        return {"items": [_safe_finding(dict(row)) for row in rows], "pagination": _pagination(total, limit, offset), "qa_run_id": qa_run_id}

    def finding(self, vertical: str, finding_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            row = connection.execute(
                """SELECT f.*, a.canonical_name asset_name, a.asset_class source_asset_class,
                a.lifecycle_status asset_lifecycle_status, a.operational_status asset_operational_status,
                r.canonical_name related_asset_name, r.asset_class related_asset_class
                FROM connectivity_qa_findings f
                LEFT JOIN canonical_utility_assets a ON a.asset_id = f.asset_id
                LEFT JOIN canonical_utility_assets r ON r.asset_id = f.related_asset_id
                WHERE f.utility_vertical = ? AND f.finding_id = ?
                ORDER BY f.created_at DESC LIMIT 1""", (vertical, finding_id),
            ).fetchone()
            if not row:
                raise ConnectivityQaError("Connectivity QA finding not found.", 404)
            result = _safe_finding(dict(row))
            definition = next(item for item in rule_profile(vertical) if item["rule_code"] == result["rule_code"])
            result["rule"] = definition
            result["graph_context"] = self._graph_context(connection, result)
            result["history"] = [
                _json_row(dict(item), ("prior_value_json", "new_value_json"))
                for item in connection.execute(
                    "SELECT * FROM connectivity_qa_history WHERE finding_id = ? ORDER BY created_at",
                    (finding_id,),
                ).fetchall()
            ]
            return result

    def review(self, vertical: str, finding_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        statuses = {
            "acknowledge": "acknowledged",
            "defer": "deferred",
            "accept-risk": "accepted_risk",
            "mark-false-positive": "false_positive",
            "reopen": "open",
        }
        if action not in statuses:
            raise ConnectivityQaError("Unsupported review action.", 404)
        reviewer = str(payload.get("reviewer", "")).strip()[:100]
        comment = str(payload.get("comment") or payload.get("rationale") or "").strip()[:1000]
        if action in {"defer", "accept-risk", "mark-false-positive"} and not comment:
            raise ConnectivityQaError("A review rationale is required for this action.")
        if not reviewer:
            raise ConnectivityQaError("Reviewer is required.")
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM connectivity_qa_findings
                WHERE utility_vertical = ? AND finding_id = ? ORDER BY created_at DESC LIMIT 1""",
                (vertical, finding_id),
            ).fetchone()
            if not row:
                raise ConnectivityQaError("Connectivity QA finding not found.", 404)
            prior = {"review_status": row["review_status"], "review_comment": row["review_comment"], "reviewed_by": row["reviewed_by"]}
            now = intake_registry_service.utc_now()
            connection.execute(
                """UPDATE connectivity_qa_findings SET review_status = ?, review_comment = ?,
                reviewed_by = ?, reviewed_at = ?, updated_at = ?
                WHERE qa_run_id = ? AND finding_id = ?""",
                (statuses[action], comment, reviewer, now, now, row["qa_run_id"], finding_id),
            )
            self._history(connection, row["qa_run_id"], finding_id, action, prior, {"review_status": statuses[action], "review_comment": comment, "reviewed_by": reviewer}, reviewer, comment)
            run = connection.execute(
                "SELECT summary_json FROM connectivity_qa_runs WHERE qa_run_id = ?",
                (row["qa_run_id"],),
            ).fetchone()
            summary = _load(run["summary_json"]) if run else {}
            summary["by_review_status"] = _counts(connection, row["qa_run_id"], "review_status")
            connection.execute(
                "UPDATE connectivity_qa_runs SET summary_json = ? WHERE qa_run_id = ?",
                (_dump(summary), row["qa_run_id"]),
            )
            connection.commit()
        return self.finding(vertical, finding_id)

    def _finish(
        self,
        connection: sqlite3.Connection,
        qa_run_id: str,
        status: str,
        rules_executed: int,
        rules_skipped: int,
        findings_count: int,
        blocking_count: int,
        error_count: int,
    ) -> dict[str, Any]:
        by_severity = _counts(connection, qa_run_id, "severity")
        by_rule = _counts(connection, qa_run_id, "rule_code")
        by_review = _counts(connection, qa_run_id, "review_status")
        summary = {
            "qa_run_id": qa_run_id,
            "status": status,
            "findings_count": findings_count,
            "blocking_findings_count": blocking_count,
            "by_severity": by_severity,
            "by_rule": by_rule,
            "by_review_status": by_review,
            "rules_executed": rules_executed,
            "rules_skipped": rules_skipped,
            "error_count": error_count,
            "message": "Connectivity QA completed from explicit canonical relationships only." if status != "blocked" else "No canonical assets are available for this utility vertical.",
            "limitations": [
                "This is not an ArcFM, GE Smallworld, or telecom network-inventory trace.",
                "No topology repair, snapping, service publishing, or source editing occurs.",
                "Provisional and inferred relationships are candidates, not authoritative connectivity.",
            ],
        }
        now = intake_registry_service.utc_now()
        connection.execute(
            """UPDATE connectivity_qa_runs SET status = ?, rules_executed = ?, rules_skipped = ?,
            findings_count = ?, blocking_findings_count = ?, error_count = ?, summary_json = ?, completed_at = ?
            WHERE qa_run_id = ?""",
            (status, rules_executed, rules_skipped, findings_count, blocking_count, error_count, _dump(summary), now, qa_run_id),
        )
        connection.commit()
        return summary

    def _graph_context(self, connection: sqlite3.Connection, finding: dict[str, Any]) -> dict[str, Any]:
        asset_ids = [item for item in (finding.get("asset_id"), finding.get("related_asset_id")) if item]
        assets = []
        if asset_ids:
            placeholders = ",".join("?" for _ in asset_ids)
            assets = [
                {
                    "asset_id": row["asset_id"], "canonical_name": row["canonical_name"],
                    "asset_class": row["asset_class"], "lifecycle_status": row["lifecycle_status"],
                    "operational_status": row["operational_status"],
                }
                for row in connection.execute(
                    f"SELECT asset_id, canonical_name, asset_class, lifecycle_status, operational_status FROM canonical_utility_assets WHERE asset_id IN ({placeholders})",
                    asset_ids,
                ).fetchall()
            ]
        relationship = None
        if finding.get("relationship_id"):
            row = connection.execute(
                """SELECT relationship_id, from_asset_id, to_asset_id, relationship_type, direction,
                confidence, source, provisional FROM utility_asset_relationships WHERE relationship_id = ?""",
                (finding["relationship_id"],),
            ).fetchone()
            relationship = dict(row) if row else None
        return {"assets": assets, "relationship": relationship, "geometry": "logical_graph_only"}

    def _history(
        self,
        connection: sqlite3.Connection,
        qa_run_id: str,
        finding_id: str | None,
        action: str,
        prior: dict[str, Any],
        new: dict[str, Any],
        actor: str,
        comment: str,
    ) -> None:
        connection.execute(
            """INSERT INTO connectivity_qa_history
            (history_id, qa_run_id, finding_id, action, prior_value_json, new_value_json, actor, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), qa_run_id, finding_id, action, _dump(prior), _dump(new), actor[:100], comment[:1000], intake_registry_service.utc_now()),
        )

    @staticmethod
    def _vertical(vertical: str) -> None:
        if vertical not in PROFILES:
            raise ConnectivityQaError("Unsupported utility vertical.", 404)


def _counts(connection: sqlite3.Connection, qa_run_id: str, field: str) -> dict[str, int]:
    rows = connection.execute(
        f"SELECT {field}, COUNT(*) count FROM connectivity_qa_findings WHERE qa_run_id = ? GROUP BY {field}",
        (qa_run_id,),
    ).fetchall()
    return {str(row[field]): int(row["count"]) for row in rows}


def _safe_run(row: dict[str, Any]) -> dict[str, Any]:
    row["force_recalculate"] = bool(row.get("force_recalculate"))
    row["summary"] = _load(row.pop("summary_json", "{}"))
    row.pop("asset_checksum", None)
    row.pop("relationship_checksum", None)
    return row


def _safe_finding(row: dict[str, Any]) -> dict[str, Any]:
    row["blocking"] = bool(row.get("blocking"))
    row["evidence"] = _load(row.pop("evidence_json", "{}"))
    return row


def _json_row(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    for field in fields:
        row[field] = _load(row.get(field, "{}"))
    for field in ("provisional", "is_synthetic"):
        if field in row:
            row[field] = bool(row[field])
    return row


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _load(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _pagination(total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total}


service = ConnectivityQaService()
