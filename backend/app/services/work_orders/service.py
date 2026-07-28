from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from app.services import intake_registry_service
from app.services.proposed_edits import engine as proposed_engine
from app.services.proposed_edits import service as proposed_edits
from app.services.utility_assets.domain import stable_fingerprint, stable_id

from . import engine


class WorkOrderError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


RECORD_TABLES = {
    "assignments": ("work_order_assignments", "assignment_id"),
    "phases": ("work_order_phases", "phase_id"),
    "steps": ("work_order_steps", "step_id"),
    "prerequisites": ("work_order_prerequisites", "prerequisite_id"),
    "inspections": ("work_order_inspections", "inspection_id"),
    "evidence": ("work_order_evidence", "evidence_id"),
}


class WorkOrderService:
    def connect(self) -> sqlite3.Connection:
        connection = proposed_edits.connect()
        self._initialize(connection)
        self._seed_scenarios(connection)
        return connection

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS utility_work_orders (
                work_order_id TEXT NOT NULL,
                work_order_version INTEGER NOT NULL,
                parent_version INTEGER,
                supersedes_version INTEGER,
                scenario_code TEXT NOT NULL DEFAULT '',
                work_order_number TEXT NOT NULL,
                utility_vertical TEXT NOT NULL,
                work_order_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                design_status TEXT NOT NULL,
                field_work_status TEXT NOT NULL,
                gis_implementation_status TEXT NOT NULL,
                inspection_status TEXT NOT NULL,
                qa_status TEXT NOT NULL,
                trace_status TEXT NOT NULL,
                review_status TEXT NOT NULL,
                closeout_status TEXT NOT NULL,
                readiness TEXT NOT NULL,
                closeout_readiness TEXT NOT NULL,
                linked_proposal_id TEXT NOT NULL DEFAULT '',
                linked_proposal_version INTEGER NOT NULL DEFAULT 0,
                proposal_fingerprint TEXT NOT NULL DEFAULT '',
                baseline_fingerprint TEXT NOT NULL DEFAULT '',
                baseline_current INTEGER NOT NULL DEFAULT 0,
                proposal_approved INTEGER NOT NULL DEFAULT 0,
                affected_asset_ids_json TEXT NOT NULL DEFAULT '[]',
                affected_relationship_ids_json TEXT NOT NULL DEFAULT '[]',
                service_area_reference TEXT NOT NULL DEFAULT '',
                work_area_summary TEXT NOT NULL DEFAULT '',
                requested_date TEXT NOT NULL DEFAULT '',
                target_start_date TEXT NOT NULL DEFAULT '',
                target_completion_date TEXT NOT NULL DEFAULT '',
                actual_start_date TEXT NOT NULL DEFAULT '',
                field_completion_date TEXT NOT NULL DEFAULT '',
                gis_recorded_date TEXT NOT NULL DEFAULT '',
                closeout_date TEXT NOT NULL DEFAULT '',
                requested_by TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL,
                current_owner TEXT NOT NULL DEFAULT '',
                final_approver TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at TEXT NOT NULL DEFAULT '',
                external_system TEXT NOT NULL DEFAULT '',
                external_work_order_id TEXT NOT NULL DEFAULT '',
                external_mapping_status TEXT NOT NULL DEFAULT 'adapter_required',
                external_job_status TEXT NOT NULL DEFAULT '',
                synchronization_status TEXT NOT NULL DEFAULT 'not_connected',
                synchronization_direction TEXT NOT NULL DEFAULT '',
                last_synchronized_at TEXT NOT NULL DEFAULT '',
                external_version TEXT NOT NULL DEFAULT '',
                external_transaction_id TEXT NOT NULL DEFAULT '',
                adapter_required INTEGER NOT NULL DEFAULT 1,
                implementation_confirmation_status TEXT NOT NULL DEFAULT 'not_started',
                sensitivity TEXT NOT NULL DEFAULT 'internal',
                notes TEXT NOT NULL DEFAULT '',
                version_fingerprint TEXT NOT NULL DEFAULT '',
                release_fingerprint TEXT NOT NULL DEFAULT '',
                locked INTEGER NOT NULL DEFAULT 0,
                is_synthetic INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (work_order_id, work_order_version)
            );
            CREATE INDEX IF NOT EXISTS idx_work_order_list
                ON utility_work_orders(utility_vertical, updated_at DESC);

            CREATE TABLE IF NOT EXISTS work_order_assignments (
                assignment_id TEXT NOT NULL, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                role TEXT NOT NULL, status TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (work_order_id, work_order_version, assignment_id)
            );
            CREATE TABLE IF NOT EXISTS work_order_phases (
                phase_id TEXT NOT NULL, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, sequence INTEGER NOT NULL,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (work_order_id, work_order_version, phase_id)
            );
            CREATE TABLE IF NOT EXISTS work_order_steps (
                step_id TEXT NOT NULL, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, sequence INTEGER NOT NULL,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (work_order_id, work_order_version, step_id)
            );
            CREATE TABLE IF NOT EXISTS work_order_prerequisites (
                prerequisite_id TEXT NOT NULL, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (work_order_id, work_order_version, prerequisite_id)
            );
            CREATE TABLE IF NOT EXISTS work_order_inspections (
                inspection_id TEXT NOT NULL, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (work_order_id, work_order_version, inspection_id)
            );
            CREATE TABLE IF NOT EXISTS work_order_evidence (
                evidence_id TEXT NOT NULL, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, sequence INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (work_order_id, work_order_version, evidence_id)
            );
            CREATE TABLE IF NOT EXISTS work_order_runs (
                run_id TEXT PRIMARY KEY, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                run_type TEXT NOT NULL, status TEXT NOT NULL, fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_work_order_runs
                ON work_order_runs(work_order_id, work_order_version, run_type, created_at DESC);
            CREATE TABLE IF NOT EXISTS work_order_history (
                history_id TEXT PRIMARY KEY, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                phase_id TEXT NOT NULL DEFAULT '', step_id TEXT NOT NULL DEFAULT '',
                inspection_id TEXT NOT NULL DEFAULT '', evidence_id TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL, prior_value_json TEXT NOT NULL, new_value_json TEXT NOT NULL,
                actor_type TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS work_order_packages (
                package_id TEXT PRIMARY KEY, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                fingerprint TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(work_order_id, work_order_version)
            );
            CREATE TABLE IF NOT EXISTS work_order_receipts (
                receipt_id TEXT PRIMARY KEY, work_order_id TEXT NOT NULL, work_order_version INTEGER NOT NULL,
                fingerprint TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(work_order_id, work_order_version)
            );
            CREATE TABLE IF NOT EXISTS work_order_seed_versions (
                version TEXT PRIMARY KEY, applied_at TEXT NOT NULL
            );
            """
        )
        connection.commit()

    def types(self, vertical: str | None = None) -> dict[str, Any]:
        try:
            return engine.catalog(vertical)
        except ValueError as exc:
            raise WorkOrderError(str(exc), 404) from exc

    @staticmethod
    def roles() -> dict[str, Any]:
        return {"roles": list(engine.ROLES), "synthetic_identities_only": True}

    @staticmethod
    def prerequisite_types() -> dict[str, Any]:
        return {"prerequisite_types": list(engine.PREREQUISITE_TYPES)}

    @staticmethod
    def inspection_types() -> dict[str, Any]:
        return {"inspection_types": list(engine.INSPECTION_TYPES)}

    @staticmethod
    def evidence_types() -> dict[str, Any]:
        return {"evidence_types": list(engine.EVIDENCE_TYPES), "attachment_storage": "metadata_only"}

    def list_work_orders(self, vertical: str, filters: dict[str, Any]) -> dict[str, Any]:
        self._vertical(vertical)
        clauses = [
            "w.utility_vertical = ?",
            """w.work_order_version = (
                SELECT MAX(v.work_order_version) FROM utility_work_orders v
                WHERE v.work_order_id = w.work_order_id
            )""",
        ]
        values: list[Any] = [vertical]
        fields = {
            "status": "overall_status", "work_order_type": "work_order_type", "priority": "priority",
            "readiness": "readiness", "qa_status": "qa_status", "trace_status": "trace_status",
            "closeout_status": "closeout_status", "external_mapping_status": "external_mapping_status",
        }
        for key, column in fields.items():
            if filters.get(key):
                clauses.append(f"w.{column} = ?")
                values.append(str(filters[key]))
        if filters.get("proposal"):
            clauses.append("w.linked_proposal_id = ?")
            values.append(str(filters["proposal"]))
        if filters.get("affected_asset"):
            clauses.append("w.affected_asset_ids_json LIKE ?")
            values.append(f'%"{str(filters["affected_asset"])}"%')
        if filters.get("search"):
            clauses.append("(LOWER(w.title) LIKE ? OR LOWER(w.work_order_number) LIKE ? OR LOWER(w.scenario_code) LIKE ?)")
            term = f"%{str(filters['search']).lower()}%"
            values.extend((term, term, term))
        limit = max(1, min(int(filters.get("limit", 100)), 500))
        offset = max(0, int(filters.get("offset", 0)))
        where = " AND ".join(clauses)
        with self.connect() as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM utility_work_orders w WHERE {where}", values).fetchone()[0])
            rows = connection.execute(
                f"""SELECT w.* FROM utility_work_orders w WHERE {where}
                ORDER BY w.scenario_code, w.updated_at DESC LIMIT ? OFFSET ?""",
                (*values, limit, offset),
            ).fetchall()
        return {
            "items": [self._safe_work_order(dict(row)) for row in rows],
            "pagination": {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total},
            "disclaimer": engine.DISCLAIMER,
        }

    def create(self, vertical: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._vertical(vertical)
        allowed = {
            "proposal_id", "proposal_version", "work_order_type", "title", "summary", "priority",
            "created_by", "requested_by", "current_owner", "target_start_date",
            "target_completion_date", "work_area_summary", "notes",
        }
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed)
            work_order_type = engine.validate_type(vertical, payload.get("work_order_type"))
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        title = str(payload.get("title", "")).strip()[:180]
        actor = str(payload.get("created_by", "")).strip()[:100]
        if not title or not actor:
            raise WorkOrderError("Work-order title and creator are required.")
        proposal_id = str(payload.get("proposal_id", "")).strip()[:120]
        with self.connect() as connection:
            proposal = self._proposal(connection, vertical, proposal_id, payload.get("proposal_version"))
            if work_order_type != "manual_investigation":
                if not proposal or proposal["approval_status"] != "approved":
                    raise WorkOrderError("Operational work orders require an approved Proposed Edit.", 409)
            elif proposal:
                raise WorkOrderError("Manual investigation work orders do not carry network-changing proposal operations.")
            work_order_id = stable_id("work-order", vertical, proposal_id or title, actor)
            existing = self._row(connection, vertical, work_order_id)
            if existing:
                return self._detail(connection, existing)
            row = self._new_row(
                vertical, work_order_id, 1, work_order_type, title, actor, payload,
                proposal=proposal, scenario_code="", synthetic=False,
            )
            self._insert(connection, row)
            operations = self._proposal_operations(connection, proposal)
            self._seed_records(connection, row, operations, invalid=False, blocked=False)
            self._refresh(connection, row)
            self._history(connection, row, "work_order_created", {}, {"status": "draft"}, actor, "")
            connection.commit()
            return self._detail(connection, self._require(connection, vertical, work_order_id))

    def work_order(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        self._vertical(vertical)
        with self.connect() as connection:
            return self._detail(connection, self._require(connection, vertical, work_order_id))

    def clone(self, vertical: str, work_order_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"created_by", "title"})
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        with self.connect() as connection:
            source = self._require(connection, vertical, work_order_id)
            actor = str(payload.get("created_by") or source["created_by"])[:100]
            title = str(payload.get("title") or f"Copy of {source['title']}")[:180]
            clone_id = stable_id("work-order-clone", work_order_id, source["work_order_version"], title, actor)
            existing = self._row(connection, vertical, clone_id)
            if existing:
                return self._detail(connection, existing)
            clone = dict(source)
            now = intake_registry_service.utc_now()
            clone.update({
                "work_order_id": clone_id, "work_order_version": 1, "scenario_code": "",
                "work_order_number": self._work_order_number(vertical, clone_id, False),
                "title": title, "overall_status": "draft", "review_status": "not_submitted",
                "closeout_status": "not_ready", "locked": 0, "created_by": actor,
                "approved_by": "", "approved_at": "", "release_fingerprint": "",
                "created_at": now, "updated_at": now,
            })
            self._insert(connection, clone)
            self._copy_records(connection, source, clone)
            self._refresh(connection, clone)
            self._history(connection, clone, "work_order_cloned", {}, {"source_work_order_id": work_order_id}, actor, "")
            connection.commit()
            return self._detail(connection, self._require(connection, vertical, clone_id))

    def new_version(self, vertical: str, work_order_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"actor", "reason"})
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        actor = str(payload.get("actor", "")).strip()[:100]
        reason = str(payload.get("reason", "")).strip()[:1000]
        if not actor or not reason:
            raise WorkOrderError("Actor and reason are required for a new work-order version.")
        with self.connect() as connection:
            source = self._require(connection, vertical, work_order_id)
            version = int(source["work_order_version"]) + 1
            clone = dict(source)
            now = intake_registry_service.utc_now()
            clone.update({
                "work_order_version": version, "parent_version": source["work_order_version"],
                "supersedes_version": source["work_order_version"], "overall_status": "planning",
                "review_status": "not_submitted", "closeout_status": "not_ready", "locked": 0,
                "approved_by": "", "approved_at": "", "release_fingerprint": "",
                "version_fingerprint": "", "created_by": actor, "created_at": now, "updated_at": now,
            })
            self._insert(connection, clone)
            self._copy_records(connection, source, clone)
            self._refresh(connection, clone)
            self._history(connection, clone, "work_order_version_created", {"version": source["work_order_version"]}, {"version": version}, actor, reason)
            connection.commit()
            return self._detail(connection, self._require(connection, vertical, work_order_id))

    def records(self, vertical: str, work_order_id: str, kind: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            return {"items": self._records(connection, row, kind), "work_order_id": work_order_id}

    def record(self, vertical: str, work_order_id: str, kind: str, record_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            return self._record(connection, row, kind, record_id)

    def add_record(self, vertical: str, work_order_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if kind not in RECORD_TABLES:
            raise WorkOrderError("Unsupported work-order record type.")
        allowed = {
            "assignments": {"role", "assignee", "assignment_status", "notes"},
            "steps": {"phase_code", "step_type", "title", "instructions", "affected_asset_ids", "affected_relationship_ids", "prerequisites", "expected_result", "validation_method", "assigned_role"},
            "prerequisites": {"prerequisite_type", "title", "description", "required", "status", "notes"},
            "inspections": {"inspection_type", "title", "required", "affected_asset_ids", "affected_relationship_ids", "expected_condition", "notes"},
            "evidence": {"step_id", "inspection_id", "evidence_type", "title", "summary", "source", "recorded_by", "sensitivity", "external_reference", "attachment_name", "attachment_type", "attachment_checksum", "safe_metadata", "review_status"},
        }
        if kind not in allowed:
            raise WorkOrderError("This record type is generated from the approved work-order definition.")
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed[kind])
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        with self.connect() as connection:
            row = self._require_editable(connection, vertical, work_order_id) if kind != "evidence" else self._require(connection, vertical, work_order_id)
            item = self._normalize_record(connection, row, kind, payload)
            self._write_record(connection, row, kind, item)
            self._refresh(connection, row)
            self._history(connection, row, f"{kind[:-1]}_added", {}, item, str(payload.get("recorded_by") or payload.get("assignee") or row["created_by"]), "")
            connection.commit()
            return item

    def update_assignment(
        self, vertical: str, work_order_id: str, assignment_id: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            engine.reject_unsafe(payload, allowed_keys={"assignee", "assignment_status", "notes"})
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        with self.connect() as connection:
            row = self._require_editable(connection, vertical, work_order_id)
            item = self._record(connection, row, "assignments", assignment_id)
            prior = dict(item)
            if payload.get("assignment_status") and payload["assignment_status"] not in {"assigned", "accepted", "in_progress", "completed", "declined", "reassigned", "removed"}:
                raise WorkOrderError("Unsupported assignment status.")
            item.update({key: value for key, value in payload.items() if value is not None})
            self._write_record(connection, row, "assignments", item)
            self._refresh(connection, row)
            self._history(connection, row, "assignment_updated", prior, item, str(payload.get("assignee") or row["created_by"]), "")
            connection.commit()
            return item

    def update_step(
        self, vertical: str, work_order_id: str, step_id: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = {
            "phase_code", "step_type", "title", "instructions", "affected_asset_ids",
            "affected_relationship_ids", "prerequisites", "expected_result",
            "validation_method", "assigned_role",
        }
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed)
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        with self.connect() as connection:
            row = self._require_editable(connection, vertical, work_order_id)
            item = self._record(connection, row, "steps", step_id)
            prior = dict(item)
            item.update(payload)
            self._write_record(connection, row, "steps", item)
            self._refresh(connection, row)
            self._history(connection, row, "step_updated", prior, item, row["created_by"], "")
            connection.commit()
            return item

    def delete_assignment(self, vertical: str, work_order_id: str, assignment_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require_editable(connection, vertical, work_order_id)
            item = self._record(connection, row, "assignments", assignment_id)
            table, key = RECORD_TABLES["assignments"]
            connection.execute(
                f"DELETE FROM {table} WHERE work_order_id = ? AND work_order_version = ? AND {key} = ?",
                (work_order_id, row["work_order_version"], assignment_id),
            )
            self._refresh(connection, row)
            self._history(connection, row, "assignment_removed", item, {}, row["created_by"], "")
            connection.commit()
            return {"removed": True, "assignment_id": assignment_id, "history_preserved": True}

    def complete_step(
        self, vertical: str, work_order_id: str, step_id: str, payload: dict[str, Any], *, exception: bool = False,
    ) -> dict[str, Any]:
        try:
            engine.reject_unsafe(payload, allowed_keys={"actor", "notes", "status"})
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        actor = str(payload.get("actor", "")).strip()[:100]
        if not actor:
            raise WorkOrderError("Actor is required.")
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            item = self._record(connection, row, "steps", step_id)
            prior = dict(item)
            item.update({
                "completion_status": "completed_with_exception" if exception else str(payload.get("status") or "completed"),
                "completed_by": actor, "completed_at": intake_registry_service.utc_now(),
                "completion_notes": str(payload.get("notes", ""))[:1000],
                "exception_status": "recorded" if exception else "none",
            })
            self._write_record(connection, row, "steps", item)
            self._history(connection, row, "step_exception_recorded" if exception else "step_completed", prior, item, actor, str(payload.get("notes", "")))
            connection.commit()
            return item

    def confirm_prerequisite(
        self, vertical: str, work_order_id: str, prerequisite_id: str, payload: dict[str, Any], *, waive: bool = False,
    ) -> dict[str, Any]:
        allowed = {"actor", "notes", "status", "evidence_reference", "reason"}
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed)
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        actor = str(payload.get("actor", "")).strip()[:100]
        reason = str(payload.get("reason") or payload.get("notes") or "").strip()[:1000]
        if not actor or (waive and not reason):
            raise WorkOrderError("Reviewer identity and reason are required to waive a prerequisite.")
        with self.connect() as connection:
            row = self._require_editable(connection, vertical, work_order_id)
            item = self._record(connection, row, "prerequisites", prerequisite_id)
            prior = dict(item)
            item.update({
                "status": "waived" if waive else str(payload.get("status") or "satisfied"),
                "confirmed_by": actor, "confirmed_at": intake_registry_service.utc_now(),
                "evidence_reference": str(payload.get("evidence_reference", ""))[:200],
                "notes": reason,
            })
            self._write_record(connection, row, "prerequisites", item)
            self._refresh(connection, row)
            self._history(connection, row, "prerequisite_waived" if waive else "prerequisite_confirmed", prior, item, actor, reason)
            connection.commit()
            return item

    def record_inspection(
        self, vertical: str, work_order_id: str, inspection_id: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = {"result", "inspector", "observed_condition", "evidence_ids", "notes"}
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed)
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        result = str(payload.get("result", ""))
        if result not in {"pass", "pass_with_conditions", "fail", "unable_to_verify", "not_applicable"}:
            raise WorkOrderError("Unsupported inspection result.")
        inspector = str(payload.get("inspector", "")).strip()[:100]
        if not inspector:
            raise WorkOrderError("Inspector identity is required.")
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            item = self._record(connection, row, "inspections", inspection_id)
            prior = dict(item)
            item.update({
                "result": result, "status": "passed" if result == "pass" else (
                    "passed_with_conditions" if result == "pass_with_conditions" else "failed"
                ),
                "inspector": inspector, "inspected_at": intake_registry_service.utc_now(),
                "observed_condition": str(payload.get("observed_condition", ""))[:1000],
                "evidence_ids": engine.string_list(payload.get("evidence_ids")),
                "notes": str(payload.get("notes", ""))[:1000],
            })
            self._write_record(connection, row, "inspections", item)
            self._history(connection, row, "inspection_recorded", prior, item, inspector, item["notes"])
            connection.commit()
            return item

    def readiness(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            result = self._readiness(connection, row)
            return {**result, "work_order_id": work_order_id}

    def closeout_readiness(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            result = self._closeout_readiness(connection, row)
            return {**result, "work_order_id": work_order_id}

    def transition(
        self, vertical: str, work_order_id: str, action: str, payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"actor", "reviewer", "notes", "reason"})
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        actor = str(payload.get("actor") or payload.get("reviewer") or "").strip()[:100]
        notes = str(payload.get("notes") or payload.get("reason") or "").strip()[:1000]
        notes_required = {
            "request-revision", "approve-release", "reject", "defer", "pause-work", "cancel",
            "suspend", "supersede", "approve-closeout", "reopen",
        }
        if not actor or (action in notes_required and not notes):
            raise WorkOrderError("Actor identity and decision notes are required for this action.")
        transitions: dict[str, tuple[set[str], dict[str, Any]]] = {
            "submit": ({"draft", "planning", "ready_for_review"}, {"overall_status": "ready_for_review", "review_status": "submitted"}),
            "start-review": ({"ready_for_review"}, {"overall_status": "under_review", "review_status": "under_review"}),
            "request-revision": ({"under_review"}, {"overall_status": "planning", "design_status": "revision_required", "review_status": "revision_requested"}),
            "approve-release": ({"under_review"}, {"overall_status": "approved_for_release", "design_status": "approved", "review_status": "approved", "approved_by": actor, "approved_at": intake_registry_service.utc_now()}),
            "reject": ({"under_review", "ready_for_review"}, {"overall_status": "rejected", "review_status": "rejected", "locked": 1}),
            "defer": ({"draft", "planning", "ready_for_review", "under_review"}, {"overall_status": "deferred", "review_status": "deferred"}),
            "release": ({"approved_for_release"}, {"overall_status": "released", "field_work_status": "released", "locked": 1}),
            "start-work": ({"released"}, {"overall_status": "in_progress", "field_work_status": "in_progress", "actual_start_date": intake_registry_service.utc_now()}),
            "pause-work": ({"in_progress"}, {"field_work_status": "paused"}),
            "resume-work": ({"in_progress"}, {"field_work_status": "in_progress"}),
            "field-complete": ({"in_progress"}, {"overall_status": "field_complete", "field_work_status": "completed", "field_completion_date": intake_registry_service.utc_now()}),
            "gis-update": ({"field_complete", "gis_update_pending", "in_progress"}, {"overall_status": "gis_update_pending", "gis_implementation_status": "pending"}),
            "submit-closeout": ({"post_work_validation", "gis_update_recorded", "field_complete"}, {"overall_status": "closeout_review", "closeout_status": "under_review"}),
            "approve-closeout": ({"closeout_review"}, {"overall_status": "closed", "closeout_status": "closed", "closeout_date": intake_registry_service.utc_now(), "final_approver": actor, "locked": 1}),
            "reopen": ({"closed"}, {"overall_status": "planning", "closeout_status": "reopened", "locked": 0}),
            "suspend": (set(engine.OVERALL_STATUSES) - {"closed", "archived"}, {"overall_status": "suspended"}),
            "cancel": (set(engine.OVERALL_STATUSES) - {"closed", "archived"}, {"overall_status": "cancelled", "field_work_status": "cancelled", "locked": 1}),
            "supersede": (set(engine.OVERALL_STATUSES) - {"closed", "archived"}, {"overall_status": "superseded", "locked": 1}),
        }
        if action not in transitions:
            raise WorkOrderError("Unsupported work-order action.")
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            allowed_states, changes = transitions[action]
            if row["overall_status"] not in allowed_states:
                raise WorkOrderError(f"Action {action} is not allowed from {row['overall_status']}.", 409)
            if action == "approve-release":
                preflight = self._readiness(connection, {**row, "review_status": "approved"})
                if preflight["blockers"]:
                    raise WorkOrderError("Release approval is blocked: " + " ".join(preflight["blockers"]), 409)
            if action == "release":
                preflight = self._readiness(connection, row)
                if preflight["state"] != "ready_for_release":
                    raise WorkOrderError("Work order is not ready for release.", 409)
            if action == "submit-closeout":
                closeout = self._closeout_readiness(connection, row)
                if closeout["state"] != "ready":
                    raise WorkOrderError("Closeout is blocked: " + " ".join(closeout["blockers"]), 409)
            prior = {key: row.get(key) for key in changes}
            self._update(connection, row, changes)
            current = self._require(connection, vertical, work_order_id)
            self._refresh(connection, current)
            if action in {"approve-release", "release"}:
                detail = self._detail(connection, self._require(connection, vertical, work_order_id))
                self._update(connection, current, {"release_fingerprint": engine.release_fingerprint(detail, self._record_map(detail))})
            self._history(connection, row, action.replace("-", "_"), prior, changes, actor, notes)
            connection.commit()
            if action == "approve-closeout":
                self._create_receipt(connection, self._require(connection, vertical, work_order_id))
                connection.commit()
            return self._detail(connection, self._require(connection, vertical, work_order_id))

    def record_implementation(
        self, vertical: str, work_order_id: str, payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = payload or {}
        allowed = {
            "completed_operation_ids", "skipped_operation_ids", "exception_operation_ids",
            "recorded_by", "notes", "status", "external_reference",
        }
        try:
            engine.reject_unsafe(payload, allowed_keys=allowed)
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            if row["overall_status"] not in {"released", "in_progress", "field_complete", "gis_update_pending", "gis_update_recorded"}:
                raise WorkOrderError("Release is required before implementation can be recorded.", 409)
            result = self._record_implementation(connection, row, payload)
            connection.commit()
            return result

    def implementation(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        return self._latest_run(vertical, work_order_id, "implementation")

    def run_conformance(self, vertical: str, work_order_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            result = self._run_conformance(connection, row)
            connection.commit()
            return result

    def conformance(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        return self._latest_run(vertical, work_order_id, "conformance")

    def run_post_qa(self, vertical: str, work_order_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            result = self._run_post_qa(connection, row)
            connection.commit()
            return result

    def post_qa(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        return self._latest_run(vertical, work_order_id, "post_qa")

    def run_post_traces(self, vertical: str, work_order_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            result = self._run_post_traces(connection, row)
            connection.commit()
            return result

    def post_traces(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            return {"items": self._runs(connection, row, "post_trace"), "disclaimer": engine.IMPLEMENTATION_NOTICE}

    def validation_summary(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            return {
                "work_order_id": work_order_id,
                "conformance": self._latest_run_connection(connection, row, "conformance"),
                "post_work_qa": self._latest_run_connection(connection, row, "post_qa"),
                "post_work_traces": self._runs(connection, row, "post_trace"),
                "closeout_readiness": self._closeout_readiness(connection, row),
                "three_state_comparison": self._three_state(connection, row),
                "notice": engine.IMPLEMENTATION_NOTICE,
            }

    def safe_summary(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        detail = self.work_order(vertical, work_order_id)
        return {
            "work_order": {key: value for key, value in detail.items() if key not in {"notes"}},
            "three_state_comparison": detail["three_state_comparison"],
            "executable": False,
            "disclaimer": engine.DISCLAIMER,
        }

    def create_package(self, vertical: str, work_order_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        try:
            engine.reject_unsafe(payload, allowed_keys={"actor", "notes"})
        except ValueError as exc:
            raise WorkOrderError(str(exc)) from exc
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            if row["review_status"] != "approved" and row["overall_status"] not in {"released", "in_progress", "field_complete", "gis_update_recorded", "post_work_validation", "closeout_review", "closed"}:
                raise WorkOrderError("Release approval is required before a job package can be generated.", 409)
            detail = self._detail(connection, row)
            package = engine.package_payload(
                detail,
                self._record_map(detail),
                {"approved_by": row["approved_by"], "approved_at": row["approved_at"], "release_fingerprint": row["release_fingerprint"]},
            )
            package_id = stable_id("work-order-package", work_order_id, row["work_order_version"], row["version_fingerprint"])
            package["package_id"] = package_id
            package["created_at"] = intake_registry_service.utc_now()
            fingerprint = stable_fingerprint(package)
            connection.execute(
                """INSERT INTO work_order_packages
                (package_id, work_order_id, work_order_version, fingerprint, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(work_order_id, work_order_version) DO UPDATE SET
                    package_id=excluded.package_id, fingerprint=excluded.fingerprint,
                    payload_json=excluded.payload_json, created_at=excluded.created_at""",
                (package_id, work_order_id, row["work_order_version"], fingerprint, _dump(package), package["created_at"]),
            )
            self._history(connection, row, "job_package_created", {}, {"package_id": package_id}, str(payload.get("actor") or row["approved_by"]), str(payload.get("notes", "")))
            connection.commit()
            return package

    def package(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            value = connection.execute(
                "SELECT payload_json FROM work_order_packages WHERE work_order_id=? AND work_order_version=?",
                (work_order_id, row["work_order_version"]),
            ).fetchone()
            if not value:
                raise WorkOrderError("Job package has not been generated.", 404)
            return _loads(value["payload_json"], {})

    def receipt(self, vertical: str, work_order_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            value = connection.execute(
                "SELECT payload_json FROM work_order_receipts WHERE work_order_id=? AND work_order_version=?",
                (work_order_id, row["work_order_version"]),
            ).fetchone()
            if not value:
                raise WorkOrderError("Completion receipt is available only after approved closeout.", 404)
            return _loads(value["payload_json"], {})

    def _record_implementation(self, connection: sqlite3.Connection, row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        proposal = self._proposal(connection, row["utility_vertical"], row["linked_proposal_id"], row["linked_proposal_version"])
        operations = self._proposal_operations(connection, proposal)
        expected = [item["operation_id"] for item in operations]
        completed = engine.string_list(payload.get("completed_operation_ids")) or expected
        skipped = engine.string_list(payload.get("skipped_operation_ids"))
        exceptions = engine.string_list(payload.get("exception_operation_ids"))
        selected = [item for item in operations if item["operation_id"] in set(completed)]
        assets, relationships = proposed_edits._graph(connection, row["utility_vertical"])
        overlay = proposed_engine.apply_overlay(row["utility_vertical"], assets, relationships, selected)
        now = intake_registry_service.utc_now()
        record = {
            "implementation_record_id": stable_id("work-order-implementation", row["work_order_id"], row["work_order_version"], completed, skipped, exceptions),
            "work_order_id": row["work_order_id"], "proposal_id": row["linked_proposal_id"],
            "proposal_version": row["linked_proposal_version"], "implementation_type": "synthetic_overlay",
            "status": "simulated_overlay_only", "operation_results": [
                {"operation_id": item, "result": "completed" if item in completed else "not_recorded"}
                for item in expected
            ],
            "completed_operation_ids": completed, "skipped_operation_ids": skipped,
            "exception_operation_ids": exceptions, "external_system": "",
            "external_reference": str(payload.get("external_reference", ""))[:200],
            "recorded_by": str(payload.get("recorded_by") or "Synthetic GIS Technician")[:100],
            "recorded_at": now, "verified_by": "", "verified_at": "",
            "notes": str(payload.get("notes", ""))[:1000],
            "overlay_fingerprint": overlay["overlay_fingerprint"],
            "overlay_summary": {
                key: overlay["summary"][key] for key in (
                    "assets_added", "assets_modified", "assets_removed", "relationships_added",
                    "relationships_modified", "relationships_removed", "changed_asset_ids",
                    "changed_relationship_ids",
                )
            },
            "notice": engine.IMPLEMENTATION_NOTICE, "created_at": now,
        }
        self._store_run(connection, row, "implementation", record, record["status"], engine.implementation_fingerprint(record), record["implementation_record_id"])
        self._update(connection, row, {
            "overall_status": "gis_update_recorded", "field_work_status": "completed",
            "gis_implementation_status": "recorded_in_overlay",
            "implementation_confirmation_status": "simulated_overlay_only",
            "field_completion_date": row["field_completion_date"] or now, "gis_recorded_date": now,
        })
        self._history(connection, row, "implementation_recorded", {}, {"implementation_record_id": record["implementation_record_id"]}, record["recorded_by"], record["notes"])
        return record

    def _run_conformance(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        implementation = self._latest_run_connection(connection, row, "implementation")
        if not implementation:
            raise WorkOrderError("Record implementation before running conformance.", 409)
        proposal = self._proposal(connection, row["utility_vertical"], row["linked_proposal_id"], row["linked_proposal_version"])
        result = engine.conformance(self._proposal_operations(connection, proposal), implementation)
        now = intake_registry_service.utc_now()
        result.update({
            "conformance_run_id": stable_id("work-order-conformance", row["work_order_id"], row["work_order_version"], implementation["implementation_record_id"]),
            "work_order_id": row["work_order_id"], "proposal_id": row["linked_proposal_id"],
            "proposal_version": row["linked_proposal_version"], "proposal_fingerprint": row["proposal_fingerprint"],
            "implementation_record_id": implementation["implementation_record_id"],
            "started_at": now, "completed_at": now, "created_at": now,
        })
        self._store_run(connection, row, "conformance", result, result["status"], stable_fingerprint(result), result["conformance_run_id"])
        self._history(connection, row, "implementation_conformance_run", {}, {"status": result["status"]}, "system", "")
        return result

    def _run_post_qa(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        implementation = self._latest_run_connection(connection, row, "implementation")
        if not implementation:
            raise WorkOrderError("Record implementation before post-work QA.", 409)
        proposal = self._proposal(connection, row["utility_vertical"], row["linked_proposal_id"], row["linked_proposal_version"])
        operations = self._proposal_operations(connection, proposal)
        completed = set(implementation["completed_operation_ids"])
        selected = [item for item in operations if item["operation_id"] in completed]
        assets, relationships = proposed_edits._graph(connection, row["utility_vertical"])
        overlay = proposed_engine.apply_overlay(row["utility_vertical"], assets, relationships, selected)
        baseline = proposed_engine.run_proposed_qa(row["utility_vertical"], assets, relationships, f"{row['work_order_id']}:baseline")
        implemented = proposed_engine.run_proposed_qa(row["utility_vertical"], overlay["assets"], overlay["relationships"], f"{row['work_order_id']}:implemented")
        comparison = proposed_engine.compare_qa(baseline, implemented, row["work_order_id"])
        status = "failed" if comparison["new_issue_group_ids"] or comparison["worsened_issue_group_ids"] else (
            "passed_with_warnings" if comparison["proposed_warning_count"] else "passed"
        )
        now = intake_registry_service.utc_now()
        result = {
            "work_order_post_qa_run_id": stable_id("work-order-post-qa", row["work_order_id"], row["work_order_version"], implementation["implementation_record_id"]),
            "work_order_id": row["work_order_id"], "implementation_record_id": implementation["implementation_record_id"],
            "baseline_qa_run_id": baseline["proposal_qa_run_id"],
            "approved_proposal_qa_run_id": row["linked_proposal_id"],
            "implemented_overlay_fingerprint": overlay["overlay_fingerprint"],
            "qa_rule_version": proposed_engine.QA_RULE_VERSION,
            "qa_calibration_version": proposed_engine.CALIBRATION_RULE_VERSION,
            "status": status, "comparison": comparison,
            "raw_findings": implemented["findings"], "actionable_groups": implemented["groups"],
            "blockers": comparison["new_issue_group_ids"], "trace_stopping_groups": [],
            "warnings": comparison["unchanged_issue_group_ids"], "started_at": now,
            "completed_at": now, "created_at": now,
        }
        self._store_run(connection, row, "post_qa", result, status, stable_fingerprint(result), result["work_order_post_qa_run_id"])
        self._update(connection, row, {"qa_status": status, "overall_status": "post_work_validation"})
        self._history(connection, row, "post_work_qa_run", {}, {"status": status}, "system", "")
        return result

    def _run_post_traces(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        implementation = self._latest_run_connection(connection, row, "implementation")
        if not implementation:
            raise WorkOrderError("Record implementation before post-work traces.", 409)
        proposal = self._proposal(connection, row["utility_vertical"], row["linked_proposal_id"], row["linked_proposal_version"])
        if not proposal or not proposal.get("trace_type") or not proposal.get("trace_start_asset_id"):
            self._update(connection, row, {"trace_status": "not_required"})
            return {"items": [], "status": "not_required"}
        operations = self._proposal_operations(connection, proposal)
        completed = set(implementation["completed_operation_ids"])
        selected = [item for item in operations if item["operation_id"] in completed]
        assets, relationships = proposed_edits._graph(connection, row["utility_vertical"])
        approved_overlay = proposed_engine.apply_overlay(row["utility_vertical"], assets, relationships, operations)
        implemented_overlay = proposed_engine.apply_overlay(row["utility_vertical"], assets, relationships, selected)
        baseline_groups = proposed_engine.run_proposed_qa(
            row["utility_vertical"], assets, relationships, f"{row['work_order_id']}:trace-baseline",
        )["groups"]
        approved_groups = proposed_engine.run_proposed_qa(
            row["utility_vertical"], approved_overlay["assets"], approved_overlay["relationships"],
            f"{row['work_order_id']}:trace-approved",
        )["groups"]
        implemented_groups = proposed_engine.run_proposed_qa(
            row["utility_vertical"], implemented_overlay["assets"], implemented_overlay["relationships"],
            f"{row['work_order_id']}:trace-implemented",
        )["groups"]
        baseline = proposed_engine.run_proposed_trace(
            row["utility_vertical"], assets, relationships, baseline_groups,
            proposal["trace_type"], proposal["trace_start_asset_id"], f"{row['work_order_id']}:baseline",
        )
        approved = proposed_engine.run_proposed_trace(
            row["utility_vertical"], approved_overlay["assets"], approved_overlay["relationships"],
            approved_groups, proposal["trace_type"], proposal["trace_start_asset_id"],
            f"{row['work_order_id']}:approved",
        )
        implemented = proposed_engine.run_proposed_trace(
            row["utility_vertical"], implemented_overlay["assets"], implemented_overlay["relationships"],
            implemented_groups, proposal["trace_type"], proposal["trace_start_asset_id"],
            f"{row['work_order_id']}:implemented",
        )
        comparison = proposed_engine.compare_trace(row["work_order_id"], row["scenario_code"] or "work-order", approved, implemented)
        status = "passed" if (
            comparison["result"] in {"unchanged", "improved"}
            and implemented.get("calibrated", {}).get("objective_reached")
            == approved.get("calibrated", {}).get("objective_reached")
        ) else "failed"
        now = intake_registry_service.utc_now()
        result = {
            "work_order_post_trace_run_id": stable_id("work-order-post-trace", row["work_order_id"], row["work_order_version"], implementation["implementation_record_id"], proposal["trace_type"]),
            "work_order_id": row["work_order_id"], "implementation_record_id": implementation["implementation_record_id"],
            "trace_type": proposal["trace_type"], "start_asset_id": proposal["trace_start_asset_id"],
            "target_asset_id": "", "baseline_trace_run_id": baseline["trace_run_id"],
            "proposal_trace_run_id": approved["trace_run_id"],
            "implemented_trace_run_id": implemented["trace_run_id"],
            "baseline_calibration_id": stable_id("proposal-trace-calibration", baseline.get("trace_run_id", "")),
            "proposal_calibration_id": stable_id("proposal-trace-calibration", approved.get("trace_run_id", "")),
            "implemented_calibration_id": stable_id("proposal-trace-calibration", implemented.get("trace_run_id", "")),
            "status": status, "comparison_result": {
                **comparison,
                "baseline": _trace_summary(baseline), "approved": _trace_summary(approved),
                "implemented": _trace_summary(implemented),
            },
            "created_at": now,
        }
        self._store_run(connection, row, "post_trace", result, status, stable_fingerprint(result), result["work_order_post_trace_run_id"])
        self._update(connection, row, {"trace_status": status, "overall_status": "post_work_validation"})
        self._history(connection, row, "post_work_trace_run", {}, {"status": status}, "system", "")
        return {"items": [result], "status": status}

    def _create_receipt(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        closeout = self._closeout_readiness(connection, row)
        if closeout["state"] not in {"approved", "ready"} or row["overall_status"] != "closed":
            raise WorkOrderError("Approved closeout is required before a completion receipt.", 409)
        implementation = self._latest_run_connection(connection, row, "implementation")
        conformance = self._latest_run_connection(connection, row, "conformance")
        qa = self._latest_run_connection(connection, row, "post_qa")
        traces = self._runs(connection, row, "post_trace")
        evidence = self._records(connection, row, "evidence")
        now = intake_registry_service.utc_now()
        receipt = {
            "receipt_version": engine.RECEIPT_VERSION,
            "receipt_id": stable_id("work-order-receipt", row["work_order_id"], row["work_order_version"], row["version_fingerprint"]),
            "work_order_id": row["work_order_id"], "work_order_version": row["work_order_version"],
            "linked_approved_proposal": {"proposal_id": row["linked_proposal_id"], "version": row["linked_proposal_version"], "fingerprint": row["proposal_fingerprint"]},
            "implementation_record_id": implementation.get("implementation_record_id", "") if implementation else "",
            "implementation_result": implementation.get("status", "not_started") if implementation else "not_started",
            "conformance": conformance or {}, "completed_steps": [
                item["step_id"] for item in self._records(connection, row, "steps")
                if item.get("completion_status") in {"completed", "completed_with_exception"}
            ],
            "exceptions": conformance.get("exceptions", []) if conformance else [],
            "inspections": self._records(connection, row, "inspections"),
            "evidence_ids": [item["evidence_id"] for item in evidence],
            "post_work_qa": qa or {}, "post_work_traces": traces,
            "unresolved_blockers": closeout["blockers"],
            "closeout_approval": {"approved_by": row["final_approver"], "approved_at": row["closeout_date"]},
            "external_implementation_status": row["implementation_confirmation_status"],
            "created_at": now, "disclaimer": engine.RECEIPT_NOTICE,
        }
        fingerprint = engine.closeout_fingerprint(row, receipt)
        receipt["closeout_fingerprint"] = fingerprint
        connection.execute(
            """INSERT INTO work_order_receipts
            (receipt_id, work_order_id, work_order_version, fingerprint, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_order_id, work_order_version) DO UPDATE SET
                receipt_id=excluded.receipt_id, fingerprint=excluded.fingerprint,
                payload_json=excluded.payload_json, created_at=excluded.created_at""",
            (receipt["receipt_id"], row["work_order_id"], row["work_order_version"], fingerprint, _dump(receipt), now),
        )
        return receipt

    def _detail(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        result = self._safe_work_order(row)
        for kind in RECORD_TABLES:
            result[kind] = self._records(connection, row, kind)
        result["implementation"] = self._latest_run_connection(connection, row, "implementation")
        result["conformance"] = self._latest_run_connection(connection, row, "conformance")
        result["post_work_qa"] = self._latest_run_connection(connection, row, "post_qa")
        result["post_work_traces"] = self._runs(connection, row, "post_trace")
        result["history"] = [
            _json_row(dict(item), ("prior_value_json", "new_value_json"))
            for item in connection.execute(
                """SELECT * FROM work_order_history WHERE work_order_id=? AND work_order_version=?
                ORDER BY created_at, history_id""",
                (row["work_order_id"], row["work_order_version"]),
            ).fetchall()
        ]
        result["versions"] = [
            {"work_order_version": item["work_order_version"], "overall_status": item["overall_status"], "version_fingerprint": item["version_fingerprint"], "created_at": item["created_at"]}
            for item in connection.execute(
                """SELECT work_order_version, overall_status, version_fingerprint, created_at
                FROM utility_work_orders WHERE work_order_id=? ORDER BY work_order_version""",
                (row["work_order_id"],),
            ).fetchall()
        ]
        result["three_state_comparison"] = self._three_state(connection, row)
        result["disclaimer"] = engine.DISCLAIMER
        return result

    def _three_state(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        proposal_qa = {}
        proposal_traces: list[dict[str, Any]] = []
        if row.get("linked_proposal_id"):
            proposal = self._proposal(connection, row["utility_vertical"], row["linked_proposal_id"], row["linked_proposal_version"])
            if proposal:
                qa = connection.execute(
                    """SELECT result_json FROM proposed_edit_qa_comparisons
                    WHERE proposal_id=? AND proposal_version=? ORDER BY created_at DESC LIMIT 1""",
                    (proposal["proposal_id"], proposal["proposal_version"]),
                ).fetchone()
                proposal_qa = _loads(qa["result_json"], {}) if qa else {}
                proposal_traces = [
                    _loads(item["result_json"], {})
                    for item in connection.execute(
                        """SELECT result_json FROM proposed_edit_trace_comparisons
                        WHERE proposal_id=? AND proposal_version=? ORDER BY created_at""",
                        (proposal["proposal_id"], proposal["proposal_version"]),
                    ).fetchall()
                ]
        post_qa = self._latest_run_connection(connection, row, "post_qa") or {}
        return {
            "baseline": {
                "label": "Baseline", "qa_blockers": proposal_qa.get("baseline_blocker_count"),
                "qa_warnings": proposal_qa.get("baseline_warning_count"),
                "trace": [item.get("baseline_outcome") for item in proposal_traces],
            },
            "approved_plan": {
                "label": "Approved Plan", "qa_blockers": proposal_qa.get("proposed_blocker_count"),
                "qa_warnings": proposal_qa.get("proposed_warning_count"),
                "trace": [item.get("proposed_outcome") for item in proposal_traces],
            },
            "recorded_implementation": {
                "label": "Recorded Implementation",
                "qa_blockers": (post_qa.get("comparison") or {}).get("proposed_blocker_count"),
                "qa_warnings": (post_qa.get("comparison") or {}).get("proposed_warning_count"),
                "trace": [
                    (item.get("comparison_result") or {}).get("implemented", {}).get("outcome")
                    for item in self._runs(connection, row, "post_trace")
                ],
                "status": row.get("implementation_confirmation_status"),
            },
            "notice": engine.IMPLEMENTATION_NOTICE,
        }

    def _refresh(self, connection: sqlite3.Connection, row: dict[str, Any]) -> None:
        current = self._require_version(connection, row["work_order_id"], row["work_order_version"])
        readiness = self._readiness(connection, current)
        closeout = self._closeout_readiness(connection, current)
        detail = self._safe_work_order(current)
        records = {kind: self._records(connection, current, kind) for kind in RECORD_TABLES}
        fingerprint = engine.definition_fingerprint(detail, records)
        self._update(connection, current, {
            "readiness": readiness["state"], "closeout_readiness": closeout["state"],
            "version_fingerprint": fingerprint,
        })

    def _readiness(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        return engine.readiness(
            self._safe_work_order(row),
            self._records(connection, row, "assignments"),
            self._records(connection, row, "prerequisites"),
            self._records(connection, row, "steps"),
        )

    def _closeout_readiness(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        return engine.closeout_readiness(
            self._safe_work_order(row),
            self._records(connection, row, "steps"),
            self._records(connection, row, "inspections"),
            self._latest_run_connection(connection, row, "conformance"),
            self._latest_run_connection(connection, row, "post_qa"),
            self._runs(connection, row, "post_trace"),
        )

    def _new_row(
        self,
        vertical: str,
        work_order_id: str,
        version: int,
        work_order_type: str,
        title: str,
        actor: str,
        payload: dict[str, Any],
        *,
        proposal: dict[str, Any] | None,
        scenario_code: str,
        synthetic: bool,
        blocked: bool = False,
    ) -> dict[str, Any]:
        now = intake_registry_service.utc_now()
        operations = [] if proposal is None else payload.get("_operations", [])
        affected_assets = sorted({
            str(item.get(key))
            for item in operations
            for key in ("target_asset_id", "from_asset_id", "to_asset_id", "new_asset_temporary_id")
            if item.get(key)
        })
        affected_relationships = sorted({
            str(item["target_relationship_id"]) for item in operations if item.get("target_relationship_id")
        })
        approved = bool(proposal and proposal.get("approval_status") == "approved" and not blocked)
        return {
            "work_order_id": work_order_id, "work_order_version": version,
            "parent_version": None, "supersedes_version": None, "scenario_code": scenario_code,
            "work_order_number": self._work_order_number(vertical, work_order_id, synthetic),
            "utility_vertical": vertical, "work_order_type": work_order_type, "title": title,
            "summary": str(payload.get("summary") or "Vendor-neutral synthetic job package.")[:2000],
            "priority": str(payload.get("priority") or "normal"),
            "overall_status": "planning", "design_status": "draft", "field_work_status": "not_released",
            "gis_implementation_status": "not_started", "inspection_status": "pending",
            "qa_status": "not_run", "trace_status": "not_run", "review_status": "not_submitted",
            "closeout_status": "not_ready", "readiness": "not_evaluated",
            "closeout_readiness": "not_evaluated",
            "linked_proposal_id": proposal["proposal_id"] if proposal else "",
            "linked_proposal_version": int(proposal["proposal_version"]) if proposal else 0,
            "proposal_fingerprint": proposal.get("proposal_fingerprint", "") if proposal else "",
            "baseline_fingerprint": proposal.get("baseline_fingerprint", "") if proposal else "",
            "baseline_current": 0 if blocked else 1,
            "proposal_approved": int(approved),
            "affected_asset_ids_json": _dump(affected_assets),
            "affected_relationship_ids_json": _dump(affected_relationships),
            "service_area_reference": "", "work_area_summary": str(payload.get("work_area_summary", ""))[:1000],
            "requested_date": now[:10], "target_start_date": str(payload.get("target_start_date", ""))[:30],
            "target_completion_date": str(payload.get("target_completion_date", ""))[:30],
            "actual_start_date": "", "field_completion_date": "", "gis_recorded_date": "",
            "closeout_date": "", "requested_by": str(payload.get("requested_by") or actor)[:100],
            "created_by": actor, "current_owner": str(payload.get("current_owner") or actor)[:100],
            "final_approver": "", "approved_by": "", "approved_at": "",
            "external_system": "", "external_work_order_id": "", "external_mapping_status": "adapter_required",
            "external_job_status": "", "synchronization_status": "not_connected",
            "synchronization_direction": "", "last_synchronized_at": "", "external_version": "",
            "external_transaction_id": "", "adapter_required": 1,
            "implementation_confirmation_status": "not_started", "sensitivity": "internal",
            "notes": str(payload.get("notes", ""))[:2000], "version_fingerprint": "",
            "release_fingerprint": "", "locked": 0, "is_synthetic": int(synthetic),
            "created_at": now, "updated_at": now,
        }

    @staticmethod
    def _insert(connection: sqlite3.Connection, row: dict[str, Any]) -> None:
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        connection.execute(
            f"INSERT INTO utility_work_orders ({columns}) VALUES ({placeholders})",
            tuple(row.values()),
        )

    def _seed_records(
        self,
        connection: sqlite3.Connection,
        row: dict[str, Any],
        operations: list[dict[str, Any]],
        *,
        invalid: bool,
        blocked: bool,
    ) -> None:
        records = {
            "assignments": engine.default_assignments(row["work_order_id"], row["work_order_version"], invalid=invalid),
            "phases": engine.default_phases(row["work_order_id"], row["work_order_version"]),
            "steps": engine.operation_steps(row["work_order_id"], row["work_order_version"], operations, invalid=invalid),
            "prerequisites": engine.default_prerequisites(
                row["work_order_id"], row["work_order_version"],
                approved=bool(row["proposal_approved"]) or row["work_order_type"] == "manual_investigation",
                blocked=blocked, invalid=invalid,
            ),
            "inspections": engine.default_inspections(
                row["utility_vertical"], row["work_order_id"], row["work_order_version"], operations, invalid=invalid,
            ),
        }
        for kind, items in records.items():
            for item in items:
                self._write_record(connection, row, kind, item)

    def _copy_records(self, connection: sqlite3.Connection, source: dict[str, Any], target: dict[str, Any]) -> None:
        for kind in RECORD_TABLES:
            for source_item in self._records(connection, source, kind):
                item = dict(source_item)
                key = RECORD_TABLES[kind][1]
                item[key] = stable_id(f"work-order-{kind[:-1]}", target["work_order_id"], target["work_order_version"], source_item[key])
                if kind in {"steps", "inspections"}:
                    item.update({
                        "completion_status": "not_started" if kind == "steps" else item.get("completion_status"),
                        "result": "not_recorded" if kind == "inspections" else item.get("result"),
                        "status": "pending" if kind == "inspections" else item.get("status"),
                    })
                self._write_record(connection, target, kind, item)

    def _normalize_record(
        self, connection: sqlite3.Connection, row: dict[str, Any], kind: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = intake_registry_service.utc_now()
        if kind == "assignments":
            role = str(payload.get("role", ""))
            if role not in engine.ROLES:
                raise WorkOrderError("Unsupported work-order role.")
            return {
                "assignment_id": stable_id("work-order-assignment", row["work_order_id"], row["work_order_version"], role, payload.get("assignee")),
                "role": role, "assignee": str(payload.get("assignee", ""))[:100],
                "assignment_status": str(payload.get("assignment_status") or "assigned"),
                "assigned_at": now, "accepted_at": "", "completed_at": "",
                "notes": str(payload.get("notes", ""))[:1000],
            }
        if kind == "steps":
            sequence = len(self._records(connection, row, "steps")) + 1
            step_type = str(payload.get("step_type", "review_asset"))
            return {
                "step_id": stable_id("work-order-step", row["work_order_id"], row["work_order_version"], sequence, step_type),
                "source_operation_id": "", "sequence": sequence, "phase_code": str(payload.get("phase_code") or "planning"),
                "step_type": step_type, "title": str(payload.get("title", ""))[:180],
                "instructions": str(payload.get("instructions", ""))[:1000],
                "affected_asset_ids": engine.string_list(payload.get("affected_asset_ids")),
                "affected_relationship_ids": engine.string_list(payload.get("affected_relationship_ids")),
                "prerequisites": engine.string_list(payload.get("prerequisites")),
                "expected_result": str(payload.get("expected_result", ""))[:1000],
                "validation_method": str(payload.get("validation_method", ""))[:1000],
                "assigned_role": str(payload.get("assigned_role") or "utility_gis_technician"),
                "completion_status": "not_started", "completed_by": "", "completed_at": "",
                "completion_notes": "", "exception_status": "none",
            }
        if kind == "prerequisites":
            prerequisite_type = str(payload.get("prerequisite_type", ""))
            if prerequisite_type not in engine.PREREQUISITE_TYPES:
                raise WorkOrderError("Unsupported prerequisite type.")
            return {
                "prerequisite_id": stable_id("work-order-prerequisite", row["work_order_id"], row["work_order_version"], prerequisite_type),
                "prerequisite_type": prerequisite_type, "title": str(payload.get("title", ""))[:180],
                "description": str(payload.get("description", ""))[:1000], "required": bool(payload.get("required", True)),
                "status": str(payload.get("status") or "not_evaluated"), "evidence_reference": "",
                "confirmed_by": "", "confirmed_at": "", "notes": str(payload.get("notes", ""))[:1000],
            }
        if kind == "inspections":
            inspection_type = str(payload.get("inspection_type", ""))
            if inspection_type not in engine.INSPECTION_TYPES:
                raise WorkOrderError("Unsupported inspection type.")
            return {
                "inspection_id": stable_id("work-order-inspection", row["work_order_id"], row["work_order_version"], inspection_type),
                "inspection_type": inspection_type, "title": str(payload.get("title", ""))[:180],
                "required": bool(payload.get("required", True)), "status": "pending",
                "affected_asset_ids": engine.string_list(payload.get("affected_asset_ids")),
                "affected_relationship_ids": engine.string_list(payload.get("affected_relationship_ids")),
                "expected_condition": str(payload.get("expected_condition", ""))[:1000],
                "observed_condition": "", "result": "not_recorded", "inspector": "", "inspected_at": "",
                "evidence_ids": [], "notes": str(payload.get("notes", ""))[:1000],
            }
        evidence_type = str(payload.get("evidence_type", ""))
        if evidence_type not in engine.EVIDENCE_TYPES:
            raise WorkOrderError("Unsupported evidence type.")
        return {
            "evidence_id": stable_id("work-order-evidence", row["work_order_id"], row["work_order_version"], evidence_type, payload.get("title"), now),
            "step_id": str(payload.get("step_id", ""))[:120], "inspection_id": str(payload.get("inspection_id", ""))[:120],
            "evidence_type": evidence_type, "title": str(payload.get("title", ""))[:180],
            "summary": str(payload.get("summary", ""))[:2000], "source": str(payload.get("source", ""))[:100],
            "recorded_by": str(payload.get("recorded_by", ""))[:100], "recorded_at": now,
            "sensitivity": str(payload.get("sensitivity") or "internal"), "external_reference": str(payload.get("external_reference", ""))[:200],
            "attachment_name": str(payload.get("attachment_name", ""))[:180], "attachment_type": str(payload.get("attachment_type", ""))[:100],
            "attachment_checksum": str(payload.get("attachment_checksum", ""))[:128],
            "safe_metadata": payload.get("safe_metadata") if isinstance(payload.get("safe_metadata"), dict) else {},
            "review_status": str(payload.get("review_status") or "unreviewed"),
        }

    @staticmethod
    def _write_record(
        connection: sqlite3.Connection, row: dict[str, Any], kind: str, item: dict[str, Any],
    ) -> None:
        table, key = RECORD_TABLES[kind]
        now = intake_registry_service.utc_now()
        status_key = {
            "assignments": "assignment_status", "phases": "status", "steps": "completion_status",
            "prerequisites": "status", "inspections": "status", "evidence": "review_status",
        }[kind]
        role = str(item.get("role") or item.get("assigned_role") or "")
        sequence = int(item.get("sequence", 0))
        connection.execute(
            f"""INSERT INTO {table}
            ({key}, work_order_id, work_order_version, role, status, sequence, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(work_order_id, work_order_version, {key}) DO UPDATE SET
                role=excluded.role, status=excluded.status, sequence=excluded.sequence,
                payload_json=excluded.payload_json, updated_at=excluded.updated_at""",
            (
                item[key], row["work_order_id"], row["work_order_version"], role,
                str(item.get(status_key, "")), sequence, _dump(item), now, now,
            ),
        )

    @staticmethod
    def _records(connection: sqlite3.Connection, row: dict[str, Any], kind: str) -> list[dict[str, Any]]:
        table, key = RECORD_TABLES[kind]
        values = connection.execute(
            f"""SELECT payload_json FROM {table}
            WHERE work_order_id=? AND work_order_version=?
            ORDER BY sequence, {key}""",
            (row["work_order_id"], row["work_order_version"]),
        ).fetchall()
        return [_loads(item["payload_json"], {}) for item in values]

    def _record(
        self, connection: sqlite3.Connection, row: dict[str, Any], kind: str, record_id: str,
    ) -> dict[str, Any]:
        table, key = RECORD_TABLES[kind]
        value = connection.execute(
            f"SELECT payload_json FROM {table} WHERE work_order_id=? AND work_order_version=? AND {key}=?",
            (row["work_order_id"], row["work_order_version"], record_id),
        ).fetchone()
        if not value:
            raise WorkOrderError(f"{kind[:-1].replace('_', ' ').title()} not found.", 404)
        return _loads(value["payload_json"], {})

    @staticmethod
    def _record_map(detail: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        return {kind: detail.get(kind, []) for kind in RECORD_TABLES}

    @staticmethod
    def _store_run(
        connection: sqlite3.Connection,
        row: dict[str, Any],
        run_type: str,
        payload: dict[str, Any],
        status: str,
        fingerprint: str,
        run_id: str,
    ) -> None:
        connection.execute(
            """INSERT INTO work_order_runs
            (run_id, work_order_id, work_order_version, run_type, status, fingerprint, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,
                fingerprint=excluded.fingerprint, payload_json=excluded.payload_json""",
            (
                run_id, row["work_order_id"], row["work_order_version"], run_type, status,
                fingerprint, _dump(payload), intake_registry_service.utc_now(),
            ),
        )

    @staticmethod
    def _runs(connection: sqlite3.Connection, row: dict[str, Any], run_type: str) -> list[dict[str, Any]]:
        return [
            _loads(item["payload_json"], {})
            for item in connection.execute(
                """SELECT payload_json FROM work_order_runs
                WHERE work_order_id=? AND work_order_version=? AND run_type=?
                ORDER BY created_at DESC, run_id""",
                (row["work_order_id"], row["work_order_version"], run_type),
            ).fetchall()
        ]

    def _latest_run_connection(
        self, connection: sqlite3.Connection, row: dict[str, Any], run_type: str,
    ) -> dict[str, Any] | None:
        values = self._runs(connection, row, run_type)
        return values[0] if values else None

    def _latest_run(self, vertical: str, work_order_id: str, run_type: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = self._require(connection, vertical, work_order_id)
            result = self._latest_run_connection(connection, row, run_type)
            if not result:
                raise WorkOrderError(f"{run_type.replace('_', ' ').title()} has not been recorded.", 404)
            return result

    @staticmethod
    def _proposal(
        connection: sqlite3.Connection,
        vertical: str,
        proposal_id: str,
        version: object | None,
    ) -> dict[str, Any] | None:
        if not proposal_id:
            return None
        if version:
            value = connection.execute(
                """SELECT * FROM proposed_edit_proposals
                WHERE utility_vertical=? AND proposal_id=? AND proposal_version=?""",
                (vertical, proposal_id, int(version)),
            ).fetchone()
        else:
            value = connection.execute(
                """SELECT * FROM proposed_edit_proposals
                WHERE utility_vertical=? AND proposal_id=? ORDER BY proposal_version DESC LIMIT 1""",
                (vertical, proposal_id),
            ).fetchone()
        return dict(value) if value else None

    @staticmethod
    def _proposal_operations(
        connection: sqlite3.Connection, proposal: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if not proposal:
            return []
        return proposed_edits._operations(connection, proposal["proposal_id"], proposal["proposal_version"])

    @staticmethod
    def _row(connection: sqlite3.Connection, vertical: str, work_order_id: str) -> dict[str, Any] | None:
        value = connection.execute(
            """SELECT * FROM utility_work_orders WHERE utility_vertical=? AND work_order_id=?
            ORDER BY work_order_version DESC LIMIT 1""",
            (vertical, work_order_id),
        ).fetchone()
        return dict(value) if value else None

    def _require(self, connection: sqlite3.Connection, vertical: str, work_order_id: str) -> dict[str, Any]:
        row = self._row(connection, vertical, work_order_id)
        if not row:
            raise WorkOrderError("Work order not found.", 404)
        return row

    @staticmethod
    def _require_version(connection: sqlite3.Connection, work_order_id: str, version: int) -> dict[str, Any]:
        value = connection.execute(
            "SELECT * FROM utility_work_orders WHERE work_order_id=? AND work_order_version=?",
            (work_order_id, version),
        ).fetchone()
        if not value:
            raise WorkOrderError("Work-order version not found.", 404)
        return dict(value)

    def _require_editable(self, connection: sqlite3.Connection, vertical: str, work_order_id: str) -> dict[str, Any]:
        row = self._require(connection, vertical, work_order_id)
        if row["locked"] or row["overall_status"] in {"released", "in_progress", "field_complete", "gis_update_pending", "gis_update_recorded", "post_work_validation", "closeout_review", "closed", "archived"}:
            raise WorkOrderError("Released work-order definitions are immutable; create a controlled new version.", 409)
        return row

    @staticmethod
    def _update(connection: sqlite3.Connection, row: dict[str, Any], fields: dict[str, Any]) -> None:
        allowed = {
            "overall_status", "design_status", "field_work_status", "gis_implementation_status",
            "inspection_status", "qa_status", "trace_status", "review_status", "closeout_status",
            "readiness", "closeout_readiness", "actual_start_date", "field_completion_date",
            "gis_recorded_date", "closeout_date", "current_owner", "final_approver", "approved_by",
            "approved_at", "external_mapping_status", "external_job_status", "synchronization_status",
            "implementation_confirmation_status", "notes", "version_fingerprint",
            "release_fingerprint", "locked", "updated_at",
        }
        if set(fields) - allowed:
            raise WorkOrderError(f"Unsupported work-order update: {sorted(set(fields) - allowed)[0]}.")
        values = dict(fields)
        values.setdefault("updated_at", intake_registry_service.utc_now())
        assignments = ", ".join(f"{key}=?" for key in values)
        connection.execute(
            f"""UPDATE utility_work_orders SET {assignments}
            WHERE work_order_id=? AND work_order_version=?""",
            (*values.values(), row["work_order_id"], row["work_order_version"]),
        )

    @staticmethod
    def _history(
        connection: sqlite3.Connection,
        row: dict[str, Any],
        action: str,
        prior: Any,
        new: Any,
        actor: str,
        reason: str,
    ) -> None:
        now = intake_registry_service.utc_now()
        history_id = stable_id("work-order-history", row["work_order_id"], row["work_order_version"], action, now, str(uuid.uuid4()))
        connection.execute(
            """INSERT INTO work_order_history
            (history_id, work_order_id, work_order_version, action, prior_value_json,
             new_value_json, actor_type, actor, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                history_id, row["work_order_id"], row["work_order_version"], action,
                _dump(prior), _dump(new), "application_user", actor[:100], reason[:1000], now,
            ),
        )

    def _seed_scenarios(self, connection: sqlite3.Connection) -> None:
        if connection.execute(
            "SELECT 1 FROM work_order_seed_versions WHERE version=?", (engine.SCENARIO_VERSION,),
        ).fetchone():
            return
        for vertical, scenarios in engine.SCENARIOS.items():
            for scenario in scenarios:
                proposal = connection.execute(
                    """SELECT * FROM proposed_edit_proposals
                    WHERE utility_vertical=? AND scenario_code=? ORDER BY proposal_version DESC LIMIT 1""",
                    (vertical, scenario.get("proposal", "")),
                ).fetchone()
                proposal_row = dict(proposal) if proposal else None
                blocked = bool(scenario.get("blocked"))
                if proposal_row and scenario.get("ready") and not blocked:
                    self._approve_synthetic_proposal(connection, proposal_row)
                    proposal_row = self._proposal(connection, vertical, proposal_row["proposal_id"], proposal_row["proposal_version"])
                work_order_id = stable_id("work-order", vertical, scenario["code"], "synthetic_demo")
                if self._row(connection, vertical, work_order_id):
                    continue
                operations = self._proposal_operations(connection, proposal_row)
                payload = {
                    "summary": "Deterministic synthetic work-order scenario.",
                    "priority": "normal", "_operations": operations,
                }
                row = self._new_row(
                    vertical, work_order_id, 1, scenario["type"], scenario["title"],
                    "synthetic_demo", payload, proposal=proposal_row,
                    scenario_code=scenario["code"], synthetic=True, blocked=blocked,
                )
                self._insert(connection, row)
                self._seed_records(
                    connection, row, operations,
                    invalid=bool(scenario.get("invalid")), blocked=blocked,
                )
                self._refresh(connection, row)
                self._history(connection, row, "synthetic_scenario_seeded", {}, {"scenario_code": scenario["code"]}, "system", "Synthetic portfolio scenario.")
                if scenario.get("complete") and not blocked:
                    self._complete_seed(connection, self._require(connection, vertical, work_order_id))
                connection.commit()
        connection.execute(
            "INSERT INTO work_order_seed_versions (version, applied_at) VALUES (?, ?)",
            (engine.SCENARIO_VERSION, intake_registry_service.utc_now()),
        )
        connection.commit()

    def _approve_synthetic_proposal(self, connection: sqlite3.Connection, proposal: dict[str, Any]) -> None:
        if proposal["approval_status"] == "approved":
            return
        now = intake_registry_service.utc_now()
        connection.execute(
            """UPDATE proposed_edit_proposals SET status='approved', review_status='decision_recorded',
            approval_status='approved', implementation_readiness='approved_plan_only',
            reviewed_by='Synthetic Technical Reviewer', reviewed_at=?,
            approved_by='Synthetic Final Reviewer', approved_at=?, locked=1, updated_at=?
            WHERE proposal_id=? AND proposal_version=?""",
            (now, now, now, proposal["proposal_id"], proposal["proposal_version"]),
        )

    def _complete_seed(self, connection: sqlite3.Connection, row: dict[str, Any]) -> None:
        for kind in ("assignments", "steps", "inspections"):
            for item in self._records(connection, row, kind):
                if kind == "assignments":
                    item["assignment_status"] = "completed"
                elif kind == "steps":
                    item.update({"completion_status": "completed", "completed_by": "Synthetic GIS Technician", "completed_at": intake_registry_service.utc_now()})
                else:
                    item.update({"status": "passed", "result": "pass", "inspector": "Synthetic Inspector", "inspected_at": intake_registry_service.utc_now()})
                self._write_record(connection, row, kind, item)
        self._update(connection, row, {
            "overall_status": "in_progress", "review_status": "approved", "design_status": "approved",
            "field_work_status": "in_progress", "approved_by": "Synthetic Final Reviewer",
            "approved_at": intake_registry_service.utc_now(), "final_approver": "Synthetic Final Reviewer",
        })
        row = self._require_version(connection, row["work_order_id"], row["work_order_version"])
        self._record_implementation(connection, row, {"recorded_by": "Synthetic GIS Technician"})
        row = self._require_version(connection, row["work_order_id"], row["work_order_version"])
        self._run_conformance(connection, row)
        self._run_post_qa(connection, row)
        self._run_post_traces(connection, row)
        row = self._require_version(connection, row["work_order_id"], row["work_order_version"])
        self._refresh(connection, row)
        row = self._require_version(connection, row["work_order_id"], row["work_order_version"])
        closeout = self._closeout_readiness(connection, row)
        if not closeout["blockers"]:
            self._update(connection, row, {
                "overall_status": "closed", "closeout_status": "closed",
                "closeout_date": intake_registry_service.utc_now(), "locked": 1,
            })
            row = self._require_version(connection, row["work_order_id"], row["work_order_version"])
            self._create_receipt(connection, row)

    @staticmethod
    def _safe_work_order(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["affected_asset_ids"] = _loads(result.pop("affected_asset_ids_json", "[]"), [])
        result["affected_relationship_ids"] = _loads(result.pop("affected_relationship_ids_json", "[]"), [])
        for field in ("baseline_current", "proposal_approved", "adapter_required", "locked", "is_synthetic"):
            result[field] = bool(result.get(field))
        result.pop("external_transaction_id", None)
        return result

    @staticmethod
    def _work_order_number(vertical: str, work_order_id: str, synthetic: bool) -> str:
        prefix = "SYN-E-WO" if vertical == "electric_distribution" else "SYN-T-WO"
        if not synthetic:
            prefix = "UP-WO"
        return f"{prefix}-{work_order_id[-8:].upper()}"

    @staticmethod
    def _vertical(vertical: str) -> None:
        try:
            engine.validate_vertical(vertical)
        except ValueError as exc:
            raise WorkOrderError(str(exc), 404) from exc


def _loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
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
        row[field.removesuffix("_json")] = _loads(row.pop(field, ""), {})
    return row


def _trace_summary(value: dict[str, Any]) -> dict[str, Any]:
    calibrated = value.get("calibrated", {})
    return {
        "outcome": calibrated.get("calibrated_outcome"), "confidence": calibrated.get("calibrated_confidence"),
        "objective_reached": calibrated.get("objective_reached"),
        "path_signature": calibrated.get("path_signature"),
        "branch_signature": calibrated.get("branch_signature"),
    }


service = WorkOrderService()
