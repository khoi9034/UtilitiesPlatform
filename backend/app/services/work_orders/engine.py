from __future__ import annotations

import re
from typing import Any, Iterable

from app.services.proposed_edits import engine as proposed_engine
from app.services.utility_assets.domain import UTILITY_VERTICALS, stable_fingerprint, stable_id

WORK_ORDER_VERSION = "work-order-v1"
JOB_PACKAGE_VERSION = "work-order-job-package-v1"
RECEIPT_VERSION = "work-order-completion-receipt-v1"
SCENARIO_VERSION = "work-order-scenarios-v1"

DISCLAIMER = (
    "UtilitiesPlatform Work Order and Job Package V1 converts approved vendor-neutral proposed "
    "changes into structured synthetic job workflows. It records planning, review, evidence, "
    "validation, and closeout without modifying an operational utility GIS or executing work."
)
IMPLEMENTATION_NOTICE = "Synthetic implementation record - no operational GIS was changed."
RECEIPT_NOTICE = (
    "Completion receipt records the UtilitiesPlatform job-review workflow. It does not prove that "
    "a real operational utility system was updated unless separately verified through an "
    "authorized external process."
)

OVERALL_STATUSES = (
    "draft", "planning", "ready_for_review", "under_review", "approved_for_release", "released",
    "in_progress", "field_complete", "gis_update_pending", "gis_update_recorded",
    "post_work_validation", "closeout_review", "closed", "suspended", "cancelled", "rejected",
    "deferred", "superseded", "archived",
)
DESIGN_STATUSES = ("not_started", "draft", "reviewed", "approved", "revision_required", "not_applicable")
FIELD_STATUSES = ("not_released", "released", "scheduled", "in_progress", "paused", "completed", "incomplete", "cancelled", "not_applicable")
GIS_STATUSES = ("not_started", "pending", "in_progress", "recorded_in_overlay", "externally_implemented_unverified", "externally_implemented_verified", "failed", "not_applicable")
INSPECTION_STATUSES = ("not_required", "pending", "in_progress", "passed", "passed_with_conditions", "failed", "deferred")
QA_STATUSES = ("not_required", "not_run", "running", "passed", "passed_with_warnings", "failed", "blocked")
TRACE_STATUSES = QA_STATUSES
REVIEW_STATUSES = ("not_submitted", "submitted", "under_review", "revision_requested", "approved", "rejected", "deferred")
CLOSEOUT_STATUSES = ("not_ready", "ready", "under_review", "approved", "rejected", "reopened", "closed")
PRIORITIES = ("low", "normal", "high", "urgent", "emergency_record_review")

