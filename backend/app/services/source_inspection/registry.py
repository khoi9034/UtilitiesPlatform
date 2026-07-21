from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import intake_registry_service
from app.services.source_inspection.models import ClassificationCandidate, DuplicateGroup, SourceContainer, SourceLayer, StagingPlanItem


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(root: Path) -> sqlite3.Connection:
    connection = intake_registry_service.connect(root)
    initialize(connection)
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS inspection_containers (
            submission_id TEXT PRIMARY KEY,
            container_id TEXT NOT NULL,
            container_name TEXT NOT NULL,
            source_format TEXT NOT NULL,
            source_type TEXT,
            package_utility_system TEXT,
            source_owner TEXT,
            project_id TEXT,
            sensitivity_level TEXT,
            inspection_status TEXT NOT NULL,
            spatial_reference_count INTEGER,
            child_layer_count INTEGER,
            table_count INTEGER,
            relationship_count INTEGER,
            domain_count INTEGER,
            subtype_count INTEGER,
            attachment_count INTEGER,
            inspection_run_id TEXT,
            inspected_at TEXT,
            warnings_json TEXT,
            blockers_json TEXT
        );

        CREATE TABLE IF NOT EXISTS inspected_layers (
            layer_id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            container_id TEXT NOT NULL,
            source_layer_name TEXT NOT NULL,
            source_layer_alias TEXT,
            source_schema TEXT,
            source_owner_prefix TEXT,
            feature_dataset TEXT,
            object_type TEXT,
            geometry_type TEXT,
            record_count INTEGER,
            spatial_reference_name TEXT,
            spatial_reference_wkid INTEGER,
            linear_unit TEXT,
            angular_unit TEXT,
            has_z INTEGER,
            has_m INTEGER,
            extent_summary_json TEXT,
            field_count INTEGER,
            field_profile_json TEXT,
            domain_profile_json TEXT,
            subtype_profile_json TEXT,
            relationship_profile_json TEXT,
            likely_id_fields_json TEXT,
            likely_status_fields_json TEXT,
            likely_date_fields_json TEXT,
            likely_dimension_fields_json TEXT,
            likely_owner_fields_json TEXT,
            domain_names_json TEXT,
            subtype_summary TEXT,
            relationship_summary TEXT,
            attachment_status TEXT,
            editor_tracking_status TEXT,
            proposed_or_existing_signal TEXT,
            operational_role TEXT,
            lifecycle_representation TEXT,
            owner_or_jurisdiction TEXT,
            classification_status TEXT,
            duplicate_status TEXT,
            coordinate_status TEXT,
            sensitivity_status TEXT,
            staging_status TEXT,
            routing_state TEXT,
            latest_review_status TEXT,
            latest_reviewer TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_inspected_layers_submission ON inspected_layers(submission_id);

        CREATE TABLE IF NOT EXISTS layer_classification_candidates (
            candidate_id TEXT PRIMARY KEY,
            layer_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            utility_system TEXT,
            network_group TEXT,
            asset_category TEXT,
            asset_subcategory TEXT,
            operational_role TEXT,
            lifecycle_representation TEXT,
            owner_or_jurisdiction TEXT,
            confidence TEXT,
            score REAL,
            evidence_json TEXT,
            warnings_json TEXT,
            rule_version TEXT,
            rule_code TEXT,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_layer_candidates_layer ON layer_classification_candidates(layer_id);

        CREATE TABLE IF NOT EXISTS layer_reviews (
            review_id TEXT PRIMARY KEY,
            layer_id TEXT NOT NULL,
            workflow_status TEXT,
            classification_decision TEXT,
            approved_utility_system TEXT,
            approved_network_group TEXT,
            approved_asset_category TEXT,
            approved_asset_subcategory TEXT,
            approved_operational_role TEXT,
            approved_lifecycle_representation TEXT,
            approved_owner_or_jurisdiction TEXT,
            duplicate_decision TEXT,
            coordinate_decision TEXT,
            sensitivity_decision TEXT,
            reviewer TEXT,
            review_notes TEXT,
            data_owner_confirmation_required INTEGER,
            engineering_review_required INTEGER,
            reviewed_at TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_layer_reviews_layer ON layer_reviews(layer_id);

        CREATE TABLE IF NOT EXISTS inspection_review_history (
            history_id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT,
            before_json TEXT,
            after_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS duplicate_groups (
            duplicate_group_id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            comparison_type TEXT,
            confidence TEXT,
            status TEXT,
            recommended_action TEXT,
            authoritative_layer_id TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_duplicate_groups_submission ON duplicate_groups(submission_id);

        CREATE TABLE IF NOT EXISTS duplicate_group_members (
            duplicate_group_id TEXT NOT NULL,
            layer_id TEXT NOT NULL,
            member_role TEXT,
            similarity_score REAL,
            notes TEXT,
            PRIMARY KEY (duplicate_group_id, layer_id)
        );

        CREATE TABLE IF NOT EXISTS staging_plan_items (
            staging_plan_item_id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            layer_id TEXT NOT NULL,
            proposed_target_name TEXT,
            target_utility_system TEXT,
            target_network_group TEXT,
            target_asset_category TEXT,
            target_asset_subcategory TEXT,
            target_owner_or_jurisdiction TEXT,
            source_spatial_reference TEXT,
            target_spatial_reference TEXT,
            projection_required INTEGER,
            approved_for_staging INTEGER,
            approval_status TEXT,
            blocker TEXT,
            reviewer TEXT,
            reviewed_at TEXT,
            staged_output_name TEXT,
            staged_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_staging_plan_submission ON staging_plan_items(submission_id);
        """
    )
    connection.commit()


def save_inspection(
    root: Path,
    container: SourceContainer,
    layers: list[SourceLayer],
    candidates_by_layer: dict[str, list[ClassificationCandidate]],
    duplicate_groups: list[DuplicateGroup],
    staging_items: list[StagingPlanItem],
) -> None:
    with connect(root) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO inspection_containers (
                submission_id, container_id, container_name, source_format, source_type, package_utility_system,
                source_owner, project_id, sensitivity_level, inspection_status, spatial_reference_count,
                child_layer_count, table_count, relationship_count, domain_count, subtype_count, attachment_count,
                inspection_run_id, inspected_at, warnings_json, blockers_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                container.submission_id,
                container.container_id,
                container.container_name,
                container.source_format,
                container.source_type,
                container.package_utility_system,
                container.source_owner,
                container.project_id,
                container.sensitivity_level,
                container.inspection_status,
                container.spatial_reference_count,
                container.child_layer_count,
                container.table_count,
                container.relationship_count,
                container.domain_count,
                container.subtype_count,
                container.attachment_count,
                container.inspection_run_id,
                container.inspected_at,
                dumps(container.warnings),
                dumps(container.blockers),
            ),
        )
        for layer in layers:
            upsert_layer(connection, layer)
            connection.execute("DELETE FROM layer_classification_candidates WHERE layer_id = ?", (layer.layer_id,))
            for candidate in candidates_by_layer.get(layer.layer_id, []):
                insert_candidate(connection, candidate)
        connection.execute("DELETE FROM duplicate_group_members WHERE duplicate_group_id IN (SELECT duplicate_group_id FROM duplicate_groups WHERE submission_id = ?)", (container.submission_id,))
        connection.execute("DELETE FROM duplicate_groups WHERE submission_id = ?", (container.submission_id,))
        for group in duplicate_groups:
            insert_duplicate_group(connection, group)
        connection.execute("DELETE FROM staging_plan_items WHERE submission_id = ?", (container.submission_id,))
        for item in staging_items:
            insert_staging_item(connection, item)
        connection.commit()


def upsert_layer(connection: sqlite3.Connection, layer: SourceLayer) -> None:
    existing = connection.execute("SELECT latest_review_status, latest_reviewer, staging_status FROM inspected_layers WHERE layer_id = ?", (layer.layer_id,)).fetchone()
    if existing:
        layer.latest_review_status = existing["latest_review_status"] or layer.latest_review_status
        layer.latest_reviewer = existing["latest_reviewer"] or layer.latest_reviewer
        layer.staging_status = existing["staging_status"] or layer.staging_status
    row = layer.to_row()
    row.update(
        {
            "has_z": int(layer.has_z),
            "has_m": int(layer.has_m),
            "extent_summary_json": dumps(layer.extent_summary),
            "field_profile_json": dumps(layer.field_profile),
            "domain_profile_json": dumps(layer.domain_profile),
            "subtype_profile_json": dumps(layer.subtype_profile),
            "relationship_profile_json": dumps(layer.relationship_profile),
            "likely_id_fields_json": dumps(layer.likely_id_fields),
            "likely_status_fields_json": dumps(layer.likely_status_fields),
            "likely_date_fields_json": dumps(layer.likely_date_fields),
            "likely_dimension_fields_json": dumps(layer.likely_dimension_fields),
            "likely_owner_fields_json": dumps(layer.likely_owner_fields),
            "domain_names_json": dumps(layer.domain_names),
        }
    )
    for key in [
        "extent_summary",
        "field_profile",
        "domain_profile",
        "subtype_profile",
        "relationship_profile",
        "likely_id_fields",
        "likely_status_fields",
        "likely_date_fields",
        "likely_dimension_fields",
        "likely_owner_fields",
        "domain_names",
    ]:
        row.pop(key, None)
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    assignments = ", ".join(f"{key}=excluded.{key}" for key in row if key != "layer_id")
    connection.execute(f"INSERT INTO inspected_layers ({columns}) VALUES ({placeholders}) ON CONFLICT(layer_id) DO UPDATE SET {assignments}", tuple(row.values()))


def insert_candidate(connection: sqlite3.Connection, candidate: ClassificationCandidate) -> None:
    row = candidate.to_row()
    row["evidence_json"] = dumps(candidate.evidence)
    row["warnings_json"] = dumps(candidate.warnings)
    row.pop("evidence", None)
    row.pop("warnings", None)
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    connection.execute(f"INSERT OR REPLACE INTO layer_classification_candidates ({columns}) VALUES ({placeholders})", tuple(row.values()))


def insert_duplicate_group(connection: sqlite3.Connection, group: DuplicateGroup) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO duplicate_groups (
            duplicate_group_id, submission_id, comparison_type, confidence, status, recommended_action,
            authoritative_layer_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            group.duplicate_group_id,
            group.submission_id,
            group.comparison_type,
            group.confidence,
            group.status,
            group.recommended_action,
            group.authoritative_layer_id,
            group.created_at,
            group.updated_at,
        ),
    )
    for member in group.members:
        connection.execute(
            """
            INSERT OR REPLACE INTO duplicate_group_members
            (duplicate_group_id, layer_id, member_role, similarity_score, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                member["duplicate_group_id"],
                member["layer_id"],
                member.get("member_role", ""),
                member.get("similarity_score", 0),
                member.get("notes", ""),
            ),
        )


def insert_staging_item(connection: sqlite3.Connection, item: StagingPlanItem) -> None:
    row = item.to_row()
    row["projection_required"] = int(item.projection_required)
    row["approved_for_staging"] = int(item.approved_for_staging)
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    connection.execute(f"INSERT OR REPLACE INTO staging_plan_items ({columns}) VALUES ({placeholders})", tuple(row.values()))


def inspection_status(root: Path, submission_id: str) -> dict[str, Any] | None:
    with connect(root) as connection:
        row = connection.execute("SELECT * FROM inspection_containers WHERE submission_id = ?", (submission_id,)).fetchone()
    return safe_container(dict(row)) if row else None


def list_layers(root: Path, submission_id: str, **filters: Any) -> tuple[list[dict[str, Any]], int]:
    rows = all_layers(root, submission_id)
    for field in [
        "utility_system",
        "network_group",
        "asset_category",
        "asset_subcategory",
        "operational_role",
        "lifecycle_representation",
        "classification_status",
        "duplicate_status",
        "coordinate_status",
        "staging_status",
        "confidence",
    ]:
        expected = filters.get(field)
        if expected:
            rows = [row for row in rows if str(row.get(field, "")).lower() == str(expected).lower()]
    search = str(filters.get("search") or "").lower()
    if search:
        rows = [row for row in rows if search in " ".join(str(row.get(key, "")) for key in ["source_layer_name", "source_layer_alias", "owner_or_jurisdiction"]).lower()]
    total = len(rows)
    limit = int(filters.get("limit", 100))
    offset = int(filters.get("offset", 0))
    return rows[offset : offset + limit], total


def all_layers(root: Path, submission_id: str) -> list[dict[str, Any]]:
    with connect(root) as connection:
        rows = connection.execute("SELECT * FROM inspected_layers WHERE submission_id = ? ORDER BY source_layer_name", (submission_id,)).fetchall()
        candidates = candidates_by_layer(connection, [row["layer_id"] for row in rows])
    return [decorate_layer(dict(row), candidates.get(row["layer_id"], []), detail=False) for row in rows]


def layer_detail(root: Path, submission_id: str, layer_id: str) -> dict[str, Any] | None:
    with connect(root) as connection:
        row = connection.execute("SELECT * FROM inspected_layers WHERE submission_id = ? AND layer_id = ?", (submission_id, layer_id)).fetchone()
        if not row:
            return None
        candidates = candidates_by_layer(connection, [layer_id]).get(layer_id, [])
        reviews = [dict(item) for item in connection.execute("SELECT * FROM layer_reviews WHERE layer_id = ? ORDER BY created_at DESC", (layer_id,)).fetchall()]
    payload = decorate_layer(dict(row), candidates, detail=True)
    payload["reviews"] = [safe_review(review) for review in reviews]
    return payload


def layer_candidates(root: Path, layer_id: str) -> list[dict[str, Any]]:
    with connect(root) as connection:
        rows = connection.execute("SELECT * FROM layer_classification_candidates WHERE layer_id = ? ORDER BY rank", (layer_id,)).fetchall()
    return [safe_candidate(dict(row)) for row in rows]


def latest_candidate(root: Path, layer_id: str) -> dict[str, Any] | None:
    candidates = layer_candidates(root, layer_id)
    return candidates[0] if candidates else None


def add_layer_review(root: Path, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with connect(root) as connection:
        before = connection.execute("SELECT * FROM layer_reviews WHERE layer_id = ? ORDER BY created_at DESC LIMIT 1", (layer_id,)).fetchone()
        layer = connection.execute("SELECT * FROM inspected_layers WHERE submission_id = ? AND layer_id = ?", (submission_id, layer_id)).fetchone()
        if not layer:
            raise KeyError("Layer not found.")
        candidates = candidates_by_layer(connection, [layer_id]).get(layer_id, [])
        review = normalized_review_payload(payload, candidates)
        now = utc_now()
        review_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO layer_reviews (
                review_id, layer_id, workflow_status, classification_decision, approved_utility_system,
                approved_network_group, approved_asset_category, approved_asset_subcategory, approved_operational_role,
                approved_lifecycle_representation, approved_owner_or_jurisdiction, duplicate_decision, coordinate_decision,
                sensitivity_decision, reviewer, review_notes, data_owner_confirmation_required, engineering_review_required,
                reviewed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                layer_id,
                review.get("workflow_status", "classification_approved"),
                review.get("classification_decision", "approve_top_candidate"),
                review.get("approved_utility_system", ""),
                review.get("approved_network_group", ""),
                review.get("approved_asset_category", ""),
                review.get("approved_asset_subcategory", ""),
                review.get("approved_operational_role", ""),
                review.get("approved_lifecycle_representation", ""),
                review.get("approved_owner_or_jurisdiction", ""),
                review.get("duplicate_decision", ""),
                review.get("coordinate_decision", ""),
                review.get("sensitivity_decision", ""),
                review.get("reviewer", ""),
                review.get("review_notes", ""),
                int(bool(review.get("data_owner_confirmation_required", False))),
                int(bool(review.get("engineering_review_required", False))),
                review.get("reviewed_at", now),
                now,
                now,
            ),
        )
        connection.execute(
            """
            UPDATE inspected_layers
            SET latest_review_status = ?, latest_reviewer = ?, classification_status = ?, sensitivity_status = ?, updated_at = ?
            WHERE layer_id = ?
            """,
            (
                review.get("workflow_status", "classification_approved"),
                review.get("reviewer", ""),
                "classification_approved" if review.get("workflow_status") in {"classification_approved", "reference_approved"} else str(review.get("workflow_status", "")),
                "sensitivity_review_complete" if review.get("sensitivity_decision") in {"complete", "approved"} else dict(layer).get("sensitivity_status", ""),
                now,
                layer_id,
            ),
        )
        add_history(connection, submission_id, "layer", layer_id, "layer_review_updated", str(review.get("reviewer", "")), dict(before) if before else {}, review)
        connection.commit()
    return layer_detail(root, submission_id, layer_id) or {}


def normalized_review_payload(payload: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    top = candidates[0] if candidates else {}
    decision = str(payload.get("classification_decision") or "approve_top_candidate")
    if decision == "manual_override" and not str(payload.get("review_notes") or "").strip():
        raise ValueError("Manual classification overrides require review_notes.")
    output = dict(payload)
    if decision == "approve_top_candidate":
        for source, target in [
            ("utility_system", "approved_utility_system"),
            ("network_group", "approved_network_group"),
            ("asset_category", "approved_asset_category"),
            ("asset_subcategory", "approved_asset_subcategory"),
            ("operational_role", "approved_operational_role"),
            ("lifecycle_representation", "approved_lifecycle_representation"),
            ("owner_or_jurisdiction", "approved_owner_or_jurisdiction"),
        ]:
            output.setdefault(target, top.get(source, ""))
    return output


def duplicate_groups(root: Path, submission_id: str) -> list[dict[str, Any]]:
    with connect(root) as connection:
        rows = connection.execute("SELECT * FROM duplicate_groups WHERE submission_id = ? ORDER BY created_at", (submission_id,)).fetchall()
        return [safe_duplicate_group(connection, dict(row)) for row in rows]


def duplicate_group_detail(root: Path, submission_id: str, group_id: str) -> dict[str, Any] | None:
    with connect(root) as connection:
        row = connection.execute("SELECT * FROM duplicate_groups WHERE submission_id = ? AND duplicate_group_id = ?", (submission_id, group_id)).fetchone()
        return safe_duplicate_group(connection, dict(row)) if row else None


def update_duplicate_group(root: Path, submission_id: str, group_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {key: payload[key] for key in ["status", "authoritative_layer_id", "recommended_action"] if key in payload}
    if not allowed:
        return duplicate_group_detail(root, submission_id, group_id) or {}
    with connect(root) as connection:
        before = connection.execute("SELECT * FROM duplicate_groups WHERE submission_id = ? AND duplicate_group_id = ?", (submission_id, group_id)).fetchone()
        if not before:
            raise KeyError("Duplicate group not found.")
        allowed["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in allowed)
        connection.execute(f"UPDATE duplicate_groups SET {assignments} WHERE duplicate_group_id = ?", (*allowed.values(), group_id))
        members = connection.execute("SELECT layer_id FROM duplicate_group_members WHERE duplicate_group_id = ?", (group_id,)).fetchall()
        if allowed.get("status") in {"authoritative_source_selected", "retain_both", "legacy_marked", "view_marked", "excluded", "deferred"}:
            connection.executemany("UPDATE inspected_layers SET duplicate_status = 'resolved_duplicate_review' WHERE layer_id = ?", [(row["layer_id"],) for row in members])
        add_history(connection, submission_id, "duplicate_group", group_id, "duplicate_group_review_updated", str(payload.get("reviewer", "")), dict(before), allowed)
        connection.commit()
    return duplicate_group_detail(root, submission_id, group_id) or {}


def staging_plan(root: Path, submission_id: str) -> list[dict[str, Any]]:
    with connect(root) as connection:
        rows = connection.execute("SELECT * FROM staging_plan_items WHERE submission_id = ? ORDER BY proposed_target_name", (submission_id,)).fetchall()
    return [safe_staging_item(dict(row)) for row in rows]


def update_staging_plan_item(root: Path, submission_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with connect(root) as connection:
        before = connection.execute("SELECT * FROM staging_plan_items WHERE submission_id = ? AND staging_plan_item_id = ?", (submission_id, item_id)).fetchone()
        if not before:
            raise KeyError("Staging plan item not found.")
        item = dict(before)
        layer = connection.execute("SELECT * FROM inspected_layers WHERE layer_id = ?", (item["layer_id"],)).fetchone()
        gate_blocker = approval_gate_blocker(dict(layer) if layer else {}, item)
        approved = bool(payload.get("approved_for_staging", item.get("approved_for_staging")))
        if approved and gate_blocker:
            payload = {**payload, "approved_for_staging": False, "approval_status": "blocked", "blocker": gate_blocker}
        allowed = {key: payload[key] for key in ["approved_for_staging", "approval_status", "blocker", "reviewer", "reviewed_at", "target_spatial_reference"] if key in payload}
        if "approved_for_staging" in allowed:
            allowed["approved_for_staging"] = int(bool(allowed["approved_for_staging"]))
        if allowed.get("approved_for_staging") and not allowed.get("reviewed_at"):
            allowed["reviewed_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in allowed)
        if assignments:
            connection.execute(f"UPDATE staging_plan_items SET {assignments} WHERE staging_plan_item_id = ?", (*allowed.values(), item_id))
            connection.execute(
                "UPDATE inspected_layers SET staging_status = ? WHERE layer_id = ?",
                ("approved_for_staging" if allowed.get("approved_for_staging") else str(allowed.get("approval_status", "not_approved")), item["layer_id"]),
            )
            add_history(connection, submission_id, "staging_plan_item", item_id, "staging_plan_review_updated", str(payload.get("reviewer", "")), item, allowed)
        connection.commit()
    return next((row for row in staging_plan(root, submission_id) if row["staging_plan_item_id"] == item_id), {})


def approval_gate_blocker(layer: dict[str, Any], item: dict[str, Any]) -> str:
    blockers: list[str] = []
    if layer.get("latest_review_status") not in {"classification_approved", "reference_approved", "approved_for_staging"}:
        blockers.append("classification review not approved")
    if layer.get("duplicate_status") == "potential_duplicate":
        blockers.append("duplicate review unresolved")
    if layer.get("coordinate_status") not in {"coordinate_ready", "mixed_source_spatial_references"}:
        blockers.append("coordinate review required")
    if layer.get("sensitivity_status") != "sensitivity_review_complete":
        blockers.append("sensitivity review incomplete")
    if not item.get("proposed_target_name"):
        blockers.append("target name unavailable")
    return "; ".join(blockers)


def add_history(connection: sqlite3.Connection, submission_id: str, subject_type: str, subject_id: str, event_type: str, actor: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    connection.execute(
        """
        INSERT INTO inspection_review_history
        (history_id, submission_id, subject_type, subject_id, event_type, actor, before_json, after_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), submission_id, subject_type, subject_id, event_type, actor, dumps(before), dumps(after), utc_now()),
    )


def candidates_by_layer(connection: sqlite3.Connection, layer_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not layer_ids:
        return {}
    placeholders = ", ".join("?" for _ in layer_ids)
    rows = connection.execute(f"SELECT * FROM layer_classification_candidates WHERE layer_id IN ({placeholders}) ORDER BY layer_id, rank", layer_ids).fetchall()
    output: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        output.setdefault(row["layer_id"], []).append(safe_candidate(dict(row)))
    return output


def decorate_layer(row: dict[str, Any], candidates: list[dict[str, Any]], *, detail: bool) -> dict[str, Any]:
    top = candidates[0] if candidates else {}
    payload = {
        "layer_id": row.get("layer_id", ""),
        "submission_id": row.get("submission_id", ""),
        "container_id": row.get("container_id", ""),
        "source_layer_name": row.get("source_layer_name", ""),
        "source_layer_alias": row.get("source_layer_alias", ""),
        "source_schema": row.get("source_schema", ""),
        "source_owner_prefix": row.get("source_owner_prefix", ""),
        "feature_dataset": row.get("feature_dataset", ""),
        "owner_or_jurisdiction": row.get("owner_or_jurisdiction", top.get("owner_or_jurisdiction", "")),
        "utility_system": top.get("utility_system", "review_required"),
        "network_group": top.get("network_group", "unknown"),
        "asset_category": top.get("asset_category", "unknown"),
        "asset_subcategory": top.get("asset_subcategory", "unknown"),
        "operational_role": top.get("operational_role", row.get("operational_role", "")),
        "lifecycle_representation": top.get("lifecycle_representation", row.get("lifecycle_representation", "")),
        "confidence": top.get("confidence", row.get("classification_status", "")),
        "score": top.get("score", 0),
        "object_type": row.get("object_type", ""),
        "geometry_type": row.get("geometry_type", ""),
        "record_count": row.get("record_count"),
        "spatial_reference_name": row.get("spatial_reference_name", ""),
        "spatial_reference_wkid": row.get("spatial_reference_wkid"),
        "linear_unit": row.get("linear_unit", ""),
        "angular_unit": row.get("angular_unit", ""),
        "has_z": bool(row.get("has_z")),
        "has_m": bool(row.get("has_m")),
        "field_count": row.get("field_count", 0),
        "likely_id_fields": loads(row.get("likely_id_fields_json"), []),
        "likely_status_fields": loads(row.get("likely_status_fields_json"), []),
        "likely_date_fields": loads(row.get("likely_date_fields_json"), []),
        "likely_dimension_fields": loads(row.get("likely_dimension_fields_json"), []),
        "likely_owner_fields": loads(row.get("likely_owner_fields_json"), []),
        "domain_names": loads(row.get("domain_names_json"), []),
        "subtype_summary": row.get("subtype_summary", ""),
        "relationship_summary": row.get("relationship_summary", ""),
        "attachment_status": row.get("attachment_status", ""),
        "editor_tracking_status": row.get("editor_tracking_status", ""),
        "proposed_or_existing_signal": row.get("proposed_or_existing_signal", ""),
        "classification_status": row.get("classification_status", ""),
        "duplicate_status": row.get("duplicate_status", ""),
        "coordinate_status": row.get("coordinate_status", ""),
        "sensitivity_status": row.get("sensitivity_status", ""),
        "staging_status": row.get("staging_status", ""),
        "routing_state": row.get("routing_state", ""),
        "latest_review_status": row.get("latest_review_status", ""),
        "latest_reviewer": row.get("latest_reviewer", ""),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
    }
    if detail:
        payload.update(
            {
                "extent_summary": loads(row.get("extent_summary_json"), {}),
                "field_profile": loads(row.get("field_profile_json"), []),
                "domain_profile": loads(row.get("domain_profile_json"), {}),
                "subtype_profile": loads(row.get("subtype_profile_json"), {}),
                "relationship_profile": loads(row.get("relationship_profile_json"), []),
                "classification_candidates": candidates,
            }
        )
    return payload


def safe_container(row: dict[str, Any]) -> dict[str, Any]:
    row["warnings"] = loads(row.pop("warnings_json", ""), [])
    row["blockers"] = loads(row.pop("blockers_json", ""), [])
    return row


def safe_candidate(row: dict[str, Any]) -> dict[str, Any]:
    row["evidence"] = loads(row.pop("evidence_json", ""), [])
    row["warnings"] = loads(row.pop("warnings_json", ""), [])
    return row


def safe_duplicate_group(connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
    members = connection.execute(
        """
        SELECT m.duplicate_group_id, m.layer_id, l.source_layer_name, l.geometry_type, l.record_count, m.member_role, m.similarity_score, m.notes
        FROM duplicate_group_members m
        LEFT JOIN inspected_layers l ON l.layer_id = m.layer_id
        WHERE m.duplicate_group_id = ?
        ORDER BY l.source_layer_name
        """,
        (row["duplicate_group_id"],),
    ).fetchall()
    row["members"] = [dict(member) for member in members]
    return row


def safe_staging_item(row: dict[str, Any]) -> dict[str, Any]:
    row["projection_required"] = bool(row.get("projection_required"))
    row["approved_for_staging"] = bool(row.get("approved_for_staging"))
    return row


def safe_review(row: dict[str, Any]) -> dict[str, Any]:
    row["data_owner_confirmation_required"] = bool(row.get("data_owner_confirmation_required"))
    row["engineering_review_required"] = bool(row.get("engineering_review_required"))
    return row


def dumps(value: Any) -> str:
    return json.dumps(value if value is not None else "", separators=(",", ":"), sort_keys=True)


def loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default
