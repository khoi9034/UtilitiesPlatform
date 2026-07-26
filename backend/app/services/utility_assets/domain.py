from __future__ import annotations

import hashlib
import json
import re
from typing import Any

RULE_VERSION = "canonical-assets-v1"
UTILITY_VERTICALS = ("electric_distribution", "telecom_fiber")
FUTURE_VERTICALS = ("water", "wastewater", "gas", "stormwater")
LIFECYCLE_STATES = (
    "proposed", "planned", "approved", "under_construction", "installed",
    "active", "inactive", "abandoned", "retired", "removed", "unknown",
)
REVIEW_STATES = ("imported", "mapped", "needs_review", "provisionally_approved", "approved", "deferred", "excluded")
QA_STATES = ("not_evaluated", "passed", "warning", "failed", "blocked", "acknowledged")
OWNER_STATES = ("unknown", "candidate", "provisional", "confirmed", "disputed")
ELECTRIC_OPERATIONAL_STATES = ("energized", "de_energized", "normally_open", "normally_closed", "open", "closed", "unknown")
TELECOM_OPERATIONAL_STATES = ("proposed", "installed", "active", "reserved", "unavailable", "retired", "unknown")
RELATIONSHIP_TYPES = (
    "connects_to", "upstream_of", "downstream_of", "contained_in", "mounted_on",
    "routed_through", "protected_by", "feeds", "served_by", "spliced_to",
    "terminates_at", "belongs_to_feeder", "belongs_to_circuit", "belongs_to_route",
    "associated_with_work_order", "replaces", "retires", "reference_for",
)
RELATIONSHIP_SOURCES = ("source", "spatially_inferred", "rule_inferred", "human_confirmed")
TRANSFORMATION_TYPES = (
    "direct", "renamed", "normalized_text", "normalized_identifier", "boolean_mapping",
    "lifecycle_mapping", "unit_conversion", "numeric_parse", "domain_mapping", "inferred", "unmapped",
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
    "central_office", "network_hub", "fiber_cabinet", "fiber_route", "fiber_cable",
    "conduit", "pole", "handhole", "manhole", "splice_closure", "splitter", "terminal",
    "service_area", "proposed_construction_segment", "telecom_structure", "reference_boundary",
)
TELECOM_FIELDS = (
    "route_id", "cable_id", "cable_type", "fiber_count", "strand_start", "strand_end",
    "placement_type", "from_structure_id", "to_structure_id", "splice_closure_id",
    "cabinet_id", "terminal_id", "splitter_ratio", "total_capacity", "used_capacity",
    "reserved_capacity", "available_capacity", "construction_status", "service_area_id",
    "network_tier", "hub_id",
)


def taxonomy(vertical: str | None = None) -> dict[str, Any]:
    profiles = {
        "electric_distribution": {
            "label": "Electric Distribution",
            "asset_classes": list(ELECTRIC_CLASSES),
            "canonical_attributes": list(ELECTRIC_FIELDS),
            "operational_states": list(ELECTRIC_OPERATIONAL_STATES),
        },
        "telecom_fiber": {
            "label": "Telecom/Fiber",
            "asset_classes": list(TELECOM_CLASSES),
            "canonical_attributes": list(TELECOM_FIELDS),
            "operational_states": list(TELECOM_OPERATIONAL_STATES),
        },
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
    classes = ELECTRIC_CLASSES if vertical == "electric_distribution" else TELECOM_CLASSES if vertical == "telecom_fiber" else ()
    if asset_class not in classes:
        raise ValueError("Asset class is not valid for the selected utility vertical.")


def validate_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    transformation = str(mapping.get("transformation_type", ""))
    if transformation not in TRANSFORMATION_TYPES:
        raise ValueError("Transformation type must use the deterministic allowlist.")
    if any(key in mapping for key in ("expression", "script", "python", "sql", "command", "url")):
        raise ValueError("Executable mappings and external references are not accepted.")
    canonical_field = str(mapping.get("canonical_field", ""))
    valid_fields = set(SHARED_FIELDS) | set(ELECTRIC_FIELDS) | set(TELECOM_FIELDS)
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
