from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterable
from typing import Any

from app.services import intake_registry_service
from app.services.connectivity_qa.calibration import CALIBRATION_RULE_VERSION, build_issue_groups
from app.services.connectivity_qa.rules import (
    MODEL_VERSION,
    RULE_VERSION as QA_RULE_VERSION,
    build_graph,
    evaluate_rule,
    graph_fingerprint,
    rule_profile,
)
from app.services.network_trace.calibration import CALIBRATION_VERSION as TRACE_CALIBRATION_VERSION
from app.services.network_trace.calibration import calibrate_trace
from app.services.network_trace.engine import trace_graph
from app.services.network_trace.models import normalize_request
from app.services.network_trace.profiles import (
    TRACE_PROFILE_VERSION,
    TRACE_PROFILES,
    TRACE_RULE_VERSION,
    trace_definition,
)
from app.services.utility_assets.domain import (
    ELECTRIC_FIELDS,
    ELECTRIC_OPERATIONAL_STATES,
    LIFECYCLE_STATES,
    RELATIONSHIP_TYPES,
    SHARED_FIELDS,
    TELECOM_FIELDS,
    TELECOM_OPERATIONAL_STATES,
    UTILITY_VERTICALS,
    WATER_FIELDS,
    WATER_OPERATIONAL_STATES,
    WASTEWATER_FIELDS,
    WASTEWATER_OPERATIONAL_STATES,
    stable_fingerprint,
    stable_id,
    validate_vertical_and_class,
)

PROPOSAL_RULE_VERSION = "proposed-edit-rules-v1"
OVERLAY_VERSION = "proposed-edit-overlay-v1"
ANALYSIS_VERSION = "proposed-edit-analysis-v1"
PACKAGE_VERSION = "proposed-edit-package-v1"
SCENARIO_VERSION = "proposed-edit-scenarios-v1"

DISCLAIMER = (
    "UtilitiesPlatform Proposed Edit Workspace V1 creates isolated vendor-neutral change plans and "
    "evaluates them against temporary network overlays. Approval confirms the plan for future "
    "implementation review; it does not modify an operational utility GIS, execute switching, "
    "allocate telecom capacity, or apply changes to ArcFM, Smallworld, Esri Utility Network, or "
    "another proprietary system."
)

LIFECYCLE_STATES_PROPOSAL = (
    "draft", "validation_failed", "ready_for_analysis", "analyzing", "analysis_complete",
    "needs_revision", "submitted_for_review", "under_review", "approved", "rejected",
    "deferred", "withdrawn", "superseded", "implementation_ready",
    "implementation_exported", "archived",
)
REVIEW_STATUSES = ("not_submitted", "submitted", "under_review", "decision_recorded")
APPROVAL_STATUSES = ("not_requested", "pending", "approved", "rejected", "deferred", "withdrawn")
IMPLEMENTATION_READINESS = (
    "not_evaluated", "blocked", "needs_revision", "review_ready", "conditionally_ready",
    "approved_plan_only", "implementation_package_ready",
)
COMPARISON_RESULTS = ("improved", "unchanged", "worsened", "mixed", "incomparable", "failed_safely")
EXTERNAL_MAPPING_STATUSES = ("not_mapped", "conceptually_mappable", "adapter_required", "unsupported", "unknown")
ADAPTER_CAPABILITIES = (
    "create_asset", "update_attribute", "update_lifecycle", "update_operational_state",
    "create_relationship", "remove_relationship", "replace_asset", "retire_asset",
    "geometry_edit_required", "versioned_edit_required", "network_rebuild_required",
    "topology_validation_required", "external_approval_required",
)

SHARED_PROPOSAL_TYPES = (
    "connectivity_correction", "attribute_correction", "relationship_correction",
    "lifecycle_change", "operational_state_proposal", "containment_association",
    "structure_association", "asset_replacement", "asset_retirement",
    "proposed_asset_addition", "route_or_feeder_assignment", "data_quality_correction",
    "manual_investigation", "multi_operation_change_set",
)
VERTICAL_PROPOSAL_TYPES = {
    "electric_distribution": (
        "connect_conductor_endpoint", "assign_transformer_feeder", "correct_phase",
        "correct_voltage", "associate_conductor_conduit", "confirm_or_change_device_state",
        "replace_transformer", "replace_pole", "correct_upstream_downstream",
        "add_protective_relationship", "retire_electric_asset", "add_proposed_electric_asset",
    ),
    "telecom_fiber": (
        "assign_cable_endpoint", "add_splice_relationship", "correct_strand_assignment",
        "correct_capacity", "associate_cable_conduit", "associate_aerial_support",
        "connect_terminal", "correct_route_membership", "close_proposed_route_gap",
        "replace_cable", "retire_telecom_asset", "add_proposed_telecom_asset",
    ),
    "water": (
        "add_main", "replace_main", "retire_main", "add_valve", "replace_valve",
        "add_hydrant", "relocate_hydrant", "add_service", "replace_meter",
        "update_pressure_zone_relationship", "repair_water_connectivity",
        "update_water_asset_attributes",
    ),
    "wastewater": (
        "add_gravity_main", "replace_gravity_main", "add_force_main", "add_manhole",
        "relocate_manhole", "add_lateral", "replace_lift_station_relationship",
        "update_invert_or_rim", "update_flow_direction_relationship",
        "retire_abandoned_wastewater_asset", "repair_wastewater_connectivity",
    ),
}
OPERATION_TYPES = (
    "add_asset", "update_asset_attribute", "update_asset_attributes",
    "change_lifecycle_status", "change_operational_status", "add_relationship",
    "remove_relationship", "replace_relationship", "update_relationship",
    "confirm_provisional_relationship", "mark_relationship_provisional",
    "assign_membership", "remove_membership", "retire_asset", "replace_asset",
    "associate_container", "remove_container_association", "associate_structure",
    "remove_structure_association", "add_note", "request_manual_investigation",
)
EDITABLE_STATES = {"draft", "validation_failed", "ready_for_analysis", "analysis_complete"}
FIELD_ALLOWLIST = {
    "electric_distribution": set(SHARED_FIELDS) | set(ELECTRIC_FIELDS),
    "telecom_fiber": set(SHARED_FIELDS) | set(TELECOM_FIELDS),
    "water": set(SHARED_FIELDS) | set(WATER_FIELDS),
    "wastewater": set(SHARED_FIELDS) | set(WASTEWATER_FIELDS),
}
NUMERIC_FIELDS = {
    "nominal_voltage", "operating_voltage", "transformer_rating_kva", "conductor_count",
    "customer_count_safe_aggregate", "fiber_count", "strand_start", "strand_end",
    "total_capacity", "used_capacity", "reserved_capacity", "available_capacity",
    "diameter", "elevation", "capacity", "upstream_invert", "downstream_invert",
    "rim_elevation", "slope",
}
BOOLEAN_FIELDS = {"normally_open"}
LIFECYCLE_TRANSITIONS = {
    "proposed": {"planned", "approved"},
    "planned": {"approved", "deferred"},
    "approved": {"under_construction", "inactive"},
    "under_construction": {"installed", "inactive"},
    "installed": {"active", "inactive", "removed"},
    "active": {"inactive", "retired", "removed"},
    "inactive": {"active", "retired", "removed"},
    "abandoned": {"active", "retired", "removed"},
    "retired": {"active", "removed"},
    "removed": {"active"},
    "unknown": {"active", "inactive", "retired"},
}
STRONG_REVIEW_TRANSITIONS = {
    ("retired", "active"), ("removed", "active"), ("abandoned", "active"),
    ("unknown", "active"), ("active", "removed"), ("installed", "removed"),
}
_OPERATION_FIELDS = {
    "operation_type", "target_asset_id", "target_relationship_id", "new_asset_temporary_id",
    "affected_vertical", "field_name", "prior_value", "proposed_value", "prior_values",
    "proposed_values", "relationship_type", "from_asset_id", "to_asset_id",
    "replacement_asset_id", "reason", "source_issue_group_ids", "source_trace_run_ids",
    "source_trace_calibration_ids", "provisional", "direction",
}
_FORBIDDEN_KEYS = {
    "path", "filesystem_path", "sql", "python", "shell", "command", "expression",
    "script", "rule_file", "url", "external_url", "vendor_command", "credentials",
}
_PATH_OR_URL = re.compile(r"(?:[a-zA-Z]:[\\/]|\\\\|https?://)", re.IGNORECASE)