SHARED_TYPES = (
    "corrective_maintenance", "planned_maintenance", "asset_installation", "asset_replacement",
    "asset_retirement", "connectivity_correction", "data_correction", "inspection_follow_up",
    "network_extension", "route_adjustment", "construction_update",
    "emergency_record_correction", "manual_investigation", "multi_operation_job",
)
VERTICAL_TYPES = {
    "electric_distribution": (
        "transformer_replacement", "pole_replacement", "conductor_connection",
        "feeder_assignment_correction", "phase_record_correction", "voltage_record_correction",
        "conduit_installation_or_association", "device_state_verification",
        "protective_device_record_update", "electric_asset_retirement",
        "electric_network_extension",
    ),
    "telecom_fiber": (
        "fiber_route_extension", "cable_endpoint_correction", "splice_installation_or_confirmation",
        "strand_assignment_correction", "capacity_record_correction",
        "conduit_installation_or_association", "aerial_support_update", "terminal_connection",
        "cable_replacement", "telecom_asset_retirement", "proposed_construction_completion",
    ),
    "water": (
        "hydrant_and_valve_installation", "water_main_replacement", "water_main_abandonment",
        "service_and_meter_installation", "valve_isolation_repair",
        "water_main_relocation",
    ),
    "wastewater": (
        "gravity_main_replacement", "manhole_installation", "lateral_repair",
        "lift_station_and_force_main_installation", "invert_elevation_correction",
        "legacy_sewer_abandonment", "emergency_blockage_repair",
    ),
}
ROLES = (
    "requester", "planner", "designer", "utility_gis_technician", "field_technician",
    "construction_coordinator", "inspector", "qa_reviewer", "data_steward",
    "technical_reviewer", "final_approver", "closeout_reviewer", "system",
)
PREREQUISITE_TYPES = (
    "approved_proposal", "current_baseline", "required_asset_identifiers",
    "required_relationships", "design_review_complete", "field_access_confirmed",
    "source_evidence_available", "material_or_equipment_reference", "safety_review_external",
    "permit_or_authorization_external", "inspection_required", "qa_rules_available",
    "trace_scenarios_available", "reviewer_assigned", "final_approver_assigned",
    "external_adapter_required", "external_system_access_required", "manual_investigation_required",
)
INSPECTION_TYPES = (
    "identifier_verification", "installation_verification", "condition_verification",
    "location_reference_verification", "relationship_verification", "phase_verification",
    "voltage_verification", "device_state_verification", "conduit_verification",
    "structure_support_verification", "cable_endpoint_verification", "splice_verification",
    "strand_assignment_verification", "capacity_verification",
    "construction_status_verification", "retirement_verification", "replacement_verification",
    "diameter_verification", "material_verification", "pressure_zone_verification",
    "valve_state_verification", "hydrant_verification", "meter_verification",
    "invert_verification", "rim_elevation_verification", "slope_verification",
    "flow_direction_verification", "basin_verification",
)
EVIDENCE_TYPES = (
    "field_note", "inspection_note", "checklist_result", "identifier_confirmation",
    "attribute_confirmation", "relationship_confirmation", "installation_record",
    "retirement_record", "replacement_record", "source_document_reference",
    "external_ticket_reference", "safe_attachment_metadata", "before_after_summary",
    "qa_receipt", "trace_receipt", "reviewer_signoff", "implementation_statement",
    "exception_record",
)
PHASES = (
    ("intake", "Intake"), ("planning", "Planning"), ("design_review", "Design Review"),
    ("pre_work_validation", "Pre-Work Validation"), ("release", "Release"),
    ("field_work", "Field or Construction Work"), ("gis_record_update", "GIS Record Update"),
    ("inspection", "Post-Work Inspection"), ("post_work_qa", "Post-Work QA"),
    ("post_work_trace", "Post-Work Trace Verification"), ("technical_review", "Technical Review"),
    ("closeout", "Closeout"), ("archive", "Archive"),
)
EXTERNAL_MAPPING_STATUSES = ("not_mapped", "conceptually_mappable", "adapter_required", "unsupported", "unknown")
SYNC_STATUSES = ("not_connected", "not_started", "pending", "synchronized", "partial", "conflict", "failed", "externally_confirmed")
ADAPTER_CAPABILITIES = (
    "create_work_order", "update_work_order", "assign_user_or_role", "attach_job_step",
    "attach_evidence", "submit_design", "release_work", "record_completion",
    "create_versioned_edit", "apply_asset_change", "apply_relationship_change",
    "run_network_validation", "synchronize_status", "close_work_order",
    "external_approval_required",
)

_PATH_OR_URL = re.compile(r"(?:[a-zA-Z]:[\\/]|\\\\|https?://)", re.IGNORECASE)
_EXECUTABLE = re.compile(r"\.(?:exe|bat|cmd|ps1|py|sh|js|msi)$", re.IGNORECASE)
_FORBIDDEN_KEYS = {
    "path", "filesystem_path", "sql", "python", "shell", "command", "script", "credentials",
    "connection_string", "external_url", "vendor_command", "switching_command",
    "provisioning_command", "raw_geometry",
}

