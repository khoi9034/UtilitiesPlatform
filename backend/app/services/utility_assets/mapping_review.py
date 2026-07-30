from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from app.core.local_storage import require_runtime_data_root
from app.services import intake_registry_service
from app.services.review_automation.engine import initialize as initialize_review_automation
from app.services.source_inspection import registry as inspection_registry

from .domain import (
    LIFECYCLE_STATES,
    SHARED_FIELDS,
    SOURCE_UTILITY_DOMAINS,
    TRANSFORMATION_TYPES,
    VERTICAL_PROFILES,
    WATER_OPERATIONAL_STATES,
    WASTEWATER_OPERATIONAL_STATES,
    stable_fingerprint,
    stable_id,
    validate_vertical_and_class,
)

MAPPING_RULE_VERSION = "water-wastewater-mapping-review-v1"
PLAN_STATES = (
    "draft", "recommendations_ready", "needs_domain_review", "needs_taxonomy_review",
    "needs_field_mapping", "needs_value_mapping", "needs_owner_confirmation",
    "needs_jurisdiction_confirmation", "needs_coordinate_review",
    "needs_sensitivity_review", "duplicate_review_required", "staging_blocked",
    "review_ready", "under_review", "approved_plan", "deferred", "rejected",
    "superseded", "stale_source", "archived",
)
MAPPING_SOURCE_ROLES = (
    "operational_inventory", "reference_inventory", "facility_inventory",
    "network_context", "service_area", "boundary", "planning_context",
    "historical", "deprecated", "unknown",
)
ELIGIBILITY_STATES = (
    "ineligible", "source_review_required", "mapping_recommendations_available",
    "mapping_review_required", "mapping_blocked", "review_ready",
    "approved_plan_staging_blocked", "eligible_after_staging_approval",
    "deferred", "excluded",
)
MATERIAL_CODES = {
    "cast iron": "cast_iron", "ci": "cast_iron",
    "ductile iron": "ductile_iron", "di": "ductile_iron",
    "pvc": "pvc", "polyvinyl chloride": "pvc",
    "hdpe": "hdpe", "high density polyethylene": "hdpe",
    "concrete": "concrete", "rcp": "reinforced_concrete",
    "reinforced concrete": "reinforced_concrete", "clay": "clay",
    "vcp": "clay", "steel": "steel", "copper": "copper",
    "ac": "asbestos_cement", "asbestos cement": "asbestos_cement",
    "unknown": "unknown",
}
WATER_CLASS_ALIASES = {
    "potable_water_main": "water_main", "water_main": "water_main",
    "transmission_main": "transmission_main", "distribution_main": "distribution_main",
    "service_line": "service_line", "hydrant_lateral": "hydrant_lateral",
    "valve": "valve", "isolation_valve": "isolation_valve",
    "hydrant": "hydrant", "meter": "meter", "meter_vault": "meter_vault",
    "pump": "pump", "pump_station": "pump_station", "storage_tank": "storage_tank",
    "reservoir": "reservoir", "treatment_facility": "treatment_facility",
    "well": "well", "final_well_head": "well", "private_well_point": "well",
    "pressure_zone": "pressure_zone", "water_system_boundary": "water_system_boundary",
}
WASTEWATER_CLASS_ALIASES = {
    "gravity_main": "gravity_main", "force_main": "force_main",
    "pressure_sewer": "pressure_sewer", "service_lateral": "service_lateral",
    "interceptor": "interceptor", "trunk_sewer": "trunk_sewer",
    "manhole": "manhole", "cleanout": "cleanout", "lift_station": "lift_station",
    "pump": "pump", "wet_well": "wet_well", "treatment_facility": "treatment_facility",
    "outfall": "outfall", "monitoring_point": "monitoring_point",
    "sewer_basin": "sewer_basin", "wastewater_system_boundary": "wastewater_system_boundary",
}
LINE_CLASSES = {
    "water_main", "transmission_main", "distribution_main", "service_line",
    "hydrant_lateral", "raw_water_main", "reclaimed_water_main",
    "abandoned_water_main", "unknown_water_line", "gravity_main", "force_main",
    "pressure_sewer", "service_lateral", "interceptor", "trunk_sewer",
    "outfall_pipe", "abandoned_sewer", "unknown_wastewater_line",
}
POINT_CLASSES = {
    "valve", "isolation_valve", "control_valve", "pressure_reducing_valve",
    "air_release_valve", "blowoff", "hydrant", "meter", "meter_vault",
    "fitting", "tee", "elbow", "reducer", "coupling", "pump", "pump_station",
    "well", "backflow_device", "pressure_sensor", "sampling_point", "vault",
    "structure", "unknown_water_device", "manhole", "cleanout", "junction",
    "lift_station", "wet_well", "outfall", "discharge_point", "monitoring_point",
    "unknown_wastewater_device",
}
POLYGON_CLASSES = {
    "pressure_zone", "service_area", "treatment_area", "water_system_boundary",
    "easement", "facility_site", "sewer_basin", "collection_area",
    "treatment_service_area", "overflow_area", "wastewater_system_boundary",
}
FACILITY_CLASSES = {
    "storage_tank", "elevated_tank", "reservoir", "treatment_facility",
    "pump_station", "lift_station", "wet_well", "facility_site",
}
ROLE_ALIASES = {
    "network_asset": "operational_inventory",
    "facility": "facility_inventory",
    "structure": "facility_inventory",
    "service_location": "reference_inventory",
    "planning_reference": "planning_context",
    "proposed_design": "planning_context",
    "reference": "reference_inventory",
}
FIELD_ALIASES = {
    "assetid": "source_asset_identifier", "sourceid": "source_asset_identifier",
    "sourceassetid": "source_asset_id", "waterid": "main_id", "mainid": "main_id",
    "serviceid": "service_line_id", "servicelineid": "service_line_id",
    "valveid": "valve_id", "hydrantid": "hydrant_id", "meterid": "meter_id",
    "facilityid": "facility_id", "pressurezone": "pressure_zone_id",
    "pressurezoneid": "pressure_zone_id", "watersystemid": "water_system_id",
    "watersystemname": "water_system_name", "wastewatersystemid": "wastewater_system_id",
    "sewerbasin": "sewer_basin_id", "sewerbasinid": "sewer_basin_id",
    "basinid": "sewer_basin_id", "gravitymainid": "gravity_main_id",
    "forcemainid": "force_main_id", "lateralid": "lateral_id",
    "manholeid": "manhole_id", "liftstationid": "lift_station_id",
    "outfallid": "outfall_id", "fromnode": "from_node_id",
    "fromnodeid": "from_node_id", "tonode": "to_node_id", "tonodeid": "to_node_id",
    "upstreamstructure": "upstream_structure_id",
    "upstreamstructureid": "upstream_structure_id",
    "downstreamstructure": "downstream_structure_id",
    "downstreamstructureid": "downstream_structure_id",
    "diameter": "nominal_diameter", "nominaldiameter": "nominal_diameter",
    "pipesize": "nominal_diameter", "size": "nominal_diameter",
    "diameterunit": "diameter_unit", "material": "material",
    "install date": "installation_date", "installdate": "installation_date",
    "installationdate": "installation_date", "yearinstalled": "installation_date",
    "status": "lifecycle_status", "lifecyclestatus": "lifecycle_status",
    "operationalstatus": "operational_status", "main type": "main_type",
    "maintype": "main_type", "placement": "placement_type",
    "placementtype": "placement_type", "valvetype": "valve_type",
    "valvestate": "valve_state", "hydrantstatus": "hydrant_status",
    "metertype": "meter_type", "pumptype": "pump_type", "storagetype": "storage_type",
    "facilitytype": "facility_type", "owner": "owner_candidate",
    "jurisdiction": "jurisdiction", "rimelevation": "rim_elevation",
    "upstreaminvert": "upstream_invert", "downstreaminvert": "downstream_invert",
    "invertin": "upstream_invert", "invertout": "downstream_invert",
    "slope": "slope", "flowdirection": "flow_direction",
}
CODED_TRANSFORMATIONS = {
    "boolean_mapping", "lifecycle_mapping", "operational_status_mapping",
    "domain_mapping", "subtype_mapping",
}
_INITIALIZE_LOCK = threading.Lock()
_UNSAFE_KEYS = {
    "path", "source_path", "filesystem_path", "url", "external_url", "sql",
    "query", "python", "shell", "command", "script", "expression",
    "credentials", "password", "token", "secret",
}
_UNSAFE_VALUE = re.compile(
    r"(?:[a-z]:[\\/]|\\\\|[a-z][a-z0-9+.-]*://|(?:^|[\\/])\.\.?(?:[\\/]|$)|^[~\\/])",
    re.IGNORECASE,
)


