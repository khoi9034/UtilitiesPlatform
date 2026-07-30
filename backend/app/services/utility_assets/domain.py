from __future__ import annotations

import hashlib
import json
import re
from typing import Any

RULE_VERSION = "canonical-assets-v1"
UTILITY_VERTICALS = ("electric_distribution", "telecom_fiber", "water", "wastewater")
SOURCE_UTILITY_DOMAINS = (*UTILITY_VERTICALS, "water_wastewater", "multi_utility", "unknown")
FUTURE_VERTICALS = ("gas", "stormwater")
LIFECYCLE_STATES = (
    "proposed", "planned", "approved", "under_construction", "installed",
    "active", "inactive", "abandoned", "retired", "removed", "unknown",
)
REVIEW_STATES = ("imported", "mapped", "needs_review", "provisionally_approved", "approved", "deferred", "excluded")
QA_STATES = ("not_evaluated", "passed", "warning", "failed", "blocked", "acknowledged")
OWNER_STATES = ("unknown", "candidate", "provisional", "confirmed", "disputed")
ELECTRIC_OPERATIONAL_STATES = ("energized", "de_energized", "normally_open", "normally_closed", "open", "closed", "unknown")
TELECOM_OPERATIONAL_STATES = ("proposed", "installed", "active", "reserved", "unavailable", "retired", "unknown")
WATER_OPERATIONAL_STATES = (
    "open", "closed", "active", "inactive", "in_service", "out_of_service",
    "available", "unavailable", "unknown",
)
WASTEWATER_OPERATIONAL_STATES = (
    "active", "inactive", "in_service", "out_of_service", "gravity",
    "pressurized", "operating", "not_operating", "available", "unavailable", "unknown",
)
SOURCE_ROLES = (
    "operational_inventory", "reference_inventory", "facility_inventory",
    "network_context", "service_area", "boundary", "planning_context",
    "historical", "deprecated", "proposed_design", "service_availability",
    "funding_area", "reference_boundary", "unknown",
)
RELATIONSHIP_TYPES = (
    "connects_to", "upstream_of", "downstream_of", "contained_in", "mounted_on",
    "routed_through", "protected_by", "feeds", "served_by", "spliced_to",
    "terminates_at", "belongs_to_feeder", "belongs_to_circuit", "belongs_to_route",
    "associated_with_work_order", "replaces", "retires", "reference_for",
    "belongs_to_pressure_zone", "belongs_to_water_system", "belongs_to_basin",
    "flows_to", "draws_from",
)
RELATIONSHIP_SOURCES = ("source", "spatially_inferred", "rule_inferred", "human_confirmed")
TRANSFORMATION_TYPES = (
    "direct", "renamed", "normalized_text", "normalized_identifier", "numeric_parse",
    "unit_conversion", "boolean_mapping", "lifecycle_mapping",
    "operational_status_mapping", "domain_mapping", "subtype_mapping", "date_parse",
    "null_normalization", "safe_constant", "inferred_with_review", "inferred", "unmapped",
)