SCENARIOS: dict[str, tuple[dict[str, Any], ...]] = {
    "electric_distribution": (
        {"code": "E-WO-001", "proposal": "E-EDIT-001", "type": "conductor_connection", "title": "Connect conductor endpoint", "ready": True},
        {"code": "E-WO-002", "proposal": "E-EDIT-002", "type": "feeder_assignment_correction", "title": "Assign transformer feeder", "ready": True},
        {"code": "E-WO-003", "proposal": "E-EDIT-004", "type": "conduit_installation_or_association", "title": "Record conduit association", "ready": True},
        {"code": "E-WO-004", "proposal": "E-EDIT-005", "type": "device_state_verification", "title": "Confirm device-state record", "ready": True},
        {"code": "E-WO-005", "proposal": "E-EDIT-006", "type": "transformer_replacement", "title": "Review transformer replacement", "blocked": True},
        {"code": "E-WO-006", "type": "manual_investigation", "title": "Incomplete electric investigation", "invalid": True},
    ),
    "telecom_fiber": (
        {"code": "T-WO-001", "proposal": "T-EDIT-001", "type": "cable_endpoint_correction", "title": "Assign cable endpoint", "ready": True, "complete": True},
        {"code": "T-WO-002", "proposal": "T-EDIT-002", "type": "splice_installation_or_confirmation", "title": "Confirm splice relationship", "ready": True},
        {"code": "T-WO-003", "proposal": "T-EDIT-003", "type": "strand_assignment_correction", "title": "Correct strand assignment", "ready": True},
        {"code": "T-WO-004", "proposal": "T-EDIT-004", "type": "capacity_record_correction", "title": "Correct capacity record", "ready": True},
        {"code": "T-WO-005", "proposal": "T-EDIT-007", "type": "proposed_construction_completion", "title": "Review proposed route completion", "ready": True},
        {"code": "T-WO-006", "proposal": "T-EDIT-008", "type": "cable_replacement", "title": "Review retired cable replacement", "blocked": True},
        {"code": "T-WO-007", "type": "manual_investigation", "title": "Incomplete telecom investigation", "invalid": True},
    ),
    # Demo-only water scenarios live in the sessionStorage provider; local startup must not seed the real registry.
    "water": (),
    "wastewater": (),
}


def validate_vertical(vertical: str) -> None:
    if vertical not in UTILITY_VERTICALS:
        raise ValueError("Unsupported utility vertical.")


def catalog(vertical: str | None = None) -> dict[str, Any]:
    if vertical:
        validate_vertical(vertical)
        return {
            "utility_vertical": vertical,
            "work_order_types": [*SHARED_TYPES, *VERTICAL_TYPES[vertical]],
            "priorities": list(PRIORITIES),
            "overall_statuses": list(OVERALL_STATUSES),
            "disclaimer": DISCLAIMER,
        }
    return {
        "version": WORK_ORDER_VERSION,
        "utility_verticals": list(UTILITY_VERTICALS),
        "shared_work_order_types": list(SHARED_TYPES),
        "vertical_work_order_types": {key: list(value) for key, value in VERTICAL_TYPES.items()},
        "priorities": list(PRIORITIES),
        "status_dimensions": {
            "overall": list(OVERALL_STATUSES), "design": list(DESIGN_STATUSES),
            "field_work": list(FIELD_STATUSES), "gis_implementation": list(GIS_STATUSES),
            "inspection": list(INSPECTION_STATUSES), "qa": list(QA_STATUSES),
            "trace": list(TRACE_STATUSES), "review": list(REVIEW_STATUSES),
            "closeout": list(CLOSEOUT_STATUSES),
        },
        "disclaimer": DISCLAIMER,
    }


def reject_unsafe(value: Any, *, allowed_keys: set[str] | None = None) -> None:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        if keys & _FORBIDDEN_KEYS:
            raise ValueError("Executable, filesystem, vendor-command, and credential inputs are not accepted.")
        if allowed_keys is not None and keys - allowed_keys:
            raise ValueError(f"Unsupported work-order field: {sorted(keys - allowed_keys)[0]}.")
        for item in value.values():
            reject_unsafe(item)
    elif isinstance(value, list):
        for item in value:
            reject_unsafe(item)
    elif isinstance(value, str) and (_PATH_OR_URL.search(value) or _EXECUTABLE.search(value.strip())):
        raise ValueError("Local paths, external URLs, and executable attachments are not accepted.")


