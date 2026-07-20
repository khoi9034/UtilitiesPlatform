from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PIPE_ROLES: dict[str, tuple[str | None, str, str]] = {
    "asset_id": ("WSACC_ID", "high", "Source business ID field; high distinctness with some blank placeholders."),
    "facility_id": ("WSACC_ID", "medium", "Same source ID appears to serve as the business/facility identifier."),
    "upstream_manhole_id": ("U_S_NODE", "high", "Field name explicitly indicates upstream node."),
    "downstream_manhole_id": ("D_S_NODE", "high", "Field name explicitly indicates downstream node."),
    "from_node": ("U_S_NODE", "high", "Field name explicitly indicates upstream/from node."),
    "to_node": ("D_S_NODE", "high", "Field name explicitly indicates downstream/to node."),
    "diameter": ("SZ", "high", "Short size field with numeric pipe diameter-like values."),
    "material": ("MA", "high", "Short material field with pipe material-like values such as PVC and RCP."),
    "lifecycle_status": ("STATUS", "high", "Status field contains active/abandoned values."),
    "operational_status": ("STATUS", "medium", "Status field may also represent operating state; same source field as lifecycle status."),
    "pipe_type": ("TYPE", "high", "Type field contains gravity/forcemain/siphon values."),
    "install_date": ("YR", "low", "Year-like integer field; not a true date and requires source confirmation."),
    "upstream_invert": ("INVERTIN", "medium", "Invert-in field is treated as upstream invert for screening only."),
    "downstream_invert": ("INVERTOUT", "medium", "Invert-out field is treated as downstream invert for screening only."),
    "slope": (None, "unavailable", "No reliable source slope field found."),
    "length": ("LENGTH", "high", "Length field is present; geometry length is also available for QA."),
    "owner": ("SRCENT", "medium", "Source entity field likely identifies source owner/maintainer."),
    "project_id": (None, "unavailable", "No project ID field found."),
    "work_order_id": (None, "unavailable", "No work order ID field found."),
}

MANHOLE_ROLES: dict[str, tuple[str | None, str, str]] = {
    "asset_id": ("NEW_ID", "medium", "Prior inventory selected NEW_ID; field has manhole-style IDs but some blanks and duplicates."),
    "facility_id": ("WSACC_ID", "high", "Source business ID field with high distinctness."),
    "rim_elevation": ("RIM_ELEV", "high", "Field name explicitly indicates rim elevation."),
    "invert_elevation": ("INVERTOUT", "medium", "Invert-out field provides a likely representative invert elevation."),
    "lifecycle_status": ("STATUS", "high", "Status field contains active/abandoned values."),
    "operational_status": ("STATUS", "medium", "Status field may also represent operating state; same source field as lifecycle status."),
    "material": (None, "unavailable", "No reliable manhole material field found."),
    "manhole_type": (None, "unavailable", "No reliable manhole type field found."),
    "install_date": ("YR", "low", "Year-like integer field has many placeholders and requires source confirmation."),
    "condition": ("MH_Audit", "medium", "Audit field contains attention/abandoned markers and may support condition review."),
    "basin": (None, "unavailable", "Subbasin is available on pipes but no reliable manhole basin field found."),
    "owner": ("SRCENT", "medium", "Source entity field likely identifies source owner/maintainer."),
    "project_id": (None, "unavailable", "No project ID field found."),
    "work_order_id": (None, "unavailable", "No work order ID field found."),
}

MAPPING_COLUMNS = [
    "source_layer",
    "source_field",
    "field_alias",
    "semantic_role",
    "confidence",
    "evidence",
    "null_count",
    "null_percentage",
    "distinct_count",
    "notes",
]


@dataclass(frozen=True)
class FieldProfile:
    name: str
    alias: str
    type: str
    length: int
    nullable: bool
    required: bool
    domain: str
    null_count: int
    null_percentage: float
    distinct_count: int
    top_values: list[tuple[str, int]]


def blankish(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"<null>", "null", "none", "-9999-"}