def catalog(vertical: str | None = None) -> dict[str, Any]:
    if vertical is not None:
        validate_vertical(vertical)
        return {
            "utility_vertical": vertical,
            "proposal_types": [*SHARED_PROPOSAL_TYPES, *VERTICAL_PROPOSAL_TYPES[vertical]],
            "operation_types": list(OPERATION_TYPES),
            "lifecycle_states": list(LIFECYCLE_STATES_PROPOSAL),
            "disclaimer": DISCLAIMER,
        }
    return {
        "proposal_rule_version": PROPOSAL_RULE_VERSION,
        "utility_verticals": list(UTILITY_VERTICALS),
        "shared_proposal_types": list(SHARED_PROPOSAL_TYPES),
        "vertical_proposal_types": {key: list(value) for key, value in VERTICAL_PROPOSAL_TYPES.items()},
        "lifecycle_states": list(LIFECYCLE_STATES_PROPOSAL),
        "review_statuses": list(REVIEW_STATUSES),
        "approval_statuses": list(APPROVAL_STATUSES),
        "implementation_readiness": list(IMPLEMENTATION_READINESS),
        "disclaimer": DISCLAIMER,
    }


def operation_catalog() -> dict[str, Any]:
    return {
        "operation_types": list(OPERATION_TYPES),
        "external_mapping_statuses": list(EXTERNAL_MAPPING_STATUSES),
        "required_adapter_capabilities": list(ADAPTER_CAPABILITIES),
        "executable_operations_supported": False,
        "disclaimer": DISCLAIMER,
    }


def validate_vertical(vertical: str) -> None:
    if vertical not in UTILITY_VERTICALS:
        raise ValueError("Unsupported utility vertical.")


def proposal_type(vertical: str, value: object) -> str:
    validate_vertical(vertical)
    normalized = str(value or "").strip()
    if normalized not in {*SHARED_PROPOSAL_TYPES, *VERTICAL_PROPOSAL_TYPES[vertical]}:
        raise ValueError("Proposal type is not allowed for the selected utility vertical.")
    return normalized


def reject_unsafe(value: Any, *, allowed_keys: set[str] | None = None) -> None:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        if _FORBIDDEN_KEYS.intersection(keys):
            raise ValueError("Executable, external, and filesystem proposal inputs are not accepted.")
        if allowed_keys is not None:
            unknown = keys.difference(allowed_keys)
            if unknown:
                raise ValueError(f"Unsupported proposal field: {sorted(unknown)[0]}.")
        for item in value.values():
            reject_unsafe(item)
    elif isinstance(value, list):
        for item in value:
            reject_unsafe(item)
    elif isinstance(value, str) and _PATH_OR_URL.search(value):
        raise ValueError("Filesystem paths and external URLs are not accepted.")


