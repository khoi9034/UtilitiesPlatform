from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from app.services import intake_registry_service
from app.services.connectivity_qa import service as connectivity_qa
from app.services.utility_assets.domain import stable_fingerprint, stable_id

from . import engine


class ProposedEditError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProposedEditService:
    def connect(self) -> sqlite3.Connection:
        connection = connectivity_qa.connect()
        self._initialize(connection)
        self._seed_scenarios(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS proposed_edit_proposals (
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                parent_proposal_version INTEGER,
                supersedes_proposal_version INTEGER,
                scenario_code TEXT NOT NULL DEFAULT '',
                utility_vertical TEXT NOT NULL,
                proposal_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                baseline_fingerprint TEXT NOT NULL,
                canonical_asset_dataset_fingerprint TEXT NOT NULL,
                canonical_relationship_dataset_fingerprint TEXT NOT NULL,
                qa_run_fingerprint TEXT NOT NULL,
                qa_calibration_fingerprint TEXT NOT NULL,
                trace_profile_version TEXT NOT NULL,
                trace_calibration_version TEXT NOT NULL,
                source_snapshot_identifier TEXT NOT NULL,
                proposal_fingerprint TEXT NOT NULL DEFAULT '',
                version_fingerprint TEXT NOT NULL DEFAULT '',
                overlay_fingerprint TEXT NOT NULL DEFAULT '',
                analysis_fingerprint TEXT NOT NULL DEFAULT '',
                validation_status TEXT NOT NULL DEFAULT 'not_evaluated',
                analysis_status TEXT NOT NULL DEFAULT 'not_started',
                review_status TEXT NOT NULL DEFAULT 'not_submitted',
                approval_status TEXT NOT NULL DEFAULT 'not_requested',
                implementation_readiness TEXT NOT NULL DEFAULT 'not_evaluated',
                source_issue_group_ids_json TEXT NOT NULL DEFAULT '[]',
                source_trace_run_ids_json TEXT NOT NULL DEFAULT '[]',
                trace_type TEXT NOT NULL DEFAULT '',
                trace_start_asset_id TEXT NOT NULL DEFAULT '',
                impact_summary_json TEXT NOT NULL DEFAULT '{}',
                created_by TEXT NOT NULL,
                submitted_by TEXT NOT NULL DEFAULT '',
                submitted_at TEXT NOT NULL DEFAULT '',
                reviewed_by TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at TEXT NOT NULL DEFAULT '',
                rejection_reason TEXT NOT NULL DEFAULT '',
                superseded_by TEXT NOT NULL DEFAULT '',
                locked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (proposal_id, proposal_version)
            );
            CREATE INDEX IF NOT EXISTS idx_proposed_edits_list
                ON proposed_edit_proposals(utility_vertical, updated_at DESC);

            CREATE TABLE IF NOT EXISTS proposed_edit_operations (
                operation_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                operation_type TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                target_asset_id TEXT NOT NULL DEFAULT '',
                target_relationship_id TEXT NOT NULL DEFAULT '',
                new_asset_temporary_id TEXT NOT NULL DEFAULT '',
                affected_vertical TEXT NOT NULL,
                field_name TEXT NOT NULL DEFAULT '',
                prior_value_json TEXT NOT NULL DEFAULT 'null',
                proposed_value_json TEXT NOT NULL DEFAULT 'null',
                prior_values_json TEXT NOT NULL DEFAULT '{}',
                proposed_values_json TEXT NOT NULL DEFAULT '{}',
                relationship_type TEXT NOT NULL DEFAULT '',
                from_asset_id TEXT NOT NULL DEFAULT '',
                to_asset_id TEXT NOT NULL DEFAULT '',
                replacement_asset_id TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                source_issue_group_ids_json TEXT NOT NULL DEFAULT '[]',
                source_trace_run_ids_json TEXT NOT NULL DEFAULT '[]',
                source_trace_calibration_ids_json TEXT NOT NULL DEFAULT '[]',
                provisional INTEGER NOT NULL DEFAULT 0,
                direction TEXT NOT NULL DEFAULT 'forward',
                validation_status TEXT NOT NULL DEFAULT 'not_evaluated',
                validation_errors_json TEXT NOT NULL DEFAULT '[]',
                validation_warnings_json TEXT NOT NULL DEFAULT '[]',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (proposal_id, proposal_version, operation_id),
                UNIQUE (proposal_id, proposal_version, sequence)
            );

            CREATE TABLE IF NOT EXISTS proposed_edit_validation_runs (
                validation_run_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                rule_version TEXT NOT NULL,
                status TEXT NOT NULL,
                errors_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposed_edit_overlay_runs (
                overlay_run_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                baseline_fingerprint TEXT NOT NULL,
                overlay_fingerprint TEXT NOT NULL,
                assets_read INTEGER NOT NULL,
                assets_added INTEGER NOT NULL,
                assets_modified INTEGER NOT NULL,
                assets_removed INTEGER NOT NULL,
                relationships_read INTEGER NOT NULL,
                relationships_added INTEGER NOT NULL,
                relationships_modified INTEGER NOT NULL,
                relationships_removed INTEGER NOT NULL,
                status TEXT NOT NULL,
                safe_error_message TEXT NOT NULL DEFAULT '',
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposed_edit_qa_comparisons (
                comparison_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                analysis_fingerprint TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposed_edit_trace_comparisons (
                comparison_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                analysis_fingerprint TEXT NOT NULL,
                trace_scenario_code TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposed_edit_reviews (
                review_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                reviewer TEXT NOT NULL,
                reviewer_role TEXT NOT NULL,
                action TEXT NOT NULL,
                decision TEXT NOT NULL,
                notes TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposed_edit_history (
                history_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                operation_id TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                prior_value_json TEXT NOT NULL,
                new_value_json TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proposed_edit_packages (
                package_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                package_fingerprint TEXT NOT NULL,
                package_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(proposal_id, proposal_version)
            );
            CREATE TABLE IF NOT EXISTS proposed_edit_seed_versions (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """
        )
        connection.commit()

    def types(self, vertical: str | None = None) -> dict[str, Any]:
        try:
            return engine.catalog(vertical)
        except ValueError as exc:
            raise ProposedEditError(str(exc), 404) from exc

    def operation_types(self) -> dict[str, Any]:
        return engine.operation_catalog()

    def list_proposals(self, vertical: str, filters: dict[str, Any]) -> dict[str, Any]:
        self._vertical(vertical)
        clauses = [
            "p.utility_vertical = ?",
            """p.proposal_version = (
                SELECT MAX(v.proposal_version) FROM proposed_edit_proposals v
                WHERE v.proposal_id = p.proposal_id
            )""",
        ]
        values: list[Any] = [vertical]
        for field in ("status", "proposal_type", "validation_status", "approval_status"):
            if filters.get(field):
                clauses.append(f"p.{field} = ?")
                values.append(str(filters[field]))
        if filters.get("search"):
            clauses.append("(LOWER(p.title) LIKE ? OR LOWER(p.proposal_id) LIKE ?)")
            term = f"%{str(filters['search']).lower()}%"
            values.extend((term, term))
        limit = max(1, min(int(filters.get("limit", 100)), 500))
        offset = max(0, int(filters.get("offset", 0)))
        where = " AND ".join(clauses)
        with self.connect() as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM proposed_edit_proposals p WHERE {where}", values).fetchone()[0])
            rows = connection.execute(
                f"""SELECT p.*, (SELECT COUNT(*) FROM proposed_edit_operations o
                     WHERE o.proposal_id = p.proposal_id AND o.proposal_version = p.proposal_version) operation_count
                    FROM proposed_edit_proposals p WHERE {where}
                    ORDER BY p.scenario_code, p.updated_at DESC LIMIT ? OFFSET ?""",
                (*values, limit, offset),
            ).fetchall()
        return {
            "items": [self._safe_proposal(dict(row)) for row in rows],
            "pagination": {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total},
            "disclaimer": engine.DISCLAIMER,
        }

    def create_proposal(self, vertical: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._vertical(vertical)
        allowed = {
            "proposal_type", "title", "summary", "created_by", "source_issue_group_ids",
            "source_trace_run_ids", "trace_type", "trace_start_asset_id", "scenario_code",
        }
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed)
            selected_type = engine.proposal_type(vertical, payload.get("proposal_type"))
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc
        title = str(payload.get("title", "")).strip()[:180]
        actor = str(payload.get("created_by", "")).strip()[:100]
        if not title or not actor:
            raise ProposedEditError("Proposal title and author are required.")
        scenario_code = str(payload.get("scenario_code", "")).strip()[:40]
        proposal_id = stable_id(
            "proposed-edit",
            vertical,
            scenario_code or title,
            actor,
            sorted(payload.get("source_issue_group_ids") or []),
            sorted(payload.get("source_trace_run_ids") or []),
        )
        with self.connect() as connection:
            existing = self._row(connection, vertical, proposal_id)
            if existing:
                return self._detail(connection, existing)
            proposal = self._insert_proposal(
                connection,
                proposal_id,
                1,
                vertical,
                selected_type,
                title,
                str(payload.get("summary", "")).strip()[:2000],
                actor,
                scenario_code,
                payload,
            )
            self._history(connection, proposal_id, 1, "", "proposal_created", {}, {"status": "draft"}, "proposal_author", actor, "")
            connection.commit()
            return self._detail(connection, proposal)

    def proposal(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            return self._detail(connection, self._require(connection, vertical, proposal_id))

    def clone(self, vertical: str, proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"created_by", "title"})
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc
        with self.connect() as connection:
            source = self._require(connection, vertical, proposal_id)
            actor = str(payload.get("created_by") or source["created_by"]).strip()[:100]
            title = str(payload.get("title") or f"Copy of {source['title']}").strip()[:180]
            new_id = stable_id("proposed-edit-clone", proposal_id, source["proposal_version"], title, actor)
            existing = self._row(connection, vertical, new_id)
            if existing:
                return self._detail(connection, existing)
            clone = self._insert_proposal(
                connection, new_id, 1, vertical, source["proposal_type"], title,
                source["summary"], actor, "", {
                    "source_issue_group_ids": _loads(source["source_issue_group_ids_json"], []),
                    "source_trace_run_ids": _loads(source["source_trace_run_ids_json"], []),
                    "trace_type": source["trace_type"],
                    "trace_start_asset_id": source["trace_start_asset_id"],
                },
            )
            self._copy_operations(connection, source, clone)
            self._history(connection, new_id, 1, "", "proposal_cloned", {}, {"source_proposal_id": proposal_id}, "proposal_author", actor, "")
            connection.commit()
            return self._detail(connection, clone)

    def new_version(self, vertical: str, proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"created_by", "reason"})
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc
        with self.connect() as connection:
            source = self._require(connection, vertical, proposal_id)
            actor = str(payload.get("created_by") or source["created_by"]).strip()[:100]
            version = int(source["proposal_version"]) + 1
            clone = self._insert_proposal(
                connection, proposal_id, version, vertical, source["proposal_type"], source["title"],
                source["summary"], actor, source["scenario_code"], {
                    "source_issue_group_ids": _loads(source["source_issue_group_ids_json"], []),
                    "source_trace_run_ids": _loads(source["source_trace_run_ids_json"], []),
                    "trace_type": source["trace_type"],
                    "trace_start_asset_id": source["trace_start_asset_id"],
                }, parent_version=int(source["proposal_version"]),
            )
            self._copy_operations(connection, source, clone)
            self._history(
                connection, proposal_id, version, "", "proposal_version_created",
                {"parent_version": source["proposal_version"]}, {"status": "draft"},
                "proposal_author", actor, str(payload.get("reason", ""))[:1000],
            )
            connection.commit()
            return self._detail(connection, clone)

    def operations(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            return {
                "items": self._operations(connection, proposal_id, proposal["proposal_version"]),
                "proposal_id": proposal_id,
                "proposal_version": proposal["proposal_version"],
            }

    def add_operation(self, vertical: str, proposal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require_editable(connection, vertical, proposal_id)
            sequence = int(connection.execute(
                """SELECT COALESCE(MAX(sequence), 0) + 1 FROM proposed_edit_operations
                WHERE proposal_id = ? AND proposal_version = ?""",
                (proposal_id, proposal["proposal_version"]),
            ).fetchone()[0])
            operation = self._normalize_operation(proposal, sequence, payload)
            self._insert_operation(connection, operation, str(payload.get("created_by") or proposal["created_by"]))
            self._invalidate(connection, proposal, "operation_added")
            self._history(
                connection, proposal_id, proposal["proposal_version"], operation["operation_id"],
                "operation_added", {}, operation, "proposal_author", str(payload.get("created_by") or proposal["created_by"]), operation["reason"],
            )
            connection.commit()
            return operation

    def update_operation(
        self, vertical: str, proposal_id: str, operation_id: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require_editable(connection, vertical, proposal_id)
            existing = connection.execute(
                """SELECT * FROM proposed_edit_operations
                WHERE proposal_id = ? AND proposal_version = ? AND operation_id = ?""",
                (proposal_id, proposal["proposal_version"], operation_id),
            ).fetchone()
            if not existing:
                raise ProposedEditError("Proposed operation not found.", 404)
            current = self._safe_operation(dict(existing))
            merged = {
                key: payload.get(key, current.get(key))
                for key in (
                    "operation_type", "target_asset_id", "target_relationship_id", "new_asset_temporary_id",
                    "field_name", "prior_value", "proposed_value", "prior_values", "proposed_values",
                    "relationship_type", "from_asset_id", "to_asset_id", "replacement_asset_id",
                    "reason", "source_issue_group_ids", "source_trace_run_ids",
                    "source_trace_calibration_ids", "provisional", "direction",
                )
            }
            operation = self._normalize_operation(proposal, int(existing["sequence"]), merged)
            self._write_operation(connection, operation, str(payload.get("created_by") or proposal["created_by"]), existing["created_at"])
            self._invalidate(connection, proposal, "operation_updated")
            self._history(
                connection, proposal_id, proposal["proposal_version"], operation_id, "operation_updated",
                current, operation, "proposal_author", str(payload.get("created_by") or proposal["created_by"]), operation["reason"],
            )
            connection.commit()
            return operation

    def delete_operation(self, vertical: str, proposal_id: str, operation_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        with self.connect() as connection:
            proposal = self._require_editable(connection, vertical, proposal_id)
            row = connection.execute(
                """SELECT * FROM proposed_edit_operations
                WHERE proposal_id = ? AND proposal_version = ? AND operation_id = ?""",
                (proposal_id, proposal["proposal_version"], operation_id),
            ).fetchone()
            if not row:
                raise ProposedEditError("Proposed operation not found.", 404)
            prior = self._safe_operation(dict(row))
            connection.execute(
                """DELETE FROM proposed_edit_operations
                WHERE proposal_id = ? AND proposal_version = ? AND operation_id = ?""",
                (proposal_id, proposal["proposal_version"], operation_id),
            )
            actor = str(payload.get("actor") or proposal["created_by"])[:100]
            self._invalidate(connection, proposal, "operation_removed")
            self._history(connection, proposal_id, proposal["proposal_version"], operation_id, "operation_removed", prior, {}, "proposal_author", actor, str(payload.get("reason", ""))[:1000])
            connection.commit()
            return {"deleted": True, "operation_id": operation_id, "history_preserved": True}

    def validate(self, vertical: str, proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"actor"})
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            if proposal["locked"]:
                raise ProposedEditError("Submitted and approved proposal versions are immutable.", 409)
            result = self._validate(connection, proposal, str(payload.get("actor") or proposal["created_by"]))
            connection.commit()
            return result

    def validation(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        return self._latest_result(vertical, proposal_id, "proposed_edit_validation_runs", "validation_run_id", ("errors_json", "warnings_json"))

    def analyze(self, vertical: str, proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"actor", "force_recalculate"})
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            if proposal["locked"]:
                raise ProposedEditError("Submitted and approved proposal versions are immutable.", 409)
            result = self._analyze(
                connection,
                proposal,
                str(payload.get("actor") or proposal["created_by"]),
                bool(payload.get("force_recalculate", False)),
            )
            connection.commit()
            return result

    def overlay(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        result = self._latest_result(vertical, proposal_id, "proposed_edit_overlay_runs", "overlay_run_id", ("summary_json",))
        summary = result.pop("summary_json", {})
        return {**result, **summary, "notice": "Proposed overlay - no canonical or source records have been changed."}

    def qa_comparison(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        return self._comparison(vertical, proposal_id, "proposed_edit_qa_comparisons", one=True)

    def trace_comparisons(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        result = self._comparison(vertical, proposal_id, "proposed_edit_trace_comparisons", one=False)
        return {"items": result, "disclaimer": engine.DISCLAIMER}

    def impact(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            result = _loads(proposal["impact_summary_json"], {})
            if not result:
                raise ProposedEditError("Proposal impact analysis has not been completed.", 404)
            return result

    def review(self, vertical: str, proposal_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        allowed = {"actor", "reviewer", "reviewer_role", "notes", "acknowledge_new_blockers"}
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed)
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc
        transitions = {
            "submit": ({"analysis_complete", "needs_revision"}, "submitted_for_review", "submitted", "pending", False),
            "start-review": ({"submitted_for_review"}, "under_review", "under_review", "pending", False),
            "request-revision": ({"submitted_for_review", "under_review"}, "needs_revision", "decision_recorded", "not_requested", True),
            "approve": ({"under_review"}, "approved", "decision_recorded", "approved", True),
            "reject": ({"submitted_for_review", "under_review"}, "rejected", "decision_recorded", "rejected", True),
            "defer": ({"draft", "analysis_complete", "submitted_for_review", "under_review", "needs_revision"}, "deferred", "decision_recorded", "deferred", True),
            "withdraw": ({"draft", "analysis_complete", "needs_revision", "submitted_for_review"}, "withdrawn", "decision_recorded", "withdrawn", False),
            "reopen": ({"rejected", "deferred", "withdrawn"}, "needs_revision", "not_submitted", "not_requested", False),
        }
        if action not in transitions:
            raise ProposedEditError("Unsupported proposal review action.")
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            allowed_states, status, review_status, approval_status, notes_required = transitions[action]
            if proposal["status"] not in allowed_states:
                raise ProposedEditError(f"Proposal cannot {action} from {proposal['status']}.", 409)
            notes = str(payload.get("notes", "")).strip()[:2000]
            actor = str(payload.get("reviewer") or payload.get("actor") or "").strip()[:100]
            role = str(payload.get("reviewer_role") or ("proposal_author" if action in {"submit", "withdraw"} else "technical_reviewer")).strip()[:50]
            if notes_required and not notes:
                raise ProposedEditError("Reviewer notes are required for this action.")
            if not actor:
                raise ProposedEditError("Reviewer identity is required.")
            if action == "submit":
                self._approval_prerequisites(connection, proposal, actor, final=False, acknowledge=False)
            if action == "approve":
                self._approval_prerequisites(
                    connection, proposal, actor, final=True,
                    acknowledge=bool(payload.get("acknowledge_new_blockers", False)),
                )
            now = intake_registry_service.utc_now()
            fields: dict[str, Any] = {
                "status": status, "review_status": review_status, "approval_status": approval_status,
                "reviewed_by": actor, "reviewed_at": now, "updated_at": now,
                "locked": int(status in {"submitted_for_review", "under_review", "approved"}),
            }
            if action == "submit":
                fields.update({"submitted_by": actor, "submitted_at": now, "locked": 1})
            elif action == "approve":
                fields.update({
                    "approved_by": actor, "approved_at": now,
                    "implementation_readiness": "approved_plan_only", "locked": 1,
                })
            elif action == "reject":
                fields["rejection_reason"] = notes
            self._update_proposal(connection, proposal, fields)
            review_id = stable_id("proposal-review", proposal_id, proposal["proposal_version"], action, now, actor)
            connection.execute(
                """INSERT INTO proposed_edit_reviews
                (review_id, proposal_id, proposal_version, reviewer, reviewer_role, action, decision, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (review_id, proposal_id, proposal["proposal_version"], actor, role, action, status, notes, now),
            )
            self._history(
                connection, proposal_id, proposal["proposal_version"], "", action,
                {"status": proposal["status"]}, {"status": status}, role, actor, notes,
            )
            connection.commit()
            return self._detail(connection, self._require(connection, vertical, proposal_id))

    def supersede(self, vertical: str, proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        notes = str(payload.get("notes", "")).strip()[:2000]
        actor = str(payload.get("actor") or payload.get("reviewer") or "").strip()[:100]
        if not actor or not notes:
            raise ProposedEditError("Reviewer identity and notes are required to supersede a proposal.")
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            if proposal["status"] in {"superseded", "archived"}:
                raise ProposedEditError("Proposal is already closed.", 409)
            version = int(proposal["proposal_version"]) + 1
            successor = self._insert_proposal(
                connection, proposal_id, version, vertical, proposal["proposal_type"], proposal["title"],
                proposal["summary"], actor, proposal["scenario_code"], {
                    "source_issue_group_ids": _loads(proposal["source_issue_group_ids_json"], []),
                    "source_trace_run_ids": _loads(proposal["source_trace_run_ids_json"], []),
                    "trace_type": proposal["trace_type"],
                    "trace_start_asset_id": proposal["trace_start_asset_id"],
                }, parent_version=int(proposal["proposal_version"]),
                supersedes_version=int(proposal["proposal_version"]),
            )
            self._copy_operations(connection, proposal, successor)
            self._update_proposal(connection, proposal, {"status": "superseded", "superseded_by": f"{proposal_id}:v{version}", "locked": 1})
            self._history(connection, proposal_id, proposal["proposal_version"], "", "superseded", {}, {"successor_version": version}, "technical_reviewer", actor, notes)
            self._history(connection, proposal_id, version, "", "superseding_version_created", {"version": proposal["proposal_version"]}, {"version": version}, "technical_reviewer", actor, notes)
            connection.commit()
            return self._detail(connection, successor)

    def safe_summary(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            operations = self._operations(connection, proposal_id, proposal["proposal_version"])
            return {
                "proposal": self._safe_proposal(proposal),
                "operations": operations,
                "impact_summary": _loads(proposal["impact_summary_json"], {}),
                "external_mapping_status": "adapter_required",
                "required_adapter_capabilities": engine.required_adapter_capabilities(operations),
                "executable": False,
                "disclaimer": engine.DISCLAIMER,
            }

    def create_package(self, vertical: str, proposal_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._vertical(vertical)
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"actor", "notes"})
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            if proposal["approval_status"] != "approved" or proposal["status"] not in {"approved", "implementation_ready", "implementation_exported"}:
                raise ProposedEditError("Only an approved change plan can produce an implementation package.", 409)
            operations = self._operations(connection, proposal_id, proposal["proposal_version"])
            now = intake_registry_service.utc_now()
            package_id = stable_id("proposed-edit-package", proposal_id, proposal["proposal_version"], proposal["proposal_fingerprint"])
            package = {
                "package_id": package_id,
                "package_version": engine.PACKAGE_VERSION,
                "proposal_id": proposal_id,
                "proposal_version": proposal["proposal_version"],
                "utility_vertical": vertical,
                "proposal_type": proposal["proposal_type"],
                "baseline_fingerprint": proposal["baseline_fingerprint"],
                "proposal_fingerprint": proposal["proposal_fingerprint"],
                "overlay_fingerprint": proposal["overlay_fingerprint"],
                "approval": {
                    "status": proposal["approval_status"],
                    "approved_by": proposal["approved_by"],
                    "approved_at": proposal["approved_at"],
                },
                "operations": [
                    {
                        key: item.get(key)
                        for key in (
                            "sequence", "operation_type", "target_asset_id", "target_relationship_id",
                            "new_asset_temporary_id", "field_name", "prior_value", "proposed_value",
                            "prior_values", "proposed_values", "relationship_type", "from_asset_id",
                            "to_asset_id", "replacement_asset_id", "reason",
                        )
                    }
                    for item in operations
                ],
                "qa_comparison": self._comparison_from_connection(connection, proposal, "proposed_edit_qa_comparisons", one=True),
                "trace_comparisons": self._comparison_from_connection(connection, proposal, "proposed_edit_trace_comparisons", one=False),
                "impact_summary": _loads(proposal["impact_summary_json"], {}),
                "implementation_readiness": "implementation_package_ready",
                "external_mapping_status": "adapter_required",
                "external_asset_mapping_status": "not_mapped",
                "external_relationship_mapping_status": "not_mapped",
                "external_operation_mapping_status": "adapter_required",
                "implementation_status": "not_implemented",
                "required_adapter_capabilities": engine.required_adapter_capabilities(operations),
                "adapter_notes": "A future licensed-system adapter, schema mapping, permissions, and utility validation are required.",
                "descriptive_only": True,
                "executable": False,
                "created_at": now,
                "disclaimer": engine.DISCLAIMER,
            }
            fingerprint = stable_fingerprint(package)
            connection.execute(
                """INSERT INTO proposed_edit_packages
                (package_id, proposal_id, proposal_version, package_fingerprint, package_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id, proposal_version) DO UPDATE SET
                    package_id = excluded.package_id,
                    package_fingerprint = excluded.package_fingerprint,
                    package_json = excluded.package_json,
                    created_at = excluded.created_at""",
                (package_id, proposal_id, proposal["proposal_version"], fingerprint, _dump(package), now),
            )
            self._update_proposal(connection, proposal, {
                "status": "implementation_ready",
                "implementation_readiness": "implementation_package_ready",
            })
            actor = str(payload.get("actor") or proposal["approved_by"])[:100]
            self._history(connection, proposal_id, proposal["proposal_version"], "", "implementation_package_created", {}, {"package_id": package_id}, "system", actor, str(payload.get("notes", ""))[:1000])
            connection.commit()
            return package

    def package(self, vertical: str, proposal_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            row = connection.execute(
                """SELECT package_json FROM proposed_edit_packages
                WHERE proposal_id = ? AND proposal_version = ?""",
                (proposal_id, proposal["proposal_version"]),
            ).fetchone()
            if not row:
                raise ProposedEditError("Implementation package has not been generated.", 404)
            return _loads(row["package_json"], {})

    def _insert_proposal(
        self,
        connection: sqlite3.Connection,
        proposal_id: str,
        version: int,
        vertical: str,
        selected_type: str,
        title: str,
        summary: str,
        actor: str,
        scenario_code: str,
        payload: dict[str, Any],
        parent_version: int | None = None,
        supersedes_version: int | None = None,
    ) -> dict[str, Any]:
        assets, relationships = self._graph(connection, vertical)
        baseline = self._baseline(connection, vertical, assets, relationships)
        now = intake_registry_service.utc_now()
        connection.execute(
            """INSERT INTO proposed_edit_proposals
            (proposal_id, proposal_version, parent_proposal_version, supersedes_proposal_version,
             scenario_code, utility_vertical, proposal_type, title, summary, status,
             baseline_fingerprint, canonical_asset_dataset_fingerprint,
             canonical_relationship_dataset_fingerprint, qa_run_fingerprint,
             qa_calibration_fingerprint, trace_profile_version, trace_calibration_version,
             source_snapshot_identifier, source_issue_group_ids_json, source_trace_run_ids_json,
             trace_type, trace_start_asset_id, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                proposal_id, version, parent_version, supersedes_version, scenario_code,
                vertical, selected_type, title, summary, baseline["baseline_fingerprint"],
                baseline["canonical_asset_dataset_fingerprint"],
                baseline["canonical_relationship_dataset_fingerprint"],
                baseline["qa_run_fingerprint"], baseline["qa_calibration_fingerprint"],
                baseline["trace_profile_version"], baseline["trace_calibration_version"],
                baseline["source_snapshot_identifier"],
                _dump(sorted(payload.get("source_issue_group_ids") or [])),
                _dump(sorted(payload.get("source_trace_run_ids") or [])),
                str(payload.get("trace_type", ""))[:50],
                str(payload.get("trace_start_asset_id", ""))[:120],
                actor, now, now,
            ),
        )
        return dict(connection.execute(
            "SELECT * FROM proposed_edit_proposals WHERE proposal_id = ? AND proposal_version = ?",
            (proposal_id, version),
        ).fetchone())

    def _copy_operations(self, connection: sqlite3.Connection, source: dict[str, Any], target: dict[str, Any]) -> None:
        for index, operation in enumerate(
            self._operations(connection, source["proposal_id"], source["proposal_version"]), 1,
        ):
            payload = {
                key: operation.get(key)
                for key in (
                    "operation_type", "target_asset_id", "target_relationship_id",
                    "new_asset_temporary_id", "field_name", "prior_value", "proposed_value",
                    "prior_values", "proposed_values", "relationship_type", "from_asset_id",
                    "to_asset_id", "replacement_asset_id", "reason", "source_issue_group_ids",
                    "source_trace_run_ids", "source_trace_calibration_ids", "provisional", "direction",
                )
            }
            if payload.get("new_asset_temporary_id"):
                payload["new_asset_temporary_id"] = f"PROP-{target['proposal_id']}-{index}"
            copied = self._normalize_operation(target, index, payload)
            self._insert_operation(connection, copied, target["created_by"])

    def _normalize_operation(self, proposal: dict[str, Any], sequence: int, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return engine.normalize_operation(
                proposal["utility_vertical"], proposal["proposal_id"],
                int(proposal["proposal_version"]), sequence, payload,
            )
        except ValueError as exc:
            raise ProposedEditError(str(exc)) from exc

    def _insert_operation(self, connection: sqlite3.Connection, operation: dict[str, Any], actor: str) -> None:
        self._write_operation(connection, operation, actor, intake_registry_service.utc_now())

    def _write_operation(
        self, connection: sqlite3.Connection, operation: dict[str, Any], actor: str, created_at: str,
    ) -> None:
        now = intake_registry_service.utc_now()
        connection.execute(
            """INSERT OR REPLACE INTO proposed_edit_operations
            (operation_id, proposal_id, proposal_version, operation_type, sequence,
             target_asset_id, target_relationship_id, new_asset_temporary_id, affected_vertical,
             field_name, prior_value_json, proposed_value_json, prior_values_json,
             proposed_values_json, relationship_type, from_asset_id, to_asset_id,
             replacement_asset_id, reason, source_issue_group_ids_json, source_trace_run_ids_json,
             source_trace_calibration_ids_json, provisional, direction, validation_status,
             validation_errors_json, validation_warnings_json, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                operation["operation_id"], operation["proposal_id"], operation["proposal_version"],
                operation["operation_type"], operation["sequence"], operation["target_asset_id"],
                operation["target_relationship_id"], operation["new_asset_temporary_id"],
                operation["affected_vertical"], operation["field_name"], _dump(operation["prior_value"]),
                _dump(operation["proposed_value"]), _dump(operation["prior_values"]),
                _dump(operation["proposed_values"]), operation["relationship_type"],
                operation["from_asset_id"], operation["to_asset_id"], operation["replacement_asset_id"],
                operation["reason"], _dump(operation["source_issue_group_ids"]),
                _dump(operation["source_trace_run_ids"]), _dump(operation["source_trace_calibration_ids"]),
                int(operation["provisional"]), operation["direction"], operation["validation_status"],
                _dump(operation["validation_errors"]), _dump(operation["validation_warnings"]),
                actor[:100], created_at, now,
            ),
        )

    def _validate(self, connection: sqlite3.Connection, proposal: dict[str, Any], actor: str) -> dict[str, Any]:
        assets, relationships = self._graph(connection, proposal["utility_vertical"])
        current = self._baseline(connection, proposal["utility_vertical"], assets, relationships)
        operations = self._operations(connection, proposal["proposal_id"], proposal["proposal_version"])
        result = engine.validate_operations(
            proposal["utility_vertical"], operations, assets, relationships,
            current["baseline_fingerprint"] == proposal["baseline_fingerprint"],
        )
        started = completed = intake_registry_service.utc_now()
        validation_id = stable_id(
            "proposal-validation", proposal["proposal_id"], proposal["proposal_version"],
            engine.PROPOSAL_RULE_VERSION, engine.proposal_fingerprint(proposal, operations),
        )
        connection.execute(
            """INSERT OR REPLACE INTO proposed_edit_validation_runs
            (validation_run_id, proposal_id, proposal_version, rule_version, status,
             errors_json, warnings_json, started_at, completed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                validation_id, proposal["proposal_id"], proposal["proposal_version"],
                engine.PROPOSAL_RULE_VERSION, result["status"], _dump(result["errors"]),
                _dump(result["warnings"]), started, completed, completed,
            ),
        )
        by_operation_errors: dict[str, list[dict[str, str]]] = {}
        by_operation_warnings: dict[str, list[dict[str, str]]] = {}
        for item in result["errors"]:
            by_operation_errors.setdefault(item["operation_id"], []).append(item)
        for item in result["warnings"]:
            by_operation_warnings.setdefault(item["operation_id"], []).append(item)
        for operation in operations:
            errors = by_operation_errors.get(operation["operation_id"], [])
            warnings = by_operation_warnings.get(operation["operation_id"], [])
            connection.execute(
                """UPDATE proposed_edit_operations SET validation_status = ?,
                validation_errors_json = ?, validation_warnings_json = ?, updated_at = ?
                WHERE proposal_id = ? AND proposal_version = ? AND operation_id = ?""",
                (
                    "failed" if errors else "passed", _dump(errors), _dump(warnings), completed,
                    proposal["proposal_id"], proposal["proposal_version"], operation["operation_id"],
                ),
            )
        fingerprint = engine.proposal_fingerprint(proposal, operations)
        status = "validation_failed" if result["status"] == "failed" else "ready_for_analysis"
        self._update_proposal(connection, proposal, {
            "status": status,
            "validation_status": result["status"],
            "proposal_fingerprint": fingerprint,
            "version_fingerprint": stable_fingerprint(proposal["proposal_id"], proposal["proposal_version"], fingerprint),
            "updated_at": completed,
        })
        self._history(
            connection, proposal["proposal_id"], proposal["proposal_version"], "", "proposal_validated",
            {"status": proposal["validation_status"]}, {"status": result["status"]}, "system", actor,
            f"{len(result['errors'])} errors; {len(result['warnings'])} warnings",
        )
        return {
            "validation_run_id": validation_id,
            "proposal_id": proposal["proposal_id"],
            "proposal_version": proposal["proposal_version"],
            **result,
            "baseline_current": current["baseline_fingerprint"] == proposal["baseline_fingerprint"],
        }

    def _analyze(
        self,
        connection: sqlite3.Connection,
        proposal: dict[str, Any],
        actor: str,
        force: bool,
    ) -> dict[str, Any]:
        validation = self._validate(connection, proposal, actor)
        if validation["status"] != "passed":
            raise ProposedEditError("Proposal validation failed; temporary analysis was not run.", 409)
        proposal = self._require_version(connection, proposal["proposal_id"], proposal["proposal_version"])
        assets, relationships = self._graph(connection, proposal["utility_vertical"])
        operations = self._operations(connection, proposal["proposal_id"], proposal["proposal_version"])
        overlay = engine.apply_overlay(proposal["utility_vertical"], assets, relationships, operations)
        analysis_fingerprint = stable_fingerprint(
            engine.ANALYSIS_VERSION, proposal["proposal_fingerprint"], overlay["overlay_fingerprint"],
        )
        if not force and proposal["analysis_fingerprint"] == analysis_fingerprint:
            comparison = self._comparison_from_connection(connection, proposal, "proposed_edit_qa_comparisons", one=True)
            if comparison:
                return {
                    "proposal_id": proposal["proposal_id"],
                    "proposal_version": proposal["proposal_version"],
                    "analysis_status": "complete",
                    "analysis_fingerprint": analysis_fingerprint,
                    "reused": True,
                    "overlay": overlay["summary"],
                    "qa_comparison": comparison,
                    "trace_comparisons": self._comparison_from_connection(
                        connection, proposal, "proposed_edit_trace_comparisons", one=False,
                    ),
                    "impact_summary": _loads(proposal["impact_summary_json"], {}),
                }
        self._update_proposal(connection, proposal, {"status": "analyzing", "analysis_status": "running"})
        baseline_qa = engine.run_proposed_qa(
            proposal["utility_vertical"], assets, relationships,
            f"{proposal['baseline_fingerprint']}:baseline",
        )
        proposed_qa = engine.run_proposed_qa(
            proposal["utility_vertical"], overlay["assets"], overlay["relationships"],
            f"{overlay['overlay_fingerprint']}:proposed",
        )
        qa_comparison = engine.compare_qa(baseline_qa, proposed_qa, proposal["proposal_id"])
        traces: list[dict[str, Any]] = []
        trace_type = proposal["trace_type"]
        start_asset_id = proposal["trace_start_asset_id"]
        if trace_type and start_asset_id:
            before_trace = engine.run_proposed_trace(
                proposal["utility_vertical"], assets, relationships, baseline_qa["groups"],
                trace_type, start_asset_id, f"{proposal['baseline_fingerprint']}:baseline",
            )
            after_trace = engine.run_proposed_trace(
                proposal["utility_vertical"], overlay["assets"], overlay["relationships"], proposed_qa["groups"],
                trace_type, start_asset_id, f"{overlay['overlay_fingerprint']}:proposed",
            )
            traces.append(engine.compare_trace(
                proposal["proposal_id"], proposal["scenario_code"] or trace_type, before_trace, after_trace,
            ))
        impact = engine.impact_summary(proposal, operations, overlay, qa_comparison, traces)
        now = intake_registry_service.utc_now()
        overlay_id = stable_id("proposal-overlay-run", proposal["proposal_id"], proposal["proposal_version"], analysis_fingerprint)
        summary = overlay["summary"]
        connection.execute(
            """INSERT OR REPLACE INTO proposed_edit_overlay_runs
            (overlay_run_id, proposal_id, proposal_version, baseline_fingerprint, overlay_fingerprint,
             assets_read, assets_added, assets_modified, assets_removed, relationships_read,
             relationships_added, relationships_modified, relationships_removed, status,
             safe_error_message, summary_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'succeeded', '', ?, ?)""",
            (
                overlay_id, proposal["proposal_id"], proposal["proposal_version"],
                proposal["baseline_fingerprint"], overlay["overlay_fingerprint"],
                summary["assets_read"], summary["assets_added"], summary["assets_modified"],
                summary["assets_removed"], summary["relationships_read"], summary["relationships_added"],
                summary["relationships_modified"], summary["relationships_removed"], _dump(summary), now,
            ),
        )
        connection.execute(
            """INSERT OR REPLACE INTO proposed_edit_qa_comparisons
            (comparison_id, proposal_id, proposal_version, analysis_fingerprint, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                qa_comparison["comparison_id"], proposal["proposal_id"], proposal["proposal_version"],
                analysis_fingerprint, _dump(qa_comparison), now,
            ),
        )
        connection.execute(
            "DELETE FROM proposed_edit_trace_comparisons WHERE proposal_id = ? AND proposal_version = ?",
            (proposal["proposal_id"], proposal["proposal_version"]),
        )
        for trace in traces:
            connection.execute(
                """INSERT INTO proposed_edit_trace_comparisons
                (comparison_id, proposal_id, proposal_version, analysis_fingerprint,
                 trace_scenario_code, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace["comparison_id"], proposal["proposal_id"], proposal["proposal_version"],
                    analysis_fingerprint, trace["trace_scenario_code"], _dump(trace), now,
                ),
            )
        self._update_proposal(connection, proposal, {
            "status": "analysis_complete",
            "analysis_status": "complete",
            "overlay_fingerprint": overlay["overlay_fingerprint"],
            "analysis_fingerprint": analysis_fingerprint,
            "implementation_readiness": impact["implementation_readiness"],
            "impact_summary_json": _dump(impact),
            "updated_at": now,
        })
        self._history(
            connection, proposal["proposal_id"], proposal["proposal_version"], "", "proposal_analyzed",
            {}, {"analysis_fingerprint": analysis_fingerprint}, "system", actor,
            "Temporary QA and trace comparisons completed without changing canonical records.",
        )
        return {
            "proposal_id": proposal["proposal_id"],
            "proposal_version": proposal["proposal_version"],
            "analysis_status": "complete",
            "analysis_fingerprint": analysis_fingerprint,
            "reused": False,
            "overlay": summary,
            "qa_comparison": qa_comparison,
            "trace_comparisons": traces,
            "impact_summary": impact,
        }

    def _approval_prerequisites(
        self,
        connection: sqlite3.Connection,
        proposal: dict[str, Any],
        actor: str,
        *,
        final: bool,
        acknowledge: bool,
    ) -> None:
        current_assets, current_relationships = self._graph(connection, proposal["utility_vertical"])
        current = self._baseline(connection, proposal["utility_vertical"], current_assets, current_relationships)
        operations = self._operations(connection, proposal["proposal_id"], proposal["proposal_version"])
        qa = self._comparison_from_connection(connection, proposal, "proposed_edit_qa_comparisons", one=True)
        traces = self._comparison_from_connection(connection, proposal, "proposed_edit_trace_comparisons", one=False)
        blockers = []
        if proposal["validation_status"] != "passed":
            blockers.append("validation has not passed")
        if proposal["analysis_status"] != "complete":
            blockers.append("analysis is incomplete")
        if current["baseline_fingerprint"] != proposal["baseline_fingerprint"]:
            blockers.append("the proposal baseline is stale")
        if not operations:
            blockers.append("the operation list is empty")
        if not qa:
            blockers.append("the QA comparison is missing")
        if proposal["trace_type"] and not traces:
            blockers.append("a required trace comparison is missing")
        if final and actor == proposal["created_by"] and actor != "synthetic_demo":
            blockers.append("the proposal author cannot be the final approver")
        if final and qa and qa.get("proposed_blocker_count", 0) > qa.get("baseline_blocker_count", 0) and not acknowledge:
            blockers.append("new blockers require explicit acknowledgement")
        if blockers:
            raise ProposedEditError("Approval prerequisites failed: " + "; ".join(blockers) + ".", 409)

    def _latest_result(
        self,
        vertical: str,
        proposal_id: str,
        table: str,
        order_field: str,
        json_fields: tuple[str, ...],
    ) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            row = connection.execute(
                f"""SELECT * FROM {table} WHERE proposal_id = ? AND proposal_version = ?
                ORDER BY {order_field} DESC LIMIT 1""",
                (proposal_id, proposal["proposal_version"]),
            ).fetchone()
            if not row:
                raise ProposedEditError("Requested proposal evidence is not available.", 404)
            result = dict(row)
            for field in json_fields:
                result[field] = _loads(result[field], [] if field.endswith(("errors_json", "warnings_json")) else {})
            return result

    def _comparison(self, vertical: str, proposal_id: str, table: str, *, one: bool) -> Any:
        self._vertical(vertical)
        with self.connect() as connection:
            proposal = self._require(connection, vertical, proposal_id)
            result = self._comparison_from_connection(connection, proposal, table, one=one)
            if one and not result:
                raise ProposedEditError("Requested proposal comparison is not available.", 404)
            return result

    @staticmethod
    def _comparison_from_connection(
        connection: sqlite3.Connection,
        proposal: dict[str, Any],
        table: str,
        *,
        one: bool,
    ) -> Any:
        rows = connection.execute(
            f"""SELECT result_json FROM {table}
            WHERE proposal_id = ? AND proposal_version = ? ORDER BY created_at, comparison_id""",
            (proposal["proposal_id"], proposal["proposal_version"]),
        ).fetchall()
        values = [_loads(row["result_json"], {}) for row in rows]
        return values[-1] if one and values else {} if one else values

    def _detail(self, connection: sqlite3.Connection, proposal: dict[str, Any]) -> dict[str, Any]:
        versions = connection.execute(
            """SELECT proposal_version, status, proposal_fingerprint, created_at
            FROM proposed_edit_proposals WHERE proposal_id = ? ORDER BY proposal_version""",
            (proposal["proposal_id"],),
        ).fetchall()
        result = self._safe_proposal(proposal)
        result.update({
            "operations": self._operations(connection, proposal["proposal_id"], proposal["proposal_version"]),
            "versions": [dict(row) for row in versions],
            "qa_comparison": self._comparison_from_connection(
                connection, proposal, "proposed_edit_qa_comparisons", one=True,
            ),
            "trace_comparisons": self._comparison_from_connection(
                connection, proposal, "proposed_edit_trace_comparisons", one=False,
            ),
            "impact_summary": _loads(proposal["impact_summary_json"], {}),
            "reviews": [dict(row) for row in connection.execute(
                """SELECT review_id, reviewer, reviewer_role, action, decision, notes, created_at
                FROM proposed_edit_reviews WHERE proposal_id = ? AND proposal_version = ?
                ORDER BY created_at""",
                (proposal["proposal_id"], proposal["proposal_version"]),
            ).fetchall()],
            "history": [
                self._safe_history(dict(row)) for row in connection.execute(
                    """SELECT * FROM proposed_edit_history
                    WHERE proposal_id = ? AND proposal_version = ? ORDER BY created_at, history_id""",
                    (proposal["proposal_id"], proposal["proposal_version"]),
                ).fetchall()
            ],
            "disclaimer": engine.DISCLAIMER,
        })
        return result

    @staticmethod
    def _safe_proposal(row: dict[str, Any]) -> dict[str, Any]:
        excluded = {
            "source_issue_group_ids_json", "source_trace_run_ids_json", "impact_summary_json",
            "canonical_asset_dataset_fingerprint", "canonical_relationship_dataset_fingerprint",
            "qa_run_fingerprint", "qa_calibration_fingerprint",
        }
        result = {key: value for key, value in row.items() if key not in excluded}
        result["source_issue_group_ids"] = _loads(row.get("source_issue_group_ids_json"), [])
        result["source_trace_run_ids"] = _loads(row.get("source_trace_run_ids_json"), [])
        result["locked"] = bool(result.get("locked"))
        result["approved_not_implemented"] = result.get("approval_status") == "approved"
        result["implementation_status"] = "not_implemented"
        return result

    @staticmethod
    def _safe_operation(row: dict[str, Any]) -> dict[str, Any]:
        mapping = {
            "prior_value_json": ("prior_value", None),
            "proposed_value_json": ("proposed_value", None),
            "prior_values_json": ("prior_values", {}),
            "proposed_values_json": ("proposed_values", {}),
            "source_issue_group_ids_json": ("source_issue_group_ids", []),
            "source_trace_run_ids_json": ("source_trace_run_ids", []),
            "source_trace_calibration_ids_json": ("source_trace_calibration_ids", []),
            "validation_errors_json": ("validation_errors", []),
            "validation_warnings_json": ("validation_warnings", []),
        }
        result = {key: value for key, value in row.items() if key not in mapping}
        for source, (target, fallback) in mapping.items():
            result[target] = _loads(row.get(source), fallback)
        result["provisional"] = bool(result.get("provisional"))
        return result

    @staticmethod
    def _safe_history(row: dict[str, Any]) -> dict[str, Any]:
        row["prior_value"] = _loads(row.pop("prior_value_json"), {})
        row["new_value"] = _loads(row.pop("new_value_json"), {})
        return row

    def _operations(self, connection: sqlite3.Connection, proposal_id: str, version: int) -> list[dict[str, Any]]:
        return [
            self._safe_operation(dict(row))
            for row in connection.execute(
                """SELECT * FROM proposed_edit_operations
                WHERE proposal_id = ? AND proposal_version = ? ORDER BY sequence""",
                (proposal_id, version),
            ).fetchall()
        ]

    def _graph(self, connection: sqlite3.Connection, vertical: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        assets = [
            _json_row(dict(row), ("source_attributes_json", "canonical_attributes_json", "geometry_summary_json", "evidence_json"))
            for row in connection.execute(
                "SELECT * FROM canonical_utility_assets WHERE utility_vertical = ? ORDER BY asset_id",
                (vertical,),
            ).fetchall()
        ]
        asset_ids = {item["asset_id"] for item in assets}
        relationships = [
            _json_row(dict(row), ("evidence_json",))
            for row in connection.execute(
                "SELECT * FROM utility_asset_relationships ORDER BY relationship_id",
            ).fetchall()
            if row["from_asset_id"] in asset_ids or row["to_asset_id"] in asset_ids
        ]
        return assets, relationships

    @staticmethod
    def _baseline(
        connection: sqlite3.Connection,
        vertical: str,
        assets: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        qa = connection.execute(
            """SELECT run_fingerprint FROM connectivity_qa_runs
            WHERE utility_vertical = ? ORDER BY started_at DESC LIMIT 1""",
            (vertical,),
        ).fetchone()
        calibration = connection.execute(
            """SELECT input_fingerprint FROM connectivity_qa_calibration_runs
            WHERE utility_vertical = ? ORDER BY started_at DESC LIMIT 1""",
            (vertical,),
        ).fetchone()
        return engine.baseline_snapshot(
            vertical, assets, relationships,
            qa["run_fingerprint"] if qa else stable_fingerprint("no-qa", vertical),
            calibration["input_fingerprint"] if calibration else stable_fingerprint("no-calibration", vertical),
        )

    def _row(self, connection: sqlite3.Connection, vertical: str, proposal_id: str) -> dict[str, Any] | None:
        row = connection.execute(
            """SELECT * FROM proposed_edit_proposals
            WHERE utility_vertical = ? AND proposal_id = ?
            ORDER BY proposal_version DESC LIMIT 1""",
            (vertical, proposal_id),
        ).fetchone()
        return dict(row) if row else None

    def _require(self, connection: sqlite3.Connection, vertical: str, proposal_id: str) -> dict[str, Any]:
        row = self._row(connection, vertical, proposal_id)
        if not row:
            raise ProposedEditError("Proposed edit not found.", 404)
        return row

    @staticmethod
    def _require_version(connection: sqlite3.Connection, proposal_id: str, version: int) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM proposed_edit_proposals WHERE proposal_id = ? AND proposal_version = ?",
            (proposal_id, version),
        ).fetchone()
        if not row:
            raise ProposedEditError("Proposed edit version not found.", 404)
        return dict(row)

    def _require_editable(self, connection: sqlite3.Connection, vertical: str, proposal_id: str) -> dict[str, Any]:
        proposal = self._require(connection, vertical, proposal_id)
        if proposal["locked"] or proposal["status"] not in engine.EDITABLE_STATES:
            raise ProposedEditError("This proposal version is locked; create a new version to change operations.", 409)
        return proposal

    @staticmethod
    def _update_proposal(connection: sqlite3.Connection, proposal: dict[str, Any], fields: dict[str, Any]) -> None:
        if not fields:
            return
        allowed = {
            "status", "proposal_fingerprint", "version_fingerprint", "overlay_fingerprint",
            "analysis_fingerprint", "validation_status", "analysis_status", "review_status",
            "approval_status", "implementation_readiness", "impact_summary_json", "submitted_by",
            "submitted_at", "reviewed_by", "reviewed_at", "approved_by", "approved_at",
            "rejection_reason", "superseded_by", "locked", "updated_at",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ProposedEditError(f"Unsupported proposal update: {sorted(unknown)[0]}.")
        values = dict(fields)
        values.setdefault("updated_at", intake_registry_service.utc_now())
        assignments = ", ".join(f"{key} = ?" for key in values)
        connection.execute(
            f"""UPDATE proposed_edit_proposals SET {assignments}
            WHERE proposal_id = ? AND proposal_version = ?""",
            (*values.values(), proposal["proposal_id"], proposal["proposal_version"]),
        )

    def _invalidate(self, connection: sqlite3.Connection, proposal: dict[str, Any], reason: str) -> None:
        self._update_proposal(connection, proposal, {
            "status": "draft", "validation_status": "not_evaluated", "analysis_status": "not_started",
            "implementation_readiness": "not_evaluated", "proposal_fingerprint": "",
            "overlay_fingerprint": "", "analysis_fingerprint": "", "impact_summary_json": "{}",
        })
        self._history(
            connection, proposal["proposal_id"], proposal["proposal_version"], "", "analysis_invalidated",
            {}, {"reason": reason}, "system", "proposal_service", reason,
        )

    @staticmethod
    def _history(
        connection: sqlite3.Connection,
        proposal_id: str,
        version: int,
        operation_id: str,
        action: str,
        prior: Any,
        new: Any,
        actor_type: str,
        actor: str,
        reason: str,
    ) -> None:
        now = intake_registry_service.utc_now()
        history_id = stable_id("proposal-history", proposal_id, version, operation_id, action, now, str(uuid.uuid4()))
        connection.execute(
            """INSERT INTO proposed_edit_history
            (history_id, proposal_id, proposal_version, operation_id, action, prior_value_json,
             new_value_json, actor_type, actor, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                history_id, proposal_id, version, operation_id, action, _dump(prior), _dump(new),
                actor_type[:50], actor[:100], reason[:1000], now,
            ),
        )

    @staticmethod
    def _vertical(vertical: str) -> None:
        try:
            engine.validate_vertical(vertical)
        except ValueError as exc:
            raise ProposedEditError(str(exc), 404) from exc

    def _seed_scenarios(self, connection: sqlite3.Connection) -> None:
        if connection.execute(
            "SELECT 1 FROM proposed_edit_seed_versions WHERE version = ?",
            (engine.SCENARIO_VERSION,),
        ).fetchone():
            return
        config_path = Path(__file__).resolve().parents[4] / "config" / "proposed_edit_scenarios_v1.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for vertical in ("electric_distribution", "telecom_fiber"):
            assets, relationships = self._graph(connection, vertical)
            by_name = {item["canonical_name"]: item["asset_id"] for item in assets}
            for scenario in config[vertical]:
                proposal_id = stable_id("proposed-edit", vertical, scenario["scenario_code"], "synthetic_demo", [], [])
                if self._row(connection, vertical, proposal_id):
                    continue
                trace_start = by_name.get(scenario.get("trace_start_name", ""), "")
                proposal = self._insert_proposal(
                    connection, proposal_id, 1, vertical, scenario["proposal_type"],
                    scenario["title"], "Deterministic synthetic proposed-edit scenario.",
                    "synthetic_demo", scenario["scenario_code"], {
                        "trace_type": scenario.get("trace_type", ""),
                        "trace_start_asset_id": trace_start,
                    },
                )
                temporary: dict[str, str] = {}
                for sequence, source in enumerate(scenario["operations"], 1):
                    payload = self._resolve_scenario_operation(
                        proposal_id, sequence, source, by_name, relationships, temporary,
                    )
                    operation = self._normalize_operation(proposal, sequence, payload)
                    self._insert_operation(connection, operation, "synthetic_demo")
                self._history(
                    connection, proposal_id, 1, "", "synthetic_scenario_seeded", {},
                    {"scenario_code": scenario["scenario_code"]}, "system", "synthetic_demo",
                    "Synthetic portfolio scenario.",
                )
                validation = self._validate(connection, proposal, "synthetic_demo")
                if validation["status"] == "passed":
                    self._analyze(connection, self._require_version(connection, proposal_id, 1), "synthetic_demo", False)
                connection.commit()
        connection.execute(
            "INSERT INTO proposed_edit_seed_versions (version, applied_at) VALUES (?, ?)",
            (engine.SCENARIO_VERSION, intake_registry_service.utc_now()),
        )
        connection.commit()

    @staticmethod
    def _resolve_scenario_operation(
        proposal_id: str,
        sequence: int,
        source: dict[str, Any],
        by_name: dict[str, str],
        relationships: list[dict[str, Any]],
        temporary: dict[str, str],
    ) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in source.items()
            if key not in {
                "target_asset_name", "from_asset_name", "to_asset_name", "temporary_key",
                "from_temporary_key", "to_temporary_key", "target_relationship",
            }
        }
        if source.get("target_asset_name"):
            payload["target_asset_id"] = by_name.get(source["target_asset_name"], "")
        if source.get("from_asset_name"):
            payload["from_asset_id"] = by_name.get(source["from_asset_name"], "")
        if source.get("to_asset_name"):
            payload["to_asset_id"] = by_name.get(source["to_asset_name"], "")
        if source.get("temporary_key"):
            temporary_id = f"PROP-{proposal_id}-{sequence}"
            temporary[source["temporary_key"]] = temporary_id
            payload["new_asset_temporary_id"] = temporary_id
        if source.get("from_temporary_key"):
            payload["from_asset_id"] = temporary.get(source["from_temporary_key"], "")
        if source.get("to_temporary_key"):
            payload["to_asset_id"] = temporary.get(source["to_temporary_key"], "")
        target = source.get("target_relationship")
        if isinstance(target, dict):
            from_id = by_name.get(target.get("from_asset_name", ""), "")
            to_id = by_name.get(target.get("to_asset_name", ""), "")
            match = next(
                (
                    item["relationship_id"]
                    for item in relationships
                    if item["from_asset_id"] == from_id
                    and item["to_asset_id"] == to_id
                    and item["relationship_type"] == target.get("relationship_type")
                ),
                "",
            )
            payload["target_relationship_id"] = match
        return payload


def _loads(value: Any, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _json_row(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    for field in fields:
        row[field] = _loads(row.get(field), {})
    for field in ("is_synthetic", "provisional"):
        if field in row:
            row[field] = bool(row[field])
    return row


service = ProposedEditService()
