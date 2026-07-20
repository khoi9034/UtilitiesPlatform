from __future__ import annotations

from collections import defaultdict
from typing import Any

from .field_mapping import blankish
from .issue_writer import make_issue


def missing_id_issues(
    records: list[dict[str, Any]],
    field_name: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    source_layer: str,
) -> list[dict[str, Any]]:
    issues = []
    for record in records:
        if blankish(record["attributes"].get(field_name)):
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer=source_layer,
                    source_asset_id="",
                    source_objectid=record["objectid"],
                    description=f"{source_layer} OBJECTID {record['objectid']} has no mapped asset ID in {field_name}.",
                    geometry=record.get("geometry"),
                    confidence="high",
                    issue_key=field_name,
                )
            )
    return issues


def duplicate_id_issues(
    records: list[dict[str, Any]],
    field_name: str,
    rule: dict[str, Any],
    run_id: str,
    created_at: str,
    source_layer: str,
) -> list[dict[str, Any]]:
    by_value: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        value = record["attributes"].get(field_name)
        if not blankish(value):
            by_value[str(value).strip()].append(record)
    issues = []
    for value, matches in sorted(by_value.items()):
        if len(matches) < 2:
            continue
        for record in matches:
            issues.append(
                make_issue(
                    run_id=run_id,
                    created_at=created_at,
                    rule=rule,
                    source_layer=source_layer,
                    source_asset_id=value,
                    source_objectid=record["objectid"],
                    related_asset_id=value,
                    related_objectid=",".join(str(item["objectid"]) for item in matches if item["objectid"] != record["objectid"]),
                    description=f"{source_layer} asset ID {value} appears on {len(matches)} features.",
                    geometry=record.get("geometry"),
                    confidence="candidate",
                    issue_key=value,
                )
            )
    return issues


def identity_metrics(records: list[dict[str, Any]], field_name: str | None) -> dict[str, int]:
    if not field_name:
        return {"available": 0, "total": len(records), "missing": len(records), "duplicates": 0}
    values = [str(record["attributes"].get(field_name)).strip() for record in records if not blankish(record["attributes"].get(field_name))]
    duplicates = len(values) - len(set(values))
    return {"available": len(values), "total": len(records), "missing": len(records) - len(values), "duplicates": duplicates}
