from __future__ import annotations

from collections import defaultdict
from typing import Any

from .attribute_checks import safe_asset_id
from .issue_writer import make_issue


def feet_to_source_units(feet: float, linear_unit_name: str) -> float:
    unit = linear_unit_name.lower()
    if "foot" in unit or "feet" in unit:
        return feet
    if "meter" in unit or "metre" in unit:
        return feet * 0.3048
    return feet * 0.3048


def null_geometry_issues(records: list[dict[str, Any]], rule: dict[str, Any], run_id: str, created_at: str, source_layer: str) -> list[dict[str, Any]]:
    return [
        make_issue(
            run_id=run_id,
            created_at=created_at,
            rule=rule,
            source_layer=source_layer,
            source_asset_id="",
            source_objectid=record["objectid"],
            description=f"{source_layer} OBJECTID {record['objectid']} has null or empty geometry.",
            geometry=None,
            confidence="high",
        )
        for record in records
        if not record.get("geometry") or record["geometry"].get("is_empty")
    ]


def invalid_geometry_issues(records: list[dict[str, Any]], rule: dict[str, Any], run_id: str, created_at: str, source_layer: str) -> list[dict[str, Any]]:
    issues = []
    for record in records:
        geometry = record.get("geometry") or {}
        if geometry.get("type") == "polyline" and len((geometry.get("paths") or [[]])[0]) < 2:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer=source_layer,
                    source_asset_id="",
                    source_objectid=record["objectid"],
                    description=f"{source_layer} OBJECTID {record['objectid']} has fewer than two vertices.",
                    geometry=geometry,
                    confidence="high",
                    issue_key="vertex_count",
                )
            )
    return issues


def short_pipe_issues(
    pipes: list[dict[str, Any]],
    threshold_units: float,
    threshold_label: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    issues = []
    for record in pipes:
        geometry = record.get("geometry") or {}
        length = float(geometry.get("length") or 0)
        if length < threshold_units:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(record, asset_id_field),
                    source_objectid=record["objectid"],
                    description=f"Pipe OBJECTID {record['objectid']} is {length:.2f} source units, below {threshold_label}.",
                    geometry=geometry,
                    threshold_used=threshold_label,
                    confidence="candidate",
                    issue_key=f"{length:.4f}",
                )
            )
    return issues


def duplicate_geometry_issues(
    records: list[dict[str, Any]],
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    source_layer: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        signature = geometry_signature(record.get("geometry") or {})
        if signature:
            groups[signature].append(record)
    issues = []
    for signature, matches in groups.items():
        if len(matches) < 2:
            continue
        for record in matches:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer=source_layer,
                    source_asset_id=safe_asset_id(record, asset_id_field),
                    source_objectid=record["objectid"],
                    related_objectid=",".join(str(item["objectid"]) for item in matches if item["objectid"] != record["objectid"]),
                    description=f"{source_layer} OBJECTID {record['objectid']} has candidate duplicate geometry with {len(matches) - 1} other feature(s).",
                    geometry=record.get("geometry"),
                    confidence="candidate",
                    issue_key=signature,
                )
            )
    return issues


def multipart_issues(records: list[dict[str, Any]], rule: dict[str, Any], run_id: str, created_at: str, source_layer: str, asset_id_field: str | None) -> list[dict[str, Any]]:
    issues = []
    for record in records:
        if (record.get("geometry") or {}).get("is_multipart"):
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer=source_layer,
                    source_asset_id=safe_asset_id(record, asset_id_field),
                    source_objectid=record["objectid"],
                    description=f"{source_layer} OBJECTID {record['objectid']} has multipart geometry.",
                    geometry=record.get("geometry"),
                    confidence="candidate",
                    issue_key="multipart",
                )
            )
    return issues


def pipe_anomaly_issues(pipes: list[dict[str, Any]], rule: dict[str, Any], run_id: str, created_at: str, asset_id_field: str | None) -> list[dict[str, Any]]:
    issues = []
    for record in pipes:
        points = first_path(record.get("geometry") or {})
        if len(points) < 2:
            continue
        repeated = len(points) != len({(round(x, 4), round(y, 4)) for x, y in points})
        closed = round(points[0][0], 4) == round(points[-1][0], 4) and round(points[0][1], 4) == round(points[-1][1], 4)
        if repeated or closed:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(record, asset_id_field),
                    source_objectid=record["objectid"],
                    description=f"Pipe OBJECTID {record['objectid']} has {'closed-line' if closed else 'repeated-vertex'} geometry behavior.",
                    geometry=record.get("geometry"),
                    confidence="candidate",
                    issue_key=f"{repeated}:{closed}",
                )
            )
    return issues


def geometry_signature(geometry: dict[str, Any]) -> str:
    if geometry.get("type") == "point":
        return f"point:{round(float(geometry.get('x', 0)), 3)}:{round(float(geometry.get('y', 0)), 3)}"
    points = first_path(geometry)
    if not points:
        return ""
    return "line:" + ";".join(f"{round(x, 3)},{round(y, 3)}" for x, y in points)


def first_path(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    paths = geometry.get("paths") or []
    if not paths:
        return []
    return [(float(x), float(y)) for x, y in paths[0]]