SHARED_FIELDS = (
    "asset_id", "utility_vertical", "asset_class", "asset_subtype", "canonical_name",
    "display_name", "geometry_type", "lifecycle_status", "operational_status",
    "owner_candidate", "owner_status", "jurisdiction", "source_system",
    "source_submission_id", "source_layer_id", "source_record_id",
    "source_asset_identifier", "parent_asset_id", "container_asset_id",
    "connected_from_asset_id", "connected_to_asset_id", "network_level", "work_order_id",
    "qa_status", "review_status", "sensitivity", "confidence", "installation_date",
    "retirement_date", "last_inspected_at", "last_reviewed_at", "created_at", "updated_at",
    "notes", "source_attributes_json", "canonical_attributes_json", "geometry_summary_json",
    "evidence_json",
)
ELECTRIC_CLASSES = (
    "substation", "feeder", "feeder_breaker", "switch", "fuse", "recloser",
    "transformer", "pole", "overhead_conductor", "underground_conductor", "secondary_conductor", "conduit",
    "service_point", "junction", "attachment", "electric_structure", "reference_boundary",
)
ELECTRIC_FIELDS = (
    "feeder_id", "circuit_id", "phase", "nominal_voltage", "operating_voltage",
    "normally_open", "device_state", "protective_device_type", "upstream_asset_id",
    "downstream_asset_id", "transformer_rating_kva", "transformer_configuration",
    "conductor_material", "conductor_size", "conductor_count", "placement_type",
    "energized_status", "conduit_id", "structure_id", "service_type",
    "customer_count_safe_aggregate",
)
TELECOM_CLASSES = (
    "central_office", "headend", "olt", "network_hub", "fiber_cabinet",
    "fiber_route", "fiber_cable", "feeder_cable", "distribution_cable",
    "conduit", "pole", "handhole", "manhole", "splice_closure", "splitter", "terminal",
    "service_drop", "customer_location", "service_area", "proposed_construction_segment",
    "telecom_structure", "reference_boundary",
)
TELECOM_FIELDS = (
    "route_id", "cable_id", "cable_type", "fiber_count", "strand_start", "strand_end",
    "placement_type", "from_structure_id", "to_structure_id", "splice_closure_id",
    "cabinet_id", "terminal_id", "splitter_ratio", "total_capacity", "used_capacity",
    "reserved_capacity", "available_capacity", "construction_status", "service_area_id",
    "network_tier", "hub_id",
)
WATER_CLASSES = (
    "water_main", "transmission_main", "distribution_main", "service_line",
    "hydrant_lateral", "raw_water_main", "reclaimed_water_main",
    "abandoned_water_main", "unknown_water_line", "valve", "isolation_valve",
    "control_valve", "pressure_reducing_valve", "air_release_valve", "blowoff",
    "hydrant", "meter", "meter_vault", "fitting", "tee", "elbow", "reducer",
    "coupling", "pump", "pump_station", "storage_tank", "elevated_tank",
    "reservoir", "treatment_facility", "well", "backflow_device",
    "pressure_sensor", "sampling_point", "vault", "structure",
    "unknown_water_device", "pressure_zone", "service_area", "treatment_area",
    "water_system_boundary", "easement", "facility_site",
)
WATER_FIELDS = (
    "water_system_id", "water_system_name", "main_id", "service_line_id",
    "valve_id", "hydrant_id", "meter_id", "facility_id", "pressure_zone_id",
    "from_node_id", "to_node_id", "nominal_diameter", "diameter", "diameter_unit",
    "material", "installation_date", "main_type", "placement_type", "valve_type",
    "valve_state", "hydrant_status", "meter_type", "pump_type", "storage_type",
    "facility_type", "source_asset_id", "elevation", "elevation_unit", "capacity",
    "capacity_unit", "owner", "jurisdiction", "source_document_id",
)
WASTEWATER_CLASSES = (
    "gravity_main", "force_main", "pressure_sewer", "service_lateral",
    "interceptor", "trunk_sewer", "outfall_pipe", "abandoned_sewer",
    "unknown_wastewater_line", "manhole", "cleanout", "fitting", "junction",
    "lift_station", "pump", "wet_well", "treatment_facility", "outfall",
    "discharge_point", "monitoring_point", "sampling_point", "valve",
    "air_release_valve", "vault", "structure", "unknown_wastewater_device",
    "sewer_basin", "collection_area", "treatment_service_area", "facility_site",
    "easement", "overflow_area", "wastewater_system_boundary",
)
WASTEWATER_FIELDS = (
    "wastewater_system_id", "sewer_basin_id", "basin_id", "gravity_main_id",
    "force_main_id", "lateral_id", "manhole_id", "lift_station_id", "facility_id",
    "outfall_id", "from_node_id", "to_node_id", "upstream_structure_id",
    "downstream_structure_id", "nominal_diameter", "diameter", "diameter_unit",
    "material", "rim_elevation", "upstream_invert", "downstream_invert",
    "elevation_unit", "slope", "flow_direction", "main_type", "installation_date",
    "owner", "jurisdiction", "source_document_id",
)