def validate_type(vertical: str, value: object) -> str:
    validate_vertical(vertical)
    selected = str(value or "").strip()
    if selected not in {*SHARED_TYPES, *VERTICAL_TYPES[vertical]}:
        raise ValueError("Work-order type is not allowed for the selected utility vertical.")
    return selected


def definition_fingerprint(work_order: dict[str, Any], records: dict[str, list[dict[str, Any]]]) -> str:
    return stable_fingerprint(
        WORK_ORDER_VERSION,
        {
            key: work_order.get(key)
            for key in (
                "work_order_id", "work_order_version", "utility_vertical", "work_order_type",
                "title", "priority", "linked_proposal_id", "linked_proposal_version",
                "proposal_fingerprint", "baseline_fingerprint",
            )
        },
        {
            key: [
                {field: item.get(field) for field in sorted(item) if field not in {"created_at", "updated_at"}}
                for item in sorted(value, key=lambda row: (int(row.get("sequence", 0)), str(row.get("record_id", row.get("step_id", "")))))
            ]
            for key, value in sorted(records.items())
        },
    )


def release_fingerprint(work_order: dict[str, Any], records: dict[str, list[dict[str, Any]]]) -> str:
    return stable_fingerprint(
        "release-v1", definition_fingerprint(work_order, records),
        work_order.get("review_status"), work_order.get("approved_by"), work_order.get("approved_at"),
    )


def implementation_fingerprint(record: dict[str, Any]) -> str:
    return stable_fingerprint(
        "implementation-v1",
        sorted(record.get("completed_operation_ids", [])),
        sorted(record.get("skipped_operation_ids", [])),
        sorted(record.get("exception_operation_ids", [])),
        record.get("overlay_fingerprint", ""),
        record.get("status", ""),
    )


def closeout_fingerprint(work_order: dict[str, Any], evidence: dict[str, Any]) -> str:
    return stable_fingerprint("closeout-v1", work_order.get("version_fingerprint"), evidence)


def default_phases(work_order_id: str, version: int) -> list[dict[str, Any]]:
    return [
        {
            "phase_id": stable_id("work-order-phase", work_order_id, version, code),
            "phase_code": code, "phase_name": name, "sequence": index, "required": code != "archive",
            "status": "ready" if index == 1 else "not_started", "blocked_reason": "",
            "assigned_role": _phase_role(code), "notes": "",
        }
        for index, (code, name) in enumerate(PHASES, 1)
    ]


def default_assignments(work_order_id: str, version: int, *, invalid: bool = False) -> list[dict[str, Any]]:
    roles = ("planner", "utility_gis_technician", "qa_reviewer", "technical_reviewer", "final_approver")
    if invalid:
        roles = ("planner", "utility_gis_technician")
    return [
        {
            "assignment_id": stable_id("work-order-assignment", work_order_id, version, role),
            "role": role, "assignee": f"Synthetic {role.replace('_', ' ').title()}",
            "assignment_status": "assigned", "notes": "Synthetic application role.",
        }
        for role in roles
    ]


def default_prerequisites(
    work_order_id: str,
    version: int,
    *,
    approved: bool,
    blocked: bool = False,
    invalid: bool = False,
) -> list[dict[str, Any]]:
    types = (
        "approved_proposal", "current_baseline", "required_asset_identifiers",
        "source_evidence_available", "qa_rules_available", "trace_scenarios_available",
        "reviewer_assigned", "final_approver_assigned",
    )
    rows = []
    for prerequisite_type in types:
        status = "satisfied"
        if prerequisite_type == "approved_proposal" and not approved:
            status = "blocked"
        if blocked and prerequisite_type in {"approved_proposal", "current_baseline"}:
            status = "blocked"
        if invalid and prerequisite_type in {"final_approver_assigned", "reviewer_assigned"}:
            status = "blocked"
        rows.append({
            "prerequisite_id": stable_id("work-order-prerequisite", work_order_id, version, prerequisite_type),
            "prerequisite_type": prerequisite_type,
            "title": prerequisite_type.replace("_", " ").title(),
            "description": _prerequisite_description(prerequisite_type),
            "required": True, "status": status, "evidence_reference": "",
            "confirmed_by": "Synthetic System" if status == "satisfied" else "",
            "confirmed_at": "", "notes": "",
        })
    return rows


