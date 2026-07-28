from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.utility_assets.domain import stable_fingerprint, stable_id

CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "network_trace" / "trace_calibration_v1.json"
DISCLAIMER = (
    "UtilitiesPlatform trace calibration interprets immutable vendor-neutral trace evidence for human review. "
    "It does not alter utility assets, repair connectivity, execute switching, allocate fiber capacity, predict "
    "outages, or reproduce proprietary utility-system traces."
)


def load_calibration_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "version", "event_grouping_version", "warning_relevance_version", "branch_analysis_version",
        "stopping_precedence_version", "outcome_calibration_version", "confidence_calibration_version",
        "warning_scopes", "event_categories", "stopping_precedence", "relevance_profiles",
        "event_grouping", "branch_classifications", "outcome_values", "confidence_values",
        "recommended_edits", "recommended_edit_categories", "external_mapping_statuses",
    }
    if required.difference(config):
        raise ValueError("Trace calibration configuration is incomplete.")
    if len(config["warning_scopes"]) != len(set(config["warning_scopes"])):
        raise ValueError("Trace warning scopes must be unique.")
    if len(config["event_categories"]) != len(set(config["event_categories"])):
        raise ValueError("Trace event categories must be unique.")
    if set(config["outcome_values"]) != {
        "complete", "complete_with_warnings", "partial", "blocked", "no_path", "ambiguous", "failed_safely",
    }:
        raise ValueError("Trace calibration outcomes are not allowlisted.")
    if set(config["confidence_values"]) != {"high", "medium", "low", "indeterminate"}:
        raise ValueError("Trace calibration confidence values are not allowlisted.")
    if set(config["recommended_edits"].values()).difference(config["recommended_edit_categories"]):
        raise ValueError("Trace calibration recommended edit category is not allowlisted.")
    if set(config["external_mapping_statuses"]) != {
        "not_mapped", "conceptually_mappable", "adapter_required", "unsupported", "unknown",
    }:
        raise ValueError("External trace mapping statuses are not allowlisted.")
    return config


CONFIG = load_calibration_config()
CALIBRATION_VERSION = CONFIG["version"]
VERSION_KEYS = (
    "version", "event_grouping_version", "warning_relevance_version", "branch_analysis_version",
    "stopping_precedence_version", "outcome_calibration_version", "confidence_calibration_version",
)


def calibration_fingerprint(
    run: dict[str, Any],
    paths: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    raw_events: list[dict[str, Any]],
    issue_groups: list[dict[str, Any]],
) -> str:
    return stable_fingerprint(
        run["trace_run_id"],
        run["input_fingerprint"],
        [(p["trace_path_id"], _path_signature(p), p["stopping_reason"]) for p in paths],
        [(s["trace_step_id"], s["trace_path_id"], s["sequence"], s["decision"], s["decision_reason"]) for s in steps],
        [(e["trace_event_id"], e["event_type"], e["asset_id"], e["relationship_id"], e["issue_group_id"]) for e in raw_events],
        [
            (
                g.get("issue_group_id"), g.get("finding_fingerprint") or g.get("input_fingerprint"),
                g.get("trace_impact"), g.get("review_status"),
            )
            for g in issue_groups
        ],
        *[CONFIG[key] for key in VERSION_KEYS],
    )