def normalize_operation(
    vertical: str,
    proposal_id: str,
    version: int,
    sequence: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validate_vertical(vertical)
    reject_unsafe(payload, allowed_keys=_OPERATION_FIELDS)
    operation_type = str(payload.get("operation_type", "")).strip()
    if operation_type not in OPERATION_TYPES:
        raise ValueError("Operation type must use the deterministic allowlist.")
    proposed_values = payload.get("proposed_values") or {}
    prior_values = payload.get("prior_values") or {}
    if not isinstance(proposed_values, dict) or not isinstance(prior_values, dict):
        raise ValueError("Operation value collections must be JSON objects.")
    operation_id = stable_id("proposal-operation", proposal_id, version, sequence)
    return {
        "operation_id": operation_id,
        "proposal_id": proposal_id,
        "proposal_version": version,
        "operation_type": operation_type,
        "sequence": sequence,
        "target_asset_id": _text(payload.get("target_asset_id"), 120),
        "target_relationship_id": _text(payload.get("target_relationship_id"), 120),
        "new_asset_temporary_id": _text(payload.get("new_asset_temporary_id"), 120),
        "affected_vertical": vertical,
        "field_name": _text(payload.get("field_name"), 100),
        "prior_value": payload.get("prior_value"),
        "proposed_value": payload.get("proposed_value"),
        "prior_values": prior_values,
        "proposed_values": proposed_values,
        "relationship_type": _text(payload.get("relationship_type"), 80),
        "from_asset_id": _text(payload.get("from_asset_id"), 120),
        "to_asset_id": _text(payload.get("to_asset_id"), 120),
        "replacement_asset_id": _text(payload.get("replacement_asset_id"), 120),
        "reason": _text(payload.get("reason"), 1000),
        "source_issue_group_ids": _string_list(payload.get("source_issue_group_ids")),
        "source_trace_run_ids": _string_list(payload.get("source_trace_run_ids")),
        "source_trace_calibration_ids": _string_list(payload.get("source_trace_calibration_ids")),
        "provisional": bool(payload.get("provisional", False)),
        "direction": _text(payload.get("direction") or "forward", 30),
        "validation_status": "not_evaluated",
        "validation_errors": [],
        "validation_warnings": [],
    }


def baseline_snapshot(
    vertical: str,
    assets: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    qa_fingerprint: str,
    qa_calibration_fingerprint: str,
) -> dict[str, Any]:
    graph, asset_checksum, relationship_checksum = graph_fingerprint(vertical, assets, relationships)
    fingerprint = stable_fingerprint(
        graph, asset_checksum, relationship_checksum, qa_fingerprint, qa_calibration_fingerprint,
        MODEL_VERSION, QA_RULE_VERSION, CALIBRATION_RULE_VERSION, TRACE_PROFILE_VERSION,
        TRACE_RULE_VERSION, TRACE_CALIBRATION_VERSION, PROPOSAL_RULE_VERSION,
    )
    return {
        "baseline_fingerprint": fingerprint,
        "canonical_asset_dataset_fingerprint": asset_checksum,
        "canonical_relationship_dataset_fingerprint": relationship_checksum,
        "qa_run_fingerprint": qa_fingerprint,
        "qa_calibration_fingerprint": qa_calibration_fingerprint,
        "trace_profile_version": TRACE_PROFILE_VERSION,
        "trace_calibration_version": TRACE_CALIBRATION_VERSION,
        "source_snapshot_identifier": stable_id("proposal-baseline", vertical, fingerprint),
    }


def proposal_fingerprint(proposal: dict[str, Any], operations: list[dict[str, Any]]) -> str:
    return stable_fingerprint(
        proposal["proposal_id"], proposal["proposal_version"], proposal["utility_vertical"],
        proposal["proposal_type"], proposal["title"], proposal.get("summary", ""),
        proposal["baseline_fingerprint"],
        [
            {
                key: operation.get(key)
                for key in (
                    "operation_type", "sequence", "target_asset_id", "target_relationship_id",
                    "new_asset_temporary_id", "field_name", "proposed_value", "proposed_values",
                    "relationship_type", "from_asset_id", "to_asset_id", "replacement_asset_id",
                )
            }
            for operation in sorted(operations, key=lambda item: item["sequence"])
        ],
        PROPOSAL_RULE_VERSION,
    )


def validate_operations(
    vertical: str,
    operations: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    baseline_is_current: bool,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    nodes = {item["asset_id"]: item for item in assets}
    edges = {item["relationship_id"]: item for item in relationships}
    temporary: dict[str, dict[str, Any]] = {}
    seen_operations: set[str] = set()
    field_updates: dict[tuple[str, str], Any] = {}
    relationship_changes: set[tuple[str, str]] = set()

    if not operations:
        errors.append(_problem("", "empty_operation_list", "At least one proposed operation is required."))
    if not baseline_is_current:
        errors.append(_problem("", "stale_baseline", "Canonical evidence or analysis rules changed after this proposal baseline was captured."))

    for operation in sorted(operations, key=lambda item: item["sequence"]):
        operation_id = operation["operation_id"]
        signature = stable_fingerprint({
            key: operation.get(key) for key in (
                "operation_type", "target_asset_id", "target_relationship_id", "new_asset_temporary_id",
                "field_name", "proposed_value", "proposed_values", "relationship_type",
                "from_asset_id", "to_asset_id",
            )
        })
        if signature in seen_operations:
            errors.append(_problem(operation_id, "duplicate_operation", "The proposal contains a duplicate operation."))
        seen_operations.add(signature)

        kind = operation["operation_type"]
        target_id = operation.get("target_asset_id", "")
        relationship_id = operation.get("target_relationship_id", "")
        if kind == "add_asset":
            temporary_id = operation.get("new_asset_temporary_id", "")
            values = operation.get("proposed_values", {})
            if not temporary_id or temporary_id in nodes or temporary_id in temporary:
                errors.append(_problem(operation_id, "invalid_temporary_id", "A unique proposal-local asset ID is required."))
                continue
            asset_class = str(values.get("asset_class", ""))
            try:
                validate_vertical_and_class(vertical, asset_class)
            except ValueError as exc:
                errors.append(_problem(operation_id, "invalid_asset_class", str(exc)))
                continue
            temporary[temporary_id] = _temporary_asset(vertical, temporary_id, values)
            continue

        if kind in {
            "update_asset_attribute", "update_asset_attributes", "change_lifecycle_status",
            "change_operational_status", "assign_membership", "remove_membership", "retire_asset",
            "replace_asset", "add_note", "request_manual_investigation",
        } and target_id not in nodes and target_id not in temporary:
            errors.append(_problem(operation_id, "missing_target_asset", "The target asset does not exist in the fixed baseline or proposal overlay."))
            continue

        if kind in {
            "remove_relationship", "replace_relationship", "update_relationship",
            "confirm_provisional_relationship", "mark_relationship_provisional",
            "remove_container_association", "remove_structure_association",
        } and relationship_id not in edges:
            errors.append(_problem(operation_id, "missing_target_relationship", "The target relationship does not exist in the fixed baseline."))
            continue

        if kind in {"update_asset_attribute", "assign_membership", "remove_membership"}:
            _validate_field_update(operation, vertical, nodes.get(target_id) or temporary.get(target_id), errors, field_updates)
        elif kind == "update_asset_attributes":
            for field, value in operation.get("proposed_values", {}).items():
                candidate = {**operation, "field_name": field, "proposed_value": value}
                _validate_field_update(candidate, vertical, nodes.get(target_id) or temporary.get(target_id), errors, field_updates)
        elif kind in {"change_lifecycle_status", "retire_asset"}:
            current = str((nodes.get(target_id) or temporary.get(target_id) or {}).get("lifecycle_status", "unknown"))
            proposed = "retired" if kind == "retire_asset" else str(operation.get("proposed_value", ""))
            if proposed not in LIFECYCLE_STATES or proposed not in LIFECYCLE_TRANSITIONS.get(current, set()):
                errors.append(_problem(operation_id, "invalid_lifecycle_transition", f"Lifecycle transition {current} to {proposed or 'missing'} is not allowlisted."))
            elif (current, proposed) in STRONG_REVIEW_TRANSITIONS:
                warnings.append(_problem(operation_id, "strong_lifecycle_review", "This lifecycle transition requires explicit technical and final review."))
        elif kind == "change_operational_status":
            allowed = {
                "electric_distribution": ELECTRIC_OPERATIONAL_STATES,
                "telecom_fiber": TELECOM_OPERATIONAL_STATES,
                "water": WATER_OPERATIONAL_STATES,
                "wastewater": WASTEWATER_OPERATIONAL_STATES,
            }[vertical]
            if operation.get("proposed_value") not in allowed:
                errors.append(_problem(operation_id, "invalid_operational_state", "The proposed operational state is not allowlisted for this utility vertical."))
            if vertical == "electric_distribution":
                warnings.append(_problem(operation_id, "not_switching_instruction", "This is a proposed data change, not a switching instruction."))

        if kind in {
            "add_relationship", "replace_relationship", "associate_container", "associate_structure",
        }:
            _validate_relationship(operation, vertical, nodes, temporary, relationships, errors)
            pair = (operation.get("from_asset_id", ""), operation.get("to_asset_id", ""))
            if pair in relationship_changes:
                errors.append(_problem(operation_id, "duplicate_relationship_change", "The same relationship endpoints are changed more than once."))
            relationship_changes.add(pair)

    if not errors:
        try:
            effective = apply_overlay(vertical, assets, relationships, operations)
            _validate_effective_values(vertical, effective["assets"], operations, errors)
        except ValueError as exc:
            errors.append(_problem("", "overlay_validation_failed", str(exc)))

    return {
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": warnings,
        "operations_evaluated": len(operations),
        "rule_version": PROPOSAL_RULE_VERSION,
    }


def apply_overlay(
    vertical: str,
    assets: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = {item["asset_id"]: copy.deepcopy(item) for item in assets}
    edges = {item["relationship_id"]: copy.deepcopy(item) for item in relationships}
    asset_states = {asset_id: "unchanged" for asset_id in nodes}
    relationship_states = {relationship_id: "unchanged" for relationship_id in edges}

    for operation in sorted(operations, key=lambda item: item["sequence"]):
        kind = operation["operation_type"]
        target_id = operation.get("target_asset_id", "")
        relationship_id = operation.get("target_relationship_id", "")
        if kind == "add_asset":
            temporary_id = operation["new_asset_temporary_id"]
            nodes[temporary_id] = _temporary_asset(vertical, temporary_id, operation.get("proposed_values", {}))
            asset_states[temporary_id] = "added"
        elif kind == "update_asset_attribute":
            _set_asset_value(nodes[target_id], operation["field_name"], operation.get("proposed_value"))
            asset_states[target_id] = "modified"
        elif kind == "update_asset_attributes":
            for field, value in operation.get("proposed_values", {}).items():
                _set_asset_value(nodes[target_id], field, value)
            asset_states[target_id] = "modified"
        elif kind == "change_lifecycle_status":
            nodes[target_id]["lifecycle_status"] = operation.get("proposed_value")
            asset_states[target_id] = "modified"
        elif kind == "change_operational_status":
            nodes[target_id]["operational_status"] = operation.get("proposed_value")
            asset_states[target_id] = "modified"
        elif kind in {"assign_membership", "remove_membership"}:
            _set_asset_value(nodes[target_id], operation["field_name"], operation.get("proposed_value") if kind == "assign_membership" else "")
            asset_states[target_id] = "modified"
        elif kind == "retire_asset":
            nodes[target_id]["lifecycle_status"] = "retired"
            asset_states[target_id] = "modified"
        elif kind == "replace_asset":
            replacement_id = operation.get("replacement_asset_id") or operation.get("new_asset_temporary_id")
            if not replacement_id:
                raise ValueError("Replacement requires a proposal-local replacement asset.")
            asset_states[target_id] = "replaced"
        elif kind in {"remove_relationship", "remove_container_association", "remove_structure_association"}:
            if relationship_id in edges:
                relationship_states[relationship_id] = "removed"
                del edges[relationship_id]
        elif kind == "replace_relationship":
            if relationship_id in edges:
                relationship_states[relationship_id] = "replaced"
                del edges[relationship_id]
            _add_overlay_relationship(edges, relationship_states, operation)
        elif kind == "add_relationship":
            _add_overlay_relationship(edges, relationship_states, operation)
        elif kind == "update_relationship":
            edge = edges[relationship_id]
            for field, value in operation.get("proposed_values", {}).items():
                if field in {"direction", "confidence", "provisional"}:
                    edge[field] = value
            relationship_states[relationship_id] = "modified"
        elif kind == "confirm_provisional_relationship":
            edges[relationship_id]["provisional"] = False
            edges[relationship_id]["source"] = "human_confirmed"
            relationship_states[relationship_id] = "confirmed_in_proposal"
        elif kind == "mark_relationship_provisional":
            edges[relationship_id]["provisional"] = True
            relationship_states[relationship_id] = "provisional"
        elif kind in {"associate_container", "associate_structure"}:
            candidate = {
                **operation,
                "relationship_type": "routed_through" if kind == "associate_container" else "mounted_on",
            }
            _add_overlay_relationship(edges, relationship_states, candidate)

    selected = sorted(nodes.values(), key=lambda item: item["asset_id"])
    effective_relationships = sorted(edges.values(), key=lambda item: item["relationship_id"])
    overlay_fingerprint = stable_fingerprint(
        OVERLAY_VERSION,
        [(item["asset_id"], asset_states[item["asset_id"]], item.get("lifecycle_status"), item.get("operational_status"), item.get("canonical_attributes_json", {})) for item in selected],
        [(item["relationship_id"], relationship_states[item["relationship_id"]], item.get("from_asset_id"), item.get("to_asset_id"), item.get("relationship_type"), item.get("provisional")) for item in effective_relationships],
    )
    return {
        "assets": selected,
        "relationships": effective_relationships,
        "asset_states": asset_states,
        "relationship_states": relationship_states,
        "overlay_fingerprint": overlay_fingerprint,
        "summary": {
            "assets_read": len(assets),
            "assets_added": _count(asset_states, "added"),
            "assets_modified": sum(1 for value in asset_states.values() if value in {"modified", "replaced"}),
            "assets_removed": _count(asset_states, "removed"),
            "relationships_read": len(relationships),
            "relationships_added": _count(relationship_states, "added"),
            "relationships_modified": sum(1 for value in relationship_states.values() if value in {"modified", "confirmed_in_proposal", "provisional", "replaced"}),
            "relationships_removed": _count(relationship_states, "removed") + _count(relationship_states, "replaced"),
            "changed_asset_ids": sorted(key for key, value in asset_states.items() if value != "unchanged"),
            "changed_relationship_ids": sorted(key for key, value in relationship_states.items() if value != "unchanged"),
        },
        "notice": "Proposed overlay - no canonical or source records have been changed.",
    }


def run_proposed_qa(vertical: str, assets: list[dict[str, Any]], relationships: list[dict[str, Any]], run_key: str) -> dict[str, Any]:
    graph = build_graph(vertical, assets, assets, relationships)
    findings: list[dict[str, Any]] = []
    for definition in rule_profile(vertical):
        for finding in evaluate_rule(definition, graph):
            findings.append({
                **finding,
                "utility_vertical": vertical,
                "rule_code": definition["rule_code"],
                "rule_version": QA_RULE_VERSION,
                "severity": definition["severity"],
                "blocking": bool(definition["blocking"]),
                "review_status": "open",
            })
    created_at = intake_registry_service.utc_now()
    qa_run_id = stable_id("proposal-qa", vertical, run_key, [item["finding_fingerprint"] for item in findings])
    groups = build_issue_groups(vertical, qa_run_id, findings, {item["asset_id"]: item for item in assets}, created_at)
    return {
        "proposal_qa_run_id": qa_run_id,
        "rule_version": QA_RULE_VERSION,
        "calibration_rule_version": CALIBRATION_RULE_VERSION,
        "status": "succeeded",
        "assets_evaluated": len(assets),
        "relationships_evaluated": len(relationships),
        "findings": findings,
        "groups": groups,
        "findings_created": len(findings),
        "blocking_findings": sum(1 for item in findings if item["blocking"]),
        "warnings": sum(1 for item in findings if not item["blocking"]),
    }


def compare_qa(baseline: dict[str, Any], proposed: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    before = {item["root_cause_key"]: item for item in baseline["groups"]}
    after = {item["root_cause_key"]: item for item in proposed["groups"]}
    resolved = sorted(before.keys() - after.keys())
    new = sorted(after.keys() - before.keys())
    unchanged: list[str] = []
    worsened: list[str] = []
    improved: list[str] = []
    severity = {"info": 0, "warning": 1, "error": 2, "critical": 3}
    for key in sorted(before.keys() & after.keys()):
        prior, current = before[key], after[key]
        if severity.get(current["highest_severity"], 0) > severity.get(prior["highest_severity"], 0):
            worsened.append(key)
        elif severity.get(current["highest_severity"], 0) < severity.get(prior["highest_severity"], 0):
            improved.append(key)
        else:
            unchanged.append(key)
    baseline_blockers = sum(1 for item in baseline["groups"] if item["effective_blocking"])
    proposed_blockers = sum(1 for item in proposed["groups"] if item["effective_blocking"])
    return {
        "comparison_id": stable_id("proposal-qa-comparison", proposal_id, baseline["proposal_qa_run_id"], proposed["proposal_qa_run_id"]),
        "baseline_qa_run_id": baseline["proposal_qa_run_id"],
        "proposed_qa_run_id": proposed["proposal_qa_run_id"],
        "resolved_issue_group_ids": [before[key]["issue_group_id"] for key in resolved],
        "unchanged_issue_group_ids": [after[key]["issue_group_id"] for key in unchanged],
        "new_issue_group_ids": [after[key]["issue_group_id"] for key in new],
        "worsened_issue_group_ids": [after[key]["issue_group_id"] for key in worsened],
        "improved_issue_group_ids": [after[key]["issue_group_id"] for key in improved],
        "baseline_blocker_count": baseline_blockers,
        "proposed_blocker_count": proposed_blockers,
        "blocker_delta": proposed_blockers - baseline_blockers,
        "baseline_warning_count": baseline["warnings"],
        "proposed_warning_count": proposed["warnings"],
        "warning_delta": proposed["warnings"] - baseline["warnings"],
        "passed_rules_delta": len(resolved) - len(new),
        "comparison_status": "worsened" if new and proposed_blockers > baseline_blockers else "improved" if resolved and proposed_blockers <= baseline_blockers else "unchanged" if not resolved and not new and not worsened and not improved else "mixed",
        "created_at": intake_registry_service.utc_now(),
    }


def run_proposed_trace(
    vertical: str,
    assets: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    trace_type: str,
    start_asset_id: str,
    run_key: str,
) -> dict[str, Any]:
    nodes = {item["asset_id"]: item for item in assets}
    definition = trace_definition(vertical, trace_type)
    if start_asset_id not in nodes or nodes[start_asset_id]["asset_class"] not in definition["start_asset_classes"]:
        return {
            "status": "incomparable", "trace_type": trace_type, "start_asset_id": start_asset_id,
            "calibrated": {"calibrated_outcome": "failed_safely", "calibrated_confidence": "indeterminate", "objective_reached": False},
        }
    request = normalize_request(vertical, {
        "trace_type": trace_type,
        "start_asset_id": start_asset_id,
        "direction": definition["default_direction"],
        "lifecycle_mode": "include_proposed" if any(item.get("lifecycle_status") == "proposed" for item in assets) else "active_only",
        "operational_mode": "diagnostic",
        "provisional_relationship_policy": "include_with_warning",
        "qa_policy": "diagnostic",
        "requested_by": "proposal_analysis",
    }, {item["trace_type"] for item in TRACE_PROFILES[vertical]["traces"]})
    raw = trace_graph(request, definition, build_graph(vertical, assets, assets, relationships), groups)
    trace_run_id = stable_id("proposal-trace", vertical, run_key, trace_type, start_asset_id)
    paths = []
    steps = []
    for path in raw["paths"]:
        trace_path_id = stable_id("proposal-trace-path", trace_run_id, path["path_rank"])
        converted = {**path, "trace_path_id": trace_path_id}
        paths.append(converted)
        for step in path["steps"]:
            steps.append({
                **step,
                "trace_step_id": stable_id("proposal-trace-step", trace_path_id, step["sequence"]),
                "trace_path_id": trace_path_id,
            })
    events = [
        {**event, "trace_event_id": stable_id("proposal-trace-event", trace_run_id, index, event["event_type"])}
        for index, event in enumerate(raw["events"])
    ]
    run = {
        "trace_run_id": trace_run_id,
        "input_fingerprint": stable_fingerprint(run_key, trace_type, start_asset_id, OVERLAY_VERSION),
        "request_fingerprint": stable_fingerprint(request),
        "utility_vertical": vertical,
        "trace_type": trace_type,
        "start_asset_id": start_asset_id,
        "target_asset_id": "",
        "outcome": raw["outcome"],
        "confidence": raw["confidence"],
        "status": "succeeded",
        "warnings_count": raw["warnings_count"],
        "blockers_count": raw["blockers_count"],
    }
    calibrated = calibrate_trace(run, paths, steps, events, groups)["result"]
    return {
        "status": "succeeded",
        "trace_run_id": trace_run_id,
        "trace_type": trace_type,
        "start_asset_id": start_asset_id,
        "raw": {
            "outcome": raw["outcome"],
            "confidence": raw["confidence"],
            "warnings_count": raw["warnings_count"],
            "blockers_count": raw["blockers_count"],
            "paths_evaluated": raw["paths_evaluated"],
        },
        "calibrated": calibrated,
    }


def compare_trace(proposal_id: str, scenario_code: str, baseline: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    before = baseline.get("calibrated", {})
    after = proposed.get("calibrated", {})
    if baseline.get("status") != "succeeded" or proposed.get("status") != "succeeded":
        result = "incomparable"
    elif not before.get("objective_reached") and after.get("objective_reached"):
        result = "improved"
    elif before.get("objective_reached") and not after.get("objective_reached"):
        result = "worsened"
    elif before.get("calibrated_outcome") == after.get("calibrated_outcome") and before.get("path_signature") == after.get("path_signature"):
        result = "unchanged"
    elif _outcome_rank(after.get("calibrated_outcome")) > _outcome_rank(before.get("calibrated_outcome")):
        result = "improved"
    elif _outcome_rank(after.get("calibrated_outcome")) < _outcome_rank(before.get("calibrated_outcome")):
        result = "worsened"
    else:
        result = "mixed"
    before_groups = set(before.get("path_specific_issue_group_ids", []))
    after_groups = set(after.get("path_specific_issue_group_ids", []))
    return {
        "comparison_id": stable_id("proposal-trace-comparison", proposal_id, scenario_code, baseline.get("trace_run_id"), proposed.get("trace_run_id")),
        "trace_scenario_code": scenario_code,
        "baseline_trace_run_id": baseline.get("trace_run_id", ""),
        "proposed_trace_run_id": proposed.get("trace_run_id", ""),
        "baseline_calibration_run_id": stable_id("proposal-trace-calibration", baseline.get("trace_run_id", "")),
        "proposed_calibration_run_id": stable_id("proposal-trace-calibration", proposed.get("trace_run_id", "")),
        "baseline_outcome": before.get("calibrated_outcome", "failed_safely"),
        "proposed_outcome": after.get("calibrated_outcome", "failed_safely"),
        "baseline_confidence": before.get("calibrated_confidence", "indeterminate"),
        "proposed_confidence": after.get("calibrated_confidence", "indeterminate"),
        "baseline_objective_reached": bool(before.get("objective_reached")),
        "proposed_objective_reached": bool(after.get("objective_reached")),
        "reachable_asset_delta": len(after.get("reachable_asset_ids", [])) - len(before.get("reachable_asset_ids", [])),
        "unreachable_asset_delta": len(after.get("unreachable_asset_ids", [])) - len(before.get("unreachable_asset_ids", [])),
        "resolved_blocker_ids": sorted(before_groups - after_groups),
        "new_blocker_ids": sorted(after_groups - before_groups),
        "baseline_path_signature": before.get("path_signature", ""),
        "proposed_path_signature": after.get("path_signature", ""),
        "baseline_branch_signature": before.get("branch_signature", ""),
        "proposed_branch_signature": after.get("branch_signature", ""),
        "result": result,
        "warnings": [
            "Trace comparison is analytical and vendor-neutral.",
            "A changed path is not automatically safer or operationally correct.",
        ],
        "created_at": intake_registry_service.utc_now(),
    }


def impact_summary(
    proposal: dict[str, Any],
    operations: list[dict[str, Any]],
    overlay: dict[str, Any],
    qa: dict[str, Any],
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    improved = sum(1 for item in traces if item["result"] == "improved")
    worsened = sum(1 for item in traces if item["result"] == "worsened")
    new_blockers = qa["proposed_blocker_count"] > qa["baseline_blocker_count"]
    readiness = "blocked" if new_blockers or qa["comparison_status"] == "worsened" else "review_ready"
    return {
        "proposal_id": proposal["proposal_id"],
        "proposal_version": proposal["proposal_version"],
        "utility_vertical": proposal["utility_vertical"],
        "proposal_type": proposal["proposal_type"],
        "operation_count": len(operations),
        "affected_asset_ids": overlay["summary"]["changed_asset_ids"],
        "affected_relationship_ids": overlay["summary"]["changed_relationship_ids"],
        "baseline_fingerprint": proposal["baseline_fingerprint"],
        "overlay_fingerprint": overlay["overlay_fingerprint"],
        "validation_result": "passed",
        "qa_blockers_before": qa["baseline_blocker_count"],
        "qa_blockers_after": qa["proposed_blocker_count"],
        "qa_groups_resolved": len(qa["resolved_issue_group_ids"]),
        "qa_groups_introduced": len(qa["new_issue_group_ids"]),
        "traces_improved": improved,
        "traces_worsened": worsened,
        "objectives_newly_reached": sum(1 for item in traces if not item["baseline_objective_reached"] and item["proposed_objective_reached"]),
        "objectives_lost": sum(1 for item in traces if item["baseline_objective_reached"] and not item["proposed_objective_reached"]),
        "confidence_changes": [
            f"{item['baseline_confidence']} to {item['proposed_confidence']}"
            for item in traces if item["baseline_confidence"] != item["proposed_confidence"]
        ],
        "provisional_dependencies": sum(1 for item in overlay["relationship_states"].values() if item == "provisional"),
        "lifecycle_effects": sum(1 for item in operations if item["operation_type"] in {"change_lifecycle_status", "retire_asset"}),
        "recommended_reviewer_action": "Request revision before review." if readiness == "blocked" else "Review the operation sequence and before-and-after evidence.",
        "implementation_readiness": readiness,
        "disclaimer": DISCLAIMER,
    }


def required_adapter_capabilities(operations: Iterable[dict[str, Any]]) -> list[str]:
    mapping = {
        "add_asset": "create_asset",
        "update_asset_attribute": "update_attribute",
        "update_asset_attributes": "update_attribute",
        "change_lifecycle_status": "update_lifecycle",
        "change_operational_status": "update_operational_state",
        "add_relationship": "create_relationship",
        "associate_container": "create_relationship",
        "associate_structure": "create_relationship",
        "remove_relationship": "remove_relationship",
        "replace_relationship": "remove_relationship",
        "replace_asset": "replace_asset",
        "retire_asset": "retire_asset",
    }
    return sorted({mapping[item["operation_type"]] for item in operations if item["operation_type"] in mapping} | {"external_approval_required", "topology_validation_required"})


def _validate_field_update(
    operation: dict[str, Any],
    vertical: str,
    asset: dict[str, Any] | None,
    errors: list[dict[str, str]],
    updates: dict[tuple[str, str], Any],
) -> None:
    field = str(operation.get("field_name", ""))
    value = operation.get("proposed_value")
    operation_id = operation["operation_id"]
    if field not in FIELD_ALLOWLIST[vertical] or field.endswith("_json"):
        errors.append(_problem(operation_id, "invalid_field", "The field is not editable through the proposed-operation allowlist."))
        return
    if field in NUMERIC_FIELDS and (isinstance(value, bool) or not isinstance(value, (int, float))):
        errors.append(_problem(operation_id, "invalid_numeric_value", f"{field} requires a numeric value."))
    if field in BOOLEAN_FIELDS and not isinstance(value, bool):
        errors.append(_problem(operation_id, "invalid_boolean_value", f"{field} requires a boolean value."))
    if field == "phase" and str(value).upper() not in {"A", "B", "C", "AB", "AC", "BC", "ABC", "N", ""}:
        errors.append(_problem(operation_id, "invalid_phase", "Phase must use the V1 allowlist; missing phase is not invented."))
    key = (str(asset.get("asset_id", "") if asset else ""), field)
    if key in updates and updates[key] != value:
        errors.append(_problem(operation_id, "contradictory_attribute_change", f"The proposal assigns conflicting values to {field}."))
    updates[key] = value


def _validate_relationship(
    operation: dict[str, Any],
    vertical: str,
    nodes: dict[str, dict[str, Any]],
    temporary: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> None:
    operation_id = operation["operation_id"]
    from_id, to_id = operation.get("from_asset_id", ""), operation.get("to_asset_id", "")
    left, right = nodes.get(from_id) or temporary.get(from_id), nodes.get(to_id) or temporary.get(to_id)
    relationship_type = operation.get("relationship_type", "")
    if not left or not right:
        errors.append(_problem(operation_id, "missing_relationship_endpoint", "Both relationship endpoints must exist in the baseline or proposal overlay."))
        return
    if from_id == to_id:
        errors.append(_problem(operation_id, "relationship_self_loop", "A proposed relationship cannot connect an asset to itself."))
    if left.get("utility_vertical") != vertical or right.get("utility_vertical") != vertical:
        errors.append(_problem(operation_id, "cross_vertical_relationship", "Operational relationships cannot cross utility verticals."))
    if relationship_type not in RELATIONSHIP_TYPES:
        errors.append(_problem(operation_id, "invalid_relationship_type", "Relationship type must use the canonical allowlist."))
    if relationship_type == "routed_through" and right.get("asset_class") != "conduit":
        errors.append(_problem(operation_id, "invalid_container", "A routed-through relationship must target a conduit."))
    if relationship_type == "mounted_on" and right.get("asset_class") not in {"pole", "electric_structure", "telecom_structure", "structure", "vault"}:
        errors.append(_problem(operation_id, "invalid_structure", "A mounted-on relationship must target a supported structure."))
    if any(
        item.get("from_asset_id") == from_id
        and item.get("to_asset_id") == to_id
        and item.get("relationship_type") == relationship_type
        for item in relationships
    ) and operation["operation_type"] == "add_relationship":
        errors.append(_problem(operation_id, "duplicate_relationship", "An identical canonical relationship already exists."))


def _validate_effective_values(
    vertical: str,
    assets: list[dict[str, Any]],
    operations: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> None:
    touched = {
        item.get("target_asset_id") or item.get("new_asset_temporary_id")
        for item in operations
        if item.get("target_asset_id") or item.get("new_asset_temporary_id")
    }
    for asset in assets:
        if asset["asset_id"] not in touched:
            continue
        attrs = asset.get("canonical_attributes_json", {})
        if vertical == "electric_distribution":
            nominal, operating = attrs.get("nominal_voltage"), attrs.get("operating_voltage")
            if isinstance(nominal, (int, float)) and isinstance(operating, (int, float)) and abs(nominal - operating) > 0.001:
                errors.append(_problem("", "voltage_conflict", "The proposal creates a nominal and operating voltage conflict."))
        elif vertical == "telecom_fiber":
            start, end, count = attrs.get("strand_start"), attrs.get("strand_end"), attrs.get("fiber_count")
            if all(isinstance(value, (int, float)) for value in (start, end, count)) and (start < 1 or end < start or end > count):
                errors.append(_problem("", "invalid_strand_range", "The proposal creates a strand range outside the cable fiber count."))
            total, used, reserved, available = (
                attrs.get("total_capacity"), attrs.get("used_capacity"),
                attrs.get("reserved_capacity"), attrs.get("available_capacity"),
            )
            if all(isinstance(value, (int, float)) for value in (total, used, reserved)):
                if used + reserved > total:
                    errors.append(_problem("", "capacity_conflict", "The proposal allocates more capacity than the total."))
                if isinstance(available, (int, float)) and abs(available - (total - used - reserved)) > 0.001:
                    errors.append(_problem("", "capacity_arithmetic", "Available capacity does not reconcile with total, used, and reserved values."))
        else:
            diameter = attrs.get("diameter")
            if isinstance(diameter, (int, float)) and diameter <= 0:
                errors.append(_problem("", "invalid_diameter", "The proposal creates a non-positive pipe diameter."))
            if vertical == "wastewater" and asset.get("asset_class") == "gravity_main":
                upstream, downstream = attrs.get("upstream_invert"), attrs.get("downstream_invert")
                if isinstance(upstream, (int, float)) and isinstance(downstream, (int, float)) and upstream <= downstream:
                    errors.append(_problem("", "invert_contradiction", "The proposal conflicts with the explicit mapped gravity-flow direction."))


def _temporary_asset(vertical: str, asset_id: str, values: dict[str, Any]) -> dict[str, Any]:
    attrs = copy.deepcopy(values.get("canonical_attributes") or {})
    return {
        "asset_id": asset_id,
        "utility_vertical": vertical,
        "asset_class": values.get("asset_class", ""),
        "asset_subtype": values.get("asset_subtype", ""),
        "canonical_name": values.get("canonical_name") or asset_id,
        "display_name": values.get("canonical_name") or asset_id,
        "geometry_type": values.get("geometry_type", "none"),
        "lifecycle_status": values.get("lifecycle_status", "proposed"),
        "operational_status": values.get("operational_status", "unknown"),
        "source_system": "proposed_edit_overlay",
        "source_submission_id": "synthetic-proposal" if values.get("synthetic", True) else "proposal",
        "source_layer_id": "proposal-overlay",
        "source_record_id": asset_id,
        "source_asset_identifier": asset_id,
        "qa_status": "not_evaluated",
        "review_status": "needs_review",
        "sensitivity": "internal",
        "canonical_attributes_json": attrs,
        "geometry_summary_json": values.get("geometry_summary") or {},
        "evidence_json": {"proposal_local": True},
        "is_synthetic": 1,
    }


def _set_asset_value(asset: dict[str, Any], field: str, value: Any) -> None:
    if field in {"lifecycle_status", "operational_status", "canonical_name", "display_name", "asset_subtype"}:
        asset[field] = value
    else:
        attrs = asset.setdefault("canonical_attributes_json", {})
        attrs[field] = value


def _add_overlay_relationship(
    edges: dict[str, dict[str, Any]],
    states: dict[str, str],
    operation: dict[str, Any],
) -> None:
    relationship_id = stable_id(
        "proposal-relationship", operation["proposal_id"], operation["proposal_version"],
        operation["sequence"], operation.get("from_asset_id"), operation.get("to_asset_id"),
        operation.get("relationship_type"),
    )
    edges[relationship_id] = {
        "relationship_id": relationship_id,
        "from_asset_id": operation.get("from_asset_id", ""),
        "to_asset_id": operation.get("to_asset_id", ""),
        "relationship_type": operation.get("relationship_type", ""),
        "direction": operation.get("direction", "forward"),
        "confidence": "proposal",
        "source": "proposed_edit_overlay",
        "provisional": bool(operation.get("provisional", False)),
        "evidence_json": {"proposal_id": operation["proposal_id"], "operation_id": operation["operation_id"]},
    }
    states[relationship_id] = "added"


def _outcome_rank(value: object) -> int:
    return {
        "failed_safely": 0, "no_path": 1, "blocked": 2, "partial": 3,
        "ambiguous": 3, "complete_with_warnings": 4, "complete": 5,
    }.get(str(value), 0)


def _count(values: dict[str, str], expected: str) -> int:
    return sum(1 for value in values.values() if value == expected)


def _problem(operation_id: str, code: str, message: str) -> dict[str, str]:
    return {"operation_id": operation_id, "code": code, "message": message}


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Identifier collections must be arrays.")
    return sorted({_text(item, 120) for item in value if _text(item, 120)})


def dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
