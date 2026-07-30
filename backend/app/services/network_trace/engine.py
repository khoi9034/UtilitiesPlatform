from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from .profiles import TRACE_PROFILES, relationship_category

_COMPLETE_REASONS = {"target_reached", "source_reached", "terminal_reached"}
_EXHAUSTIVE_TRACES = {
    "ELEC-TRACE-004", "ELEC-TRACE-006",
    "TEL-TRACE-003", "TEL-TRACE-004", "TEL-TRACE-006", "TEL-TRACE-008",
    "WATER-TRACE-001", "WATER-TRACE-004", "WATER-TRACE-005", "WATER-TRACE-006",
    "WW-TRACE-002", "WW-TRACE-006", "WW-TRACE-007",
}
_SOURCE_CLASSES = {
    "electric_distribution": {"substation", "feeder_breaker", "feeder"},
    "telecom_fiber": {"network_hub", "central_office", "fiber_cabinet"},
    "water": {"treatment_facility", "well", "reservoir", "storage_tank", "elevated_tank"},
    "wastewater": set(),
}
_OPEN_STATES = {"open", "normally_open"}
_INACTIVE_OPERATIONAL = {"inactive", "de_energized", "unavailable", "retired", "not_operating"}


@dataclass
class PathState:
    asset_ids: list[str]
    relationship_ids: list[str] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    blockers: list[dict[str, str]] = field(default_factory=list)
    qa_issue_group_ids: list[str] = field(default_factory=list)
    provisional: bool = False
    ambiguous: bool = False
    stopping_reason: str = ""

    def branch(self, asset_id: str, relationship_id: str) -> "PathState":
        return PathState(
            asset_ids=[*self.asset_ids, asset_id],
            relationship_ids=[*self.relationship_ids, relationship_id],
            warnings=[*self.warnings],
            blockers=[*self.blockers],
            qa_issue_group_ids=[*self.qa_issue_group_ids],
            provisional=self.provisional,
            ambiguous=self.ambiguous,
        )