VERTICAL_PROFILES = {
    "electric_distribution": {
        "label": "Electric Distribution",
        "family": "electric",
        "asset_classes": ELECTRIC_CLASSES,
        "canonical_attributes": ELECTRIC_FIELDS,
        "operational_states": ELECTRIC_OPERATIONAL_STATES,
    },
    "telecom_fiber": {
        "label": "Telecom/Fiber",
        "family": "telecom",
        "asset_classes": TELECOM_CLASSES,
        "canonical_attributes": TELECOM_FIELDS,
        "operational_states": TELECOM_OPERATIONAL_STATES,
    },
    "water": {
        "label": "Water",
        "family": "water_wastewater",
        "asset_classes": WATER_CLASSES,
        "canonical_attributes": WATER_FIELDS,
        "operational_states": WATER_OPERATIONAL_STATES,
    },
    "wastewater": {
        "label": "Wastewater",
        "family": "water_wastewater",
        "asset_classes": WASTEWATER_CLASSES,
        "canonical_attributes": WASTEWATER_FIELDS,
        "operational_states": WASTEWATER_OPERATIONAL_STATES,
    },
}


def taxonomy(vertical: str | None = None) -> dict[str, Any]:
    profiles = {
        key: {field: list(value) if isinstance(value, tuple) else value for field, value in profile.items()}
        for key, profile in VERTICAL_PROFILES.items()
    }
    if vertical:
        if vertical not in profiles:
            raise ValueError("Unsupported utility vertical.")
        return {"utility_vertical": vertical, **profiles[vertical], **shared_taxonomy()}
    return {
        "utility_verticals": [{"id": key, **value} for key, value in profiles.items()],
        "future_verticals": list(FUTURE_VERTICALS),
        **shared_taxonomy(),
    }


def shared_taxonomy() -> dict[str, Any]:
    return {
        "shared_fields": list(SHARED_FIELDS),
        "lifecycle_states": list(LIFECYCLE_STATES),
        "review_states": list(REVIEW_STATES),
        "qa_states": list(QA_STATES),
        "owner_states": list(OWNER_STATES),
        "relationship_types": list(RELATIONSHIP_TYPES),
        "relationship_sources": list(RELATIONSHIP_SOURCES),
        "source_roles": list(SOURCE_ROLES),
        "source_utility_domains": list(SOURCE_UTILITY_DOMAINS),
        "transformation_types": list(TRANSFORMATION_TYPES),
        "rule_version": RULE_VERSION,
    }


def stable_id(prefix: str, *values: object) -> str:
    normalized = "|".join(re.sub(r"\s+", " ", str(value).strip().lower()) for value in values)
    return f"{prefix}_{hashlib.sha256(normalized.encode()).hexdigest()[:20]}"


def stable_fingerprint(*values: object) -> str:
    normalized = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


def validate_vertical_and_class(vertical: str, asset_class: str) -> None:
    classes = VERTICAL_PROFILES.get(vertical, {}).get("asset_classes", ())
    if asset_class not in classes:
        raise ValueError("Asset class is not valid for the selected utility vertical.")


def validate_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    transformation = str(mapping.get("transformation_type", ""))
    if transformation not in TRANSFORMATION_TYPES:
        raise ValueError("Transformation type must use the deterministic allowlist.")
    unsafe = {"expression", "script", "python", "sql", "command", "url", "path", "credentials"}
    if unsafe & {str(key).casefold() for key in mapping}:
        raise ValueError("Executable mappings and external references are not accepted.")
    canonical_field = str(mapping.get("canonical_field", ""))
    valid_fields = set(SHARED_FIELDS)
    for profile in VERTICAL_PROFILES.values():
        valid_fields.update(profile["canonical_attributes"])
    if transformation != "unmapped" and canonical_field not in valid_fields:
        raise ValueError("Canonical field is not part of Canonical Utility Asset Model V1.")
    return {
        "source_field": str(mapping.get("source_field", "")).strip(),
        "source_alias": str(mapping.get("source_alias", "")).strip(),
        "canonical_field": canonical_field,
        "transformation_type": transformation,
        "confidence": str(mapping.get("confidence", "unavailable")),
        "evidence_json": mapping.get("evidence_json", {}),
        "mapping_status": str(mapping.get("mapping_status", "proposed")),
        "reviewer_type": str(mapping.get("reviewer_type", "human")),
        "human_override": bool(mapping.get("human_override", False)),
        "notes": str(mapping.get("notes", ""))[:500],
    }