def operation_steps(
    work_order_id: str,
    version: int,
    operations: list[dict[str, Any]],
    *,
    invalid: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, operation in enumerate(sorted(operations, key=lambda row: int(row.get("sequence", 0))), 1):
        step_type = _step_type(operation)
        asset_ids = sorted({
            str(operation.get(key, ""))
            for key in ("target_asset_id", "from_asset_id", "to_asset_id", "new_asset_temporary_id")
            if operation.get(key)
        })
        relationship_ids = [str(operation["target_relationship_id"])] if operation.get("target_relationship_id") else []
        rows.append({
            "step_id": stable_id("work-order-step", work_order_id, version, operation["operation_id"]),
            "source_operation_id": operation["operation_id"], "sequence": index,
            "phase_code": "gis_record_update", "step_type": step_type,
            "title": _step_title(step_type),
            "instructions": _safe_instruction(step_type),
            "affected_asset_ids": asset_ids, "affected_relationship_ids": relationship_ids,
            "prerequisites": ["approved_proposal", "current_baseline"],
            "expected_result": "Recorded implementation matches the approved proposal operation.",
            "validation_method": "Compare the recorded result to the immutable approved proposal.",
            "completion_status": "not_started", "completed_by": "", "completed_at": "",
            "completion_notes": "", "exception_status": "none",
        })
    if invalid and rows:
        rows.pop()
    return rows


def default_inspections(
    vertical: str,
    work_order_id: str,
    version: int,
    operations: list[dict[str, Any]],
    *,
    invalid: bool = False,
) -> list[dict[str, Any]]:
    selected = {"identifier_verification", "relationship_verification"}
    serialized = str(operations).lower()
    for token, inspection in (
        ("phase", "phase_verification"), ("voltage", "voltage_verification"),
        ("device_state", "device_state_verification"), ("conduit", "conduit_verification"),
        ("splice", "splice_verification"), ("strand", "strand_assignment_verification"),
        ("capacity", "capacity_verification"), ("endpoint", "cable_endpoint_verification"),
        ("retire", "retirement_verification"), ("replace", "replacement_verification"),
        ("diameter", "diameter_verification"), ("material", "material_verification"),
        ("pressure_zone", "pressure_zone_verification"), ("valve", "valve_state_verification"),
        ("hydrant", "hydrant_verification"), ("meter", "meter_verification"),
        ("invert", "invert_verification"), ("rim", "rim_elevation_verification"),
        ("slope", "slope_verification"), ("flow_direction", "flow_direction_verification"),
        ("basin", "basin_verification"),
    ):
        if token in serialized:
            selected.add(inspection)
    if vertical == "electric_distribution" and "operational_status" in serialized:
        selected.add("device_state_verification")
    if invalid and vertical == "telecom_fiber":
        selected.discard("splice_verification")
    return [
        {
            "inspection_id": stable_id("work-order-inspection", work_order_id, version, inspection_type),
            "inspection_type": inspection_type, "title": inspection_type.replace("_", " ").title(),
            "required": True, "status": "pending", "affected_asset_ids": [],
            "affected_relationship_ids": [], "expected_condition": "Condition agrees with approved evidence.",
            "observed_condition": "", "result": "not_recorded", "inspector": "",
            "inspected_at": "", "evidence_ids": [], "notes": "",
        }
        for inspection_type in sorted(selected)
    ]


def readiness(
    work_order: dict[str, Any],
    assignments: list[dict[str, Any]],
    prerequisites: list[dict[str, Any]],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    blockers: list[str] = []
    if work_order.get("work_order_type") != "manual_investigation":
        if not work_order.get("linked_proposal_id") or not work_order.get("proposal_approved"):
            blockers.append("An approved Proposed Edit is required.")
        if not work_order.get("baseline_current"):
            blockers.append("The proposal baseline is stale.")
    assigned_roles = {item["role"] for item in assignments if item.get("assignment_status") != "removed"}
    for role in ("technical_reviewer", "final_approver"):
        if role not in assigned_roles:
            blockers.append(f"Required {role.replace('_', ' ')} assignment is missing.")
    blocked_prerequisites = [
        item["title"] for item in prerequisites
        if item.get("required") and item.get("status") not in {"satisfied", "satisfied_with_conditions", "waived", "not_applicable"}
    ]
    blockers.extend(f"Prerequisite blocked: {title}." for title in blocked_prerequisites)
    if not steps and work_order.get("work_order_type") != "manual_investigation":
        blockers.append("Required operation checklist is empty.")
    state = "blocked" if blockers else (
        "released" if work_order.get("overall_status") in {
            "released", "in_progress", "field_complete", "gis_update_pending", "gis_update_recorded",
            "post_work_validation", "closeout_review", "closed",
        }
        else "ready_for_release" if work_order.get("review_status") == "approved"
        else "ready_for_review"
    )
    return {"state": state, "blockers": blockers, "evaluated": True}


def closeout_readiness(
    work_order: dict[str, Any],
    steps: list[dict[str, Any]],
    inspections: list[dict[str, Any]],
    conformance: dict[str, Any] | None,
    qa: dict[str, Any] | None,
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    blockers: list[str] = []
    if any(item.get("completion_status") not in {"completed", "completed_with_exception", "skipped"} for item in steps):
        blockers.append("Required job steps are incomplete.")
    if any(item.get("required") and item.get("result") not in {"pass", "pass_with_conditions", "not_applicable"} for item in inspections):
        blockers.append("Required inspections are incomplete or failed.")
    if not conformance or conformance.get("status") not in {"conformant", "conformant_with_conditions"}:
        blockers.append("Implementation conformance is incomplete or nonconformant.")
    if not qa or qa.get("status") not in {"passed", "passed_with_warnings"}:
        blockers.append("Post-work Connectivity QA has not passed.")
    if not traces or any(item.get("status") not in {"passed", "passed_with_warnings"} for item in traces):
        blockers.append("Required post-work trace verification has not passed.")
    if not work_order.get("final_approver"):
        blockers.append("Final approver is missing.")
    state = "blocked" if blockers else ("approved" if work_order.get("closeout_status") in {"approved", "closed"} else "ready")
    return {"state": state, "blockers": blockers, "evaluated": True}


def conformance(
    operations: list[dict[str, Any]],
    implementation: dict[str, Any],
) -> dict[str, Any]:
    expected = [item["operation_id"] for item in sorted(operations, key=lambda row: int(row["sequence"]))]
    completed = list(dict.fromkeys(str(item) for item in implementation.get("completed_operation_ids", [])))
    skipped = set(str(item) for item in implementation.get("skipped_operation_ids", []))
    exceptions = set(str(item) for item in implementation.get("exception_operation_ids", []))
    expected_set = set(expected)
    missing = [item for item in expected if item not in completed and item not in skipped and item not in exceptions]
    unexpected = [item for item in completed if item not in expected_set]
    mismatched = sorted((skipped | exceptions) & expected_set)
    compliant = [item for item in expected if item in completed]
    status = "nonconformant" if missing or unexpected else ("conformant_with_conditions" if mismatched else "conformant")
    return {
        "status": status, "approved_operation_count": len(expected),
        "completed_operation_count": len(compliant), "missing_operation_ids": missing,
        "unexpected_operation_ids": unexpected, "mismatched_operation_ids": mismatched,
        "compliant_operation_ids": compliant,
        "exceptions": [{"operation_id": item, "reason": "Recorded exception requires review."} for item in sorted(exceptions)],
        "warnings": ["Skipped or exception operations require a revised or superseding Proposed Edit."] if mismatched else [],
    }


def package_payload(
    work_order: dict[str, Any],
    records: dict[str, list[dict[str, Any]]],
    approval: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "package_version": JOB_PACKAGE_VERSION,
        "work_order_id": work_order["work_order_id"],
        "work_order_version": work_order["work_order_version"],
        "utility_vertical": work_order["utility_vertical"],
        "work_order_type": work_order["work_order_type"],
        "linked_proposal_id": work_order.get("linked_proposal_id", ""),
        "linked_proposal_version": work_order.get("linked_proposal_version", 0),
        "approved_proposal_fingerprint": work_order.get("proposal_fingerprint", ""),
        "work_order_fingerprint": work_order.get("version_fingerprint", ""),
        "priority": work_order["priority"],
        "assignments": records["assignments"],
        "prerequisites": records["prerequisites"],
        "work_phases": records["phases"],
        "ordered_job_steps": records["steps"],
        "inspection_requirements": records["inspections"],
        "qa_requirements": ["Connectivity QA against recorded implementation overlay"],
        "trace_requirements": ["Selected proposal and affected-asset trace scenarios"],
        "affected_canonical_asset_ids": work_order.get("affected_asset_ids", []),
        "affected_relationship_ids": work_order.get("affected_relationship_ids", []),
        "release_approval": approval,
        "implementation_readiness": work_order.get("readiness", "not_evaluated"),
        "external_mapping_status": work_order.get("external_mapping_status", "adapter_required"),
        "required_adapter_capabilities": list(ADAPTER_CAPABILITIES),
        "executable": False,
        "descriptive_only": True,
        "disclaimer": DISCLAIMER,
    }
    reject_unsafe(payload)
    return payload


def _phase_role(code: str) -> str:
    return {
        "intake": "requester", "planning": "planner", "design_review": "designer",
        "pre_work_validation": "technical_reviewer", "release": "final_approver",
        "field_work": "field_technician", "gis_record_update": "utility_gis_technician",
        "inspection": "inspector", "post_work_qa": "qa_reviewer",
        "post_work_trace": "qa_reviewer", "technical_review": "technical_reviewer",
        "closeout": "closeout_reviewer", "archive": "data_steward",
    }[code]


def _prerequisite_description(value: str) -> str:
    descriptions = {
        "approved_proposal": "The linked Proposed Edit is approved and locked.",
        "current_baseline": "The approved proposal baseline still matches canonical evidence.",
        "required_asset_identifiers": "Affected assets have safe stable identifiers.",
        "source_evidence_available": "Approved supporting evidence is available for review.",
        "qa_rules_available": "Connectivity QA rules are available for the utility vertical.",
        "trace_scenarios_available": "Required Network Trace scenarios are defined.",
        "reviewer_assigned": "A technical reviewer is assigned.",
        "final_approver_assigned": "A separate final approver is assigned.",
    }
    return descriptions.get(value, value.replace("_", " ").capitalize())


def _step_type(operation: dict[str, Any]) -> str:
    operation_type = str(operation.get("operation_type", ""))
    field_name = str(operation.get("field_name", ""))
    if field_name in {"phase"}:
        return "verify_phase"
    if field_name in {"nominal_voltage", "operating_voltage"}:
        return "verify_voltage"
    if field_name in {"device_state", "normally_open", "operational_status"}:
        return "confirm_device_state"
    if field_name in {"strand_start", "strand_end"}:
        return "verify_strand"
    if "capacity" in field_name:
        return "verify_capacity"
    return {
        "add_asset": "install_asset", "replace_asset": "replace_asset", "retire_asset": "retire_asset",
        "add_relationship": "connect_asset", "remove_relationship": "disconnect_asset",
        "replace_relationship": "verify_relationship", "update_relationship": "verify_relationship",
        "confirm_provisional_relationship": "verify_relationship",
        "update_asset_attribute": "update_attribute", "update_asset_attributes": "update_attribute",
        "assign_membership": "assign_membership", "associate_container": "verify_conduit",
        "associate_structure": "verify_structure",
    }.get(operation_type, "review_asset")


def _step_title(step_type: str) -> str:
    return step_type.replace("_", " ").title()


def _safe_instruction(step_type: str) -> str:
    if step_type == "confirm_device_state":
        return "Verify the proposed device-state record with approved source evidence. Do not operate equipment through UtilitiesPlatform."
    return f"Review and record the approved {step_type.replace('_', ' ')} result in the synthetic job package."


def string_list(value: object) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return []
    return [str(item)[:120] for item in value if str(item).strip()]