def number_or_none(value: Any) -> float | None:
    if blankish(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def profiles_from_records(fields: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, FieldProfile]:
    total = max(len(records), 1)
    profiles: dict[str, FieldProfile] = {}
    for field in fields:
        name = field["name"]
        if field["type"] in {"Geometry", "Blob", "Raster"}:
            null_count = 0
            distinct: set[str] = set()
            top_values: list[tuple[str, int]] = []
        else:
            values = [record.get(name) for record in records]
            null_count = sum(1 for value in values if blankish(value))
            counts: dict[str, int] = {}
            distinct = set()
            for value in values:
                if blankish(value):
                    continue
                text = str(value)
                distinct.add(text)
                if len(text) <= 80:
                    counts[text] = counts.get(text, 0) + 1
            top_values = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        profiles[name] = FieldProfile(
            name=name,
            alias=field.get("alias", name),
            type=field.get("type", ""),
            length=int(field.get("length") or 0),
            nullable=bool(field.get("nullable", True)),
            required=bool(field.get("required", False)),
            domain=field.get("domain", ""),
            null_count=null_count,
            null_percentage=round(null_count * 100 / total, 2),
            distinct_count=len(distinct),
            top_values=top_values,
        )
    return profiles


def build_field_mapping(layer_name: str, profiles: dict[str, FieldProfile]) -> list[dict[str, str]]:
    specs = PIPE_ROLES if layer_name == "wastewater_gravity_main" else MANHOLE_ROLES
    rows: list[dict[str, str]] = []
    for role, (field_name, confidence, evidence) in specs.items():
        profile = profiles.get(field_name or "")
        rows.append(
            {
                "source_layer": layer_name,
                "source_field": field_name or "",
                "field_alias": profile.alias if profile else "",
                "semantic_role": role,
                "confidence": confidence if profile or field_name is None else "unavailable",
                "evidence": evidence if profile or field_name is None else f"Configured candidate field {field_name} was not found.",
                "null_count": str(profile.null_count) if profile else "",
                "null_percentage": f"{profile.null_percentage:.2f}" if profile else "",
                "distinct_count": str(profile.distinct_count) if profile else "",
                "notes": "" if profile or field_name is None else "Candidate field unavailable in staged layer.",
            }
        )
    return rows


def mapping_lookup(mapping_rows: list[dict[str, str]], layer_name: str) -> dict[str, str]:
    return {
        row["semantic_role"]: row["source_field"]
        for row in mapping_rows
        if row["source_layer"] == layer_name and row["source_field"] and row["confidence"] != "unavailable"
    }


def role_available(mapping_rows: list[dict[str, str]], layer_name: str, role: str) -> bool:
    return bool(mapping_lookup(mapping_rows, layer_name).get(role))


def write_mapping_reports(rows: list[dict[str, str]], output_csv: Path, output_json: Path, review_md: Path, layer_meta: dict[str, Any]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MAPPING_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    output_json.write_text(json.dumps({"layers": layer_meta, "mappings": rows}, indent=2), encoding="utf-8")
    lines = [
        "# Wastewater Schema Review",
        "",
        "This review uses staged wastewater layers only. Field mappings are inferred from field names, aliases, domains, types, null rates, distinct counts, and safe aggregate value patterns.",
        "",
    ]
    for layer_name, meta in layer_meta.items():
        lines += [
            f"## {layer_name}",
            "",
            f"- Geometry: {meta.get('geometry_type', '')}",
            f"- Records: {meta.get('record_count', 0)}",
            f"- Spatial reference: {meta.get('spatial_reference', '')}",
            f"- Linear unit: {meta.get('linear_unit', '')}",
            f"- Z/M: {meta.get('has_z', False)} / {meta.get('has_m', False)}",
            f"- GlobalID field: {meta.get('globalid', '') or 'None reported'}",
            f"- Editor tracking: {meta.get('editor_tracking_enabled', False)}",
            f"- Attachments: {meta.get('attachments', False)}",
            "",
            "| Semantic role | Source field | Confidence | Evidence | Nulls | Distinct |",
            "|---|---:|---|---|---:|---:|",
        ]
        for row in rows:
            if row["source_layer"] == layer_name:
                lines.append(
                    f"| {row['semantic_role']} | {row['source_field'] or 'Unavailable'} | {row['confidence']} | {row['evidence']} | {row['null_count']} | {row['distinct_count']} |"
                )
        lines.append("")
    review_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
