from __future__ import annotations

from typing import Any

TRACE_RULE_VERSION = "network-trace-rules-v1"
TRACE_PROFILE_VERSION = "network-trace-profiles-v1"

RELATIONSHIP_CATEGORIES = {
    "feeds": "operational_flow",
    "upstream_of": "operational_flow",
    "downstream_of": "operational_flow",
    "served_by": "operational_flow",
    "connects_to": "operational_connection",
    "spliced_to": "operational_connection",
    "terminates_at": "operational_connection",
    "protected_by": "operational_connection",
    "belongs_to_feeder": "membership_context",
    "belongs_to_circuit": "membership_context",
    "belongs_to_route": "membership_context",
    "contained_in": "containment_context",
    "routed_through": "containment_context",
    "mounted_on": "support_context",
    "associated_with_work_order": "reference_context",
    "reference_for": "reference_context",
    "replaces": "historical_context",
    "retires": "historical_context",
}

ELECTRIC_FLOW_CLASSES = {
    "substation", "feeder", "feeder_breaker", "switch", "fuse", "recloser",
    "transformer", "overhead_conductor", "underground_conductor",
    "secondary_conductor", "service_point", "junction",
}
TELECOM_FLOW_CLASSES = {
    "central_office", "network_hub", "fiber_cabinet", "fiber_route", "fiber_cable",
    "handhole", "manhole", "splice_closure", "splitter", "terminal",
    "proposed_construction_segment",
}


def _trace(
    code: str,
    name: str,
    vertical: str,
    start_classes: set[str],
    terminal_classes: set[str],
    direction: str,
    description: str,
) -> dict[str, Any]:
    return {
        "trace_type": code,
        "name": name,
        "utility_vertical": vertical,
        "start_asset_classes": sorted(start_classes),
        "terminal_asset_classes": sorted(terminal_classes),
        "default_direction": direction,
        "description": description,
        "trace_profile_version": TRACE_PROFILE_VERSION,
        "trace_rule_version": TRACE_RULE_VERSION,
        "read_only": True,
    }


ELECTRIC_TRACES = (
    _trace("ELEC-TRACE-001", "Feeder downstream trace", "electric_distribution",
           {"feeder", "feeder_breaker", "substation"}, {"service_point"}, "downstream",
           "Traverse downstream distribution relationships while honoring device state and calibrated QA evidence."),
    _trace("ELEC-TRACE-002", "Asset upstream trace", "electric_distribution",
           {"overhead_conductor", "underground_conductor", "secondary_conductor", "transformer", "service_point", "switch", "fuse", "recloser", "junction"},
           {"feeder_breaker", "feeder", "substation"}, "upstream",
           "Find a nearest represented upstream feeder origin from explicit canonical relationships."),
    _trace("ELEC-TRACE-003", "Protective device trace", "electric_distribution",
           {"transformer", "overhead_conductor", "underground_conductor", "secondary_conductor", "service_point", "junction"},
           {"fuse", "recloser", "switch", "feeder_breaker"}, "upstream",
           "Find nearest upstream protective-device candidates; this is not a coordination study."),
    _trace("ELEC-TRACE-004", "Isolation trace", "electric_distribution",
           {"switch", "fuse", "recloser", "feeder_breaker", "overhead_conductor", "underground_conductor", "secondary_conductor"},
           {"service_point"}, "downstream",
           "Identify represented downstream assets if the selected asset is analytically treated as unavailable."),
    _trace("ELEC-TRACE-005", "Transformer service trace", "electric_distribution",
           {"transformer"}, {"service_point"}, "downstream",
           "Traverse represented secondary conductors and safe aggregate service points."),
    _trace("ELEC-TRACE-006", "Feeder membership trace", "electric_distribution",
           ELECTRIC_FLOW_CLASSES, set(), "bidirectional",
           "Compare explicit connectivity and feeder membership evidence."),
    _trace("ELEC-TRACE-007", "Trace to source", "electric_distribution",
           ELECTRIC_FLOW_CLASSES, {"feeder_breaker", "substation"}, "toward_source",
           "Find all plausible represented upstream paths toward a feeder breaker or substation."),
)