def trace_graph(
    request: dict[str, Any],
    definition: dict[str, Any],
    graph: dict[str, Any],
    issue_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = graph["nodes"]
    start_id = request["start_asset_id"]
    start = nodes[start_id]
    groups_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups_by_relationship: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in issue_groups:
        for asset_id in group.get("affected_asset_ids", []):
            groups_by_asset[asset_id].append(group)
        for relationship_id in group.get("affected_relationship_ids", []):
            groups_by_relationship[relationship_id].append(group)

    events: list[dict[str, str]] = []
    initial = PathState([start_id])
    _apply_qa(initial, groups_by_asset[start_id], request, events, start_id, "")
    initial_stop = _asset_stop(start, request, definition, is_start=True)
    if initial_stop:
        _stop(initial, initial_stop, _stop_message(initial_stop, start), start_id, "", events)

    queue: deque[PathState] = deque()
    terminal_paths: list[PathState] = []
    if initial.blockers or initial.stopping_reason:
        terminal_paths.append(initial)
    else:
        queue.append(initial)

    expanded: set[str] = set()
    excluded_assets: set[str] = set()
    excluded_relationships: set[str] = set()
    max_paths = 25
    truncated = False

    while queue and len(terminal_paths) < max_paths:
        path = queue.popleft()
        current_id = path.asset_ids[-1]
        current = nodes[current_id]
        depth = len(path.relationship_ids)
        if depth >= request["max_depth"]:
            _stop(path, "maximum_depth", "The configured maximum trace depth was reached.", current_id, "", events)
            terminal_paths.append(path)
            continue
        if len(expanded) >= request["max_assets"] and current_id not in expanded:
            _stop(path, "maximum_assets", "The configured maximum visited-asset count was reached.", current_id, "", events)
            terminal_paths.append(path)
            continue
        expanded.add(current_id)

        terminal_reason = _terminal_reason(current, current_id, request, definition, depth)
        if terminal_reason:
            path.stopping_reason = terminal_reason
            terminal_paths.append(path)
            events.append(_event("terminal_reached", _stop_message(terminal_reason, current), current_id))
            continue

        candidates = _candidates(current_id, graph["relationships"], request)
        traversable: list[tuple[dict[str, Any], str]] = []
        confirmed_exists = any(
            not bool(rel.get("provisional"))
            and _category_allowed(relationship_category(str(rel.get("relationship_type", ""))), request, definition)
            and next_id in nodes
            and nodes[next_id].get("utility_vertical") == request["utility_vertical"]
            and nodes[next_id].get("asset_class") in TRACE_PROFILES[request["utility_vertical"]]["flow_classes"]
            for rel, next_id in candidates
        )
        cycle_only = bool(candidates)

        for relationship, next_id in candidates:
            relationship_id = str(relationship.get("relationship_id", ""))
            category = relationship_category(str(relationship.get("relationship_type", "")))
            if not _category_allowed(category, request, definition):
                excluded_relationships.add(relationship_id)
                events.append(_event("relationship_excluded", f"{category.replace('_', ' ')} is context, not operational continuity.", current_id, relationship_id))
                continue
            if not next_id or next_id not in nodes:
                stopped = path.branch(next_id or "missing_asset", relationship_id)
                _stop(stopped, "missing_endpoint", "A relationship endpoint is absent from the canonical registry.", current_id, relationship_id, events)
                terminal_paths.append(stopped)
                continue
            next_asset = nodes[next_id]
            if next_asset.get("utility_vertical") != request["utility_vertical"]:
                stopped = path.branch(next_id, relationship_id)
                _stop(stopped, "incompatible_vertical", "Cross-vertical relationships are not traversable.", next_id, relationship_id, events)
                terminal_paths.append(stopped)
                continue
            if next_id in path.asset_ids:
                events.append(_event("cycle_detected", "A cycle candidate was skipped without repeating an asset.", current_id, relationship_id))
                continue
            cycle_only = False
            if next_asset.get("asset_class") not in TRACE_PROFILES[request["utility_vertical"]]["flow_classes"]:
                excluded_assets.add(next_id)
                events.append(_event("asset_excluded", "The connected asset class is not an operational node for this trace profile.", next_id, relationship_id))
                continue
            if relationship.get("provisional") and request["provisional_relationship_policy"] == "exclude":
                excluded_relationships.add(relationship_id)
                events.append(_event("provisional_excluded", "A provisional relationship was excluded by request policy.", current_id, relationship_id))
                continue
            if (
                relationship.get("provisional")
                and request["provisional_relationship_policy"] == "require_when_only_path"
                and confirmed_exists
            ):
                excluded_relationships.add(relationship_id)
                events.append(_event("provisional_excluded", "A confirmed alternative exists, so the provisional relationship was not used.", current_id, relationship_id))
                continue
            traversable.append((relationship, next_id))

        if len(traversable) > 1:
            events.append(_event("branch_detected", f"{len(traversable)} deterministic branch candidates were found.", current_id))

        if not traversable:
            if cycle_only:
                _stop(path, "cycle_detected", "Only already-visited cycle edges remained.", current_id, "", events, blocker=False)
            elif request["trace_type"] in _EXHAUSTIVE_TRACES and depth:
                path.stopping_reason = "terminal_reached"
                events.append(_event("terminal_reached", "The represented branch ended at its current evidence boundary.", current_id))
            else:
                reason = "missing_relationship" if not candidates else "no_traversable_edge"
                _stop(path, reason, _stop_message(reason, current), current_id, "", events, blocker=False)
            terminal_paths.append(path)
            continue

        for relationship, next_id in traversable:
            relationship_id = relationship["relationship_id"]
            next_asset = nodes[next_id]
            branch = path.branch(next_id, relationship_id)
            if relationship.get("provisional"):
                branch.provisional = True
                _warn(branch, "provisional_relationship", "The path uses provisional relationship evidence.", next_id, relationship_id, events)

            constraint = _asset_stop(next_asset, request, definition)
            transition = _transition_stop(current, next_asset, request)
            if transition and request["qa_policy"] == "diagnostic":
                _warn(branch, transition, _stop_message(transition, next_asset), next_id, relationship_id, events)
            elif transition:
                _stop(branch, transition, _stop_message(transition, next_asset), next_id, relationship_id, events)
            if constraint and not branch.blockers:
                _stop(branch, constraint, _stop_message(constraint, next_asset), next_id, relationship_id, events)

            _apply_qa(
                branch,
                [*groups_by_relationship[relationship_id], *groups_by_asset[next_id]],
                request,
                events,
                next_id,
                relationship_id,
            )
            if branch.blockers or branch.stopping_reason:
                terminal_paths.append(branch)
            else:
                queue.append(branch)

    if queue:
        truncated = True
        events.append(_event("paths_truncated", f"Trace results were limited to {max_paths} ranked paths."))

    if not terminal_paths:
        initial.stopping_reason = "no_traversable_edge"
        terminal_paths = [initial]
    ranked = _rank_paths(terminal_paths)[:max_paths]
    outcome = _outcome(ranked, request)
    confidence = _confidence(ranked, outcome, bool(issue_groups))
    return {
        "outcome": outcome,
        "confidence": confidence,
        "paths": [_path_result(path, nodes, index + 1) for index, path in enumerate(ranked)],
        "events": events,
        "assets_visited": len({asset_id for path in ranked for asset_id in path.asset_ids if asset_id in nodes}),
        "relationships_traversed": len({relationship_id for path in ranked for relationship_id in path.relationship_ids}),
        "paths_evaluated": len(ranked),
        "warnings_count": sum(len(path.warnings) for path in ranked),
        "blockers_count": sum(len(path.blockers) for path in ranked),
        "provisional_segments": len({
            relationship_id
            for path in ranked for relationship_id in path.relationship_ids
            if next((row for row in graph["relationships"] if row.get("relationship_id") == relationship_id and row.get("provisional")), None)
        }),
        "excluded_asset_ids": sorted(excluded_assets),
        "excluded_relationship_ids": sorted(excluded_relationships),
        "truncated": truncated,
    }


def _candidates(
    current_id: str,
    relationships: list[dict[str, Any]],
    request: dict[str, Any],
) -> list[tuple[dict[str, Any], str]]:
    upstream = request["direction"] in {"upstream", "toward_source"}
    downstream = request["direction"] in {"downstream", "toward_terminal"}
    bidirectional = request["direction"] == "bidirectional"
    rows: list[tuple[dict[str, Any], str]] = []
    for relationship in relationships:
        left = str(relationship.get("from_asset_id", ""))
        right = str(relationship.get("to_asset_id", ""))
        direction = str(relationship.get("direction", "forward"))
        if bidirectional:
            if current_id == left:
                rows.append((relationship, right))
            elif current_id == right:
                rows.append((relationship, left))
        elif downstream:
            if direction in {"forward", "bidirectional"} and current_id == left:
                rows.append((relationship, right))
            elif direction in {"reverse", "bidirectional"} and current_id == right:
                rows.append((relationship, left))
        elif upstream:
            if direction in {"forward", "bidirectional"} and current_id == right:
                rows.append((relationship, left))
            elif direction in {"reverse", "bidirectional"} and current_id == left:
                rows.append((relationship, right))
    return sorted(rows, key=lambda item: (str(item[0].get("relationship_id", "")), item[1]))


def _category_allowed(category: str, request: dict[str, Any], definition: dict[str, Any]) -> bool:
    if category in {"operational_flow", "operational_connection"}:
        return True
    if category == "membership_context":
        return request["trace_type"] == "ELEC-TRACE-006"
    # Context flags expose evidence in events; they never convert containment or reference into flow.
    if category == "containment_context" and request["include_containment_relationships"]:
        return False
    if category == "reference_context" and request["include_reference_relationships"]:
        return False
    return False


def _asset_stop(
    asset: dict[str, Any],
    request: dict[str, Any],
    definition: dict[str, Any],
    *,
    is_start: bool = False,
) -> str:
    lifecycle = str(asset.get("lifecycle_status", "unknown"))
    allowed = {
        "active_only": {"active"},
        "active_and_installed": {"active", "installed"},
        "include_proposed": {"active", "installed", "proposed", "planned", "approved", "under_construction"},
        "include_inactive": {"active", "installed", "inactive", "approved", "under_construction"},
        "historical": {
            "proposed", "planned", "approved", "under_construction", "installed", "active",
            "inactive", "abandoned", "retired", "removed", "unknown",
        },
    }[request["lifecycle_mode"]]
    if lifecycle not in allowed:
        return "retired_asset" if lifecycle in {"retired", "removed", "abandoned"} else "inactive_asset"
    operational = str(asset.get("operational_status", "unknown"))
    if request["operational_mode"] != "diagnostic" and operational in _INACTIVE_OPERATIONAL:
        return "retired_asset" if operational == "retired" else "inactive_asset"
    if (
        request["operational_mode"] == "respect_state"
        and request["direction"] in {"downstream", "toward_terminal"}
        and (operational in _OPEN_STATES or _attributes(asset).get("normally_open") is True)
        and not (is_start and request["trace_type"] in {"ELEC-TRACE-004", "WATER-TRACE-004", "WATER-TRACE-005"})
    ):
        return "open_device"
    if (
        request["utility_vertical"] == "telecom_fiber"
        and asset.get("asset_class") == "fiber_cable"
        and request["trace_type"] in {"TEL-TRACE-001", "TEL-TRACE-002", "TEL-TRACE-003", "TEL-TRACE-004", "TEL-TRACE-006", "TEL-TRACE-007"}
        and not _attributes(asset).get("to_structure_id")
    ):
        return "missing_endpoint"
    return ""


def _transition_stop(current: dict[str, Any], next_asset: dict[str, Any], request: dict[str, Any]) -> str:
    left = _attributes(current)
    right = _attributes(next_asset)
    if request["utility_vertical"] == "electric_distribution":
        left_phase, right_phase = _phase(left.get("phase")), _phase(right.get("phase"))
        if left_phase and right_phase and "transformer" not in {current.get("asset_class"), next_asset.get("asset_class")}:
            if request["direction"] in {"downstream", "toward_terminal"} and not right_phase.issubset(left_phase):
                return "phase_conflict"
            if request["direction"] in {"upstream", "toward_source"} and not left_phase.issubset(right_phase):
                return "phase_conflict"
        left_voltage, right_voltage = _number(left.get("operating_voltage")), _number(right.get("operating_voltage"))
        if left_voltage is not None and right_voltage is not None and "transformer" not in {current.get("asset_class"), next_asset.get("asset_class")}:
            if abs(left_voltage - right_voltage) > 0.001:
                return "voltage_conflict"
        left_feeder, right_feeder = str(left.get("feeder_id") or ""), str(right.get("feeder_id") or "")
        if left_feeder and right_feeder and left_feeder != right_feeder:
            return "feeder_conflict"
    elif request["utility_vertical"] == "telecom_fiber":
        left_route, right_route = str(left.get("route_id") or ""), str(right.get("route_id") or "")
        if left_route and right_route and left_route != right_route:
            return "route_conflict"
        if request["trace_type"] == "TEL-TRACE-007":
            for attributes in (left, right):
                total = _number(attributes.get("total_capacity"))
                used = _number(attributes.get("used_capacity"))
                reserved = _number(attributes.get("reserved_capacity"))
                if total is not None and used is not None and reserved is not None and used + reserved > total:
                    return "capacity_conflict"
                fiber_count = _number(attributes.get("fiber_count"))
                strand_end = _number(attributes.get("strand_end"))
                if fiber_count is not None and strand_end is not None and strand_end > fiber_count:
                    return "strand_conflict"
    elif request["utility_vertical"] == "water":
        left_system, right_system = str(left.get("water_system_id") or ""), str(right.get("water_system_id") or "")
        if left_system and right_system and left_system != right_system:
            return "system_conflict"
        left_zone, right_zone = str(left.get("pressure_zone_id") or ""), str(right.get("pressure_zone_id") or "")
        if left_zone and right_zone and left_zone != right_zone:
            return "pressure_zone_conflict"
    elif request["utility_vertical"] == "wastewater":
        left_system, right_system = str(left.get("wastewater_system_id") or ""), str(right.get("wastewater_system_id") or "")
        if left_system and right_system and left_system != right_system:
            return "system_conflict"
        left_basin, right_basin = str(left.get("basin_id") or ""), str(right.get("basin_id") or "")
        if left_basin and right_basin and left_basin != right_basin:
            return "basin_conflict"
    return ""


def _apply_qa(
    path: PathState,
    groups: list[dict[str, Any]],
    request: dict[str, Any],
    events: list[dict[str, str]],
    asset_id: str,
    relationship_id: str,
) -> None:
    seen = set(path.qa_issue_group_ids)
    for group in sorted(groups, key=lambda item: str(item.get("issue_group_id", ""))):
        group_id = str(group.get("issue_group_id", ""))
        if not group_id or group_id in seen or group.get("review_status") in {"false_positive", "superseded"}:
            continue
        seen.add(group_id)
        path.qa_issue_group_ids.append(group_id)
        impact = str(group.get("trace_impact", "not_evaluated"))
        message = str(group.get("trace_impact_reason") or group.get("group_summary") or "Calibrated QA evidence affects this path.")
        accepted = group.get("review_status") == "accepted_risk"
        if impact == "stops_trace" and request["qa_policy"] != "diagnostic" and not accepted:
            _stop(path, "trace_stopping_issue", message, asset_id, relationship_id, events, issue_group_id=group_id)
        elif impact == "limits_trace" and request["qa_policy"] == "strict" and not accepted:
            _stop(path, "trace_stopping_issue", message, asset_id, relationship_id, events, issue_group_id=group_id)
        elif impact in {"stops_trace", "limits_trace", "advisory", "not_evaluated"} or accepted:
            _warn(path, impact, message, asset_id, relationship_id, events, issue_group_id=group_id)
        elif impact == "introduces_ambiguity":
            path.ambiguous = True
            _warn(path, impact, message, asset_id, relationship_id, events, issue_group_id=group_id)


def _terminal_reason(
    asset: dict[str, Any],
    asset_id: str,
    request: dict[str, Any],
    definition: dict[str, Any],
    depth: int,
) -> str:
    if depth and request["optional_target_asset_id"] == asset_id:
        return "target_reached"
    terminal_classes = set(definition["terminal_asset_classes"])
    if depth and asset.get("asset_class") in terminal_classes:
        if asset.get("asset_class") in _SOURCE_CLASSES[request["utility_vertical"]]:
            return "source_reached"
        return "terminal_reached"
    return ""


def _outcome(paths: list[PathState], request: dict[str, Any]) -> str:
    complete = [path for path in paths if path.stopping_reason in _COMPLETE_REASONS]
    if complete:
        target_id = request["optional_target_asset_id"]
        relevant = [path for path in complete if not target_id or path.asset_ids[-1] == target_id]
        if target_id and not relevant:
            relevant = complete
        endpoints = {path.asset_ids[-1] for path in relevant}
        upstream = request["direction"] in {"upstream", "toward_source"}
        if (any(path.ambiguous for path in relevant) and len(relevant) > 1) or (upstream and len(endpoints) > 1):
            return "ambiguous"
        if any(path.warnings or path.blockers or path.provisional for path in paths) or len(complete) != len(paths):
            return "complete_with_warnings"
        return "complete"
    if any(path.ambiguous for path in paths) and len(paths) > 1:
        return "ambiguous"
    if any(path.blockers for path in paths):
        return "blocked"
    if any(len(path.asset_ids) > 1 for path in paths):
        return "partial"
    return "no_path"


def _confidence(paths: list[PathState], outcome: str, qa_evaluated: bool) -> str:
    if outcome in {"no_path", "failed_safely"}:
        return "indeterminate"
    warnings = sum(len(path.warnings) for path in paths)
    if outcome in {"blocked", "ambiguous"} or any(path.provisional for path in paths):
        return "low"
    if not qa_evaluated or warnings:
        return "medium"
    return "high"


def _rank_paths(paths: list[PathState]) -> list[PathState]:
    status_rank = {
        "target_reached": 0, "source_reached": 0, "terminal_reached": 0,
        "open_device": 2, "trace_stopping_issue": 3,
    }
    return sorted(
        paths,
        key=lambda path: (
            status_rank.get(path.stopping_reason, 1),
            len(path.blockers),
            len(path.relationship_ids),
            tuple(path.asset_ids),
            tuple(path.relationship_ids),
        ),
    )


def _path_result(path: PathState, nodes: dict[str, dict[str, Any]], rank: int) -> dict[str, Any]:
    status = "complete" if path.stopping_reason in _COMPLETE_REASONS else "blocked" if path.blockers else "partial"
    warnings = _unique_conditions(path.warnings)
    blockers = _unique_conditions(path.blockers)
    return {
        "path_rank": rank,
        "path_status": status,
        "start_asset_id": path.asset_ids[0],
        "end_asset_id": path.asset_ids[-1],
        "asset_ids": path.asset_ids,
        "relationship_ids": path.relationship_ids,
        "hop_count": len(path.relationship_ids),
        "confidence": _confidence([path], "complete" if status == "complete" else status, bool(path.qa_issue_group_ids)),
        "provisional": path.provisional,
        "warnings": warnings,
        "blockers": blockers,
        "stopping_reason": path.stopping_reason or "no_traversable_edge",
        "qa_issue_group_ids": sorted(set(path.qa_issue_group_ids)),
        "steps": [
            {
                "sequence": index,
                "asset_id": asset_id,
                "entered_by_relationship_id": path.relationship_ids[index - 1] if index else "",
                "exited_by_relationship_id": path.relationship_ids[index] if index < len(path.relationship_ids) else "",
                "step_role": "start" if index == 0 else "stop" if index == len(path.asset_ids) - 1 else "traversed",
                "operational_state": str(nodes.get(asset_id, {}).get("operational_status", "unknown")),
                "lifecycle_status": str(nodes.get(asset_id, {}).get("lifecycle_status", "unknown")),
                "feeder_or_route_context": str(
                    _attributes(nodes.get(asset_id, {})).get("feeder_id")
                    or _attributes(nodes.get(asset_id, {})).get("route_id")
                    or _attributes(nodes.get(asset_id, {})).get("water_system_id")
                    or _attributes(nodes.get(asset_id, {})).get("wastewater_system_id")
                    or _attributes(nodes.get(asset_id, {})).get("basin_id")
                    or ""
                ),
                "qa_issue_group_ids": sorted(set(path.qa_issue_group_ids)) if index == len(path.asset_ids) - 1 else [],
                "trace_effect": "stopped" if index == len(path.asset_ids) - 1 and status != "complete" else "continued",
                "decision": "stop" if index == len(path.asset_ids) - 1 else "traverse",
                "decision_reason": path.stopping_reason if index == len(path.asset_ids) - 1 else "allowlisted canonical relationship",
            }
            for index, asset_id in enumerate(path.asset_ids)
        ],
    }


def _warn(
    path: PathState,
    code: str,
    message: str,
    asset_id: str,
    relationship_id: str,
    events: list[dict[str, str]],
    *,
    issue_group_id: str = "",
) -> None:
    condition = _condition(code, message, asset_id, relationship_id, issue_group_id)
    path.warnings.append(condition)
    events.append(_event("warning", message, asset_id, relationship_id, issue_group_id, "warning"))


def _stop(
    path: PathState,
    reason: str,
    message: str,
    asset_id: str,
    relationship_id: str,
    events: list[dict[str, str]],
    *,
    issue_group_id: str = "",
    blocker: bool = True,
) -> None:
    path.stopping_reason = reason
    condition = _condition(reason, message, asset_id, relationship_id, issue_group_id)
    (path.blockers if blocker else path.warnings).append(condition)
    events.append(_event("trace_stopped" if blocker else "evidence_boundary", message, asset_id, relationship_id, issue_group_id, "error" if blocker else "warning"))


def _condition(code: str, message: str, asset_id: str, relationship_id: str, issue_group_id: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "asset_id": asset_id,
        "relationship_id": relationship_id,
        "issue_group_id": issue_group_id,
    }


def _event(
    event_type: str,
    message: str,
    asset_id: str = "",
    relationship_id: str = "",
    issue_group_id: str = "",
    severity: str = "info",
) -> dict[str, str]:
    return {
        "event_type": event_type,
        "asset_id": asset_id,
        "relationship_id": relationship_id,
        "issue_group_id": issue_group_id,
        "severity": severity,
        "message": message,
    }


def _stop_message(reason: str, asset: dict[str, Any]) -> str:
    name = str(asset.get("canonical_name") or asset.get("asset_id") or "asset")
    messages = {
        "target_reached": f"The requested target {name} was reached.",
        "source_reached": f"A represented source candidate {name} was reached.",
        "terminal_reached": f"A represented terminal condition {name} was reached.",
        "open_device": f"{name} is open or normally open; downstream operational traversal stopped.",
        "retired_asset": f"{name} is retired or removed under the selected lifecycle policy.",
        "inactive_asset": f"{name} is inactive or unavailable under the selected policy.",
        "missing_endpoint": f"{name} lacks required endpoint evidence for this trace.",
        "missing_relationship": f"No outgoing canonical relationship is represented at {name}.",
        "phase_conflict": f"Phase evidence is incompatible at {name}.",
        "voltage_conflict": f"Voltage evidence changes without a represented transformer at {name}.",
        "feeder_conflict": f"Feeder membership conflicts at {name}.",
        "route_conflict": f"Route membership conflicts at {name}.",
        "system_conflict": f"Utility-system identity conflicts at {name}.",
        "pressure_zone_conflict": f"Pressure-zone membership conflicts at {name}.",
        "basin_conflict": f"Sewer-basin membership conflicts at {name}.",
        "strand_conflict": f"Strand evidence is inconsistent at {name}.",
        "capacity_conflict": f"Capacity evidence is inconsistent at {name}.",
        "no_traversable_edge": f"No allowlisted operational relationship continues from {name}.",
    }
    return messages.get(reason, f"Trace stopped safely at {name}: {reason.replace('_', ' ')}.")


def _attributes(asset: dict[str, Any]) -> dict[str, Any]:
    value = asset.get("canonical_attributes_json", {})
    return value if isinstance(value, dict) else {}


def _phase(value: Any) -> set[str]:
    text = str(value or "").upper().replace("N", "")
    return {character for character in text if character in "ABC"}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _unique_conditions(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return list({tuple(sorted(item.items())): item for item in items}.values())
