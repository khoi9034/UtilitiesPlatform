from __future__ import annotations

import csv
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import ISSUE_FIELDS


def issue_id(run_id: str, *parts: Any) -> str:
    key = "|".join(str(part) for part in (run_id, *parts))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"utilities-platform:wastewater:{key}"))


def make_issue(
    *,
    run_id: str,
    created_at: str,
    rule: dict[str, Any],
    source_layer: str,
    source_asset_id: str,
    source_objectid: str | int,
    description: str,
    geometry: dict[str, Any] | None,
    related_asset_id: str = "",
    related_objectid: str | int = "",
    threshold_used: str = "",
    confidence: str = "high",
    why_it_matters: str = "",
    issue_key: str = "",
) -> dict[str, Any]:
    hierarchy = {
        "wastewater_gravity_main": ("gravity_network", "pipe", "gravity_main"),
        "wastewater_manhole": ("structures", "access_structure", "manhole"),
        "network": ("gravity_network", "network", "proximity_component"),
    }.get(source_layer, ("gravity_network", "network", "proximity_component"))
    return {
        "issue_id": issue_id(run_id, rule["rule_code"], source_layer, source_objectid, related_objectid, issue_key or description),
        "rule_code": rule["rule_code"],
        "rule_name": rule["name"],
        "category": rule["category"],
        "severity": rule["severity"],
        "utility_system": "wastewater",
        "network_group": hierarchy[0],
        "asset_category": hierarchy[1],
        "asset_subcategory": hierarchy[2],
        "source_layer": source_layer,
        "source_asset_id": source_asset_id or "",
        "source_objectid": str(source_objectid or ""),
        "related_asset_id": related_asset_id or "",
        "related_objectid": str(related_objectid or ""),
        "description": description,
        "why_it_matters": why_it_matters or rule["description"],
        "recommended_action": rule["recommended_action"],
        "detection_method": rule["detection_method"],
        "threshold_used": threshold_used,
        "confidence": confidence,
        "review_status": "open",
        "reviewer": "",
        "reviewed_at": "",
        "resolution_notes": "",
        "run_id": run_id,
        "created_at": created_at,
        "geometry": geometry or {},
    }


def dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for issue in issues:
        key = issue["issue_id"]
        if key in seen:
            continue
        seen.add(key)
        output.append(issue)
    return output


def write_issue_files(issues: list[dict[str, Any]], csv_path: Path, json_path: Path, geojson_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_FIELDS)
        writer.writeheader()
        for issue in issues:
            writer.writerow({field: issue.get(field, "") for field in ISSUE_FIELDS})
    json_path.write_text(json.dumps({"issues": issues}, indent=2), encoding="utf-8")
    geojson_path.write_text(json.dumps(issue_geojson(issues), indent=2), encoding="utf-8")


def issue_geojson(issues: list[dict[str, Any]]) -> dict[str, Any]:
    features = []
    for issue in issues:
        geometry = to_geojson_geometry(issue.get("geometry") or {})
        if not geometry:
            continue
        features.append(
            {
                "type": "Feature",
                "id": issue["issue_id"],
                "geometry": geometry,
                "properties": {field: issue.get(field, "") for field in ISSUE_FIELDS},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def to_geojson_geometry(geometry: dict[str, Any]) -> dict[str, Any] | None:
    if geometry.get("type") == "point":
        return {"type": "Point", "coordinates": [geometry["x"], geometry["y"]]}
    if geometry.get("type") == "polyline":
        paths = geometry.get("paths") or []
        if not paths:
            return None
        return {"type": "LineString", "coordinates": paths[0]}
    return None


def safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def write_geodatabase_issues(
    output_gdb: Path,
    issues: list[dict[str, Any]],
    spatial_reference_wkid: int,
    *,
    replace_output: bool = False,
) -> dict[str, int]:
    import arcpy  # type: ignore

    if not output_gdb.exists():
        arcpy.management.CreateFileGDB(str(output_gdb.parent), output_gdb.stem)
    targets = {
        "ww_pipe_issues": ("POLYLINE", [issue for issue in issues if issue.get("geometry", {}).get("type") == "polyline"]),
        "ww_manhole_issues": (
            "POINT",
            [
                issue
                for issue in issues
                if issue.get("geometry", {}).get("type") == "point" and issue.get("source_layer") == "wastewater_manhole"
            ],
        ),
        "ww_network_issues": (
            "POINT",
            [
                issue
                for issue in issues
                if issue.get("geometry", {}).get("type") == "point" and issue.get("source_layer") != "wastewater_manhole"
            ],
        ),
    }
    counts: dict[str, int] = {}
    sr = arcpy.SpatialReference(spatial_reference_wkid)
    for name, (geometry_type, rows) in targets.items():
        path = output_gdb / name
        if arcpy.Exists(str(path)):
            if not replace_output:
                raise FileExistsError(f"{path} already exists. Use --replace-output to overwrite generated QA outputs.")
            arcpy.management.Delete(str(path))
        arcpy.management.CreateFeatureclass(str(output_gdb), name, geometry_type, spatial_reference=sr)
        add_issue_fields(arcpy, path)
        fields = ["SHAPE@"] + ISSUE_FIELDS
        with arcpy.da.InsertCursor(str(path), fields) as cursor:
            for issue in rows:
                cursor.insertRow([to_arcpy_geometry(arcpy, issue["geometry"], sr)] + [str(issue.get(field, "")) for field in ISSUE_FIELDS])
        counts[name] = len(rows)
    return counts


def add_issue_fields(arcpy: Any, path: Path) -> None:
    long_fields = {"description", "why_it_matters", "recommended_action", "detection_method", "resolution_notes"}
    for field in ISSUE_FIELDS:
        length = 1000 if field in long_fields else 255
        arcpy.management.AddField(str(path), field, "TEXT", field_length=length)


def to_arcpy_geometry(arcpy: Any, geometry: dict[str, Any], spatial_reference: Any) -> Any:
    if geometry["type"] == "point":
        return arcpy.PointGeometry(arcpy.Point(float(geometry["x"]), float(geometry["y"])), spatial_reference)
    array = arcpy.Array([arcpy.Point(float(x), float(y)) for x, y in geometry.get("paths", [[]])[0]])
    return arcpy.Polyline(array, spatial_reference)


def append_processing_history(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "run_id",
        "dataset_id",
        "process_name",
        "input_path",
        "output_path",
        "started_at",
        "completed_at",
        "status",
        "records_read",
        "records_written",
        "warnings",
        "errors",
        "operator",
        "script_version",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