TELECOM_TRACES = (
    _trace("TEL-TRACE-001", "Hub-to-terminal trace", "telecom_fiber",
           {"network_hub", "central_office", "fiber_cabinet"}, {"terminal"}, "toward_terminal",
           "Traverse represented cable, splice, structure, splitter, and terminal relationships."),
    _trace("TEL-TRACE-002", "Terminal upstream trace", "telecom_fiber",
           {"terminal", "splitter", "fiber_cabinet"}, {"fiber_cabinet", "network_hub", "central_office"}, "upstream",
           "Find represented upstream cable and hub candidates."),
    _trace("TEL-TRACE-003", "Cable route trace", "telecom_fiber",
           {"fiber_cable", "fiber_route", "proposed_construction_segment"}, set(), "bidirectional",
           "Inspect connected route segments while preserving lifecycle distinctions."),
    _trace("TEL-TRACE-004", "Splice sequence trace", "telecom_fiber",
           {"fiber_cable", "splice_closure", "terminal"}, {"terminal", "fiber_cabinet", "network_hub"}, "bidirectional",
           "Return represented splice or termination sequences without inferring strand continuity."),
    _trace("TEL-TRACE-005", "Cabinet downstream trace", "telecom_fiber",
           {"fiber_cabinet"}, {"terminal"}, "downstream",
           "Traverse represented downstream cables, closures, splitters, and terminals."),
    _trace("TEL-TRACE-006", "Affected-network trace", "telecom_fiber",
           {"fiber_cable", "splice_closure", "fiber_cabinet"}, {"terminal"}, "downstream",
           "Identify represented downstream dependency; this is not a customer outage prediction."),
    _trace("TEL-TRACE-007", "Capacity-path trace", "telecom_fiber",
           {"network_hub", "fiber_cabinet", "fiber_cable", "splitter"}, {"terminal"}, "toward_terminal",
           "Report safe aggregate capacity evidence without assigning strands or capacity."),
    _trace("TEL-TRACE-008", "Proposed construction continuity trace", "telecom_fiber",
           {"proposed_construction_segment", "fiber_route"}, set(), "bidirectional",
           "Evaluate represented proposed continuity separately from active service paths."),
)

TRACE_PROFILES = {
    "electric_distribution": {
        "profile_name": "electric_distribution_trace_v1",
        "flow_classes": ELECTRIC_FLOW_CLASSES,
        "traces": ELECTRIC_TRACES,
    },
    "telecom_fiber": {
        "profile_name": "telecom_fiber_trace_v1",
        "flow_classes": TELECOM_FLOW_CLASSES,
        "traces": TELECOM_TRACES,
    },
}


def trace_types(vertical: str | None = None) -> dict[str, Any]:
    if vertical:
        if vertical not in TRACE_PROFILES:
            raise ValueError("Unsupported utility vertical.")
        profile = TRACE_PROFILES[vertical]
        return {
            "utility_vertical": vertical,
            "profile_name": profile["profile_name"],
            "trace_profile_version": TRACE_PROFILE_VERSION,
            "trace_rule_version": TRACE_RULE_VERSION,
            "items": [dict(item) for item in profile["traces"]],
        }
    return {
        "trace_profile_version": TRACE_PROFILE_VERSION,
        "trace_rule_version": TRACE_RULE_VERSION,
        "profiles": {key: trace_types(key) for key in TRACE_PROFILES},
    }


def trace_definition(vertical: str, trace_type: str) -> dict[str, Any]:
    for item in TRACE_PROFILES.get(vertical, {}).get("traces", ()):
        if item["trace_type"] == trace_type:
            return item
    raise ValueError("Unsupported trace type for utility vertical.")


def relationship_category(relationship_type: str) -> str:
    return RELATIONSHIP_CATEGORIES.get(relationship_type, "prohibited_relationship")