def calibrate_trace(
    run: dict[str, Any],
    paths: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    raw_events: list[dict[str, Any]],
    issue_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    path_ids = {path["trace_path_id"] for path in paths}
    asset_paths, relationship_paths = _path_membership(paths)
    objective_paths = _objective_paths(run, paths)
    objective_ids = {path["trace_path_id"] for path in objective_paths}
    objective_reached = bool(objective_paths)
    raw_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in raw_events:
        if event.get("issue_group_id"):
            raw_by_group[event["issue_group_id"]].append(event)
    conditions = [
        {**condition, "trace_path_id": path["trace_path_id"], "effect": effect}
        for path in paths
        for effect in ("blockers", "warnings")
        for condition in path[effect]
    ]
    condition_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for condition in conditions:
        if condition.get("issue_group_id"):
            condition_by_group[condition["issue_group_id"]].append(condition)
    steps_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for step in steps:
        for group_id in step.get("qa_issue_group_ids", []):
            steps_by_group[group_id].append(step)

    calibrated_events = []
    represented_groups = {str(group.get("issue_group_id", "")): group for group in issue_groups}
    for group_id in sorted(set(represented_groups) | set(raw_by_group) | set(condition_by_group)):
        group = represented_groups.get(group_id, {})
        group_conditions = condition_by_group[group_id]
        source_events = raw_by_group[group_id]
        group_steps = steps_by_group[group_id]
        affected_assets = sorted({
            str(value) for value in group.get("affected_asset_ids", [])
        } | {str(item.get("asset_id", "")) for item in group_conditions + source_events if item.get("asset_id")})
        affected_relationships = sorted({
            str(value) for value in group.get("affected_relationship_ids", [])
        } | {str(item.get("relationship_id", "")) for item in group_conditions + source_events if item.get("relationship_id")})
        affected_paths = sorted({
            item["trace_path_id"] for item in group_conditions
        } | {item["trace_path_id"] for item in group_steps
        } | set().union(*(asset_paths.get(item, set()) for item in affected_assets))
          | set().union(*(relationship_paths.get(item, set()) for item in affected_relationships)))
        stopping = any(item["effect"] == "blockers" for item in group_conditions)
        category = _category(
            group.get("primary_rule_code", ""),
            group.get("group_title", ""),
            group_conditions[0].get("code", "") if group_conditions else "",
            group.get("issue_family", ""),
        )
        scope = _scope(
            stopping, affected_paths, objective_ids, path_ids, affected_assets,
            run["start_asset_id"], run["target_asset_id"], category,
        )
        calibrated_events.append(_calibrated_event(
            run, category, scope, group.get("group_title") or _title(category),
            group.get("group_summary") or group.get("trace_impact_reason") or _summary(category),
            [item["trace_event_id"] for item in source_events], affected_paths, affected_assets,
            affected_relationships, [group_id], stopping,
            max(1, len(group_conditions) + len(source_events) + len(group_steps)),
            group.get("trace_impact", "not_evaluated"),
            group.get("recommended_action", ""),
            {
                "source": "calibrated_qa_issue_group",
                "review_status": group.get("review_status", "open"),
                "first_affected_step": min((item["sequence"] for item in group_steps), default=None),
                "last_affected_step": max((item["sequence"] for item in group_steps), default=None),
                "affected_path_count": len(affected_paths),
                "affects_all_paths": bool(path_ids and set(affected_paths) == path_ids),
            },
        ))

    grouped_raw: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in raw_events:
        if event.get("issue_group_id"):
            continue
        category = _category(event.get("event_type", ""), event.get("message", ""), "")
        grouped_raw[(category, event.get("asset_id", ""), event.get("relationship_id", ""), event.get("message", ""))].append(event)
    for (category, asset_id, relationship_id, message), members in sorted(grouped_raw.items()):
        affected_paths = sorted(
            asset_paths.get(asset_id, set()) | relationship_paths.get(relationship_id, set())
        )
        stopping = any(item["event_type"] == "trace_stopped" for item in members)
        scope = _scope(
            stopping, affected_paths, objective_ids, path_ids, [asset_id] if asset_id else [],
            run["start_asset_id"], run["target_asset_id"], category,
        )
        calibrated_events.append(_calibrated_event(
            run, category, scope, _title(category), message or _summary(category),
            [item["trace_event_id"] for item in members], affected_paths,
            [asset_id] if asset_id else [], [relationship_id] if relationship_id else [],
            [], stopping, len(members), category, "", {"source": "raw_trace_event"},
        ))

    calibrated_events.sort(key=lambda item: (item["priority"], item["category"], item["calibrated_event_id"]))
    branch = _branch_analysis(run, paths, calibrated_events)
    primary = _primary_stopping(paths, calibrated_events, run["trace_type"])
    path_warning_count = sum(
        1 for event in calibrated_events
        if event["scope"] in {"path_specific", "start_asset_context", "target_asset_context"}
        and not event["primary"]
    )
    branch_warning_count = sum(1 for event in calibrated_events if event["scope"] == "branch_specific")
    background_count = sum(
        1 for event in calibrated_events
        if event["scope"] in {"network_background", "unrelated_to_selected_path"}
    )
    informational_count = sum(1 for event in calibrated_events if event["scope"] == "informational")
    outcome = _outcome(run, paths, objective_reached, primary, branch, calibrated_events)
    confidence, confidence_reasons = _confidence(outcome, objective_reached, branch, calibrated_events)
    selected_paths = objective_paths or [path for path in paths if len(path["asset_ids"]) > 1]
    reachable = sorted({asset for path in selected_paths for asset in path["asset_ids"]})
    visited = {asset for path in paths for asset in path["asset_ids"]}
    result = {
        "original_outcome": run["outcome"],
        "calibrated_outcome": outcome,
        "original_confidence": run["confidence"],
        "calibrated_confidence": confidence,
        "objective_reached": objective_reached,
        "primary_stopping_reason": primary.get("reason", ""),
        "primary_stopping_asset_id": primary.get("asset_id", ""),
        "primary_stopping_relationship_id": primary.get("relationship_id", ""),
        "primary_issue_group_id": primary.get("issue_group_id", ""),
        "path_specific_blocker_count": int(bool(primary and not objective_reached)),
        "path_specific_warning_count": path_warning_count,
        "branch_specific_warning_count": branch_warning_count,
        "background_warning_count": background_count,
        "informational_event_count": informational_count,
        "normal_branch_count": branch["normal_branch_count"],
        "ambiguous_branch_count": branch["ambiguous_branch_count"],
        "branch_analysis": branch,
        "provisional_segment_count": sum(int(path["provisional"]) for path in selected_paths),
        "excluded_asset_count": sum(1 for event in raw_events if event["event_type"] == "asset_excluded"),
        "excluded_relationship_count": sum(1 for event in raw_events if event["event_type"] == "relationship_excluded"),
        "related_raw_event_count": len(raw_events),
        "confidence_reason": confidence_reasons,
        "outcome_reason": _outcome_reasons(outcome, objective_reached, primary, branch),
        "recommended_action": primary.get("recommended_action") or _recommended_action(outcome),
        "recommended_edit_category": CONFIG["recommended_edits"].get(primary.get("category", ""), "manual_review"),
        "comparison_key": stable_fingerprint(
            run["utility_vertical"], run["trace_type"], run["start_asset_id"],
            run["target_asset_id"], run["request_fingerprint"],
        ),
        "path_signature": stable_fingerprint([_path_signature(path) for path in selected_paths]),
        "branch_signature": stable_fingerprint(branch["competing_paths"], branch["normal_branch_count"]),
        "reachable_asset_ids": reachable,
        "unreachable_asset_ids": sorted(visited.difference(reachable)),
        "unreachable_visited_asset_ids": sorted(visited.difference(reachable)),
        "blocked_path_ids": sorted(path["trace_path_id"] for path in paths if path["path_status"] == "blocked"),
        "path_specific_issue_group_ids": sorted({
            group_id for event in calibrated_events
            if event["scope"] in {"stopping_condition", "path_specific", "branch_specific", "start_asset_context", "target_asset_context"}
            for group_id in event["issue_group_ids"]
        }),
        "primary_stopping_category": primary.get("category", ""),
        "relevant_issue_group_ids": sorted({
            group_id for event in calibrated_events
            if event["scope"] not in {"network_background", "unrelated_to_selected_path"}
            for group_id in event["issue_group_ids"]
        }),
        "confidence_factors": confidence_reasons,
        "canonical_trace_category": run["trace_type"],
        "external_trace_mapping_status": "conceptually_mappable",
        "external_outcome_mapping_status": "adapter_required",
        "adapter_required": True,
        "vendor_concept_hints": CONFIG["vendor_concept_hints"][run["utility_vertical"]],
        "vendor_hint_notice": (
            "Vendor-equivalent hints describe general utility-network concepts only. Current traces are not "
            "direct ArcFM, Smallworld, Esri Utility Network, outage-management, or proprietary telecom traces."
        ),
        "disclaimer": DISCLAIMER,
    }
    for event in calibrated_events:
        event["primary"] = bool(
            primary and event["category"] == primary["category"]
            and (not primary.get("asset_id") or primary["asset_id"] in event["asset_ids"])
        )
    return {
        "input_fingerprint": calibration_fingerprint(run, paths, steps, raw_events, issue_groups),
        "result": result,
        "events": calibrated_events,
        "metrics": {
            "raw_events_read": len(raw_events),
            "raw_warnings_read": int(run["warnings_count"]),
            "raw_blockers_read": int(run["blockers_count"]),
            "calibrated_events_created": len(calibrated_events),
            "path_specific_warning_count": path_warning_count,
            "background_warning_count": background_count,
            "primary_blocker_count": int(bool(primary and not objective_reached)),
            "normal_branch_count": branch["normal_branch_count"],
            "ambiguous_branch_count": branch["ambiguous_branch_count"],
        },
    }


def _path_membership(paths: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    assets: dict[str, set[str]] = defaultdict(set)
    relationships: dict[str, set[str]] = defaultdict(set)
    for path in paths:
        for asset_id in path["asset_ids"]:
            assets[asset_id].add(path["trace_path_id"])
        for relationship_id in path["relationship_ids"]:
            relationships[relationship_id].add(path["trace_path_id"])
    return assets, relationships


def _objective_paths(run: dict[str, Any], paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target = run["target_asset_id"]
    if target:
        return [path for path in paths if path["end_asset_id"] == target and path["stopping_reason"] == "target_reached"]
    return [
        path for path in paths
        if path["path_status"] == "complete" and path["stopping_reason"] in {"source_reached", "terminal_reached", "target_reached"}
    ]


def _scope(
    stopping: bool,
    affected_paths: list[str],
    objective_paths: set[str],
    all_paths: set[str],
    assets: list[str],
    start_asset_id: str,
    target_asset_id: str,
    category: str,
) -> str:
    affected = set(affected_paths)
    if stopping:
        return "stopping_condition"
    if start_asset_id in assets:
        return "start_asset_context"
    if target_asset_id and target_asset_id in assets:
        return "target_asset_context"
    if category in {"excluded_asset", "excluded_relationship", "lifecycle_exclusion"}:
        return "excluded_context"
    if category in {"target_reached", "source_reached", "terminal_reached", "path_completed", "normal_branch"}:
        return "informational"
    if affected.intersection(objective_paths):
        return "path_specific" if affected.issuperset(objective_paths) else "branch_specific"
    if affected:
        return "branch_specific"
    return "network_background" if all_paths else "unrelated_to_selected_path"


def _category(*values: str) -> str:
    text = " ".join(str(value).lower().replace("-", "_") for value in values)
    checks = (
        ("missing referenced relationship endpoint", "endpoint_failure"),
        ("missing endpoint", "endpoint_failure"),
        ("endpoint", "endpoint_failure"),
        ("termination", "endpoint_failure"),
        ("open_device", "open_device"),
        ("normally open", "open_device"),
        ("operational_state", "open_device"),
        ("retired", "lifecycle_exclusion"),
        ("inactive", "lifecycle_exclusion"),
        ("lifecycle", "lifecycle_exclusion"),
        ("provisional", "provisional_relationship"),
        ("missing_relationship", "missing_relationship"),
        ("connectivity", "missing_relationship"),
        ("no traversable edge", "missing_relationship"),
        ("feeder", "feeder_conflict"),
        ("circuit", "circuit_conflict"),
        ("route", "route_conflict"),
        ("phase", "phase_conflict"),
        ("voltage", "voltage_conflict"),
        ("strand", "strand_conflict"),
        ("capacity", "capacity_conflict"),
        ("conduit", "containment_warning"),
        ("containment", "containment_warning"),
        ("proposed construction", "route_conflict"),
        ("support", "support_warning"),
        ("branch_detected", "normal_branch"),
        ("ambiguous source", "ambiguous_source"),
        ("ambiguous route", "ambiguous_route"),
        ("ambigu", "ambiguous_relationship"),
        ("cycle", "cycle_detected"),
        ("maximum", "traversal_limit"),
        ("asset_excluded", "excluded_asset"),
        ("relationship_excluded", "excluded_relationship"),
        ("target_reached", "target_reached"),
        ("source_reached", "source_reached"),
        ("terminal_reached", "terminal_reached"),
        ("trace_stopped", "path_stopped"),
        ("failed", "controlled_execution_warning"),
    )
    return next((category for needle, category in checks if needle in text), "background_qa")


def _calibrated_event(
    run: dict[str, Any],
    category: str,
    scope: str,
    title: str,
    summary: str,
    source_event_ids: list[str],
    path_ids: list[str],
    asset_ids: list[str],
    relationship_ids: list[str],
    issue_group_ids: list[str],
    primary: bool,
    repeated_count: int,
    trace_effect: str,
    recommended_action: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "calibrated_event_id": stable_id(
            "trace_calibrated_event", run["trace_run_id"], CONFIG["event_grouping_version"],
            category, scope, title, summary, issue_group_ids, path_ids, asset_ids, relationship_ids,
            recommended_action,
        ),
        "category": category,
        "scope": scope,
        "priority": _priority(category, primary),
        "title": title[:200],
        "summary": summary[:1000],
        "source_event_ids": sorted(set(source_event_ids)),
        "path_ids": sorted(set(path_ids)),
        "asset_ids": sorted(set(asset_ids)),
        "relationship_ids": sorted(set(relationship_ids)),
        "issue_group_ids": sorted(set(issue_group_ids)),
        "primary": primary,
        "repeated_count": repeated_count,
        "trace_effect": trace_effect,
        "evidence": evidence,
        "recommended_action": recommended_action or _recommended_action(category),
    }


def _branch_analysis(
    run: dict[str, Any],
    paths: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    branch_count = max(0, len(paths) - 1)
    complete = [path for path in paths if path["path_status"] == "complete"]
    endpoints = sorted({path["end_asset_id"] for path in complete})
    conflict = any(
        event["category"] in {"ambiguous_source", "ambiguous_route", "ambiguous_relationship", "feeder_conflict", "circuit_conflict", "route_conflict"}
        and event["scope"] not in {"network_background", "unrelated_to_selected_path"}
        for event in events
    )
    authoritative = run["trace_type"] in CONFIG["authoritative_trace_types"]
    ambiguous = int(bool(branch_count and authoritative and (len(endpoints) > 1 or conflict)))
    normal = max(0, branch_count - ambiguous) if run["trace_type"] in CONFIG["normal_branch_trace_types"] else 0
    competing = [path["trace_path_id"] for path in complete] if ambiguous else []
    shared_prefix, divergence = _shared_prefix(complete)
    return {
        "normal_branch_count": normal,
        "ambiguous_branch_count": ambiguous,
        "branch_reason": (
            "Multiple competing authoritative endpoints remain."
            if ambiguous else "Multiple returned branches are expected for this trace type."
            if normal else "No material branch interpretation was required."
        ),
        "branch_point": shared_prefix[-1] if shared_prefix and branch_count else "",
        "shared_prefix": shared_prefix,
        "divergence_step": divergence,
        "competing_paths": competing,
        "supporting_evidence": sorted(
            event["calibrated_event_id"] for event in events
            if event["category"] in {"normal_branch", "ambiguous_source", "ambiguous_route", "ambiguous_relationship"}
        ),
    }


def _shared_prefix(paths: list[dict[str, Any]]) -> tuple[list[str], int | None]:
    if len(paths) < 2:
        return [], None
    prefix = []
    for values in zip(*(path["asset_ids"] for path in paths)):
        if len(set(values)) != 1:
            break
        prefix.append(values[0])
    return prefix, len(prefix) if prefix else 0


def _primary_stopping(
    paths: list[dict[str, Any]],
    events: list[dict[str, Any]],
    trace_type: str,
) -> dict[str, str]:
    candidates = []
    for path in paths:
        for blocker in path["blockers"]:
            matching = next((
                event for event in events
                if blocker.get("issue_group_id")
                and blocker["issue_group_id"] in event["issue_group_ids"]
            ), None)
            candidates.append({
                "reason": blocker["code"],
                "category": matching["category"] if matching else _category(blocker["code"], blocker["message"], ""),
                "asset_id": blocker["asset_id"], "relationship_id": blocker["relationship_id"],
                "issue_group_id": blocker["issue_group_id"], "recommended_action": "",
                "direct": blocker["code"] != "trace_stopping_issue",
            })
        if path["stopping_reason"]:
            candidates.append({
                "reason": path["stopping_reason"], "category": _category(path["stopping_reason"], "", ""),
                "asset_id": path["end_asset_id"], "relationship_id": "", "issue_group_id": "",
                "recommended_action": "", "direct": path["stopping_reason"] != "trace_stopping_issue",
            })
    precedence = {reason: index for index, reason in enumerate(CONFIG["stopping_precedence"])}
    prioritized = (
        ["strand_conflict", "endpoint_failure"] if trace_type == "TEL-TRACE-003"
        else ["capacity_conflict", "strand_conflict", "endpoint_failure"] if trace_type == "TEL-TRACE-007"
        else ["endpoint_failure", "strand_conflict", "capacity_conflict"]
    )
    category_order = {
        category: index for index, category in enumerate((
            "controlled_execution_warning", *prioritized, "open_device", "phase_conflict",
            "voltage_conflict", "lifecycle_exclusion",
            "feeder_conflict", "circuit_conflict", "route_conflict", "missing_relationship",
            "ambiguous_source", "ambiguous_route", "ambiguous_relationship", "background_qa",
        ))
    }
    specific = [
        item for item in candidates
        if item["direct"] and item["reason"] in {
            "missing_endpoint", "retired_asset", "inactive_asset", "open_device",
            "phase_conflict", "voltage_conflict",
        }
    ]
    if specific:
        candidates = specific
    candidates.sort(key=lambda item: (
        precedence.get(item["reason"], len(precedence)),
        category_order.get(item["category"], len(category_order)),
        0 if item["issue_group_id"] else 1,
        item["asset_id"], item["relationship_id"], item["issue_group_id"],
    ))
    primary = candidates[0] if candidates else {}
    if primary:
        matching = next((
            event for event in events
            if event["category"] == primary["category"]
            and (not primary["asset_id"] or primary["asset_id"] in event["asset_ids"])
        ), None)
        if matching:
            primary["recommended_action"] = matching["recommended_action"]
    return primary


def _outcome(
    run: dict[str, Any],
    paths: list[dict[str, Any]],
    objective_reached: bool,
    primary: dict[str, str],
    branch: dict[str, Any],
    events: list[dict[str, Any]],
) -> str:
    if run["status"] == "failed":
        return "failed_safely"
    if objective_reached:
        if branch["ambiguous_branch_count"]:
            return "ambiguous"
        material = any(
            event["scope"] in {"stopping_condition", "path_specific", "branch_specific", "start_asset_context", "target_asset_context"}
            and event["category"] not in {"target_reached", "source_reached", "terminal_reached", "path_completed", "normal_branch"}
            for event in events
        )
        return "complete_with_warnings" if material else "complete"
    if branch["ambiguous_branch_count"]:
        return "ambiguous"
    if primary and all(path["path_status"] == "blocked" for path in paths):
        return "blocked"
    if any(len(path["asset_ids"]) > 1 for path in paths):
        return "partial"
    return "no_path"


def _confidence(
    outcome: str,
    objective_reached: bool,
    branch: dict[str, Any],
    events: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    if outcome in {"no_path", "failed_safely"}:
        return "indeterminate", ["The available evidence does not support a meaningful path-confidence estimate."]
    relevant = [
        event for event in events
        if event["scope"] not in {"network_background", "unrelated_to_selected_path", "informational"}
    ]
    if outcome in {"blocked", "partial", "ambiguous"}:
        reasons = ["The requested objective was not reached with one confirmed interpretation."]
        if branch["ambiguous_branch_count"]:
            reasons.append("Competing authoritative paths remain.")
        return "low", reasons
    if any(event["category"] == "provisional_relationship" for event in relevant) or relevant or branch["normal_branch_count"]:
        return "medium", [
            "The objective was reached.",
            "Selected path or branch evidence includes an advisory, provisional, or review condition.",
            "Background network conditions were excluded from confidence.",
        ]
    return "high", [
        "The objective was reached on confirmed represented evidence.",
        "No material selected-path warning or unresolved ambiguity was detected.",
    ]


def _outcome_reasons(
    outcome: str,
    reached: bool,
    primary: dict[str, str],
    branch: dict[str, Any],
) -> list[str]:
    reasons = [f"Objective reached: {'yes' if reached else 'no'}."]
    if primary:
        reasons.append(f"Highest-precedence represented stopping condition: {primary['reason']}.")
    if branch["normal_branch_count"]:
        reasons.append(f"{branch['normal_branch_count']} expected branch alternative(s) were not treated as ambiguity.")
    if branch["ambiguous_branch_count"]:
        reasons.append("Competing authoritative interpretations remain.")
    reasons.append(f"Calibrated outcome: {outcome}.")
    return reasons


def _priority(category: str, primary: bool) -> int:
    if primary:
        return 0
    stopping = {
        "controlled_execution_warning", "endpoint_failure", "open_device", "phase_conflict",
        "voltage_conflict", "strand_conflict", "capacity_conflict", "lifecycle_exclusion",
        "feeder_conflict", "circuit_conflict", "route_conflict", "missing_relationship",
    }
    return 1 if category in stopping else 2 if category.startswith("ambiguous") else 3


def _title(category: str) -> str:
    return category.replace("_", " ").title()


def _summary(category: str) -> str:
    return f"Calibrated {category.replace('_', ' ')} evidence was derived from the immutable trace."


def _recommended_action(value: str) -> str:
    return {
        "blocked": "Review the primary stopping evidence before proposing any source-system change.",
        "partial": "Confirm the missing or insufficient relationship evidence.",
        "ambiguous": "Have a qualified reviewer select or confirm the authoritative interpretation.",
        "complete_with_warnings": "Review selected-path warnings before relying on the result operationally.",
        "endpoint_failure": "Confirm and complete the referenced endpoint in an approved editing workflow.",
        "open_device": "Confirm device state and trace policy with an authorized operator.",
        "provisional_relationship": "Confirm the provisional relationship with the data owner.",
    }.get(value, "Review the calibrated evidence; do not alter source or canonical records from this result.")


def _path_signature(path: dict[str, Any]) -> str:
    return stable_fingerprint(path["asset_ids"], path["relationship_ids"], path["stopping_reason"])