class MappingReviewError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def normalize_material(value: object) -> dict[str, Any]:
    source = _safe_text(value, 100)
    normalized = re.sub(r"[_-]+", " ", source.casefold()).strip()
    if not normalized:
        return {"source_value": source, "target_value": "unknown", "status": "needs_review", "confidence": "unavailable"}
    target = MATERIAL_CODES.get(normalized)
    if target:
        return {"source_value": source, "target_value": target, "status": "mapped", "confidence": "high"}
    return {"source_value": source, "target_value": "other", "status": "needs_review", "confidence": "low"}


def parse_diameter(value: object, source_unit: str = "", target_unit: str = "") -> dict[str, Any]:
    source = _safe_text(value, 100)
    match = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s*([a-zA-Z\"']*)\s*", source)
    embedded_unit = match.group(2) if match else ""
    unit = _normalize_unit(source_unit or embedded_unit)
    result = {
        "source_value": source, "parsed_numeric_value": None, "source_unit": unit or "unknown",
        "canonical_unit": unit or "unknown", "conversion_used": "none",
        "parsing_confidence": "unavailable", "warning": "", "review_status": "needs_review",
    }
    if not match:
        result["warning"] = "Diameter is not a plain numeric value."
        return result
    numeric = float(match.group(1))
    result["parsed_numeric_value"] = numeric
    if not unit:
        result["warning"] = "Diameter unit is unavailable; source value was preserved without conversion."
        result["parsing_confidence"] = "medium"
        return result
    requested = _normalize_unit(target_unit) or unit
    result["canonical_unit"] = requested
    if requested != unit:
        meters = numeric * {"inch": 0.0254, "millimeter": 0.001, "foot": 0.3048, "meter": 1.0}[unit]
        numeric = meters / {"inch": 0.0254, "millimeter": 0.001, "foot": 0.3048, "meter": 1.0}[requested]
        result["parsed_numeric_value"] = round(numeric, 6)
        result["conversion_used"] = f"{unit}_to_{requested}"
    result["parsing_confidence"] = "high"
    result["review_status"] = "review_ready"
    return result


def normalize_status(value: object, kind: str, vertical: str) -> dict[str, Any]:
    source = _safe_text(value, 100)
    normalized = _norm(source)
    aliases = {
        "inservice": "in_service", "outofservice": "out_of_service",
        "construction": "under_construction", "abandon": "abandoned",
        "decommissioned": "retired", "pressurized": "pressurized",
        "gravity": "gravity", "open": "open", "closed": "closed",
    }
    target = aliases.get(normalized, normalized if normalized else "unknown")
    allowed = set(LIFECYCLE_STATES if kind == "lifecycle" else (
        WATER_OPERATIONAL_STATES if vertical == "water" else WASTEWATER_OPERATIONAL_STATES
    ))
    if target not in allowed:
        return {"source_value": source, "target_value": "unknown", "status": "needs_review", "confidence": "low"}
    return {"source_value": source, "target_value": target, "status": "mapped", "confidence": "high"}


def geometry_compatibility(asset_class: str, source_geometry: str) -> dict[str, str]:
    geometry = source_geometry.casefold().replace("multipoint", "point")
    expected: tuple[str, ...]
    if asset_class in FACILITY_CLASSES:
        expected = ("point", "polygon")
    elif asset_class in LINE_CLASSES:
        expected = ("polyline", "line")
    elif asset_class in POINT_CLASSES:
        expected = ("point",)
    elif asset_class in POLYGON_CLASSES:
        expected = ("polygon",)
    else:
        return {"status": "requires_human_review", "source_geometry": geometry or "unknown", "target_geometry": "review_required"}
    compatible = any(item in geometry for item in expected)
    return {
        "status": "compatible" if compatible else "incompatible",
        "source_geometry": geometry or "unknown",
        "target_geometry": " or ".join(expected),
    }


def proposed_preview_id(
    submission_id: str, layer_id: str, source_record_reference: str,
    asset_class: str, plan_version: int,
) -> str:
    return stable_id("preview", submission_id, layer_id, source_record_reference, asset_class, plan_version)


def recommend_layer(
    layer: dict[str, Any],
    state: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    state = state or {}
    top = candidates[0] if candidates else {}
    approved_domain = str(state.get("approved_utility_system") or top.get("utility_system") or "unknown")
    alternatives = {
        str(item.get("utility_system")) for item in candidates
        if str(item.get("utility_system")) in {"water", "wastewater"}
    }
    if approved_domain not in SOURCE_UTILITY_DOMAINS:
        approved_domain = "unknown"
    if approved_domain not in {"water", "wastewater"}:
        approved_domain = "water_wastewater" if alternatives == {"water", "wastewater"} else (
            next(iter(alternatives)) if len(alternatives) == 1 else "unknown"
        )
    subcategory = str(state.get("approved_asset_subcategory") or top.get("asset_subcategory") or "")
    aliases = WATER_CLASS_ALIASES if approved_domain == "water" else WASTEWATER_CLASS_ALIASES
    target = aliases.get(subcategory, "")
    source_tokens = _norm(" ".join((
        str(layer.get("source_layer_name", "")), str(layer.get("source_layer_alias", "")), subcategory,
    )))
    class_candidates: list[dict[str, Any]] = []
    contradictions: list[str] = []
    if approved_domain == "wastewater" and not target and any(token in source_tokens for token in ("sewer", "main", "pipe")):
        target = "unknown_wastewater_line"
        class_candidates = [
            {"asset_class": "gravity_main", "score": 0.45},
            {"asset_class": "force_main", "score": 0.45},
            {"asset_class": "pressure_sewer", "score": 0.4},
        ]
        contradictions.append("Stored evidence does not distinguish gravity, force-main, or pressure-sewer behavior.")
    elif target:
        class_candidates = [{"asset_class": target, "score": float(top.get("score") or 0.8)}]
    else:
        contradictions.append("No allowlisted canonical class is supported by the stored taxonomy evidence.")
    if approved_domain not in {"water", "wastewater"}:
        contradictions.append("Stored evidence does not confirm a single Water or Wastewater domain.")
    geometry = geometry_compatibility(target, str(layer.get("geometry_type", ""))) if target else {
        "status": "requires_human_review",
        "source_geometry": str(layer.get("geometry_type") or "unknown"),
        "target_geometry": "review_required",
    }
    if geometry["status"] == "incompatible":
        contradictions.append("Source geometry conflicts with the recommended canonical class.")
    field_profile = _load(layer.get("field_profile_json"), [])
    field_names = {_norm(item.get("name", "")) for item in field_profile if isinstance(item, dict)}
    evidence_categories = ["geometry"]
    if layer.get("source_layer_name"):
        evidence_categories.append("name")
    if layer.get("source_layer_alias"):
        evidence_categories.append("alias")
    if field_profile:
        evidence_categories.append("field_schema")
    if _load(layer.get("domain_profile_json"), {}):
        evidence_categories.append("domains")
    if _load(layer.get("subtype_profile_json"), {}):
        evidence_categories.append("subtypes")
    confidence = str(state.get("taxonomy_confidence") or top.get("confidence") or "low")
    if contradictions:
        confidence = "low"
    return {
        "recommended_domain": approved_domain,
        "alternative_domains": sorted(alternatives - {approved_domain}),
        "recommended_asset_class": target,
        "recommended_asset_subtype": subcategory,
        "confidence": confidence,
        "domain_confidence": str(state.get("taxonomy_confidence") or confidence),
        "taxonomy_confidence": confidence,
        "evidence_categories": sorted(set(evidence_categories)),
        "contradictory_evidence": contradictions,
        "geometry_compatibility": geometry,
        "source_layer_role": normalize_source_role(str(state.get("approved_operational_role") or layer.get("operational_role") or "unknown")),
        "recommendation_status": "candidate" if target and not contradictions else "review_required",
        "reviewer_requirement": "human_confirmation_required",
        "class_candidates": class_candidates,
        "safe_signals": {
            "identifier_fields_available": bool(_load(layer.get("likely_id_fields_json"), [])),
            "lifecycle_fields_available": bool(_load(layer.get("likely_status_fields_json"), [])),
            "date_fields_available": bool(_load(layer.get("likely_date_fields_json"), [])),
            "dimension_fields_available": bool(_load(layer.get("likely_dimension_fields_json"), [])),
            "owner_fields_available": bool(_load(layer.get("likely_owner_fields_json"), [])),
            "material_signal": any("material" in name or name == "ma" for name in field_names),
            "elevation_signal": any("elev" in name or "invert" in name for name in field_names),
        },
    }


def normalize_source_role(value: str) -> str:
    normalized = value.casefold().strip()
    role = ROLE_ALIASES.get(normalized, normalized)
    return role if role in MAPPING_SOURCE_ROLES else "unknown"


def recommend_fields(layer: dict[str, Any], vertical: str) -> list[dict[str, Any]]:
    profiles = _load(layer.get("field_profile_json"), [])
    likely_ids = {_norm(value) for value in _load(layer.get("likely_id_fields_json"), [])}
    allowed = set(SHARED_FIELDS) | set(VERTICAL_PROFILES.get(vertical, {}).get("canonical_attributes", ()))
    recommendations: list[dict[str, Any]] = []
    identifier_assigned = False
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        source_field = _safe_text(profile.get("name"), 128)
        alias = _safe_text(profile.get("alias"), 128)
        normalized = _norm(source_field)
        target = FIELD_ALIASES.get(normalized) or FIELD_ALIASES.get(_norm(alias), "")
        if not target and normalized in likely_ids and not identifier_assigned:
            target = "source_asset_identifier"
        if target not in allowed:
            target = ""
        identifier_assigned = identifier_assigned or target == "source_asset_identifier"
        transformation = _transformation_for(target, source_field)
        recommendations.append({
            "source_field": source_field,
            "source_alias": alias,
            "sample_safe_type_summary": _safe_text(profile.get("type"), 50) or "unknown",
            "target_field": target,
            "transformation_type": transformation,
            "source_unit": "",
            "target_unit": "",
            "mapping_status": "proposed" if target else "unmapped",
            "confidence": "high" if target and _norm(source_field) == _norm(target) else "medium" if target else "unavailable",
            "evidence_json": {"categories": ["field_name", "field_alias"], "rule_version": MAPPING_RULE_VERSION},
            "reviewer_type": "system",
            "human_override": False,
            "notes": "" if target else "No deterministic allowlisted mapping was found.",
        })
    return recommendations


class MappingReviewService:
    def root(self) -> Path:
        return require_runtime_data_root()

    def connect(self) -> sqlite3.Connection:
        connection = intake_registry_service.connect(self.root())
        connection.execute("PRAGMA busy_timeout = 30000")
        with _INITIALIZE_LOCK:
            inspection_registry.initialize(connection)
            initialize_review_automation(connection)
            self._initialize(connection)
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_canonical_mapping_plans (
                plan_id TEXT PRIMARY KEY,
                plan_version INTEGER NOT NULL,
                submission_id TEXT NOT NULL,
                inspection_run_id TEXT NOT NULL,
                source_layer_id TEXT NOT NULL,
                utility_domain TEXT NOT NULL,
                source_role TEXT NOT NULL,
                target_asset_class TEXT NOT NULL,
                target_asset_subtype TEXT NOT NULL,
                mapping_rule_version TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                plan_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                domain_confidence TEXT NOT NULL,
                taxonomy_confidence TEXT NOT NULL,
                geometry_status TEXT NOT NULL,
                coordinate_status TEXT NOT NULL,
                sensitivity_status TEXT NOT NULL,
                duplicate_status TEXT NOT NULL,
                owner_status TEXT NOT NULL,
                jurisdiction_status TEXT NOT NULL,
                staging_status TEXT NOT NULL,
                preview_record_count INTEGER NOT NULL DEFAULT 0,
                mapped_field_count INTEGER NOT NULL DEFAULT 0,
                unmapped_field_count INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,
                blocker_count INTEGER NOT NULL DEFAULT 0,
                approved_plan INTEGER NOT NULL DEFAULT 0,
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at TEXT NOT NULL DEFAULT '',
                decision_json TEXT NOT NULL DEFAULT '{}',
                recommendation_json TEXT NOT NULL DEFAULT '{}',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                blockers_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (submission_id, source_layer_id, plan_version)
            );
            CREATE INDEX IF NOT EXISTS idx_source_mapping_plan_layer
                ON source_canonical_mapping_plans(submission_id, source_layer_id, plan_version DESC);

            CREATE TABLE IF NOT EXISTS source_canonical_field_mappings (
                mapping_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                source_field TEXT NOT NULL,
                source_alias TEXT NOT NULL,
                target_field TEXT NOT NULL,
                transformation_type TEXT NOT NULL,
                source_unit TEXT NOT NULL,
                target_unit TEXT NOT NULL,
                mapping_status TEXT NOT NULL,
                confidence TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                reviewer_type TEXT NOT NULL,
                human_override INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (plan_id, source_field)
            );

            CREATE TABLE IF NOT EXISTS source_canonical_value_mappings (
                value_mapping_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                source_field TEXT NOT NULL,
                source_value TEXT NOT NULL,
                target_field TEXT NOT NULL,
                target_value TEXT NOT NULL,
                transformation_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                review_status TEXT NOT NULL,
                human_override INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (plan_id, source_field, source_value, target_field)
            );

            CREATE TABLE IF NOT EXISTS source_canonical_preview_runs (
                preview_run_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                plan_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                records_read INTEGER NOT NULL,
                records_previewed INTEGER NOT NULL,
                warnings TEXT NOT NULL,
                blockers TEXT NOT NULL,
                safe_error_message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_canonical_mapping_history (
                history_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                plan_version INTEGER NOT NULL,
                mapping_id TEXT NOT NULL,
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

    def list_candidates(self, submission_id: str = "") -> dict[str, Any]:
        with self.connect() as connection:
            clauses = ["a.submission_id = ?"] if submission_id else []
            rows = connection.execute(
                f"""SELECT l.*, a.*, p.approved_for_staging
                FROM automated_layer_state a
                JOIN inspected_layers l ON l.layer_id = a.layer_id
                LEFT JOIN staging_plan_items p ON p.layer_id = a.layer_id
                {'WHERE ' + ' AND '.join(clauses) if clauses else ''}
                ORDER BY a.approved_utility_system, l.layer_id""",
                (submission_id,) if submission_id else (),
            ).fetchall()
            items = [self._candidate(connection, dict(row)) for row in rows]
        summary = {
            "water_candidate_layers": sum(item["recommended_domain"] == "water" for item in items),
            "wastewater_candidate_layers": sum(item["recommended_domain"] == "wastewater" for item in items),
            "ambiguous_layers": sum(item["recommended_domain"] in {"water_wastewater", "multi_utility", "unknown"} for item in items),
            "reference_layers": sum(item["source_role"] in {"reference_inventory", "planning_context", "boundary", "service_area"} for item in items),
            "ineligible_layers": sum(item["eligibility_state"] in {"ineligible", "excluded"} for item in items),
            "plans_created": sum(bool(item.get("plan_id")) for item in items),
            "plans_review_ready": sum(item.get("plan_status") == "review_ready" for item in items),
            "plans_blocked": sum(bool(item.get("plan_id")) and item.get("blocker_count", 0) > 0 for item in items),
        }
        return {
            "items": items, "summary": summary,
            "message": "Candidates use stored inspection and review evidence only; no source records or geometry were read.",
        }

    def recommendations(self, submission_id: str, layer_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            evidence = self._evidence(connection, submission_id, layer_id)
            recommendation = recommend_layer(evidence["layer"], evidence["state"], evidence["candidates"])
            return {
                "submission_id": submission_id,
                "source_layer_id": layer_id,
                "source_evidence": self._safe_source_evidence(evidence["layer"], evidence["state"]),
                "recommendation": recommendation,
                "field_recommendations": recommend_fields(
                    evidence["layer"],
                    recommendation["recommended_domain"] if recommendation["recommended_domain"] in {"water", "wastewater"} else "water",
                ),
                "source_geometry_modified": False,
            }

    def list_plans(self, utility_domain: str = "") -> dict[str, Any]:
        with self.connect() as connection:
            if utility_domain:
                if utility_domain not in SOURCE_UTILITY_DOMAINS:
                    raise MappingReviewError("Unsupported utility domain.")
            where = "WHERE p.utility_domain = ?" if utility_domain else ""
            values = [utility_domain] if utility_domain else []
            rows = connection.execute(
                f"""WITH latest AS (
                    SELECT submission_id, source_layer_id, MAX(plan_version) AS plan_version
                    FROM source_canonical_mapping_plans
                    GROUP BY submission_id, source_layer_id
                )
                SELECT p.* FROM source_canonical_mapping_plans p
                JOIN latest USING (submission_id, source_layer_id, plan_version)
                {where}
                ORDER BY p.updated_at DESC""",
                values,
            ).fetchall()
            return {"items": [self._safe_plan(connection, dict(row), detail=False) for row in rows]}

    def create_plan(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _reject_unsafe(payload)
        with self.connect() as connection:
            evidence = self._evidence(connection, submission_id, layer_id)
            latest = self._latest_plan(connection, submission_id, layer_id)
            current_source = self._source_fingerprint(evidence)
            if latest and latest["source_fingerprint"] == current_source and latest["status"] not in {"superseded", "archived"}:
                return self._safe_plan(connection, latest)
            recommendation = recommend_layer(evidence["layer"], evidence["state"], evidence["candidates"])
            domain = str(payload.get("utility_domain") or recommendation["recommended_domain"])
            source_role = str(payload.get("source_role") or recommendation["source_layer_role"])
            target_class = str(payload.get("target_asset_class") or recommendation["recommended_asset_class"])
            target_subtype = str(payload.get("target_asset_subtype") or recommendation["recommended_asset_subtype"])
            self._validate_selection(domain, source_role, target_class)
            version = int(latest["plan_version"]) + 1 if latest else 1
            plan_id = stable_id("mapping_plan", submission_id, layer_id, version)
            now = intake_registry_service.utc_now()
            state = evidence["state"]
            staging_approved = bool(evidence["layer"].get("approved_for_staging"))
            inspection_run_id = str(evidence["inspection_run_id"])
            decision = {
                "reviewer_notes": _safe_text(payload.get("reviewer_notes"), 500),
                "owner_candidate": _safe_text(state.get("owner_candidate"), 200),
                "jurisdiction_candidate": "",
                "source_role_confirmed": False,
                "domain_confirmed": False,
                "taxonomy_confirmed": False,
            }
            connection.execute(
                """INSERT INTO source_canonical_mapping_plans
                (plan_id, plan_version, submission_id, inspection_run_id, source_layer_id,
                 utility_domain, source_role, target_asset_class, target_asset_subtype,
                 mapping_rule_version, source_fingerprint, plan_fingerprint, status,
                 domain_confidence, taxonomy_confidence, geometry_status, coordinate_status,
                 sensitivity_status, duplicate_status, owner_status, jurisdiction_status,
                 staging_status, decision_json, recommendation_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?)""",
                (
                    plan_id, version, submission_id, inspection_run_id, layer_id, domain, source_role,
                    target_class, target_subtype, MAPPING_RULE_VERSION, current_source,
                    stable_fingerprint(submission_id, inspection_run_id, layer_id, current_source, domain, target_class, source_role, version),
                    recommendation["domain_confidence"], recommendation["taxonomy_confidence"],
                    recommendation["geometry_compatibility"]["status"],
                    str(state.get("coordinate_status") or evidence["layer"].get("coordinate_status") or "unknown"),
                    str(state.get("sensitivity_status") or evidence["layer"].get("sensitivity_status") or "unknown"),
                    str(state.get("duplicate_status") or evidence["layer"].get("duplicate_status") or "unknown"),
                    str(state.get("owner_status") or "unknown"), "unknown",
                    "approved" if staging_approved else "not_approved", _dump(decision), _dump(recommendation), now, now,
                ),
            )
            for mapping in recommend_fields(evidence["layer"], domain if domain in {"water", "wastewater"} else "water"):
                self._upsert_field(connection, plan_id, mapping, now)
            self._history(connection, plan_id, version, "plan_created", {}, {"status": "draft"}, payload, "")
            self._refresh(connection, plan_id)
            connection.commit()
            return self._safe_plan(connection, self._required_plan(connection, submission_id, layer_id))

    def get_plan(self, submission_id: str, layer_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            plan = self._latest_plan(connection, submission_id, layer_id)
            if not plan:
                raise MappingReviewError("Mapping review plan not found.", 404)
            return self._safe_plan(connection, plan)

    def new_version(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _reject_unsafe(payload)
        with self.connect() as connection:
            prior = self._required_plan(connection, submission_id, layer_id)
            evidence = self._evidence(connection, submission_id, layer_id)
            version = int(prior["plan_version"]) + 1
            plan_id = stable_id("mapping_plan", submission_id, layer_id, version)
            now = intake_registry_service.utc_now()
            source_fingerprint = self._source_fingerprint(evidence)
            columns = (
                "submission_id", "inspection_run_id", "source_layer_id", "utility_domain",
                "source_role", "target_asset_class", "target_asset_subtype", "domain_confidence",
                "taxonomy_confidence", "geometry_status", "coordinate_status",
                "sensitivity_status", "duplicate_status", "owner_status", "jurisdiction_status",
                "staging_status", "decision_json", "recommendation_json",
            )
            values = [prior[column] for column in columns]
            connection.execute(
                f"""INSERT INTO source_canonical_mapping_plans
                (plan_id, plan_version, {', '.join(columns)}, mapping_rule_version,
                 source_fingerprint, plan_fingerprint, status, created_at, updated_at)
                VALUES (?, ?, {', '.join('?' for _ in columns)}, ?, ?, ?, 'draft', ?, ?)""",
                (
                    plan_id, version, *values, MAPPING_RULE_VERSION, source_fingerprint,
                    stable_fingerprint(prior["submission_id"], prior["source_layer_id"], source_fingerprint, version),
                    now, now,
                ),
            )
            for table, key in (
                ("source_canonical_field_mappings", "mapping_id"),
                ("source_canonical_value_mappings", "value_mapping_id"),
            ):
                for row in connection.execute(f"SELECT * FROM {table} WHERE plan_id = ?", (prior["plan_id"],)).fetchall():
                    copy = dict(row)
                    copy[key] = stable_id(key, plan_id, copy.get("source_field"), copy.get("source_value", ""), copy.get("target_field"))
                    copy["plan_id"] = plan_id
                    columns_copy = list(copy)
                    connection.execute(
                        f"INSERT INTO {table} ({', '.join(columns_copy)}) VALUES ({', '.join('?' for _ in columns_copy)})",
                        [copy[column] for column in columns_copy],
                    )
            connection.execute(
                "UPDATE source_canonical_mapping_plans SET status='superseded', updated_at=? WHERE plan_id=?",
                (now, prior["plan_id"]),
            )
            self._history(connection, prior["plan_id"], int(prior["plan_version"]), "plan_superseded", {"status": prior["status"]}, {"status": "superseded"}, payload, "")
            self._history(connection, plan_id, version, "plan_version_created", {}, {"prior_plan_id": prior["plan_id"]}, payload, "")
            self._refresh(connection, plan_id)
            connection.commit()
            return self._safe_plan(connection, dict(connection.execute(
                "SELECT * FROM source_canonical_mapping_plans WHERE plan_id=?", (plan_id,),
            ).fetchone()))

    def recalculate(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _reject_unsafe(payload)
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            evidence = self._evidence(connection, submission_id, layer_id)
            recommendation = recommend_layer(evidence["layer"], evidence["state"], evidence["candidates"])
            decision = _load(plan["decision_json"], {})
            allowed = {
                "utility_domain", "source_role", "target_asset_class", "target_asset_subtype",
                "owner_status", "jurisdiction_status", "coordinate_status",
                "sensitivity_status", "duplicate_status", "reviewer_notes",
                "owner_candidate", "jurisdiction_candidate", "domain_confirmed",
                "taxonomy_confirmed", "source_role_confirmed",
            }
            changes = {key: value for key, value in payload.items() if key in allowed}
            if any(key.endswith("_confirmed") or key in {"owner_status", "jurisdiction_status"} for key in changes):
                if not _safe_text(payload.get("actor"), 100):
                    raise MappingReviewError("actor is required for human confirmation.")
            domain = str(changes.pop("utility_domain", plan["utility_domain"]))
            role = str(changes.pop("source_role", plan["source_role"]))
            target = str(changes.pop("target_asset_class", plan["target_asset_class"]))
            subtype = str(changes.pop("target_asset_subtype", plan["target_asset_subtype"]))
            self._validate_selection(domain, role, target)
            column_changes = {
                key: str(changes.pop(key)) for key in (
                    "owner_status", "jurisdiction_status", "coordinate_status",
                    "sensitivity_status", "duplicate_status",
                ) if key in changes
            }
            decision.update(changes)
            assignments = [
                "utility_domain=?", "source_role=?", "target_asset_class=?",
                "target_asset_subtype=?", "recommendation_json=?", "decision_json=?",
                "approved_plan=0", "approved_by=''", "approved_at=''", "updated_at=?",
            ]
            values: list[Any] = [domain, role, target, subtype, _dump(recommendation), _dump(decision), intake_registry_service.utc_now()]
            for column, value in column_changes.items():
                assignments.append(f"{column}=?")
                values.append(value)
            values.append(plan["plan_id"])
            connection.execute(
                f"UPDATE source_canonical_mapping_plans SET {', '.join(assignments)} WHERE plan_id=?",
                values,
            )
            self._history(connection, plan["plan_id"], int(plan["plan_version"]), "recommendations_recalculated", {}, {"changes": sorted(changes | column_changes)}, payload, _safe_text(payload.get("reason"), 500))
            self._refresh(connection, plan["plan_id"])
            connection.commit()
            return self._safe_plan(connection, dict(connection.execute(
                "SELECT * FROM source_canonical_mapping_plans WHERE plan_id=?", (plan["plan_id"],),
            ).fetchone()))

    def fields(self, submission_id: str, layer_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            return {"items": self._field_rows(connection, plan["plan_id"]), "plan_id": plan["plan_id"]}

    def update_fields(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _reject_unsafe(payload)
        mappings = payload.get("mappings")
        if not isinstance(mappings, list) or not mappings:
            raise MappingReviewError("At least one field mapping is required.")
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            evidence = self._evidence(connection, submission_id, layer_id)
            source_fields = {
                str(item.get("name", "")) for item in _load(evidence["layer"].get("field_profile_json"), [])
                if isinstance(item, dict)
            }
            prior = self._field_rows(connection, plan["plan_id"])
            now = intake_registry_service.utc_now()
            for item in mappings:
                if not isinstance(item, dict):
                    raise MappingReviewError("Field mappings must be JSON objects.")
                normalized = self._validate_field_mapping(item, plan["utility_domain"], source_fields)
                self._upsert_field(connection, plan["plan_id"], normalized, now)
            connection.execute(
                """UPDATE source_canonical_mapping_plans SET approved_plan=0, approved_by='',
                approved_at='', updated_at=? WHERE plan_id=?""",
                (now, plan["plan_id"]),
            )
            self._history(connection, plan["plan_id"], int(plan["plan_version"]), "field_mappings_updated", prior, mappings, payload, _safe_text(payload.get("reason"), 500))
            self._refresh(connection, plan["plan_id"])
            connection.commit()
            return self._safe_plan(connection, dict(connection.execute(
                "SELECT * FROM source_canonical_mapping_plans WHERE plan_id=?", (plan["plan_id"],),
            ).fetchone()))

    def values(self, submission_id: str, layer_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            return {"items": self._value_rows(connection, plan["plan_id"]), "plan_id": plan["plan_id"]}

    def update_values(self, submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _reject_unsafe(payload)
        mappings = payload.get("mappings")
        if not isinstance(mappings, list):
            raise MappingReviewError("Value mappings must be a list.")
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            prior = self._value_rows(connection, plan["plan_id"])
            now = intake_registry_service.utc_now()
            for item in mappings:
                if not isinstance(item, dict):
                    raise MappingReviewError("Value mappings must be JSON objects.")
                normalized = self._validate_value_mapping(item, plan["utility_domain"])
                identifier = stable_id(
                    "value_map", plan["plan_id"], normalized["source_field"],
                    normalized["source_value"], normalized["target_field"],
                )
                connection.execute(
                    """INSERT INTO source_canonical_value_mappings
                    (value_mapping_id, plan_id, source_field, source_value, target_field,
                     target_value, transformation_type, confidence, evidence_json,
                     review_status, human_override, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(plan_id, source_field, source_value, target_field) DO UPDATE SET
                    target_value=excluded.target_value,
                    transformation_type=excluded.transformation_type,
                    confidence=excluded.confidence, evidence_json=excluded.evidence_json,
                    review_status=excluded.review_status, human_override=excluded.human_override,
                    updated_at=excluded.updated_at""",
                    (
                        identifier, plan["plan_id"], normalized["source_field"],
                        normalized["source_value"], normalized["target_field"],
                        normalized["target_value"], normalized["transformation_type"],
                        normalized["confidence"], _dump(normalized["evidence_json"]),
                        normalized["review_status"], int(normalized["human_override"]), now, now,
                    ),
                )
            connection.execute(
                """UPDATE source_canonical_mapping_plans SET approved_plan=0, approved_by='',
                approved_at='', updated_at=? WHERE plan_id=?""", (now, plan["plan_id"]),
            )
            self._history(connection, plan["plan_id"], int(plan["plan_version"]), "value_mappings_updated", prior, mappings, payload, _safe_text(payload.get("reason"), 500))
            self._refresh(connection, plan["plan_id"])
            connection.commit()
            return self._safe_plan(connection, dict(connection.execute(
                "SELECT * FROM source_canonical_mapping_plans WHERE plan_id=?", (plan["plan_id"],),
            ).fetchone()))

    def preview(self, submission_id: str, layer_id: str, *, create_run: bool) -> dict[str, Any]:
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            stale = self._current_source_fingerprint(connection, plan) != plan["source_fingerprint"]
            blockers = _load(plan["blockers_json"], {})
            aggregate = {
                "proposed_canonical_identifier": proposed_preview_id(
                    submission_id, layer_id, "aggregate", plan["target_asset_class"], int(plan["plan_version"]),
                ),
                "label": "Proposed canonical identifier - not created.",
                "domain": plan["utility_domain"],
                "asset_class": plan["target_asset_class"] or "review_required",
                "source_record_count": int(plan["preview_record_count"] or 0),
                "lineage": {
                    "submission_id": submission_id, "source_layer_id": layer_id,
                    "plan_id": plan["plan_id"], "mapping_version": plan["mapping_rule_version"],
                },
                "warnings": _load(plan["warnings_json"], []),
                "blockers": [key for key, value in blockers.items() if value],
                "preview_only": True,
            }
            response = {
                "plan_id": plan["plan_id"], "preview_mode": "aggregate_only",
                "items": [], "aggregate": aggregate, "records_read": 0,
                "records_previewed": 0, "canonical_assets_created": 0,
                "raw_coordinates_included": False, "local_paths_included": False,
                "source_geometry_modified": False,
                "message": "Preview only - no canonical asset has been created. Restricted source records remain local.",
            }
            if create_run:
                now = intake_registry_service.utc_now()
                run_id = stable_id("preview_run", plan["plan_id"], plan["plan_fingerprint"], now)
                connection.execute(
                    """INSERT INTO source_canonical_preview_runs
                    (preview_run_id, plan_id, source_fingerprint, plan_fingerprint, status,
                     records_read, records_previewed, warnings, blockers, safe_error_message, created_at)
                    VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?)""",
                    (
                        run_id, plan["plan_id"], plan["source_fingerprint"],
                        plan["plan_fingerprint"], "blocked" if stale else "aggregate_only",
                        _dump(response["aggregate"]["warnings"]), _dump(response["aggregate"]["blockers"]),
                        "Source metadata changed; create a new plan version." if stale else "", now,
                    ),
                )
                self._history(connection, plan["plan_id"], int(plan["plan_version"]), "preview_generated", {}, {"preview_run_id": run_id, "mode": "aggregate_only"}, {}, "")
                connection.commit()
                response["preview_run_id"] = run_id
            return response

    def workflow(self, submission_id: str, layer_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        _reject_unsafe(payload)
        actor = _safe_text(payload.get("actor") or payload.get("approved_by"), 100)
        if not actor:
            raise MappingReviewError("actor is required.")
        status_by_action = {
            "submit": "under_review", "start-review": "under_review",
            "request-revision": "mapping_review_required", "defer": "deferred",
            "reject": "rejected",
        }
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            if action == "approve":
                blockers = _load(plan["blockers_json"], {})
                unresolved = [key for key, value in blockers.items() if value and key != "staging_blocker"]
                if unresolved:
                    raise MappingReviewError(
                        f"Mapping plan cannot be approved until {unresolved[0].replace('_', ' ')} is resolved.",
                        409,
                    )
                status = "approved_plan"
                approved = 1
            elif action in status_by_action:
                status = status_by_action[action]
                approved = 0
            else:
                raise MappingReviewError("Unsupported mapping-plan workflow action.")
            now = intake_registry_service.utc_now()
            connection.execute(
                """UPDATE source_canonical_mapping_plans SET status=?, approved_plan=?,
                approved_by=?, approved_at=?, updated_at=? WHERE plan_id=?""",
                (
                    status, approved, actor if approved else "", now if approved else "",
                    now, plan["plan_id"],
                ),
            )
            self._history(connection, plan["plan_id"], int(plan["plan_version"]), f"plan_{action}", {"status": plan["status"]}, {"status": status}, payload, _safe_text(payload.get("reason"), 500))
            self._refresh(connection, plan["plan_id"], preserve_status=True)
            connection.commit()
            return self._safe_plan(connection, dict(connection.execute(
                "SELECT * FROM source_canonical_mapping_plans WHERE plan_id=?", (plan["plan_id"],),
            ).fetchone()))

    def eligibility(self, submission_id: str, layer_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            return self._eligibility(connection, plan)

    def safe_summary(self, submission_id: str, layer_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            plan = self._required_plan(connection, submission_id, layer_id)
            safe = self._safe_plan(connection, plan, detail=False)
            return {
                key: safe[key] for key in (
                    "plan_id", "plan_version", "utility_domain", "source_role",
                    "target_asset_class", "status", "domain_confidence",
                    "taxonomy_confidence", "geometry_status", "coordinate_status",
                    "sensitivity_status", "duplicate_status", "owner_status",
                    "jurisdiction_status", "staging_status", "mapped_field_count",
                    "unmapped_field_count", "warning_count", "blocker_count",
                    "approved_plan", "eligibility", "creation_enabled", "updated_at",
                )
            }

    def _candidate(self, connection: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
        candidates = [
            dict(item) for item in connection.execute(
                "SELECT * FROM layer_classification_candidates WHERE layer_id=? ORDER BY rank",
                (row["layer_id"],),
            ).fetchall()
        ]
        recommendation = recommend_layer(row, row, candidates)
        plan = self._latest_plan(connection, row["submission_id"], row["layer_id"])
        role = recommendation["source_layer_role"]
        eligibility = "mapping_recommendations_available"
        if recommendation["recommended_domain"] not in {"water", "wastewater"}:
            eligibility = "source_review_required"
        if role not in {"operational_inventory", "facility_inventory"}:
            eligibility = "excluded" if role in {"historical", "deprecated"} else "ineligible"
        return {
            "submission_id": row["submission_id"],
            "source_layer_id": row["layer_id"],
            "source_layer": self._safe_layer_label(row["layer_id"]),
            "recommended_domain": recommendation["recommended_domain"],
            "source_role": role,
            "recommended_asset_class": recommendation["recommended_asset_class"],
            "recommended_asset_subtype": recommendation["recommended_asset_subtype"],
            "domain_confidence": recommendation["domain_confidence"],
            "taxonomy_confidence": recommendation["taxonomy_confidence"],
            "geometry_status": recommendation["geometry_compatibility"]["status"],
            "coordinate_status": str(row.get("coordinate_status") or "unknown"),
            "sensitivity_status": str(row.get("sensitivity_status") or "unknown"),
            "duplicate_status": str(row.get("duplicate_status") or "unknown"),
            "owner_status": str(row.get("owner_status") or "unknown"),
            "jurisdiction_status": "unknown",
            "staging_status": "approved" if bool(row.get("approved_for_staging")) else "not_approved",
            "eligibility_state": eligibility,
            "plan_id": plan["plan_id"] if plan else "",
            "plan_status": plan["status"] if plan else "not_created",
            "blocker_count": int(plan["blocker_count"]) if plan else 0,
            "updated_at": str(plan["updated_at"]) if plan else str(row.get("updated_at") or ""),
        }

    def _evidence(self, connection: sqlite3.Connection, submission_id: str, layer_id: str) -> dict[str, Any]:
        row = connection.execute(
            """SELECT l.*, s.sha256 submission_sha, a.automation_run_id,
            a.taxonomy_status, a.taxonomy_decision, a.approved_utility_system,
            a.approved_asset_category, a.approved_asset_subcategory,
            a.approved_operational_role, a.taxonomy_confidence,
            a.coordinate_status automated_coordinate_status, a.coordinate_blocker,
            a.sensitivity_status automated_sensitivity_status, a.sensitivity_blocker,
            a.duplicate_status automated_duplicate_status, a.owner_candidate,
            a.owner_confidence, a.owner_status automated_owner_status, a.owner_blocker,
            a.staging_readiness, a.staging_blockers_json, a.approved_for_staging automated_staging_approval,
            p.approved_for_staging
            FROM inspected_layers l
            JOIN intake_submissions s ON s.submission_id=l.submission_id
            LEFT JOIN automated_layer_state a ON a.layer_id=l.layer_id
            LEFT JOIN staging_plan_items p ON p.layer_id=l.layer_id
            WHERE l.submission_id=? AND l.layer_id=?""",
            (submission_id, layer_id),
        ).fetchone()
        if not row:
            raise MappingReviewError("Reviewed source layer not found.", 404)
        combined = dict(row)
        state = {
            "automation_run_id": combined.get("automation_run_id", ""),
            "taxonomy_status": combined.get("taxonomy_status", ""),
            "taxonomy_decision": combined.get("taxonomy_decision", ""),
            "approved_utility_system": combined.get("approved_utility_system", ""),
            "approved_asset_category": combined.get("approved_asset_category", ""),
            "approved_asset_subcategory": combined.get("approved_asset_subcategory", ""),
            "approved_operational_role": combined.get("approved_operational_role", ""),
            "taxonomy_confidence": combined.get("taxonomy_confidence", ""),
            "coordinate_status": combined.get("automated_coordinate_status") or combined.get("coordinate_status"),
            "sensitivity_status": combined.get("automated_sensitivity_status") or combined.get("sensitivity_status"),
            "duplicate_status": combined.get("automated_duplicate_status") or combined.get("duplicate_status"),
            "owner_candidate": combined.get("owner_candidate", ""),
            "owner_confidence": combined.get("owner_confidence", ""),
            "owner_status": combined.get("automated_owner_status", ""),
            "staging_readiness": combined.get("staging_readiness", ""),
        }
        candidates = [
            dict(item) for item in connection.execute(
                "SELECT * FROM layer_classification_candidates WHERE layer_id=? ORDER BY rank",
                (layer_id,),
            ).fetchall()
        ]
        inspection = connection.execute(
            """SELECT inspection_run_id FROM inspection_runs WHERE submission_id=?
            ORDER BY completed_at DESC, started_at DESC LIMIT 1""", (submission_id,),
        ).fetchone()
        return {
            "layer": combined, "state": state, "candidates": candidates,
            "inspection_run_id": inspection["inspection_run_id"] if inspection else "",
        }

    def _source_fingerprint(self, evidence: dict[str, Any]) -> str:
        layer = evidence["layer"]
        return stable_fingerprint(
            layer.get("submission_sha", ""), evidence.get("inspection_run_id", ""),
            layer.get("layer_id", ""), layer.get("source_layer_name", ""),
            layer.get("record_count", 0), layer.get("field_profile_json", ""),
            layer.get("geometry_type", ""), layer.get("spatial_reference_wkid", ""),
        )

    def _current_source_fingerprint(self, connection: sqlite3.Connection, plan: dict[str, Any]) -> str:
        try:
            return self._source_fingerprint(self._evidence(connection, plan["submission_id"], plan["source_layer_id"]))
        except MappingReviewError:
            return ""

    def _safe_source_evidence(self, layer: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        profiles = _load(layer.get("field_profile_json"), [])
        names = {_norm(item.get("name", "")) for item in profiles if isinstance(item, dict)}
        return {
            "source_layer": self._safe_layer_label(str(layer.get("layer_id", ""))),
            "source_layer_id": str(layer.get("layer_id", "")),
            "geometry_type": str(layer.get("geometry_type") or "unknown"),
            "record_count": int(layer.get("record_count") or 0),
            "field_count": int(layer.get("field_count") or 0),
            "domain_count": len(_load(layer.get("domain_profile_json"), {})),
            "subtypes_available": bool(_load(layer.get("subtype_profile_json"), {})),
            "lifecycle_signals": bool(_load(layer.get("likely_status_fields_json"), [])),
            "material_signals": any("material" in name or name == "ma" for name in names),
            "diameter_signals": any("diameter" in name or "size" in name or name == "sz" for name in names),
            "elevation_signals": any("elev" in name or "invert" in name for name in names),
            "related_layers_available": bool(_load(layer.get("relationship_profile_json"), [])),
            "source_review_status": str(state.get("taxonomy_status") or layer.get("latest_review_status") or "unknown"),
            "sensitivity_status": str(state.get("sensitivity_status") or "unknown"),
            "coordinate_status": str(state.get("coordinate_status") or "unknown"),
            "local_paths_included": False,
            "raw_coordinates_included": False,
        }

    def _validate_selection(self, domain: str, role: str, target_class: str) -> None:
        if domain not in SOURCE_UTILITY_DOMAINS:
            raise MappingReviewError("Unsupported mapping-plan utility domain.")
        if role not in MAPPING_SOURCE_ROLES:
            raise MappingReviewError("Unsupported source-layer role.")
        if target_class:
            if domain not in {"water", "wastewater"}:
                raise MappingReviewError("A canonical class requires a confirmed Water or Wastewater domain.")
            try:
                validate_vertical_and_class(domain, target_class)
            except ValueError as exc:
                raise MappingReviewError(str(exc)) from exc

    def _validate_field_mapping(
        self, item: dict[str, Any], domain: str, source_fields: set[str],
    ) -> dict[str, Any]:
        _reject_unsafe(item)
        source_field = _safe_text(item.get("source_field"), 128)
        if source_field not in source_fields:
            raise MappingReviewError("Source field is not present in stored inspection evidence.")
        transformation = str(item.get("transformation_type", ""))
        if transformation not in TRANSFORMATION_TYPES:
            raise MappingReviewError("Transformation type must use the deterministic allowlist.")
        target = _safe_text(item.get("target_field"), 100)
        allowed = set(SHARED_FIELDS)
        if domain in {"water", "wastewater"}:
            allowed.update(VERTICAL_PROFILES[domain]["canonical_attributes"])
        if transformation != "unmapped" and target not in allowed:
            raise MappingReviewError("Unsupported canonical target field.")
        return {
            "source_field": source_field,
            "source_alias": _safe_text(item.get("source_alias"), 128),
            "target_field": target,
            "transformation_type": transformation,
            "source_unit": _safe_text(item.get("source_unit"), 50),
            "target_unit": _safe_text(item.get("target_unit"), 50),
            "mapping_status": str(item.get("mapping_status", "proposed")),
            "confidence": str(item.get("confidence", "unavailable")),
            "evidence_json": item.get("evidence_json", {}),
            "reviewer_type": str(item.get("reviewer_type", "human")),
            "human_override": bool(item.get("human_override", False)),
            "notes": _safe_text(item.get("notes"), 500),
        }

    def _validate_value_mapping(self, item: dict[str, Any], domain: str) -> dict[str, Any]:
        _reject_unsafe(item)
        target_field = _safe_text(item.get("target_field"), 100)
        allowed_targets = {
            "material", "lifecycle_status", "operational_status", "placement_type",
            "asset_subtype", "main_type", "valve_type", "facility_type",
        }
        if target_field not in allowed_targets:
            raise MappingReviewError("Unsupported value-mapping target field.")
        transformation = str(item.get("transformation_type", "domain_mapping"))
        if transformation not in TRANSFORMATION_TYPES:
            raise MappingReviewError("Transformation type must use the deterministic allowlist.")
        source_value = _safe_text(item.get("source_value"), 100)
        target_value = _safe_text(item.get("target_value"), 100)
        if target_field == "material" and target_value not in {*MATERIAL_CODES.values(), "other", "unknown", "needs_review"}:
            raise MappingReviewError("Material value is not in the deterministic allowlist.")
        if target_field == "lifecycle_status" and target_value not in LIFECYCLE_STATES:
            raise MappingReviewError("Lifecycle value is not in the deterministic allowlist.")
        operational = WATER_OPERATIONAL_STATES if domain == "water" else WASTEWATER_OPERATIONAL_STATES
        if target_field == "operational_status" and target_value not in operational:
            raise MappingReviewError("Operational value is not in the deterministic allowlist.")
        return {
            "source_field": _safe_text(item.get("source_field"), 128),
            "source_value": source_value,
            "target_field": target_field,
            "target_value": target_value,
            "transformation_type": transformation,
            "confidence": str(item.get("confidence", "unavailable")),
            "evidence_json": item.get("evidence_json", {}),
            "review_status": str(item.get("review_status", "proposed")),
            "human_override": bool(item.get("human_override", False)),
        }

    def _upsert_field(self, connection: sqlite3.Connection, plan_id: str, mapping: dict[str, Any], now: str) -> None:
        connection.execute(
            """INSERT INTO source_canonical_field_mappings
            (mapping_id, plan_id, source_field, source_alias, target_field,
             transformation_type, source_unit, target_unit, mapping_status,
             confidence, evidence_json, reviewer_type, human_override, notes,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id, source_field) DO UPDATE SET
            source_alias=excluded.source_alias, target_field=excluded.target_field,
            transformation_type=excluded.transformation_type,
            source_unit=excluded.source_unit, target_unit=excluded.target_unit,
            mapping_status=excluded.mapping_status, confidence=excluded.confidence,
            evidence_json=excluded.evidence_json, reviewer_type=excluded.reviewer_type,
            human_override=excluded.human_override, notes=excluded.notes,
            updated_at=excluded.updated_at""",
            (
                stable_id("field_map", plan_id, mapping["source_field"]), plan_id,
                mapping["source_field"], mapping.get("source_alias", ""),
                mapping.get("target_field", ""), mapping["transformation_type"],
                mapping.get("source_unit", ""), mapping.get("target_unit", ""),
                mapping.get("mapping_status", "proposed"), mapping.get("confidence", "unavailable"),
                _dump(mapping.get("evidence_json", {})), mapping.get("reviewer_type", "system"),
                int(bool(mapping.get("human_override"))), mapping.get("notes", ""), now, now,
            ),
        )

    def _refresh(self, connection: sqlite3.Connection, plan_id: str, *, preserve_status: bool = False) -> None:
        plan = dict(connection.execute(
            "SELECT * FROM source_canonical_mapping_plans WHERE plan_id=?", (plan_id,),
        ).fetchone())
        fields = self._field_rows(connection, plan_id)
        values = self._value_rows(connection, plan_id)
        accepted = [item for item in fields if item["mapping_status"] == "accepted" and item["transformation_type"] != "unmapped"]
        unmapped = [item for item in fields if item["transformation_type"] == "unmapped"]
        accepted_values = [item for item in values if item["review_status"] == "accepted"]
        coded_required = any(item["transformation_type"] in CODED_TRANSFORMATIONS for item in accepted)
        stale = self._current_source_fingerprint(connection, plan) != plan["source_fingerprint"]
        staging = connection.execute(
            """SELECT approved_for_staging FROM staging_plan_items
            WHERE submission_id=? AND layer_id=?""",
            (plan["submission_id"], plan["source_layer_id"]),
        ).fetchone()
        staging_approved = bool(staging and staging["approved_for_staging"])
        blockers = {
            "domain_blocker": "" if plan["utility_domain"] in {"water", "wastewater"} else "A single utility domain requires human confirmation.",
            "taxonomy_blocker": "" if plan["target_asset_class"] else "A canonical asset class requires human confirmation.",
            "geometry_blocker": "" if plan["geometry_status"] in {"compatible", "compatible_with_warning"} else "Geometry compatibility requires review.",
            "coordinate_blocker": "" if plan["coordinate_status"] in {"coordinate_ready", "approved", "confirmed", "passed"} else "Coordinate evidence is not approved.",
            "sensitivity_blocker": "" if plan["sensitivity_status"] in {"approved", "confirmed", "complete", "passed"} else "Sensitivity handling requires human confirmation.",
            "duplicate_blocker": "" if plan["duplicate_status"] in {"no_duplicate_candidate", "resolved", "not_duplicate"} else "A duplicate candidate requires review.",
            "owner_blocker": "" if plan["owner_status"] == "confirmed" else "Owner remains provisional or unknown.",
            "jurisdiction_blocker": "" if plan["jurisdiction_status"] == "confirmed" else "Jurisdiction remains provisional or unknown.",
            "source_role_blocker": "" if plan["source_role"] in {"operational_inventory", "facility_inventory"} else "Source role is not eligible for future operational asset creation.",
            "identifier_blocker": "" if any(item["target_field"] == "source_asset_identifier" for item in accepted) else "A reviewed source identifier mapping is required.",
            "field_mapping_blocker": "" if accepted else "Field mappings require human acceptance.",
            "value_mapping_blocker": "" if not coded_required or accepted_values else "Coded value mappings require human acceptance.",
            "staging_blocker": "" if staging_approved else "Final staging approval is required.",
            "stale_source_blocker": "Source metadata changed after plan creation." if stale else "",
        }
        warnings = list(_load(plan["recommendation_json"], {}).get("contradictory_evidence", []))
        active = [key for key, value in blockers.items() if value]
        status = plan["status"]
        if not preserve_status and status not in {"deferred", "rejected", "superseded", "archived", "approved_plan"}:
            status = _status_from_blockers(blockers)
        fingerprint = stable_fingerprint(
            plan["submission_id"], plan["inspection_run_id"], plan["source_layer_id"],
            plan["source_fingerprint"], plan["utility_domain"], plan["target_asset_class"],
            plan["source_role"], fields, values, _load(plan["decision_json"], {}),
            plan["geometry_status"], MAPPING_RULE_VERSION,
        )
        connection.execute(
            """UPDATE source_canonical_mapping_plans SET plan_fingerprint=?, status=?,
            staging_status=?, mapped_field_count=?, unmapped_field_count=?,
            warning_count=?, blocker_count=?, warnings_json=?, blockers_json=?, updated_at=?
            WHERE plan_id=?""",
            (
                fingerprint, status, "approved" if staging_approved else "not_approved",
                len(accepted), len(unmapped), len(warnings), len(active), _dump(warnings),
                _dump(blockers), intake_registry_service.utc_now(), plan_id,
            ),
        )

    def _eligibility(self, connection: sqlite3.Connection, plan: dict[str, Any]) -> dict[str, Any]:
        blockers = _load(plan["blockers_json"], {})
        stale = self._current_source_fingerprint(connection, plan) != plan["source_fingerprint"]
        if stale:
            blockers["stale_source_blocker"] = "Source metadata changed after plan creation."
        gates = {
            key.removesuffix("_blocker"): {
                "status": "blocked" if value else "passed",
                "reason": value or "Gate satisfied by stored review evidence.",
            }
            for key, value in blockers.items()
        }
        active = [key for key, value in blockers.items() if value]
        if plan["status"] == "deferred":
            state = "deferred"
        elif plan["status"] == "rejected":
            state = "excluded"
        elif bool(plan["approved_plan"]) and active == ["staging_blocker"]:
            state = "approved_plan_staging_blocked"
        elif not active:
            state = "eligible_after_staging_approval"
        elif set(active) == {"staging_blocker"}:
            state = "review_ready"
        else:
            state = "mapping_blocked"
        return {
            "state": state, "gates": gates, "active_blockers": active,
            "approved_plan": bool(plan["approved_plan"]),
            "creation_enabled": False,
            "creation_disabled_reason": "Canonical asset creation is not available in Mapping Review V1. Final staging approval remains a separate future action.",
            "staging_approval_required": True,
        }

    def _safe_plan(self, connection: sqlite3.Connection, plan: dict[str, Any], *, detail: bool = True) -> dict[str, Any]:
        safe = {
            key: value for key, value in plan.items()
            if key not in {"decision_json", "recommendation_json", "warnings_json", "blockers_json", "source_fingerprint"}
        }
        safe.update({
            "approved_plan": bool(plan["approved_plan"]),
            "warnings": _load(plan["warnings_json"], []),
            "blockers": _load(plan["blockers_json"], {}),
            "eligibility": self._eligibility(connection, plan),
            "creation_enabled": False,
            "source_fingerprint_status": "current" if self._current_source_fingerprint(connection, plan) == plan["source_fingerprint"] else "stale",
        })
        if detail:
            evidence = self._evidence(connection, plan["submission_id"], plan["source_layer_id"])
            safe.update({
                "source_evidence": self._safe_source_evidence(evidence["layer"], evidence["state"]),
                "recommendation": _load(plan["recommendation_json"], {}),
                "decisions": _load(plan["decision_json"], {}),
                "field_mappings": self._field_rows(connection, plan["plan_id"]),
                "value_mappings": self._value_rows(connection, plan["plan_id"]),
                "history": [
                    dict(row) for row in connection.execute(
                        """SELECT history_id, plan_version, mapping_id, action, actor_type,
                        actor, reason, created_at FROM source_canonical_mapping_history
                        WHERE plan_id=? ORDER BY created_at""", (plan["plan_id"],),
                    ).fetchall()
                ],
            })
        return safe

    def _field_rows(self, connection: sqlite3.Connection, plan_id: str) -> list[dict[str, Any]]:
        return [
            _json_row(dict(row), ("evidence_json",), ("human_override",))
            for row in connection.execute(
                """SELECT * FROM source_canonical_field_mappings
                WHERE plan_id=? ORDER BY source_field""", (plan_id,),
            ).fetchall()
        ]

    def _value_rows(self, connection: sqlite3.Connection, plan_id: str) -> list[dict[str, Any]]:
        return [
            _json_row(dict(row), ("evidence_json",), ("human_override",))
            for row in connection.execute(
                """SELECT * FROM source_canonical_value_mappings
                WHERE plan_id=? ORDER BY source_field, source_value""", (plan_id,),
            ).fetchall()
        ]

    def _latest_plan(self, connection: sqlite3.Connection, submission_id: str, layer_id: str) -> dict[str, Any] | None:
        row = connection.execute(
            """SELECT * FROM source_canonical_mapping_plans
            WHERE submission_id=? AND source_layer_id=?
            ORDER BY plan_version DESC LIMIT 1""", (submission_id, layer_id),
        ).fetchone()
        return dict(row) if row else None

    def _required_plan(self, connection: sqlite3.Connection, submission_id: str, layer_id: str) -> dict[str, Any]:
        plan = self._latest_plan(connection, submission_id, layer_id)
        if not plan:
            raise MappingReviewError("Mapping review plan not found.", 404)
        return plan

    def _history(
        self, connection: sqlite3.Connection, plan_id: str, plan_version: int,
        action: str, prior: Any, new: Any, payload: dict[str, Any], reason: str,
    ) -> None:
        connection.execute(
            """INSERT INTO source_canonical_mapping_history
            (history_id, plan_id, plan_version, mapping_id, action, prior_value,
             new_value, actor_type, actor, reason, created_at)
            VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), plan_id, plan_version, action, _dump(prior), _dump(new),
                "human" if payload.get("actor") or payload.get("approved_by") else "system",
                _safe_text(payload.get("actor") or payload.get("approved_by") or "mapping_review", 100),
                reason, intake_registry_service.utc_now(),
            ),
        )

    @staticmethod
    def _safe_layer_label(layer_id: str) -> str:
        return f"Reviewed layer {stable_id('ref', layer_id).split('_', 1)[1][:10]}"


def _status_from_blockers(blockers: dict[str, str]) -> str:
    order = (
        ("stale_source_blocker", "stale_source"),
        ("domain_blocker", "needs_domain_review"),
        ("taxonomy_blocker", "needs_taxonomy_review"),
        ("geometry_blocker", "needs_taxonomy_review"),
        ("coordinate_blocker", "needs_coordinate_review"),
        ("sensitivity_blocker", "needs_sensitivity_review"),
        ("duplicate_blocker", "duplicate_review_required"),
        ("owner_blocker", "needs_owner_confirmation"),
        ("jurisdiction_blocker", "needs_jurisdiction_confirmation"),
        ("field_mapping_blocker", "needs_field_mapping"),
        ("identifier_blocker", "needs_field_mapping"),
        ("value_mapping_blocker", "needs_value_mapping"),
        ("source_role_blocker", "mapping_blocked"),
        ("staging_blocker", "staging_blocked"),
    )
    return next((status for blocker, status in order if blockers.get(blocker)), "review_ready")


def _transformation_for(target: str, source_field: str) -> str:
    if not target:
        return "unmapped"
    if target in {"nominal_diameter", "diameter"}:
        return "numeric_parse"
    if target == "installation_date":
        return "date_parse"
    if target == "lifecycle_status":
        return "lifecycle_mapping"
    if target == "operational_status":
        return "operational_status_mapping"
    if target in {"material", "placement_type", "main_type", "valve_type", "asset_subtype"}:
        return "domain_mapping"
    if target in {"source_asset_identifier", "source_asset_id"}:
        return "normalized_identifier"
    return "direct" if _norm(source_field) == _norm(target) else "renamed"


def _normalize_unit(value: str) -> str:
    normalized = value.strip().casefold().replace(".", "")
    aliases = {
        '"': "inch", "in": "inch", "inch": "inch", "inches": "inch",
        "mm": "millimeter", "millimeter": "millimeter", "millimeters": "millimeter",
        "'": "foot", "ft": "foot", "foot": "foot", "feet": "foot",
        "m": "meter", "meter": "meter", "meters": "meter",
    }
    return aliases.get(normalized, "")


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _safe_text(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if _UNSAFE_VALUE.search(text):
        raise MappingReviewError("Filesystem paths and external URLs are not accepted.")
    return text[:limit]


def _reject_unsafe(value: Any) -> None:
    if isinstance(value, dict):
        if _UNSAFE_KEYS & {str(key).casefold() for key in value}:
            raise MappingReviewError("Filesystem, executable, credential, and external URL inputs are not accepted.")
        for item in value.values():
            _reject_unsafe(item)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe(item)
    elif isinstance(value, str) and _UNSAFE_VALUE.search(value):
        raise MappingReviewError("Filesystem, executable, credential, and external URL inputs are not accepted.")


def _load(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _json_row(row: dict[str, Any], json_fields: tuple[str, ...], bool_fields: tuple[str, ...]) -> dict[str, Any]:
    for field in json_fields:
        row[field] = _load(row.get(field), {})
    for field in bool_fields:
        row[field] = bool(row.get(field))
    return row


service = MappingReviewService()
