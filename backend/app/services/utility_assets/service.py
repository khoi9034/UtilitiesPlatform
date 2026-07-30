from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from app.core.local_storage import require_runtime_data_root
from app.services import intake_registry_service
from app.services.source_inspection import registry as inspection_registry

from .domain import RULE_VERSION, stable_fingerprint, stable_id, taxonomy, validate_mapping, validate_vertical_and_class
from .synthetic import synthetic_assets, synthetic_relationships

_INITIALIZE_LOCK = threading.Lock()


class UtilityAssetError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


class UtilityAssetService:
    def root(self) -> Path:
        return require_runtime_data_root()

    def connect(self) -> sqlite3.Connection:
        connection = intake_registry_service.connect(self.root())
        connection.execute("PRAGMA busy_timeout = 30000")
        # ponytail: process-local lock is enough for the local single-worker app; use migrations for multi-worker deployment.
        with _INITIALIZE_LOCK:
            inspection_registry.initialize(connection)
            self._initialize(connection)
            self._seed_synthetic(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS canonical_utility_assets (
                asset_id TEXT PRIMARY KEY,
                utility_vertical TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                asset_subtype TEXT,
                canonical_name TEXT NOT NULL,
                display_name TEXT,
                geometry_type TEXT,
                geometry_reference TEXT,
                lifecycle_status TEXT NOT NULL,
                operational_status TEXT NOT NULL,
                owner_candidate TEXT,
                owner_status TEXT,
                jurisdiction TEXT,
                source_system TEXT NOT NULL,
                source_submission_id TEXT NOT NULL,
                source_layer_id TEXT NOT NULL,
                source_record_id TEXT NOT NULL,
                source_asset_identifier TEXT,
                source_fingerprint TEXT,
                parent_asset_id TEXT,
                container_asset_id TEXT,
                connected_from_asset_id TEXT,
                connected_to_asset_id TEXT,
                network_level TEXT,
                work_order_id TEXT,
                qa_status TEXT NOT NULL,
                review_status TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                confidence TEXT,
                installation_date TEXT,
                retirement_date TEXT,
                last_inspected_at TEXT,
                last_reviewed_at TEXT,
                notes TEXT,
                source_attributes_json TEXT NOT NULL,
                canonical_attributes_json TEXT NOT NULL,
                geometry_summary_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                canonicalization_plan_id TEXT,
                mapping_rule_version TEXT,
                is_synthetic INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (source_submission_id, source_layer_id, source_record_id, utility_vertical, asset_class)
            );
            CREATE INDEX IF NOT EXISTS idx_canonical_assets_vertical_class
                ON canonical_utility_assets(utility_vertical, asset_class);

            CREATE TABLE IF NOT EXISTS utility_asset_relationships (
                relationship_id TEXT PRIMARY KEY,
                from_asset_id TEXT NOT NULL,
                to_asset_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                confidence TEXT,
                source TEXT NOT NULL,
                provisional INTEGER NOT NULL DEFAULT 1,
                confirmed_by TEXT,
                confirmed_at TEXT,
                evidence_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (from_asset_id, to_asset_id, relationship_type)
            );

            CREATE TABLE IF NOT EXISTS canonicalization_plans (
                plan_id TEXT PRIMARY KEY,
                plan_fingerprint TEXT NOT NULL UNIQUE,
                submission_id TEXT NOT NULL,
                layer_id TEXT NOT NULL,
                utility_vertical TEXT NOT NULL,
                target_asset_class TEXT NOT NULL,
                status TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                source_record_count INTEGER NOT NULL,
                preview_record_count INTEGER NOT NULL,
                mapped_field_count INTEGER NOT NULL,
                unmapped_field_count INTEGER NOT NULL,
                warnings_json TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                preview_records_json TEXT NOT NULL,
                approved_for_canonicalization INTEGER NOT NULL DEFAULT 0,
                approved_by TEXT,
                approved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (submission_id, layer_id)
            );

            CREATE TABLE IF NOT EXISTS canonical_field_mappings (
                mapping_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                source_field TEXT NOT NULL,
                source_alias TEXT,
                canonical_field TEXT,
                transformation_type TEXT NOT NULL,
                confidence TEXT,
                evidence_json TEXT NOT NULL,
                mapping_status TEXT NOT NULL,
                reviewer_type TEXT NOT NULL,
                human_override INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (plan_id, source_field)
            );

            CREATE TABLE IF NOT EXISTS canonicalization_history (
                history_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                action TEXT NOT NULL,
                prior_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor TEXT,
                reason TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS utility_asset_history (
                history_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                action TEXT NOT NULL,
                event_json TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS utility_asset_seed_versions (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """
        )
        connection.commit()

    def _seed_synthetic(self, connection: sqlite3.Connection) -> None:
        seed_version = "synthetic-assets-v5-network-trace"
        if connection.execute("SELECT 1 FROM utility_asset_seed_versions WHERE version = ?", (seed_version,)).fetchone():
            return
        assets = synthetic_assets()
        for asset in assets:
            if self._insert_asset(connection, asset):
                self._add_asset_history(connection, asset["asset_id"], "synthetic_asset_seeded", {"source": seed_version})
            else:
                connection.execute(
                    """UPDATE canonical_utility_assets SET canonical_attributes_json = ?, updated_at = ?
                    WHERE asset_id = ? AND is_synthetic = 1""",
                    (_dump(asset.get("canonical_attributes_json", {})), asset["updated_at"], asset["asset_id"]),
                )
        connection.execute(
            """DELETE FROM utility_asset_relationships
            WHERE from_asset_id IN (SELECT asset_id FROM canonical_utility_assets WHERE is_synthetic = 1)
              AND to_asset_id IN (SELECT asset_id FROM canonical_utility_assets WHERE is_synthetic = 1)"""
        )
        for relationship in synthetic_relationships(assets):
            connection.execute(
                """INSERT OR IGNORE INTO utility_asset_relationships
                (relationship_id, from_asset_id, to_asset_id, relationship_type, direction, confidence, source,
                 provisional, confirmed_by, confirmed_at, evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    relationship["relationship_id"], relationship["from_asset_id"], relationship["to_asset_id"],
                    relationship["relationship_type"], relationship["direction"], relationship["confidence"],
                    relationship["source"], int(relationship["provisional"]), relationship["confirmed_by"],
                    relationship["confirmed_at"], _dump(relationship["evidence_json"]), relationship["created_at"],
                ),
            )
        self._seed_plans(connection, assets)
        connection.execute(
            "INSERT INTO utility_asset_seed_versions (version, applied_at) VALUES (?, ?)",
            (seed_version, intake_registry_service.utc_now()),
        )
        connection.commit()

    def _seed_plans(self, connection: sqlite3.Connection, assets: list[dict[str, Any]]) -> None:
        now = "2026-07-26T12:00:00+00:00"
        for vertical, asset_class, status, approved in (
            ("electric_distribution", "transformer", "approved", True),
            ("telecom_fiber", "fiber_cable", "mapping_review", False),
        ):
            submission_id = "DEMO-ELEC-001" if vertical == "electric_distribution" else "DEMO-FIBER-001"
            layer_id = f"demo-plan-{vertical}-{asset_class}"
            source_fingerprint = stable_fingerprint(submission_id, layer_id, "synthetic-v1")
            plan_id = stable_id("plan", submission_id, layer_id)
            preview = [
                {"source_record_id": row["source_record_id"], "source_asset_identifier": row["source_asset_identifier"]}
                for row in assets if row["utility_vertical"] == vertical and row["asset_class"] == asset_class
            ][:3]
            connection.execute(
                """INSERT OR IGNORE INTO canonicalization_plans
                (plan_id, plan_fingerprint, submission_id, layer_id, utility_vertical, target_asset_class, status,
                 rule_version, source_fingerprint, source_record_count, preview_record_count, mapped_field_count,
                 unmapped_field_count, warnings_json, blockers_json, preview_records_json,
                 approved_for_canonicalization, approved_by, approved_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan_id, stable_fingerprint(submission_id, layer_id, source_fingerprint, vertical, asset_class, RULE_VERSION),
                    submission_id, layer_id, vertical, asset_class, status, RULE_VERSION, source_fingerprint,
                    len(preview), len(preview), 3, 1, _dump(["Synthetic preview only."]), "[]", _dump(preview),
                    int(approved), "Demo Reviewer" if approved else "", now if approved else "", now, now,
                ),
            )
            for source_field, canonical_field in (
                ("SOURCE_ID", "source_asset_identifier"),
                ("STATUS", "lifecycle_status"),
                ("TYPE", "asset_subtype"),
            ):
                connection.execute(
                    """INSERT OR IGNORE INTO canonical_field_mappings
                    (mapping_id, plan_id, source_field, source_alias, canonical_field, transformation_type,
                     confidence, evidence_json, mapping_status, reviewer_type, human_override, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        stable_id("map", plan_id, source_field), plan_id, source_field, source_field.title(),
                        canonical_field, "renamed" if source_field != "STATUS" else "lifecycle_mapping",
                        "high", _dump({"source": "synthetic schema"}), "accepted", "human",
                        0, "Synthetic demonstration mapping.", now, now,
                    ),
                )
            self._add_plan_history(connection, plan_id, "plan_seeded", {}, {"status": status}, "system", "synthetic_seed", "")

    def taxonomy(self, vertical: str | None = None) -> dict[str, Any]:
        return taxonomy(vertical)

    def list_assets(self, filters: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "utility_vertical", "asset_class", "asset_subtype", "lifecycle_status", "operational_status",
            "qa_status", "review_status", "owner_status", "source_layer_id",
        }
        clauses: list[str] = []
        values: list[Any] = []
        for key in allowed:
            if filters.get(key):
                clauses.append(f"a.{key} = ?")
                values.append(str(filters[key]))
        if filters.get("provisional_relationships") is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM utility_asset_relationships r WHERE "
                "(r.from_asset_id = a.asset_id OR r.to_asset_id = a.asset_id) AND r.provisional = ?)"
            )
            values.append(int(bool(filters["provisional_relationships"])))
        if filters.get("search"):
            clauses.append("(a.canonical_name LIKE ? OR a.display_name LIKE ? OR a.asset_id LIKE ?)")
            needle = f"%{str(filters['search'])[:100]}%"
            values.extend([needle, needle, needle])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit, offset = int(filters.get("limit", 100)), int(filters.get("offset", 0))
        with self.connect() as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM canonical_utility_assets a {where}", values).fetchone()[0])
            rows = connection.execute(
                f"""SELECT a.*,
                (SELECT COUNT(*) FROM utility_asset_relationships r
                 WHERE r.from_asset_id = a.asset_id OR r.to_asset_id = a.asset_id) AS relationship_count,
                EXISTS (SELECT 1 FROM utility_asset_relationships r
                 WHERE (r.from_asset_id = a.asset_id OR r.to_asset_id = a.asset_id) AND r.provisional = 1) AS has_provisional_relationships
                FROM canonical_utility_assets a {where}
                ORDER BY a.utility_vertical, a.asset_class, a.canonical_name LIMIT ? OFFSET ?""",
                (*values, limit, offset),
            ).fetchall()
        return {
            "items": [self._safe_asset(dict(row), detail=False) for row in rows],
            "pagination": {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total},
            "summary": self.summary(),
            "message": "Synthetic canonical asset registry loaded." if total else "No canonical utility assets exist.",
        }

    def summary(self) -> dict[str, Any]:
        with self.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM canonical_utility_assets").fetchone()[0])
            by_vertical = _counts(connection, "canonical_utility_assets", "utility_vertical")
            lifecycle = _counts(connection, "canonical_utility_assets", "lifecycle_status")
            qa = _counts(connection, "canonical_utility_assets", "qa_status")
            needs_review = int(connection.execute("SELECT COUNT(*) FROM canonical_utility_assets WHERE review_status = 'needs_review'").fetchone()[0])
            provisional = int(connection.execute("SELECT COUNT(*) FROM utility_asset_relationships WHERE provisional = 1").fetchone()[0])
            plan_rows = connection.execute("SELECT status, COUNT(*) count FROM canonicalization_plans GROUP BY status").fetchall()
        plans = {row["status"]: row["count"] for row in plan_rows}
        return {
            "total_assets": total, "electric_assets": by_vertical.get("electric_distribution", 0),
            "telecom_assets": by_vertical.get("telecom_fiber", 0), "assets_needing_review": needs_review,
            "water_assets": by_vertical.get("water", 0),
            "wastewater_assets": by_vertical.get("wastewater", 0),
            "provisional_relationships": provisional, "canonicalization_plans": plans,
            "active_plans": sum(value for key, value in plans.items() if key not in {"approved", "deferred", "created"}),
            "approved_plans": plans.get("approved", 0), "blocked_plans": plans.get("blocked", 0),
            "lifecycle_distribution": lifecycle, "qa_status_distribution": qa,
            "data_scope": "synthetic", "message": "Local application registry contains synthetic utility assets only.",
        }

    def domain_summary(self, verticals: tuple[str, ...]) -> dict[str, Any]:
        placeholders = ",".join("?" for _ in verticals)
        with self.connect() as connection:
            assets = _counts_where(connection, "canonical_utility_assets", "utility_vertical", verticals)
            plans = _counts_where(connection, "canonicalization_plans", "utility_vertical", verticals)
            counts = {
                "registered_sources": _count_where(connection, "inspection_containers", "package_utility_system", verticals),
                "inspected_layers": _count_where(connection, "layer_classification_candidates", "utility_system", verticals, distinct="layer_id"),
                "proposed_classifications": _count_where(connection, "layer_classification_candidates", "utility_system", verticals),
                "qa_runs": _count_where(connection, "connectivity_qa_runs", "utility_vertical", verticals),
                "trace_runs": _count_where(connection, "network_trace_runs", "utility_vertical", verticals),
                "proposed_edits": _count_where(connection, "proposed_edit_proposals", "utility_vertical", verticals),
                "work_orders": _count_where(connection, "utility_work_orders", "utility_vertical", verticals),
            }
            unresolved = 0
            if _table_exists(connection, "automated_layer_state"):
                unresolved = int(connection.execute(
                    f"""SELECT COUNT(*) FROM automated_layer_state
                    WHERE approved_utility_system IN ({placeholders})
                    AND (taxonomy_status != 'approved' OR staging_readiness != 'fully_ready_for_staging_review')""",
                    verticals,
                ).fetchone()[0])
        return {
            "domain_family": "water_wastewater",
            "label": "Water & Wastewater",
            **counts,
            "water_asset_candidates": assets.get("water", 0),
            "wastewater_asset_candidates": assets.get("wastewater", 0),
            "canonical_assets": sum(assets.values()),
            "canonicalization_plans": sum(plans.values()),
            "unresolved_exceptions": unresolved,
            "human_approval_required": True,
            "message": "Domain summary uses safe local registry counts; no source records or paths are returned.",
        }

    def asset(self, asset_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT a.*, (SELECT COUNT(*) FROM utility_asset_relationships r
                WHERE r.from_asset_id = a.asset_id OR r.to_asset_id = a.asset_id) relationship_count
                FROM canonical_utility_assets a WHERE asset_id = ?""", (asset_id,),
            ).fetchone()
        return self._safe_asset(dict(row), detail=True) if row else None

    def relationships(self, asset_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT r.*, target.canonical_name connected_asset_name, target.asset_class connected_asset_class
                FROM utility_asset_relationships r
                JOIN canonical_utility_assets target
                  ON target.asset_id = CASE WHEN r.from_asset_id = ? THEN r.to_asset_id ELSE r.from_asset_id END
                WHERE r.from_asset_id = ? OR r.to_asset_id = ? ORDER BY r.relationship_type, target.canonical_name""",
                (asset_id, asset_id, asset_id),
            ).fetchall()
        return {"items": [_safe_json_row(dict(row), ("evidence_json",)) for row in rows]}

    def lineage(self, asset_id: str) -> dict[str, Any]:
        asset = self.asset(asset_id)
        if not asset:
            raise UtilityAssetError("Asset not found.", 404)
        with self.connect() as connection:
            events = connection.execute(
                "SELECT action, event_json, actor_type, actor, created_at FROM utility_asset_history WHERE asset_id = ? ORDER BY created_at",
                (asset_id,),
            ).fetchall()
        return {
            "asset_id": asset_id,
            "source": {
                "source_system": asset["source_system"], "source_submission_id": asset["source_submission_id"],
                "source_layer_id": asset["source_layer_id"], "source_record_id": asset["source_record_id"],
                "source_fingerprint": asset["source_fingerprint"],
            },
            "canonicalization_plan_id": asset.get("canonicalization_plan_id", ""),
            "mapping_rule_version": asset.get("mapping_rule_version", ""),
            "history": [_safe_json_row(dict(row), ("event_json",)) for row in events],
        }

    def create_plan(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        vertical = str(payload.get("utility_vertical", ""))
        asset_class = str(payload.get("target_asset_class", ""))
        try:
            validate_vertical_and_class(vertical, asset_class)
        except ValueError as exc:
            raise UtilityAssetError(str(exc)) from exc
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM canonicalization_plans WHERE submission_id = ? AND layer_id = ?", (submission_id, layer_id),
            ).fetchone()
            if existing:
                return self._plan(connection, dict(existing))
            layer = connection.execute(
                """SELECT l.*, s.sha256 submission_sha, p.approved_for_staging
                FROM inspected_layers l JOIN intake_submissions s ON s.submission_id = l.submission_id
                LEFT JOIN staging_plan_items p ON p.layer_id = l.layer_id
                WHERE l.submission_id = ? AND l.layer_id = ?""", (submission_id, layer_id),
            ).fetchone()
            if not layer:
                raise UtilityAssetError("Reviewed source layer not found.", 404)
            layer_row = dict(layer)
            if not bool(layer_row.get("approved_for_staging")):
                raise UtilityAssetError(
                    "Not eligible for canonicalization. Human source-review and staging blockers remain unresolved.", 409,
                )
            source_fingerprint = self._source_fingerprint(layer_row)
            now = intake_registry_service.utc_now()
            plan_id = stable_id("plan", submission_id, layer_id)
            plan_fingerprint = stable_fingerprint(submission_id, layer_id, source_fingerprint, vertical, asset_class, RULE_VERSION)
            connection.execute(
                """INSERT INTO canonicalization_plans
                (plan_id, plan_fingerprint, submission_id, layer_id, utility_vertical, target_asset_class, status,
                 rule_version, source_fingerprint, source_record_count, preview_record_count, mapped_field_count,
                 unmapped_field_count, warnings_json, blockers_json, preview_records_json,
                 approved_for_canonicalization, approved_by, approved_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'mapping_review', ?, ?, ?, 0, 0, ?, ?, '[]', '[]', 0, '', '', ?, ?)""",
                (
                    plan_id, plan_fingerprint, submission_id, layer_id, vertical, asset_class, RULE_VERSION,
                    source_fingerprint, int(layer_row.get("record_count") or 0),
                    int(layer_row.get("field_count") or 0), _dump(["Record preview awaits an approved source adapter."]), now, now,
                ),
            )
            self._add_plan_history(connection, plan_id, "plan_created", {}, {"status": "mapping_review"}, "human", str(payload.get("actor", "")), "")
            connection.commit()
            row = connection.execute("SELECT * FROM canonicalization_plans WHERE plan_id = ?", (plan_id,)).fetchone()
            return self._plan(connection, dict(row))

    def get_plan(self, submission_id: str, layer_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM canonicalization_plans WHERE submission_id = ? AND layer_id = ?", (submission_id, layer_id),
            ).fetchone()
            if not row:
                return {
                    "eligible": False, "status": "not_eligible",
                    "approved_for_canonicalization": False,
                    "reason": "Human source-review and staging blockers remain unresolved.",
                }
            return self._plan(connection, dict(row))

    def list_plans(self) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM canonicalization_plans ORDER BY created_at DESC").fetchall()
            return {"items": [self._plan(connection, dict(row)) for row in rows]}

    def update_mappings(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        mappings = payload.get("mappings")
        if not isinstance(mappings, list) or not mappings:
            raise UtilityAssetError("At least one field mapping is required.")
        try:
            normalized = [validate_mapping(dict(item)) for item in mappings if isinstance(item, dict)]
        except ValueError as exc:
            raise UtilityAssetError(str(exc)) from exc
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            prior = [dict(row) for row in connection.execute("SELECT * FROM canonical_field_mappings WHERE plan_id = ?", (plan["plan_id"],)).fetchall()]
            now = intake_registry_service.utc_now()
            for mapping in normalized:
                connection.execute(
                    """INSERT INTO canonical_field_mappings
                    (mapping_id, plan_id, source_field, source_alias, canonical_field, transformation_type, confidence,
                     evidence_json, mapping_status, reviewer_type, human_override, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(plan_id, source_field) DO UPDATE SET
                    source_alias=excluded.source_alias, canonical_field=excluded.canonical_field,
                    transformation_type=excluded.transformation_type, confidence=excluded.confidence,
                    evidence_json=excluded.evidence_json, mapping_status=excluded.mapping_status,
                    reviewer_type=excluded.reviewer_type, human_override=excluded.human_override,
                    notes=excluded.notes, updated_at=excluded.updated_at""",
                    (
                        stable_id("map", plan["plan_id"], mapping["source_field"]), plan["plan_id"],
                        mapping["source_field"], mapping["source_alias"], mapping["canonical_field"],
                        mapping["transformation_type"], mapping["confidence"], _dump(mapping["evidence_json"]),
                        mapping["mapping_status"], mapping["reviewer_type"], int(mapping["human_override"]),
                        mapping["notes"], now, now,
                    ),
                )
            mapped = sum(row["transformation_type"] != "unmapped" for row in normalized)
            connection.execute(
                """UPDATE canonicalization_plans SET mapped_field_count = ?, unmapped_field_count = ?,
                status = 'mapping_review', approved_for_canonicalization = 0, approved_by = '', approved_at = '', updated_at = ?
                WHERE plan_id = ?""", (mapped, len(normalized) - mapped, now, plan["plan_id"]),
            )
            self._add_plan_history(connection, plan["plan_id"], "field_mappings_updated", prior, normalized, "human", str(payload.get("actor", "")), str(payload.get("reason", "")))
            connection.commit()
            updated = connection.execute("SELECT * FROM canonicalization_plans WHERE plan_id = ?", (plan["plan_id"],)).fetchone()
            return self._plan(connection, dict(updated))

    def approve_plan(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        actor = str(payload.get("approved_by", "")).strip()
        if not actor:
            raise UtilityAssetError("approved_by is required.")
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            if _load(plan["blockers_json"], []):
                raise UtilityAssetError("Plan blockers must be resolved before approval.", 409)
            mapping_count = int(connection.execute("SELECT COUNT(*) FROM canonical_field_mappings WHERE plan_id = ?", (plan["plan_id"],)).fetchone()[0])
            if not mapping_count:
                raise UtilityAssetError("Field mappings must be reviewed before approval.", 409)
            now = intake_registry_service.utc_now()
            connection.execute(
                """UPDATE canonicalization_plans SET status = 'approved', approved_for_canonicalization = 1,
                approved_by = ?, approved_at = ?, updated_at = ? WHERE plan_id = ?""",
                (actor, now, now, plan["plan_id"]),
            )
            self._add_plan_history(connection, plan["plan_id"], "plan_approved", {"approved": False}, {"approved": True}, "human", actor, str(payload.get("reason", "")))
            connection.commit()
            updated = connection.execute("SELECT * FROM canonicalization_plans WHERE plan_id = ?", (plan["plan_id"],)).fetchone()
            return self._plan(connection, dict(updated))

    def defer_plan(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            raise UtilityAssetError("A defer reason is required.")
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            now = intake_registry_service.utc_now()
            connection.execute(
                """UPDATE canonicalization_plans SET status = 'deferred', approved_for_canonicalization = 0,
                approved_by = '', approved_at = '', updated_at = ? WHERE plan_id = ?""", (now, plan["plan_id"]),
            )
            self._add_plan_history(connection, plan["plan_id"], "plan_deferred", {"status": plan["status"]}, {"status": "deferred"}, "human", str(payload.get("actor", "")), reason)
            connection.commit()
            updated = connection.execute("SELECT * FROM canonicalization_plans WHERE plan_id = ?", (plan["plan_id"],)).fetchone()
            return self._plan(connection, dict(updated))

    def create_assets(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        actor = str(payload.get("actor", "")).strip()
        if not actor:
            raise UtilityAssetError("actor is required.")
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            if not bool(plan["approved_for_canonicalization"]):
                raise UtilityAssetError("Canonical asset creation requires a previously approved plan.", 409)
            current_fingerprint = self._current_source_fingerprint(connection, plan)
            if current_fingerprint != plan["source_fingerprint"]:
                raise UtilityAssetError("Source metadata changed after plan approval. Recreate the plan.", 409)
            preview_records = _load(plan["preview_records_json"], [])
            if not preview_records:
                raise UtilityAssetError("No approved record adapter is available for this source layer.", 409)
            created = 0
            existing = 0
            now = intake_registry_service.utc_now()
            for record in preview_records:
                source_record_id = str(record["source_record_id"])
                asset_id = stable_id("asset", plan["utility_vertical"], submission_id, layer_id, source_record_id)
                if connection.execute("SELECT 1 FROM canonical_utility_assets WHERE asset_id = ?", (asset_id,)).fetchone():
                    existing += 1
                    continue
                asset = {
                    "asset_id": asset_id, "utility_vertical": plan["utility_vertical"],
                    "asset_class": plan["target_asset_class"], "asset_subtype": "",
                    "canonical_name": str(record.get("source_asset_identifier") or asset_id),
                    "display_name": str(record.get("source_asset_identifier") or asset_id), "geometry_type": "unknown",
                    "lifecycle_status": "unknown", "operational_status": "unknown", "owner_candidate": "",
                    "owner_status": "unknown", "jurisdiction": "", "source_system": "approved_canonicalization_plan",
                    "source_submission_id": submission_id, "source_layer_id": layer_id,
                    "source_record_id": source_record_id, "source_asset_identifier": str(record.get("source_asset_identifier", "")),
                    "parent_asset_id": "", "container_asset_id": "", "connected_from_asset_id": "",
                    "connected_to_asset_id": "", "network_level": "", "work_order_id": "",
                    "qa_status": "not_evaluated", "review_status": "imported", "sensitivity": "restricted",
                    "confidence": "medium", "installation_date": "", "retirement_date": "",
                    "last_inspected_at": "", "last_reviewed_at": "", "created_at": now, "updated_at": now,
                    "notes": "Created from a human-approved canonicalization plan.",
                    "source_attributes_json": {"source_record_id": source_record_id},
                    "canonical_attributes_json": {}, "geometry_summary_json": {"geometry_type": "unknown"},
                    "evidence_json": {"value_provenance": "human_approved_plan", "plan_id": plan["plan_id"]},
                    "canonicalization_plan_id": plan["plan_id"], "mapping_rule_version": plan["rule_version"],
                    "source_fingerprint": plan["source_fingerprint"], "is_synthetic": submission_id.startswith("DEMO-"),
                }
                if self._insert_asset(connection, asset):
                    self._add_asset_history(connection, asset_id, "canonical_asset_created", {"plan_id": plan["plan_id"]}, actor)
                    created += 1
                else:
                    existing += 1
            connection.execute("UPDATE canonicalization_plans SET status = 'created', updated_at = ? WHERE plan_id = ?", (now, plan["plan_id"]))
            self._add_plan_history(connection, plan["plan_id"], "canonical_assets_created", {}, {"created": created, "existing": existing}, "human", actor, "")
            connection.commit()
        return {"plan_id": plan["plan_id"], "created_count": created, "existing_count": existing, "source_geometry_modified": False, "staging_geometry_modified": False, "published": False}

    def _source_fingerprint(self, layer: dict[str, Any]) -> str:
        return stable_fingerprint(
            layer.get("submission_sha", ""), layer.get("layer_id", ""), layer.get("source_layer_name", ""),
            layer.get("record_count", 0), layer.get("field_profile_json", ""), layer.get("geometry_type", ""),
            layer.get("spatial_reference_wkid", ""),
        )

    def _current_source_fingerprint(self, connection: sqlite3.Connection, plan: dict[str, Any]) -> str:
        if str(plan["submission_id"]).startswith("DEMO-"):
            return plan["source_fingerprint"]
        layer = connection.execute(
            """SELECT l.*, s.sha256 submission_sha FROM inspected_layers l
            JOIN intake_submissions s ON s.submission_id = l.submission_id
            WHERE l.submission_id = ? AND l.layer_id = ?""", (plan["submission_id"], plan["layer_id"]),
        ).fetchone()
        return self._source_fingerprint(dict(layer)) if layer else ""

    def _required_plan(self, connection: sqlite3.Connection, submission_id: str, layer_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM canonicalization_plans WHERE submission_id = ? AND layer_id = ?", (submission_id, layer_id),
        ).fetchone()
        if not row:
            raise UtilityAssetError("Canonicalization plan not found.", 404)
        return dict(row)

    def _plan(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        mappings = connection.execute(
            """SELECT mapping_id, source_field, source_alias, canonical_field, transformation_type, confidence,
            evidence_json, mapping_status, reviewer_type, human_override, notes, created_at, updated_at
            FROM canonical_field_mappings WHERE plan_id = ? ORDER BY source_field""", (row["plan_id"],),
        ).fetchall()
        history = connection.execute(
            """SELECT history_id, action, actor_type, actor, reason, created_at
            FROM canonicalization_history WHERE plan_id = ? ORDER BY created_at""", (row["plan_id"],),
        ).fetchall()
        safe = {key: value for key, value in row.items() if key not in {"preview_records_json"}}
        safe.update({
            "approved_for_canonicalization": bool(row["approved_for_canonicalization"]),
            "warnings": _load(row["warnings_json"], []), "blockers": _load(row["blockers_json"], []),
            "mappings": [_safe_json_row(dict(mapping), ("evidence_json",)) for mapping in mappings],
            "history": [dict(event) for event in history],
            "eligible": True,
            "preview_records": [
                {"source_record_id": item.get("source_record_id", ""), "source_asset_identifier": item.get("source_asset_identifier", "")}
                for item in _load(row["preview_records_json"], [])
            ],
        })
        safe.pop("warnings_json", None)
        safe.pop("blockers_json", None)
        return safe

    def _insert_asset(self, connection: sqlite3.Connection, asset: dict[str, Any]) -> bool:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO canonical_utility_assets
            (asset_id, utility_vertical, asset_class, asset_subtype, canonical_name, display_name, geometry_type,
             geometry_reference, lifecycle_status, operational_status, owner_candidate, owner_status, jurisdiction,
             source_system, source_submission_id, source_layer_id, source_record_id, source_asset_identifier,
             source_fingerprint, parent_asset_id, container_asset_id, connected_from_asset_id, connected_to_asset_id,
             network_level, work_order_id, qa_status, review_status, sensitivity, confidence, installation_date,
             retirement_date, last_inspected_at, last_reviewed_at, notes, source_attributes_json,
             canonical_attributes_json, geometry_summary_json, evidence_json, canonicalization_plan_id,
             mapping_rule_version, is_synthetic, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset["asset_id"], asset["utility_vertical"], asset["asset_class"], asset.get("asset_subtype", ""),
                asset["canonical_name"], asset.get("display_name", ""), asset.get("geometry_type", "unknown"),
                asset.get("lifecycle_status", "unknown"), asset.get("operational_status", "unknown"),
                asset.get("owner_candidate", ""), asset.get("owner_status", "unknown"), asset.get("jurisdiction", ""),
                asset.get("source_system", ""), asset["source_submission_id"], asset["source_layer_id"],
                asset["source_record_id"], asset.get("source_asset_identifier", ""),
                asset.get("source_fingerprint") or stable_fingerprint(asset["source_submission_id"], asset["source_layer_id"], asset["source_record_id"]),
                asset.get("parent_asset_id", ""), asset.get("container_asset_id", ""),
                asset.get("connected_from_asset_id", ""), asset.get("connected_to_asset_id", ""),
                asset.get("network_level", ""), asset.get("work_order_id", ""), asset.get("qa_status", "not_evaluated"),
                asset.get("review_status", "imported"), asset.get("sensitivity", "restricted"),
                asset.get("confidence", "unavailable"), asset.get("installation_date", ""),
                asset.get("retirement_date", ""), asset.get("last_inspected_at", ""), asset.get("last_reviewed_at", ""),
                asset.get("notes", ""), _dump(asset.get("source_attributes_json", {})),
                _dump(asset.get("canonical_attributes_json", {})), _dump(asset.get("geometry_summary_json", {})),
                _dump(asset.get("evidence_json", {})), asset.get("canonicalization_plan_id", ""),
                asset.get("mapping_rule_version", RULE_VERSION), int(bool(asset.get("is_synthetic"))),
                asset["created_at"], asset["updated_at"],
            ),
        )
        return cursor.rowcount == 1

    def _safe_asset(self, row: dict[str, Any], *, detail: bool) -> dict[str, Any]:
        json_fields = ("source_attributes_json", "canonical_attributes_json", "geometry_summary_json", "evidence_json")
        safe = _safe_json_row(row, json_fields)
        safe["is_synthetic"] = bool(row.get("is_synthetic"))
        safe["has_provisional_relationships"] = bool(row.get("has_provisional_relationships", False))
        safe.pop("geometry_reference", None)
        if not detail:
            for field in ("source_attributes_json", "canonical_attributes_json", "geometry_summary_json", "evidence_json", "notes"):
                safe.pop(field, None)
        return safe

    def _add_plan_history(
        self, connection: sqlite3.Connection, plan_id: str, action: str, prior: Any, new: Any,
        actor_type: str, actor: str, reason: str,
    ) -> None:
        connection.execute(
            """INSERT INTO canonicalization_history
            (history_id, plan_id, action, prior_value, new_value, actor_type, actor, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), plan_id, action, _dump(prior), _dump(new), actor_type, actor, reason, intake_registry_service.utc_now()),
        )

    def _add_asset_history(self, connection: sqlite3.Connection, asset_id: str, action: str, event: Any, actor: str = "system") -> None:
        connection.execute(
            """INSERT INTO utility_asset_history
            (history_id, asset_id, action, event_json, actor_type, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), asset_id, action, _dump(event), "system" if actor == "system" else "human", actor, intake_registry_service.utc_now()),
        )


def _counts(connection: sqlite3.Connection, table: str, field: str) -> dict[str, int]:
    return {str(row[field]): int(row["count"]) for row in connection.execute(f"SELECT {field}, COUNT(*) count FROM {table} GROUP BY {field}")}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,),
    ).fetchone() is not None


def _count_where(
    connection: sqlite3.Connection,
    table: str,
    field: str,
    values: tuple[str, ...],
    *,
    distinct: str = "",
) -> int:
    if not _table_exists(connection, table):
        return 0
    placeholders = ",".join("?" for _ in values)
    expression = f"DISTINCT {distinct}" if distinct else "*"
    return int(connection.execute(
        f"SELECT COUNT({expression}) FROM {table} WHERE {field} IN ({placeholders})", values,
    ).fetchone()[0])


def _counts_where(
    connection: sqlite3.Connection,
    table: str,
    field: str,
    values: tuple[str, ...],
) -> dict[str, int]:
    if not _table_exists(connection, table):
        return {}
    placeholders = ",".join("?" for _ in values)
    return {
        str(row[field]): int(row["count"])
        for row in connection.execute(
            f"SELECT {field}, COUNT(*) count FROM {table} WHERE {field} IN ({placeholders}) GROUP BY {field}",
            values,
        )
    }


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _load(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def _safe_json_row(row: dict[str, Any], json_fields: tuple[str, ...]) -> dict[str, Any]:
    output = dict(row)
    for field in json_fields:
        output[field] = _load(output.get(field), {})
    for key in ("provisional", "human_override"):
        if key in output:
            output[key] = bool(output[key])
    return output


service = UtilityAssetService()
