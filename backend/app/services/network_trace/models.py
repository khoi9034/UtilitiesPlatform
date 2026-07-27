from __future__ import annotations

from typing import Any

VERTICALS = ("electric_distribution", "telecom_fiber")
OUTCOMES = (
    "complete",
    "complete_with_warnings",
    "partial",
    "blocked",
    "no_path",
    "ambiguous",
    "failed_safely",
)
DIRECTIONS = ("upstream", "downstream", "bidirectional", "toward_source", "toward_terminal")
LIFECYCLE_MODES = ("active_only", "active_and_installed", "include_proposed", "include_inactive", "historical")
OPERATIONAL_MODES = ("respect_state", "include_unknown", "diagnostic")
PROVISIONAL_POLICIES = ("exclude", "include_with_warning", "require_when_only_path")
QA_POLICIES = ("strict", "conservative", "diagnostic")
CONFIDENCE_LEVELS = ("high", "medium", "low", "indeterminate")
STOPPING_REASONS = (
    "target_reached",
    "source_reached",
    "terminal_reached",
    "open_device",
    "retired_asset",
    "inactive_asset",
    "missing_endpoint",
    "missing_relationship",
    "trace_stopping_issue",
    "phase_conflict",
    "voltage_conflict",
    "feeder_conflict",
    "route_conflict",
    "strand_conflict",
    "capacity_conflict",
    "lifecycle_conflict",
    "ambiguous_branch",
    "cycle_detected",
    "maximum_depth",
    "maximum_assets",
    "prohibited_relationship",
    "incompatible_vertical",
    "no_traversable_edge",
    "failed_safely",
)

_FORBIDDEN_KEYS = {
    "path", "filesystem_path", "sql", "python", "shell", "command", "expression",
    "script", "rule_file", "url", "external_url",
}
_ALLOWED_KEYS = {
    "trace_type", "start_asset_id", "optional_target_asset_id", "direction",
    "lifecycle_mode", "operational_mode", "provisional_relationship_policy", "qa_policy",
    "include_reference_relationships", "include_containment_relationships", "max_depth",
    "max_assets", "requested_by", "request_notes", "force_recalculate",
    "preserve_review_decisions",
}


def normalize_request(vertical: str, payload: dict[str, Any], trace_codes: set[str]) -> dict[str, Any]:
    if vertical not in VERTICALS:
        raise ValueError("Unsupported utility vertical.")
    if not isinstance(payload, dict):
        raise ValueError("Trace request must be a JSON object.")
    if _FORBIDDEN_KEYS.intersection(payload):
        raise ValueError("Executable, external, and filesystem trace inputs are not accepted.")
    unknown = set(payload).difference(_ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"Unsupported trace request field: {sorted(unknown)[0]}.")
    request = {
        "utility_vertical": vertical,
        "trace_type": _choice(payload, "trace_type", trace_codes),
        "start_asset_id": _text(payload, "start_asset_id", required=True, limit=120),
        "optional_target_asset_id": _text(payload, "optional_target_asset_id", limit=120),
        "direction": _choice(payload, "direction", set(DIRECTIONS), "downstream"),
        "lifecycle_mode": _choice(payload, "lifecycle_mode", set(LIFECYCLE_MODES), "active_only"),
        "operational_mode": _choice(payload, "operational_mode", set(OPERATIONAL_MODES), "respect_state"),
        "provisional_relationship_policy": _choice(
            payload, "provisional_relationship_policy", set(PROVISIONAL_POLICIES), "include_with_warning",
        ),
        "qa_policy": _choice(payload, "qa_policy", set(QA_POLICIES), "conservative"),
        "include_reference_relationships": bool(payload.get("include_reference_relationships", False)),
        "include_containment_relationships": bool(payload.get("include_containment_relationships", False)),
        "max_depth": _integer(payload, "max_depth", 40, 1, 100),
        "max_assets": _integer(payload, "max_assets", 250, 1, 1000),
        "requested_by": _text(payload, "requested_by", default="local_operator", limit=100),
        "request_notes": _text(payload, "request_notes", limit=1000),
        "force_recalculate": bool(payload.get("force_recalculate", False)),
        "preserve_review_decisions": bool(payload.get("preserve_review_decisions", True)),
    }
    return request


def _choice(
    payload: dict[str, Any],
    field: str,
    allowed: set[str],
    default: str = "",
) -> str:
    value = str(payload.get(field, default)).strip()
    if value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}.")
    return value


def _text(
    payload: dict[str, Any],
    field: str,
    *,
    default: str = "",
    required: bool = False,
    limit: int,
) -> str:
    value = str(payload.get(field, default)).strip()
    if required and not value:
        raise ValueError(f"{field} is required.")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds the {limit}-character limit.")
    return value


def _integer(payload: dict[str, Any], field: str, default: int, minimum: int, maximum: int) -> int:
    value = payload.get(field, default)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}.")
    return parsed
