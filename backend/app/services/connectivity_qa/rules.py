from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.services.utility_assets.domain import LIFECYCLE_STATES, stable_fingerprint, stable_id

MODEL_VERSION = "canonical-connectivity-graph-v1"
RULE_VERSION = "connectivity-qa-rules-v2"
PROFILES = {
    "electric_distribution": "electric_distribution_v1",
    "telecom_fiber": "telecom_fiber_v1",
    "water": "water_v1",
    "wastewater": "wastewater_v1",
}
SEVERITIES = ("info", "warning", "error", "critical")
RUN_STATUSES = ("not_started", "running", "succeeded", "partially_failed", "failed", "blocked", "skipped")
RULE_STATUSES = ("passed", "warning", "failed", "blocked", "skipped")
REVIEW_STATUSES = (
    "open", "acknowledged", "deferred", "accepted_risk",
    "resolved_externally", "false_positive", "superseded",
)


def _rule(
    code: str,
    name: str,
    vertical: str,
    severity: str,
    blocking: bool,
    scope: str,
    description: str,
    recommendation: str,
    limitation: str,
    applicable_asset_classes: tuple[str, ...] = (),
    required_any_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    category = (
        "shared" if code.startswith("SHARED") else
        "electric" if code.startswith("ELEC") else
        "telecom" if code.startswith("TEL") else
        "water" if code.startswith("WATER") else
        "wastewater"
    )
    return {
        "rule_code": code,
        "name": name,
        "utility_vertical": vertical,
        "category": category,
        "severity": severity,
        "blocking": blocking,
        "scope": scope,
        "description": description,
        "recommended_action": recommendation,
        "limitation": limitation,
        "rule_version": RULE_VERSION,
        "enabled": True,
        "applicable_asset_classes": list(applicable_asset_classes),
        "required_any_fields": list(required_any_fields),
        "result_states": ["blocking", "warning", "informational", "unable_to_determine"],
    }


SHARED_RULES = (
    _rule("SHARED-001", "Missing relationship endpoint", "shared", "error", True, "relationship", "A stored relationship references an asset that is absent from the canonical registry.", "Confirm the missing asset or retire the invalid relationship through an approved workflow.", "Registry presence is checked; source systems are not queried."),
    _rule("SHARED-002", "Self-referential relationship", "shared", "error", True, "relationship", "A relationship starts and ends at the same asset.", "Confirm the relationship intent and correct it in an approved editing workflow.", "Some specialized loop devices may require an accepted-risk review."),
    _rule("SHARED-003", "Duplicate relationship", "shared", "warning", False, "relationship", "More than one stored relationship represents the same directed asset pair and type.", "Review duplicate relationship evidence and retain one authoritative relationship.", "Opposite directions are evaluated separately."),
    _rule("SHARED-004", "Provisional relationship", "shared", "warning", False, "relationship", "A network relationship remains provisional or inferred.", "Confirm the relationship from an authoritative source or field review.", "Provisional does not mean incorrect."),
    _rule("SHARED-005", "Retired asset linked to active asset", "shared", "error", True, "relationship", "A retired or removed asset remains related to an active asset.", "Review lifecycle dates and relationship validity before operational use.", "Historical relationships can be legitimate and may be accepted as risk."),
    _rule("SHARED-006", "Incompatible utility vertical relationship", "shared", "critical", True, "relationship", "A relationship connects assets assigned to different utility verticals.", "Confirm taxonomy and relationship ownership before use.", "Shared structures may need an explicit cross-utility association type in a future model."),
    _rule("SHARED-007", "Missing canonical identifier", "shared", "error", True, "asset", "A canonical asset lacks both a canonical name and source asset identifier.", "Assign a durable approved identifier while preserving source lineage.", "A generated registry key alone is not an operational identifier."),
    _rule("SHARED-008", "Unknown lifecycle state", "shared", "warning", False, "asset", "An asset lifecycle state is unknown or outside the canonical allowlist.", "Confirm lifecycle state with the data owner.", "Unknown can be an honest source limitation."),
)

ELECTRIC_RULES = (
    _rule("ELEC-001", "Disconnected conductor", "electric_distribution", "error", True, "asset", "A conductor has no explicit stored relationship.", "Review endpoint equipment and source coverage; do not snap automatically.", "Only explicit canonical relationships are evaluated."),
    _rule("ELEC-002", "Conductor endpoint missing", "electric_distribution", "error", True, "asset", "A conductor has fewer than two explicit network relationships.", "Confirm both conductor endpoints and relationship direction.", "Tap conductors and source-boundary segments may be expected conditions."),
    _rule("ELEC-003", "Transformer missing feeder ID", "electric_distribution", "error", True, "asset", "An active transformer has no canonical feeder identifier.", "Confirm the feeder assignment from approved records.", "Feeder identity may be unavailable in early source deliveries."),
    _rule("ELEC-004", "Transformer disconnected from primary", "electric_distribution", "error", True, "asset", "A transformer has no explicit relationship to primary conductor or feeder assets.", "Review primary-side connectivity and source coverage.", "Secondary-only extracts can produce expected findings."),
    _rule("ELEC-005", "Invalid or incompatible phase", "electric_distribution", "error", True, "asset", "An electric asset contains a phase combination outside the V1 allowlist.", "Confirm phase coding and normalize through an approved mapping.", "The V1 allowlist does not model every vendor-specific phase code."),
    _rule("ELEC-006", "Voltage mismatch", "electric_distribution", "error", True, "asset", "Nominal and operating voltage conflict on the same asset.", "Confirm voltage values and units.", "Voltage transformations and regulator behavior are not traced."),
    _rule("ELEC-007", "Underground conductor missing conduit", "electric_distribution", "warning", False, "asset", "An underground conductor has no conduit identifier or routed-through relationship.", "Confirm direct-buried status or associate approved conduit evidence.", "Direct-buried construction can be an expected condition."),
    _rule("ELEC-008", "Equipment missing structure association", "electric_distribution", "warning", False, "asset", "Electric equipment has no structure identifier or mounted-on relationship.", "Confirm the supporting pole, vault, or structure.", "Pad-mounted equipment may not require a separate structure asset."),
    _rule("ELEC-009", "Feeder inconsistency across relationship", "electric_distribution", "error", True, "relationship", "Related operational electric assets carry conflicting feeder identifiers.", "Review feeder boundaries and normally open points.", "Only active operational network classes and connectivity or membership relationships are evaluated; tie points can legitimately connect feeder contexts."),
    _rule("ELEC-010", "Circuit inconsistency across relationship", "electric_distribution", "warning", False, "relationship", "Related operational electric assets carry conflicting circuit identifiers.", "Confirm circuit assignment and boundary equipment.", "Only active operational network classes and connectivity or membership relationships are evaluated; circuit identifiers may differ across source systems."),
    _rule("ELEC-011", "Invalid relationship direction", "electric_distribution", "warning", False, "relationship", "An electric relationship uses an unsupported direction value.", "Confirm source direction and map it to the canonical allowlist.", "Direction does not establish authoritative electrical flow."),
    _rule("ELEC-012", "Normally open device", "electric_distribution", "info", False, "asset", "A switch or device is marked normally open.", "Retain as operational context and verify before future tracing.", "This is an informational condition, not a defect."),
    _rule("ELEC-013", "Protective device type missing", "electric_distribution", "warning", False, "asset", "A protective device lacks its canonical device type.", "Confirm protection type and ratings from approved records.", "Protection coordination is outside V1."),
    _rule("ELEC-014", "Active-retired electric relationship", "electric_distribution", "error", True, "relationship", "An active electric asset remains related to a retired or removed asset.", "Review retirement completion and relationship history.", "Historical associations can be legitimate."),
    _rule("ELEC-015", "Electric placement contradiction", "electric_distribution", "warning", False, "asset", "Asset class and placement type conflict.", "Confirm overhead, underground, or structure placement.", "Hybrid construction requires human interpretation."),
)

TELECOM_RULES = (
    _rule("TEL-001", "Fiber cable endpoint missing", "telecom_fiber", "error", True, "asset", "A fiber cable lacks a from-structure or to-structure identifier.", "Confirm both cable endpoints from approved network records.", "Structure identifiers may be absent in route-only extracts."),
    _rule("TEL-002", "Invalid fiber termination", "telecom_fiber", "error", True, "relationship", "A fiber cable connects directly to an incompatible asset class.", "Confirm the terminating structure, closure, cabinet, or terminal.", "Vendor models can represent logical cable-to-cable relations differently."),
    _rule("TEL-003", "Overlapping strand range", "telecom_fiber", "error", True, "asset", "Fiber cables on the same route contain overlapping assigned strand ranges.", "Review strand allocation and splice documentation.", "Route-level comparison is a conservative candidate check."),
    _rule("TEL-004", "Capacity exceeds total", "telecom_fiber", "error", True, "asset", "Used and reserved capacity exceed total capacity.", "Confirm capacity counts and units.", "Splitter ports and fiber strands are not treated as interchangeable units."),
    _rule("TEL-005", "Available capacity mismatch", "telecom_fiber", "warning", False, "asset", "Available capacity does not equal total minus used and reserved.", "Reconcile the safe aggregate capacity values.", "Reserved or unavailable capacity policies can explain a difference."),
    _rule("TEL-006", "Fiber count and strand range mismatch", "telecom_fiber", "error", True, "asset", "The assigned strand range is invalid or exceeds the fiber count.", "Confirm cable count and strand numbering convention.", "One-based strand numbering is assumed."),
    _rule("TEL-007", "Disconnected splice closure", "telecom_fiber", "error", True, "asset", "A splice closure has no explicit stored relationship.", "Confirm cable and splice relationships.", "Inspection-only closure layers may omit network relationships."),
    _rule("TEL-008", "Disconnected terminal", "telecom_fiber", "error", True, "asset", "A terminal has no explicit stored relationship.", "Confirm serving cable, splitter, or cabinet relationship.", "Terminal inventory can precede route onboarding."),
    _rule("TEL-009", "Cabinet missing route", "telecom_fiber", "warning", False, "asset", "A fiber cabinet has no route identifier.", "Confirm route or hub association.", "Cabinets can serve multiple routes."),
    _rule("TEL-010", "Underground cable missing conduit", "telecom_fiber", "warning", False, "asset", "An underground fiber cable has no conduit identifier or routed-through relationship.", "Confirm conduit association or direct-buried construction.", "Direct-buried cable can be an expected condition."),
    _rule("TEL-011", "Aerial cable missing support", "telecom_fiber", "warning", False, "asset", "An aerial fiber cable has no mounted-on pole relationship.", "Confirm support structures and attachment records.", "Span-level support may be stored in a separate dependency layer."),
    _rule("TEL-012", "Proposed route gap", "telecom_fiber", "warning", False, "asset", "A proposed construction segment lacks complete explicit connectivity.", "Review construction endpoints before approval.", "Proposed designs are expected to evolve."),
    _rule("TEL-013", "Retired cable linked to active terminal", "telecom_fiber", "error", True, "relationship", "A retired cable remains related to an active terminal.", "Confirm cutover and retirement records.", "Historical termination records can be legitimate."),
    _rule("TEL-014", "Provisional splice relationship", "telecom_fiber", "warning", False, "relationship", "A splice closure relationship is provisional.", "Confirm splice evidence before operational tracing.", "Provisional does not mean incorrect."),
    _rule("TEL-015", "Splitter capacity inconsistency", "telecom_fiber", "error", True, "asset", "Splitter used and reserved capacity exceeds its total capacity.", "Confirm splitter ratio and port allocation.", "Optical loss and cascaded splitters are outside V1."),
    _rule("TEL-016", "Telecom placement contradiction", "telecom_fiber", "warning", False, "asset", "Telecom asset class and placement type conflict.", "Confirm aerial, underground, or structure placement.", "Mixed placement routes require segment-level review."),
)

WATER_LINE_CLASSES = (
    "water_main", "transmission_main", "distribution_main", "service_line",
    "hydrant_lateral", "raw_water_main", "reclaimed_water_main",
    "abandoned_water_main", "unknown_water_line",
)
WATER_RULES = (
    _rule("WATER-001", "Blank asset identifier", "water", "error", True, "asset", "A water asset lacks a source asset identifier.", "Confirm a durable identifier with the data owner.", "A generated registry key is not treated as an operational identifier."),
    _rule("WATER-002", "Duplicate asset identifier", "water", "error", True, "asset", "Two water assets share the same normalized source identifier.", "Review both source records before selecting an authoritative identifier.", "This is a duplicate candidate, not an automatic merge."),
    _rule("WATER-003", "Invalid or unsupported geometry", "water", "error", True, "asset", "Asset geometry is missing or incompatible with the represented class.", "Confirm geometry type without repairing or projecting the source.", "Only stored geometry metadata is evaluated."),
    _rule("WATER-004", "Unknown spatial reference", "water", "warning", True, "asset", "Spatial-reference metadata is unavailable.", "Confirm the coordinate system with the source owner.", "No coordinate system is defined or inferred."),
    _rule("WATER-005", "Suspicious extent", "water", "warning", False, "asset", "Stored geometry metadata flags a suspicious extent.", "Review source coordinate metadata and extent.", "Coordinates are not transformed during QA."),
    _rule("WATER-006", "Invalid diameter", "water", "error", True, "asset", "A represented water line has a non-positive or nonnumeric diameter.", "Confirm diameter value and unit.", "The rule is unable to determine a result when diameter is absent from the schema.", WATER_LINE_CLASSES, ("diameter",)),
    _rule("WATER-007", "Invalid material", "water", "warning", False, "asset", "A represented water line has an empty or explicitly unknown material code.", "Confirm the material code list with the data owner.", "The rule does not invent code translations.", WATER_LINE_CLASSES, ("material",)),
    _rule("WATER-008", "Invalid lifecycle status", "water", "warning", False, "asset", "Lifecycle status is unknown or outside the canonical allowlist.", "Confirm lifecycle state.", "Unknown can be an honest source limitation."),
    _rule("WATER-009", "Disconnected main endpoint", "water", "error", True, "asset", "A water main has fewer than two explicit network relationships.", "Review endpoint and source-coverage evidence; do not snap geometry.", "Connectivity is based only on explicit canonical relationships.", WATER_LINE_CLASSES),
    _rule("WATER-010", "Isolated service line", "water", "error", True, "asset", "A service line has no explicit network relationship.", "Confirm the serving main and endpoint relationship.", "Service extracts may omit customer-side context.", ("service_line",)),
    _rule("WATER-011", "Hydrant lacks plausible main relationship", "water", "warning", False, "asset", "A hydrant has no explicit relationship to a water main or hydrant lateral.", "Confirm the hydrant lateral or serving-main relationship.", "Spatial proximity is not inferred.", ("hydrant",)),
    _rule("WATER-012", "Valve lacks main relationship", "water", "warning", False, "asset", "A valve has no explicit relationship to a water main.", "Confirm valve placement and network relationship.", "Coincidence is not calculated from hidden geometry.", ("valve", "isolation_valve", "control_valve", "pressure_reducing_valve", "air_release_valve")),
    _rule("WATER-013", "Invalid pressure-zone reference", "water", "warning", False, "asset", "A pressure-zone identifier does not resolve to represented context.", "Confirm pressure-zone membership.", "A missing pressure-zone layer may explain this finding.", (), ("pressure_zone_id",)),
    _rule("WATER-014", "Missing owner or jurisdiction", "water", "warning", False, "asset", "Owner and jurisdiction evidence are unavailable.", "Confirm ownership or jurisdiction before operational use.", "Ownership is not inferred from geography alone."),
    _rule("WATER-015", "Invalid facility reference", "water", "warning", False, "asset", "A facility identifier does not resolve to a represented facility.", "Confirm the facility relationship.", "A missing dependent facility layer may explain this finding.", (), ("facility_id",)),
    _rule("WATER-016", "Active asset connected only to retired assets", "water", "error", True, "asset", "An active water asset has relationships only to retired or abandoned assets.", "Review lifecycle and connectivity evidence.", "Historical associations can be legitimate."),
    _rule("WATER-017", "Service line lacks endpoint", "water", "warning", False, "asset", "A service line has no represented meter or service endpoint.", "Confirm the safe endpoint relationship.", "No customer names, addresses, or accounts are evaluated.", ("service_line",)),
    _rule("WATER-018", "Conflicting water-system identity", "water", "warning", False, "relationship", "Connected water assets carry conflicting represented system identifiers.", "Review system boundaries and source mappings.", "Boundary connections may be expected.", (), ("water_system_id",)),
)

WASTEWATER_LINE_CLASSES = (
    "gravity_main", "force_main", "pressure_sewer", "service_lateral",
    "interceptor", "trunk_sewer", "outfall_pipe", "abandoned_sewer",
    "unknown_wastewater_line",
)
WASTEWATER_RULES = (
    _rule("WW-001", "Blank asset identifier", "wastewater", "error", True, "asset", "A wastewater asset lacks a source asset identifier.", "Confirm a durable identifier with the data owner.", "A generated registry key is not an operational identifier."),
    _rule("WW-002", "Duplicate asset identifier", "wastewater", "error", True, "asset", "Two wastewater assets share a normalized source identifier.", "Review duplicate candidates without merging automatically.", "Identifier equality alone does not prove duplicate geometry."),
    _rule("WW-003", "Invalid geometry", "wastewater", "error", True, "asset", "Asset geometry is missing or incompatible with its represented class.", "Confirm geometry type without repairing source geometry.", "Only stored geometry metadata is evaluated."),
    _rule("WW-004", "Unknown spatial reference", "wastewater", "warning", True, "asset", "Spatial-reference metadata is unavailable.", "Confirm the coordinate system.", "No projection is defined or inferred."),
    _rule("WW-005", "Suspicious extent", "wastewater", "warning", False, "asset", "Stored geometry metadata flags a suspicious extent.", "Review coordinate metadata and extent.", "Coordinates are not transformed."),
    _rule("WW-006", "Gravity main lacks structures", "wastewater", "error", True, "asset", "A gravity main lacks valid represented upstream or downstream structures.", "Confirm structure identifiers or explicit relationships.", "Polyline geometry alone does not establish gravity flow.", ("gravity_main",)),
    _rule("WW-007", "Gravity segment has identical endpoints", "wastewater", "error", True, "asset", "A gravity main has identical represented upstream and downstream identifiers.", "Confirm node identifiers and source mapping.", "Digitized direction is not treated as authoritative.", ("gravity_main",), ("upstream_structure_id", "downstream_structure_id", "from_node_id", "to_node_id")),
    _rule("WW-008", "Invalid or zero diameter", "wastewater", "error", True, "asset", "A wastewater line has a non-positive or nonnumeric diameter.", "Confirm diameter and unit.", "The rule is unable to determine a result when diameter is absent.", WASTEWATER_LINE_CLASSES, ("diameter",)),
    _rule("WW-009", "Invalid material", "wastewater", "warning", False, "asset", "A wastewater line has an empty or explicitly unknown material code.", "Confirm the material code list.", "No code meaning is invented.", WASTEWATER_LINE_CLASSES, ("material",)),
    _rule("WW-010", "Suspicious slope", "wastewater", "warning", False, "asset", "A represented gravity-main slope is zero, negative, or implausibly large.", "Confirm slope convention, units, and flow direction.", "The rule does not infer authoritative flow from geometry.", ("gravity_main",), ("slope",)),
    _rule("WW-011", "Missing expected invert elevation", "wastewater", "warning", False, "asset", "A gravity main is missing an invert value expected by the represented schema.", "Confirm whether invert fields are operationally required.", "Missing schema fields are source limitations, not automatic asset defects.", ("gravity_main",), ("upstream_invert", "downstream_invert")),
    _rule("WW-012", "Upstream/downstream invert contradiction", "wastewater", "error", True, "asset", "Represented upstream and downstream invert values conflict with the stated downstream direction.", "Confirm invert units, datum, and flow-direction mapping.", "Digitized direction is not used as authoritative flow.", ("gravity_main",), ("upstream_invert", "downstream_invert")),
    _rule("WW-013", "Force main carries gravity-only attributes", "wastewater", "warning", False, "asset", "A force main contains populated gravity-only slope or invert attributes.", "Confirm pressure-versus-gravity classification and source schema.", "Populated fields may be legacy metadata.", ("force_main",), ("slope", "upstream_invert", "downstream_invert")),
    _rule("WW-014", "Gravity main attached to pressure equipment", "wastewater", "error", True, "relationship", "A gravity main is directly related to pressure-only equipment.", "Review the transition and missing lift-station or wet-well context.", "A valid modeled transition may require an intermediate asset.", ("gravity_main",)),
    _rule("WW-015", "Lateral lacks receiving main", "wastewater", "error", True, "asset", "A service lateral has no represented receiving main.", "Confirm the receiving-main relationship.", "Source coverage may omit private or external connections.", ("service_lateral",)),
    _rule("WW-016", "Disconnected manhole", "wastewater", "error", True, "asset", "A manhole has no explicit relationship to a wastewater main.", "Confirm network relationships without snapping geometry.", "Inspection-only structure layers may omit connectivity.", ("manhole",)),
    _rule("WW-017", "Lift station lacks downstream force main", "wastewater", "error", True, "asset", "A lift station has no represented downstream force-main relationship.", "Confirm downstream pressure-network evidence.", "A missing force-main layer may explain this finding.", ("lift_station",)),
    _rule("WW-018", "Active asset connected only to retired assets", "wastewater", "error", True, "asset", "An active wastewater asset has relationships only to retired or abandoned assets.", "Review lifecycle and connectivity evidence.", "Historical associations can be legitimate."),
    _rule("WW-019", "Invalid basin or system reference", "wastewater", "warning", False, "asset", "A basin or system identifier does not resolve to represented context.", "Confirm basin and system membership.", "A missing basin layer may explain this finding.", (), ("basin_id", "wastewater_system_id")),
    _rule("WW-020", "Missing owner or jurisdiction", "wastewater", "warning", False, "asset", "Owner and jurisdiction evidence are unavailable.", "Confirm ownership or jurisdiction before operational use.", "Ownership is not inferred from geography alone."),
)


def rule_profile(vertical: str) -> list[dict[str, Any]]:
    if vertical not in PROFILES:
        raise ValueError("Unsupported utility vertical.")
    specific = {
        "electric_distribution": ELECTRIC_RULES,
        "telecom_fiber": TELECOM_RULES,
        "water": WATER_RULES,
        "wastewater": WASTEWATER_RULES,
    }[vertical]
    return [dict(rule) for rule in (*SHARED_RULES, *specific)]


def rule_availability(rule: dict[str, Any], graph: dict[str, Any]) -> tuple[bool, str]:
    classes = set(rule.get("applicable_asset_classes", []))
    assets = [
        asset for asset in graph["selected"]
        if not classes or asset.get("asset_class") in classes
    ]
    if classes and not assets:
        return False, "Unable to determine: no applicable canonical assets are represented."
    fields = set(rule.get("required_any_fields", []))
    if fields and not any(fields & set((asset.get("canonical_attributes_json") or {})) for asset in assets):
        return False, f"Unable to determine: required evidence is unavailable ({', '.join(sorted(fields))})."
    return True, ""


def graph_fingerprint(
    vertical: str,
    assets: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> tuple[str, str, str]:
    asset_values = sorted(
        (
            row["asset_id"], row.get("asset_class"), row.get("asset_subtype"),
            row.get("lifecycle_status"), row.get("operational_status"),
            row.get("source_asset_identifier"), row.get("canonical_attributes_json", {}),
        )
        for row in assets
    )
    relationship_values = sorted(
        (
            row["relationship_id"], row.get("from_asset_id"), row.get("to_asset_id"),
            row.get("relationship_type"), row.get("direction"), row.get("confidence"),
            bool(row.get("provisional")), row.get("source"),
        )
        for row in relationships
    )
    asset_checksum = stable_fingerprint(asset_values)
    relationship_checksum = stable_fingerprint(relationship_values)
    return (
        stable_fingerprint(vertical, asset_checksum, relationship_checksum, MODEL_VERSION, RULE_VERSION, PROFILES[vertical]),
        asset_checksum,
        relationship_checksum,
    )


def build_graph(
    vertical: str,
    selected_assets: list[dict[str, Any]],
    all_assets: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = {row["asset_id"]: row for row in all_assets}
    selected_ids = {row["asset_id"] for row in selected_assets}
    adjacency: dict[str, set[str]] = defaultdict(set)
    edge_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for relationship in relationships:
        left, right = relationship.get("from_asset_id"), relationship.get("to_asset_id")
        if left in selected_ids:
            edge_by_asset[left].append(relationship)
        if right in selected_ids and right != left:
            edge_by_asset[right].append(relationship)
        if left in selected_ids and right in selected_ids:
            adjacency[left].add(right)
            adjacency[right].add(left)
    return {
        "vertical": vertical,
        "nodes": nodes,
        "selected": selected_assets,
        "selected_ids": selected_ids,
        "relationships": relationships,
        "adjacency": adjacency,
        "edge_by_asset": edge_by_asset,
    }


def evaluate_rule(rule: dict[str, Any], graph: dict[str, Any]) -> list[dict[str, Any]]:
    code = rule["rule_code"]
    assets = graph["selected"]
    nodes = graph["nodes"]
    relationships = graph["relationships"]
    adjacency = graph["adjacency"]
    edge_by_asset = graph["edge_by_asset"]
    candidates: list[dict[str, Any]] = []

    def add(
        asset: dict[str, Any] | None,
        detail: str,
        *,
        related: dict[str, Any] | None = None,
        relationship: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        asset_id = asset.get("asset_id", "") if asset else ""
        related_id = related.get("asset_id", "") if related else ""
        relationship_id = relationship.get("relationship_id", "") if relationship else ""
        signature = stable_fingerprint(code, asset_id, related_id, relationship_id, detail, evidence or {})
        candidates.append({
            "finding_id": stable_id("finding", graph["vertical"], code, asset_id, related_id, relationship_id, signature),
            "finding_fingerprint": stable_fingerprint(graph["vertical"], code, asset_id, related_id, relationship_id, signature, RULE_VERSION),
            "asset_id": asset_id,
            "related_asset_id": related_id,
            "relationship_id": relationship_id,
            "asset_class": asset.get("asset_class", "") if asset else "",
            "short_title": rule["name"],
            "explanation": detail,
            "recommended_action": rule["recommended_action"],
            "evidence_json": evidence or {},
        })

    if code == "SHARED-001":
        for rel in relationships:
            for endpoint in ("from_asset_id", "to_asset_id"):
                if rel.get(endpoint) not in nodes:
                    add(nodes.get(rel.get("from_asset_id")) or nodes.get(rel.get("to_asset_id")), f"Relationship {rel['relationship_id']} has a missing {endpoint.replace('_', ' ')}.", relationship=rel, evidence={"missing_endpoint": endpoint})
    elif code == "SHARED-002":
        for rel in relationships:
            if rel.get("from_asset_id") == rel.get("to_asset_id"):
                add(nodes.get(rel.get("from_asset_id")), "The relationship points from an asset back to itself.", relationship=rel)
    elif code == "SHARED-003":
        seen: dict[tuple[str, str, str], dict[str, Any]] = {}
        for rel in relationships:
            key = (str(rel.get("from_asset_id")), str(rel.get("to_asset_id")), str(rel.get("relationship_type")))
            if key in seen:
                add(nodes.get(rel.get("from_asset_id")), "A duplicate directed relationship candidate was found.", related=nodes.get(rel.get("to_asset_id")), relationship=rel, evidence={"duplicate_of": seen[key]["relationship_id"]})
            else:
                seen[key] = rel
    elif code == "SHARED-004":
        for rel in relationships:
            if rel.get("provisional"):
                add(nodes.get(rel.get("from_asset_id")), "This stored relationship is explicitly provisional.", related=nodes.get(rel.get("to_asset_id")), relationship=rel, evidence={"source": rel.get("source"), "confidence": rel.get("confidence")})
    elif code in {"SHARED-005", "ELEC-014"}:
        for rel in relationships:
            left, right = nodes.get(rel.get("from_asset_id")), nodes.get(rel.get("to_asset_id"))
            if left and right and {_active_or_retired(left), _active_or_retired(right)} == {"active", "retired"}:
                add(left, "The relationship joins active and retired lifecycle contexts.", related=right, relationship=rel, evidence={"from_lifecycle": left.get("lifecycle_status"), "to_lifecycle": right.get("lifecycle_status")})
    elif code == "SHARED-006":
        for rel in relationships:
            left, right = nodes.get(rel.get("from_asset_id")), nodes.get(rel.get("to_asset_id"))
            if left and right and left.get("utility_vertical") != right.get("utility_vertical"):
                add(left, "Relationship endpoints belong to different utility verticals.", related=right, relationship=rel)
    elif code == "SHARED-007":
        for asset in assets:
            if not str(asset.get("canonical_name") or "").strip() and not str(asset.get("source_asset_identifier") or "").strip():
                add(asset, "The asset has no safe operational identifier.")
    elif code == "SHARED-008":
        for asset in assets:
            if asset.get("lifecycle_status") == "unknown" or asset.get("lifecycle_status") not in LIFECYCLE_STATES:
                add(asset, f"Lifecycle state is {asset.get('lifecycle_status') or 'missing'}.")
    elif code == "ELEC-001":
        for asset in _class_assets(assets, _electric_conductors()):
            if not edge_by_asset.get(asset["asset_id"]):
                add(asset, "The conductor has no explicit canonical relationship.")
    elif code == "ELEC-002":
        for asset in _class_assets(assets, _electric_conductors()):
            degree = len(adjacency.get(asset["asset_id"], set()))
            if degree < 2:
                add(asset, f"The conductor has {degree} explicit connected asset(s); two endpoints are expected.", evidence={"relationship_degree": degree})
    elif code == "ELEC-003":
        for asset in _class_assets(assets, {"transformer"}):
            if not _attr(asset, "feeder_id"):
                add(asset, "The transformer feeder identifier is missing.")
    elif code == "ELEC-004":
        primary = _electric_conductors() | {"feeder"}
        for asset in _class_assets(assets, {"transformer"}):
            related = [nodes.get(item) for item in adjacency.get(asset["asset_id"], set())]
            if not any(item and item.get("asset_class") in primary for item in related):
                add(asset, "No explicit primary conductor or feeder relationship reaches this transformer.")
    elif code == "ELEC-005":
        allowed = {"A", "B", "C", "AB", "AC", "BC", "ABC", "N", ""}
        for asset in assets:
            phase = str(_attr(asset, "phase") or "").upper()
            if phase not in allowed:
                add(asset, f"Phase value {phase!r} is outside the V1 allowlist.", evidence={"phase": phase})
    elif code == "ELEC-006":
        for asset in assets:
            nominal, operating = _number(_attr(asset, "nominal_voltage")), _number(_attr(asset, "operating_voltage"))
            if nominal is not None and operating is not None and abs(nominal - operating) > 0.001:
                add(asset, "Nominal and operating voltage values differ.", evidence={"nominal_voltage": nominal, "operating_voltage": operating})
    elif code == "ELEC-007":
        for asset in _class_assets(assets, {"underground_conductor"}):
            if not _attr(asset, "conduit_id") and not _related_to_class(asset, edge_by_asset, nodes, {"conduit"}, "routed_through"):
                add(asset, "The underground conductor has no conduit evidence.")
    elif code == "ELEC-008":
        for asset in _class_assets(assets, {"feeder_breaker", "switch", "fuse", "recloser", "transformer"}):
            if not _attr(asset, "structure_id") and not _related_to_class(asset, edge_by_asset, nodes, {"pole", "electric_structure"}, "mounted_on"):
                add(asset, "The equipment has no structure association.")
    elif code in {"ELEC-009", "ELEC-010"}:
        field = "feeder_id" if code == "ELEC-009" else "circuit_id"
        for rel in relationships:
            left, right = nodes.get(rel.get("from_asset_id")), nodes.get(rel.get("to_asset_id"))
            if not left or not right or rel.get("relationship_type") not in _electric_membership_relationships():
                continue
            if left.get("asset_class") not in _electric_membership_assets() or right.get("asset_class") not in _electric_membership_assets():
                continue
            if _active_or_retired(left) == "retired" or _active_or_retired(right) == "retired":
                continue
            left_value, right_value = _attr(left, field), _attr(right, field)
            if left_value and right_value and left_value != right_value:
                add(left, f"Related assets have different {field.replace('_', ' ')} values.", related=right, relationship=rel, evidence={f"from_{field}": left_value, f"to_{field}": right_value})
    elif code == "ELEC-011":
        for rel in relationships:
            if rel.get("direction") not in {"forward", "reverse", "bidirectional", "undirected"}:
                add(nodes.get(rel.get("from_asset_id")), "The relationship direction is outside the V1 allowlist.", related=nodes.get(rel.get("to_asset_id")), relationship=rel, evidence={"direction": rel.get("direction")})
    elif code == "ELEC-012":
        for asset in assets:
            if asset.get("operational_status") == "normally_open" or _attr(asset, "normally_open") is True:
                add(asset, "The device is marked normally open; future traces must honor this state.")
    elif code == "ELEC-013":
        for asset in _class_assets(assets, {"feeder_breaker", "fuse", "recloser"}):
            if not _attr(asset, "protective_device_type"):
                add(asset, "The protective device type is missing.")
    elif code == "ELEC-015":
        for asset in assets:
            placement = str(_attr(asset, "placement_type") or "")
            contradiction = (asset.get("asset_class") == "overhead_conductor" and placement == "underground") or (asset.get("asset_class") == "underground_conductor" and placement == "overhead")
            if contradiction:
                add(asset, f"Asset class conflicts with placement type {placement!r}.")
    elif code == "TEL-001":
        for asset in _class_assets(assets, {"fiber_cable"}):
            missing = [field for field in ("from_structure_id", "to_structure_id") if not _attr(asset, field)]
            if missing:
                add(asset, f"Fiber cable is missing {', '.join(missing)}.", evidence={"missing_fields": missing})
    elif code == "TEL-002":
        valid = {"network_hub", "fiber_cabinet", "pole", "handhole", "manhole", "splice_closure", "splitter", "terminal", "telecom_structure"}
        for rel in relationships:
            left, right = nodes.get(rel.get("from_asset_id")), nodes.get(rel.get("to_asset_id"))
            if left and right and "fiber_cable" in {left.get("asset_class"), right.get("asset_class")}:
                other = right if left.get("asset_class") == "fiber_cable" else left
                if other.get("asset_class") not in valid:
                    add(left, f"Fiber cable relationship reaches incompatible class {other.get('asset_class')}.", related=right, relationship=rel)
    elif code == "TEL-003":
        cables = _class_assets(assets, {"fiber_cable"})
        for index, left in enumerate(cables):
            for right in cables[index + 1:]:
                if _attr(left, "route_id") and _attr(left, "route_id") == _attr(right, "route_id") and _ranges_overlap(left, right):
                    add(left, "Assigned strand ranges overlap on the same route.", related=right, evidence={"route_id": _attr(left, "route_id"), "left_range": [_attr(left, "strand_start"), _attr(left, "strand_end")], "right_range": [_attr(right, "strand_start"), _attr(right, "strand_end")]})
    elif code in {"TEL-004", "TEL-005", "TEL-015"}:
        classes = {"splitter"} if code == "TEL-015" else {"fiber_cable", "fiber_cabinet", "splitter", "terminal"}
        for asset in _class_assets(assets, classes):
            total, used, reserved, available = (_number(_attr(asset, key)) for key in ("total_capacity", "used_capacity", "reserved_capacity", "available_capacity"))
            if total is None or used is None or reserved is None:
                continue
            if code in {"TEL-004", "TEL-015"} and used + reserved > total:
                add(asset, "Used and reserved capacity exceed total capacity.", evidence={"total": total, "used": used, "reserved": reserved})
            if code == "TEL-005" and available is not None and abs(available - (total - used - reserved)) > 0.001:
                add(asset, "Available capacity does not reconcile.", evidence={"total": total, "used": used, "reserved": reserved, "available": available})
    elif code == "TEL-006":
        for asset in _class_assets(assets, {"fiber_cable"}):
            count, start, end = (_number(_attr(asset, key)) for key in ("fiber_count", "strand_start", "strand_end"))
            if count is not None and start is not None and end is not None and (start < 1 or end < start or end > count):
                add(asset, "Strand range is invalid for the cable fiber count.", evidence={"fiber_count": count, "strand_start": start, "strand_end": end})
    elif code == "TEL-007":
        for asset in _class_assets(assets, {"splice_closure"}):
            if not edge_by_asset.get(asset["asset_id"]):
                add(asset, "The splice closure has no explicit network relationship.")
    elif code == "TEL-008":
        for asset in _class_assets(assets, {"terminal"}):
            if not edge_by_asset.get(asset["asset_id"]):
                add(asset, "The terminal has no explicit serving relationship.")
    elif code == "TEL-009":
        for asset in _class_assets(assets, {"fiber_cabinet"}):
            if not _attr(asset, "route_id") and not _related_to_class(asset, edge_by_asset, nodes, {"fiber_route"}, "belongs_to_route"):
                add(asset, "The cabinet has no route association.")
    elif code == "TEL-010":
        for asset in _class_assets(assets, {"fiber_cable"}):
            if _attr(asset, "placement_type") == "underground" and not _attr(asset, "conduit_id") and not _related_to_class(asset, edge_by_asset, nodes, {"conduit"}, "routed_through"):
                add(asset, "The underground cable has no conduit evidence.")
    elif code == "TEL-011":
        for asset in _class_assets(assets, {"fiber_cable"}):
            if _attr(asset, "placement_type") == "aerial" and not _related_to_class(asset, edge_by_asset, nodes, {"pole"}, "mounted_on"):
                add(asset, "The aerial cable has no support relationship.")
    elif code == "TEL-012":
        for asset in _class_assets(assets, {"proposed_construction_segment"}):
            degree = len(adjacency.get(asset["asset_id"], set()))
            if degree < 2 or not _attr(asset, "from_structure_id") or not _attr(asset, "to_structure_id"):
                add(asset, "The proposed construction segment has incomplete endpoint evidence.", evidence={"relationship_degree": degree})
    elif code == "TEL-013":
        for rel in relationships:
            left, right = nodes.get(rel.get("from_asset_id")), nodes.get(rel.get("to_asset_id"))
            pair = {left.get("asset_class") if left else "", right.get("asset_class") if right else ""}
            if left and right and pair == {"fiber_cable", "terminal"}:
                cable = left if left.get("asset_class") == "fiber_cable" else right
                terminal = right if cable is left else left
                if _active_or_retired(cable) == "retired" and _active_or_retired(terminal) == "active":
                    add(cable, "A retired cable remains related to an active terminal.", related=terminal, relationship=rel)
    elif code == "TEL-014":
        for rel in relationships:
            left, right = nodes.get(rel.get("from_asset_id")), nodes.get(rel.get("to_asset_id"))
            if rel.get("provisional") and left and right and "splice_closure" in {left.get("asset_class"), right.get("asset_class")}:
                add(left, "The splice closure relationship remains provisional.", related=right, relationship=rel)
    elif code == "TEL-016":
        for asset in assets:
            placement = str(_attr(asset, "placement_type") or "")
            contradiction = (asset.get("asset_class") == "pole" and placement == "underground") or (asset.get("asset_class") == "conduit" and placement == "aerial")
            if contradiction:
                add(asset, f"Asset class conflicts with placement type {placement!r}.")
    elif code in {"WATER-001", "WW-001"}:
        for asset in assets:
            if not str(asset.get("source_asset_identifier") or "").strip():
                add(asset, "The source asset identifier is blank.")
    elif code in {"WATER-002", "WW-002"}:
        seen_identifiers: dict[str, dict[str, Any]] = {}
        for asset in assets:
            identifier = str(asset.get("source_asset_identifier") or "").strip().casefold()
            if not identifier:
                continue
            if identifier in seen_identifiers:
                add(asset, "The normalized source asset identifier is shared by another asset.", related=seen_identifiers[identifier], evidence={"normalized_identifier": identifier})
            else:
                seen_identifiers[identifier] = asset
    elif code in {"WATER-003", "WW-003"}:
        line_classes = set(WATER_LINE_CLASSES if code.startswith("WATER") else WASTEWATER_LINE_CLASSES)
        area_classes = {
            "pressure_zone", "service_area", "treatment_area", "water_system_boundary",
            "sewer_basin", "collection_area", "treatment_service_area",
            "overflow_area", "wastewater_system_boundary", "easement", "facility_site",
        }
        for asset in assets:
            geometry = str(asset.get("geometry_type") or "").lower()
            expected = "polyline" if asset.get("asset_class") in line_classes else "polygon" if asset.get("asset_class") in area_classes else "point"
            if geometry != expected:
                add(asset, f"Geometry type {geometry or 'missing'} is incompatible with expected {expected}.", evidence={"geometry_type": geometry, "expected": expected})
    elif code in {"WATER-004", "WW-004"}:
        for asset in assets:
            geometry = asset.get("geometry_summary_json") or {}
            spatial_reference = geometry.get("spatial_reference") or geometry.get("spatial_reference_name")
            if not spatial_reference or str(spatial_reference).lower() == "unknown":
                add(asset, "Spatial-reference evidence is unavailable.")
    elif code in {"WATER-005", "WW-005"}:
        for asset in assets:
            geometry = asset.get("geometry_summary_json") or {}
            if geometry.get("suspicious_extent") is True or geometry.get("extent_valid") is False:
                add(asset, "Stored geometry metadata marks the extent for coordinate review.")
    elif code in {"WATER-006", "WW-008"}:
        classes = set(WATER_LINE_CLASSES if code.startswith("WATER") else WASTEWATER_LINE_CLASSES)
        for asset in _class_assets(assets, classes):
            value = _number(_attr(asset, "diameter"))
            if value is None or value <= 0:
                add(asset, "Diameter is nonnumeric, zero, or negative.", evidence={"diameter": _attr(asset, "diameter"), "diameter_unit": _attr(asset, "diameter_unit")})
    elif code in {"WATER-007", "WW-009"}:
        classes = set(WATER_LINE_CLASSES if code.startswith("WATER") else WASTEWATER_LINE_CLASSES)
        for asset in _class_assets(assets, classes):
            value = str(_attr(asset, "material") or "").strip().casefold()
            if value in {"", "unknown", "n/a", "na", "unsupported"}:
                add(asset, "Material is blank or explicitly unknown.", evidence={"material": value})
    elif code == "WATER-008":
        for asset in assets:
            if asset.get("lifecycle_status") == "unknown" or asset.get("lifecycle_status") not in LIFECYCLE_STATES:
                add(asset, f"Lifecycle state is {asset.get('lifecycle_status') or 'missing'}.")
    elif code == "WATER-009":
        for asset in _class_assets(assets, set(WATER_LINE_CLASSES) - {"service_line", "hydrant_lateral"}):
            degree = len(adjacency.get(asset["asset_id"], set()))
            if degree < 2:
                add(asset, f"The represented main has {degree} explicit connected asset(s).", evidence={"relationship_degree": degree})
    elif code == "WATER-010":
        for asset in _class_assets(assets, {"service_line"}):
            if not edge_by_asset.get(asset["asset_id"]):
                add(asset, "The service line has no explicit canonical relationship.")
    elif code == "WATER-011":
        for asset in _class_assets(assets, {"hydrant"}):
            if not _related_to_class(asset, edge_by_asset, nodes, set(WATER_LINE_CLASSES), ""):
                add(asset, "The hydrant has no represented water-main or hydrant-lateral relationship.")
    elif code == "WATER-012":
        valves = {"valve", "isolation_valve", "control_valve", "pressure_reducing_valve", "air_release_valve"}
        for asset in _class_assets(assets, valves):
            if not _related_to_class(asset, edge_by_asset, nodes, set(WATER_LINE_CLASSES), ""):
                add(asset, "The valve has no represented water-main relationship.")
    elif code in {"WATER-013", "WATER-015", "WW-019"}:
        fields = {
            "WATER-013": ("pressure_zone_id", {"pressure_zone"}),
            "WATER-015": ("facility_id", {"pump_station", "storage_tank", "elevated_tank", "reservoir", "treatment_facility", "well"}),
            "WW-019": ("basin_id", {"sewer_basin", "collection_area", "wastewater_system_boundary"}),
        }
        field, target_classes = fields[code]
        represented = {
            str(value) for target in _class_assets(assets, target_classes)
            for value in (target.get("asset_id"), target.get("source_asset_identifier"), _attr(target, field))
            if value
        }
        for asset in assets:
            value = str(_attr(asset, field) or "")
            if value and value not in represented:
                add(asset, f"The represented {field.replace('_', ' ')} does not resolve to available context.", evidence={field: value})
        if code == "WW-019":
            systems = {
                str(_attr(asset, "wastewater_system_id")) for asset in assets
                if _attr(asset, "wastewater_system_id")
            }
            if len(systems) > 1:
                add(assets[0], "Multiple wastewater-system identities are represented without an explicit boundary relationship.", evidence={"wastewater_system_ids": sorted(systems)})
    elif code in {"WATER-014", "WW-020"}:
        for asset in assets:
            if not str(asset.get("owner_candidate") or _attr(asset, "owner") or "").strip() and not str(asset.get("jurisdiction") or _attr(asset, "jurisdiction") or "").strip():
                add(asset, "Owner and jurisdiction evidence are unavailable.")
    elif code in {"WATER-016", "WW-018"}:
        for asset in assets:
            related = [nodes.get(item) for item in adjacency.get(asset["asset_id"], set())]
            if _active_or_retired(asset) == "active" and related and all(item and _active_or_retired(item) == "retired" for item in related):
                add(asset, "Every represented connected asset is retired, removed, or abandoned.", evidence={"related_asset_count": len(related)})
    elif code == "WATER-017":
        for asset in _class_assets(assets, {"service_line"}):
            if not _related_to_class(asset, edge_by_asset, nodes, {"meter", "meter_vault", "service_point"}, ""):
                add(asset, "The service line has no represented meter or service endpoint.")
    elif code == "WATER-018":
        for relationship in relationships:
            left, right = nodes.get(relationship.get("from_asset_id")), nodes.get(relationship.get("to_asset_id"))
            left_system, right_system = _attr(left, "water_system_id"), _attr(right, "water_system_id")
            if left and right and left_system and right_system and left_system != right_system:
                add(left, "Connected water assets carry different water-system identifiers.", related=right, relationship=relationship, evidence={"from_system": left_system, "to_system": right_system})
    elif code == "WW-006":
        structures = {"manhole", "cleanout", "junction", "lift_station", "wet_well"}
        for asset in _class_assets(assets, {"gravity_main"}):
            attrs = asset.get("canonical_attributes_json") or {}
            identifiers = [attrs.get(key) for key in ("upstream_structure_id", "downstream_structure_id", "from_node_id", "to_node_id")]
            related_count = sum(1 for item in adjacency.get(asset["asset_id"], set()) if nodes.get(item, {}).get("asset_class") in structures)
            if len({str(item) for item in identifiers if item}) < 2 and related_count < 2:
                add(asset, "The gravity main lacks two represented endpoint structures.", evidence={"related_structure_count": related_count})
    elif code == "WW-007":
        for asset in _class_assets(assets, {"gravity_main"}):
            attrs = asset.get("canonical_attributes_json") or {}
            upstream = attrs.get("upstream_structure_id") or attrs.get("from_node_id")
            downstream = attrs.get("downstream_structure_id") or attrs.get("to_node_id")
            if upstream and downstream and str(upstream) == str(downstream):
                add(asset, "The upstream and downstream structure identifiers are identical.", evidence={"endpoint_id": upstream})
    elif code == "WW-010":
        for asset in _class_assets(assets, {"gravity_main"}):
            slope = _number(_attr(asset, "slope"))
            if slope is not None and (slope <= 0 or abs(slope) > 1):
                add(asset, "Slope is zero, negative, or outside the conservative V1 range.", evidence={"slope": slope})
    elif code == "WW-011":
        for asset in _class_assets(assets, {"gravity_main"}):
            missing = [field for field in ("upstream_invert", "downstream_invert") if _attr(asset, field) in (None, "")]
            if missing:
                add(asset, f"Expected invert evidence is missing: {', '.join(missing)}.", evidence={"missing_fields": missing})
    elif code == "WW-012":
        for asset in _class_assets(assets, {"gravity_main"}):
            upstream, downstream = _number(_attr(asset, "upstream_invert")), _number(_attr(asset, "downstream_invert"))
            if upstream is not None and downstream is not None and upstream <= downstream:
                add(asset, "Upstream invert is not above downstream invert under the explicit mapped direction.", evidence={"upstream_invert": upstream, "downstream_invert": downstream})
    elif code == "WW-013":
        for asset in _class_assets(assets, {"force_main"}):
            populated = {field: _attr(asset, field) for field in ("slope", "upstream_invert", "downstream_invert") if _attr(asset, field) not in (None, "")}
            if populated:
                add(asset, "The force main carries populated gravity-only attributes.", evidence=populated)
    elif code == "WW-014":
        pressure_only = {"lift_station", "pump", "air_release_valve"}
        for relationship in relationships:
            left, right = nodes.get(relationship.get("from_asset_id")), nodes.get(relationship.get("to_asset_id"))
            if left and right and {left.get("asset_class"), right.get("asset_class")} & {"gravity_main"} and {left.get("asset_class"), right.get("asset_class")} & pressure_only:
                add(left if left.get("asset_class") == "gravity_main" else right, "A gravity main is directly related to pressure-only equipment.", related=right if left.get("asset_class") == "gravity_main" else left, relationship=relationship)
    elif code == "WW-015":
        receiving = {"gravity_main", "force_main", "pressure_sewer", "interceptor", "trunk_sewer"}
        for asset in _class_assets(assets, {"service_lateral"}):
            if not _related_to_class(asset, edge_by_asset, nodes, receiving, ""):
                add(asset, "The service lateral has no represented receiving-main relationship.")
    elif code == "WW-016":
        for asset in _class_assets(assets, {"manhole"}):
            if not _related_to_class(asset, edge_by_asset, nodes, set(WASTEWATER_LINE_CLASSES), ""):
                add(asset, "The manhole has no represented wastewater-main relationship.")
    elif code == "WW-017":
        for asset in _class_assets(assets, {"lift_station"}):
            if not _related_to_class(asset, edge_by_asset, nodes, {"force_main", "pressure_sewer"}, ""):
                add(asset, "The lift station has no represented downstream force-main relationship.")

    unique: dict[str, dict[str, Any]] = {}
    for finding in candidates:
        unique.setdefault(finding["finding_fingerprint"], finding)
    return list(unique.values())


def _attr(asset: dict[str, Any] | None, name: str) -> Any:
    return (asset or {}).get("canonical_attributes_json", {}).get(name)


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _class_assets(assets: list[dict[str, Any]], classes: set[str]) -> list[dict[str, Any]]:
    return [asset for asset in assets if asset.get("asset_class") in classes]


def _electric_conductors() -> set[str]:
    return {"overhead_conductor", "underground_conductor", "secondary_conductor"}


def _electric_membership_assets() -> set[str]:
    return {
        "substation", "feeder", "feeder_breaker", "switch", "fuse", "recloser",
        "transformer", "overhead_conductor", "underground_conductor",
        "secondary_conductor", "service_point", "junction",
    }


def _electric_membership_relationships() -> set[str]:
    return {
        "connects_to", "upstream_of", "downstream_of", "protected_by", "feeds",
        "belongs_to_feeder", "belongs_to_circuit",
    }


def _active_or_retired(asset: dict[str, Any]) -> str:
    return "retired" if asset.get("lifecycle_status") in {"retired", "removed", "abandoned"} else "active"


def _related_to_class(
    asset: dict[str, Any],
    edge_by_asset: dict[str, list[dict[str, Any]]],
    nodes: dict[str, dict[str, Any]],
    classes: set[str],
    relationship_type: str,
) -> bool:
    for relationship in edge_by_asset.get(asset["asset_id"], []):
        if relationship_type and relationship.get("relationship_type") != relationship_type:
            continue
        other_id = relationship["to_asset_id"] if relationship["from_asset_id"] == asset["asset_id"] else relationship["from_asset_id"]
        if nodes.get(other_id, {}).get("asset_class") in classes:
            return True
    return False


def _ranges_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_start, left_end = _number(_attr(left, "strand_start")), _number(_attr(left, "strand_end"))
    right_start, right_end = _number(_attr(right, "strand_start")), _number(_attr(right, "strand_end"))
    return None not in (left_start, left_end, right_start, right_end) and max(left_start, right_start) <= min(left_end, right_end)
