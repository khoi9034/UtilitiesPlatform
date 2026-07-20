from __future__ import annotations

from typing import Any

from .field_mapping import blankish, number_or_none
from .issue_writer import make_issue


def missing_field_issues(
    records: list[dict[str, Any]],
    field_name: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    source_layer: str,
    asset_id_field: str | None = None,
) -> list[dict[str, Any]]:
    issues = []
    for record in records:
        value = record["attributes"].get(field_name)
        if blankish(value) or (field_name.upper() == "YR" and str(value).strip() in {"0", "1"}):
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer=source_layer,
                    source_asset_id=safe_asset_id(record, asset_id_field),
                    source_objectid=record["objectid"],
                    description=f"{source_layer} OBJECTID {record['objectid']} has no usable value in {field_name}.",
                    geometry=record.get("geometry"),
                    confidence="high",
                    issue_key=field_name,
                )
            )
    return issues


def invalid_diameter_issues(
    records: list[dict[str, Any]],
    field_name: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    min_inches = float(rule.get("parameters", {}).get("min_inches", 4))
    max_inches = float(rule.get("parameters", {}).get("max_inches", 240))
    issues = []
    for record in records:
        value = number_or_none(record["attributes"].get(field_name))
        if value is None or value < min_inches or value > max_inches:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer="wastewater_gravity_main",
                    source_asset_id=safe_asset_id(record, asset_id_field),
                    source_objectid=record["objectid"],
                    description=f"Pipe OBJECTID {record['objectid']} has diameter {record['attributes'].get(field_name)!r}, outside {min_inches:g}-{max_inches:g} inches.",
                    geometry=record.get("geometry"),
                    threshold_used=f"{min_inches:g}-{max_inches:g} inches",
                    confidence="high",
                    issue_key=f"{field_name}:{record['attributes'].get(field_name)}",
                )
            )
    return issues


def invalid_domain_issues(
    records: list[dict[str, Any]],
    domain_values: dict[str, set[str]],
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    source_layer: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    issues = []
    for record in records:
        for field_name, allowed in domain_values.items():
            value = record["attributes"].get(field_name)
            if not blankish(value) and str(value) not in allowed:
                issues.append(
                    make_issue(
                        run_id=run_id,
                        created_at=created_at,
                        rule=rule,
                        source_layer=source_layer,
                        source_asset_id=safe_asset_id(record, asset_id_field),
                        source_objectid=record["objectid"],
                        description=f"{source_layer} OBJECTID {record['objectid']} has value {value!r} outside domain for {field_name}.",
                        geometry=record.get("geometry"),
                        confidence="high",
                        issue_key=f"{field_name}:{value}",
                    )
                )
    return issues


def conflicting_status_issues(
    records: list[dict[str, Any]],
    lifecycle_field: str,
    operational_field: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    source_layer: str,
    asset_id_field: str | None,
) -> list[dict[str, Any]]:
    conflicts = {("abandoned", "active"), ("retired", "active"), ("inactive", "active")}
    issues = []
    for record in records:
        lifecycle = str(record["attributes"].get(lifecycle_field, "")).strip().lower()
        operational = str(record["attributes"].get(operational_field, "")).strip().lower()
        if (lifecycle, operational) in conflicts:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer=source_layer,
                    source_asset_id=safe_asset_id(record, asset_id_field),
                    source_objectid=record["objectid"],
                    description=f"{source_layer} OBJECTID {record['objectid']} has conflicting lifecycle {lifecycle!r} and operational {operational!r} statuses.",
                    geometry=record.get("geometry"),
                    confidence="candidate",
                    issue_key=f"{lifecycle}:{operational}",
                )
            )
    return issues


def safe_asset_id(record: dict[str, Any], field_name: str | None) -> str:
    if not field_name:
        return ""
    value = record["attributes"].get(field_name)
    return "" if blankish(value) else str(value).strip()
