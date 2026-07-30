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
    "belongs_to_pressure_zone": "membership_context",
    "belongs_to_water_system": "membership_context",
    "belongs_to_basin": "membership_context",
    "flows_to": "operational_flow",
    "draws_from": "operational_flow",
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
WATER_FLOW_CLASSES = {
    "water_main", "transmission_main", "distribution_main", "service_line",
    "hydrant_lateral", "raw_water_main", "reclaimed_water_main", "valve",
    "isolation_valve", "control_valve", "pressure_reducing_valve",
    "air_release_valve", "blowoff", "hydrant", "meter", "meter_vault",
    "fitting", "tee", "elbow", "reducer", "coupling", "pump",
    "pump_station", "storage_tank", "elevated_tank", "reservoir",
    "treatment_facility", "well", "backflow_device", "vault", "structure",
}
WASTEWATER_FLOW_CLASSES = {
    "gravity_main", "force_main", "pressure_sewer", "service_lateral",
    "interceptor", "trunk_sewer", "outfall_pipe", "manhole", "cleanout",
    "fitting", "junction", "lift_station", "pump", "wet_well",
    "treatment_facility", "outfall", "discharge_point", "valve",
    "air_release_valve", "vault", "structure",
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
        "hydraulic_simulation": False,
        "disclaimer": "This is a topology/connectivity trace and not a hydraulic simulation."
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

WATER_TRACES = (
    _trace("WATER-TRACE-001", "Connected assets from main", "water",
           {"water_main", "transmission_main", "distribution_main"}, set(), "bidirectional",
           "Traverse explicit represented water-network relationships from a selected main."),
    _trace("WATER-TRACE-002", "Upstream source or facility path", "water",
           WATER_FLOW_CLASSES, {"treatment_facility", "well", "reservoir", "storage_tank", "elevated_tank"}, "toward_source",
           "Find represented upstream source or facility candidates without hydraulic inference."),
    _trace("WATER-TRACE-003", "Service and hydrant reachability", "water",
           {"water_main", "transmission_main", "distribution_main", "valve", "isolation_valve"}, {"service_line", "meter", "hydrant"}, "downstream",
           "Identify represented downstream services and hydrants."),
    _trace("WATER-TRACE-004", "Valve-isolation impact", "water",
           {"valve", "isolation_valve", "control_valve"}, {"service_line", "meter", "hydrant"}, "downstream",
           "Treat the selected valve as an analytical isolation boundary and report represented downstream assets."),
    _trace("WATER-TRACE-005", "Affected services after valve closure", "water",
           {"valve", "isolation_valve", "control_valve"}, {"service_line", "meter"}, "downstream",
           "Report represented service reachability after a simulated valve closure; no valve is operated."),
    _trace("WATER-TRACE-006", "Disconnected water assets", "water",
           WATER_FLOW_CLASSES, set(), "bidirectional",
           "Inspect represented connectivity boundaries and missing relationships."),
)

WASTEWATER_TRACES = (
    _trace("WW-TRACE-001", "Downstream gravity path", "wastewater",
           {"gravity_main", "manhole", "cleanout", "junction"}, {"lift_station", "treatment_facility", "outfall", "discharge_point"}, "downstream",
           "Follow explicit directional relationships; digitized geometry does not establish authoritative flow."),
    _trace("WW-TRACE-002", "Upstream contributing assets", "wastewater",
           {"gravity_main", "manhole", "lift_station"}, {"service_lateral", "manhole"}, "upstream",
           "Find represented upstream contributors from explicit relationship direction."),
    _trace("WW-TRACE-003", "Path to lift station", "wastewater",
           {"gravity_main", "manhole", "service_lateral"}, {"lift_station", "wet_well"}, "downstream",
           "Find a represented downstream path to a lift station or wet well."),
    _trace("WW-TRACE-004", "Force-main path", "wastewater",
           {"lift_station", "pump", "force_main", "pressure_sewer"}, {"treatment_facility", "outfall", "discharge_point"}, "downstream",
           "Traverse explicit pressure-network relationships from represented lift equipment."),
    _trace("WW-TRACE-005", "Path to treatment or outfall", "wastewater",
           WASTEWATER_FLOW_CLASSES, {"treatment_facility", "outfall", "discharge_point"}, "downstream",
           "Find represented downstream treatment or discharge endpoints."),
    _trace("WW-TRACE-006", "Affected upstream assets after blockage", "wastewater",
           {"gravity_main", "manhole", "junction"}, {"service_lateral", "manhole"}, "upstream",
           "Treat the selected asset as an analytical blockage boundary and report represented upstream assets."),
    _trace("WW-TRACE-007", "Disconnected wastewater structures", "wastewater",
           WASTEWATER_FLOW_CLASSES, set(), "bidirectional",
           "Inspect represented connectivity boundaries and missing relationships."),
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
    "water": {
        "profile_name": "water_trace_v1",
        "flow_classes": WATER_FLOW_CLASSES,
        "traces": WATER_TRACES,
    },
    "wastewater": {
        "profile_name": "wastewater_trace_v1",
        "flow_classes": WASTEWATER_FLOW_CLASSES,
        "traces": WASTEWATER_TRACES,
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
