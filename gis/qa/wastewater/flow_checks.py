from __future__ import annotations

from typing import Any

from .attribute_checks import safe_asset_id
from .field_mapping import number_or_none
from .issue_writer import make_issue


def missing_invert_issues(
    pipes: list[dict[str, Any]],
    field_name: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    issues = []
    for pipe in pipes:
        value = number_or_none(pipe["attributes"].get(field_name))
        if value is None or value == 0:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(pipe, asset_id_field),
                    source_objectid=pipe["objectid"],
                    description=f"Pipe OBJECTID {pipe['objectid']} has no usable value in {field_name}.",
                    geometry=pipe.get("geometry"),
                    confidence="candidate",
                    issue_key=field_name,
                )
            )
    return issues


def uphill_issues(
    pipes: list[dict[str, Any]],
    upstream_field: str,
    downstream_field: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    issues = []
    for pipe in pipes:
        upstream = number_or_none(pipe["attributes"].get(upstream_field))
        downstream = number_or_none(pipe["attributes"].get(downstream_field))
        if upstream is None or downstream is None or upstream == 0 or downstream == 0:
            continue
        if upstream < downstream:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(pipe, asset_id_field),
                    source_objectid=pipe["objectid"],
                    description=f"Pipe OBJECTID {pipe['objectid']} has upstream invert {upstream:g} lower than downstream invert {downstream:g}.",
                    geometry=pipe.get("geometry"),
                    confidence="candidate",
                    issue_key=f"{upstream}:{downstream}",
                )
            )
    return issues


def slope_issues(
    pipes: list[dict[str, Any]],
    upstream_field: str,
    downstream_field: str,
    length_field: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    max_slope = float(rule.get("parameters", {}).get("max_slope_percent", 25))
    issues = []
    for pipe in pipes:
        upstream = number_or_none(pipe["attributes"].get(upstream_field))
        downstream = number_or_none(pipe["attributes"].get(downstream_field))
        length = number_or_none(pipe["attributes"].get(length_field)) or float((pipe.get("geometry") or {}).get("length") or 0)
        if not upstream or not downstream or not length:
            continue
        slope = (upstream - downstream) / length * 100
        if slope <= 0 or slope > max_slope:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(pipe, asset_id_field),
                    source_objectid=pipe["objectid"],
                    description=f"Pipe OBJECTID {pipe['objectid']} has calculated slope {slope:.2f}%.",
                    geometry=pipe.get("geometry"),
                    threshold_used=f"0-{max_slope:g}%",
                    confidence="candidate",
                    issue_key=f"{slope:.4f}",
                )
            )
    return issues


def slope_conflict_issues(
    pipes: list[dict[str, Any]],
    slope_field: str,
    upstream_field: str,
    downstream_field: str,
    length_field: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    tolerance = float(rule.get("parameters", {}).get("slope_tolerance_percent", 0.5))
    issues = []
    for pipe in pipes:
        mapped = number_or_none(pipe["attributes"].get(slope_field))
        upstream = number_or_none(pipe["attributes"].get(upstream_field))
        downstream = number_or_none(pipe["attributes"].get(downstream_field))
        length = number_or_none(pipe["attributes"].get(length_field)) or float((pipe.get("geometry") or {}).get("length") or 0)
        if mapped is None or not upstream or not downstream or not length:
            continue
        calculated = (upstream - downstream) / length * 100
        if abs(mapped - calculated) > tolerance:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(pipe, asset_id_field),
                    source_objectid=pipe["objectid"],
                    description=f"Pipe OBJECTID {pipe['objectid']} has mapped slope {mapped:.2f}% but calculated slope {calculated:.2f}%.",
                    geometry=pipe.get("geometry"),
                    threshold_used=f"{tolerance:g}% tolerance",
                    confidence="candidate",
                    issue_key=f"{mapped:.4f}:{calculated:.4f}",
                )
            )
    return issues
