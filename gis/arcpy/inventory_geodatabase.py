from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[1]
sys.path.insert(0, str(CURRENT_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "data_storage"))

from classify_utility_layers import classify_layer
from common import DATA_CATALOG_COLUMNS, append_catalog_row, load_config, read_catalog, write_csv_header_if_missing

REPORT_COLUMNS = [
    "dataset_id",
    "source_name",
    "source_path",
    "source_format",
    "utility_system",
    "network_group",
    "asset_category",
    "asset_subcategory",
    "classification_confidence",
    "likely_classifications",
    "recommended_classification",
    "feature_dataset",
    "layer_name",
    "geometry_type",
    "record_count",
    "spatial_reference",
    "unique_id_field",
    "status_field",
    "material_field",
    "diameter_field",
    "install_date_field",
    "inspection_date_field",
    "project_id_field",
    "work_order_field",
    "has_domains",
    "has_subtypes",
    "has_relationships",
    "has_attachments",
    "editor_tracking_enabled",
    "sensitivity_level",
    "recommended_action",
    "notes",
]

DISCOVERY_COLUMNS = [
    "source_name",
    "source_path",
    "source_format",
    "file_size",
    "last_modified",
    "arcpy_required",
    "can_inspect",
    "error",
]

FIELD_PROFILE_COLUMNS = [
    "dataset_id",
    "layer_name",
    "field_name",
    "field_type",
    "null_count",
    "null_percentage",
    "distinct_count",
    "duplicate_count",
    "min_date",
    "max_date",
    "common_values",
]

ALLOWLIST_COLUMNS = [
    "dataset_id",
    "source_layer_name",
    "target_layer_name",
    "utility_system",
    "network_group",
    "asset_category",
    "asset_subcategory",
    "approved_to_stage",
    "reason",
    "reviewed_by",
    "reviewed_at",
]

SIDECAR_SUFFIXES = {".dbf", ".shx", ".prj", ".cpg", ".sbn", ".sbx", ".xml", ".lock", ".sr.lock"}
SUPPORTED_FILE_SUFFIXES = {
    ".shp": "shapefile",
    ".gpkg": "geopackage",
    ".dwg": "cad",
    ".dxf": "cad",
    ".csv": "csv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".tif": "raster",
    ".tiff": "raster",
    ".sde": "enterprise_geodatabase_export",
}


def safe_name(value: str) -> str:
    name = "".join(char if char.isalnum() else "_" for char in value)
    return "_".join(part for part in name.split("_") if part).lower()[:60]


def discover_sources(raw_root: Path) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    consumed: set[Path] = set()
    for path in sorted(raw_root.rglob("*")):
        if path in consumed:
            continue
        suffix = path.suffix.lower()
        try:
            if path.is_dir() and suffix == ".gdb":
                sources.append(source_row(path, "file_geodatabase"))
                consumed.update(path.rglob("*"))
            elif path.is_file() and suffix in SUPPORTED_FILE_SUFFIXES and suffix not in SIDECAR_SUFFIXES:
                sources.append(source_row(path, SUPPORTED_FILE_SUFFIXES[suffix]))
        except OSError as exc:
            sources.append(source_row(path, "unknown", can_inspect=False, error=str(exc)))
    return sources


def source_row(path: Path, source_format: str, can_inspect: bool = True, error: str = "") -> dict[str, str]:
    stat = path.stat()
    return {
        "source_name": path.name,
        "source_path": str(path),
        "source_format": source_format,
        "file_size": "" if path.is_dir() else str(stat.st_size),
        "last_modified": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "arcpy_required": "true" if source_format in {"file_geodatabase", "enterprise_geodatabase_export", "shapefile", "cad", "geopackage", "raster"} else "false",
        "can_inspect": str(can_inspect and source_format in {"file_geodatabase", "shapefile"}).lower(),
        "error": error,
    }


def load_arcpy() -> Any:
    try:
        import arcpy  # type: ignore
    except ImportError as exc:
        raise RuntimeError("ArcPy is required for geodatabase and shapefile inventory.") from exc
    return arcpy


def describe_layer(arcpy: Any, source: dict[str, str], layer_path: Path, feature_dataset: str = "") -> dict[str, Any]:
    description = arcpy.Describe(str(layer_path))
    fields = list(arcpy.ListFields(str(layer_path)))
    field_names = [field.name for field in fields]
    field_context = [f"{field.name} {getattr(field, 'aliasName', '')}" for field in fields]
    classification = classify_layer(layer_path.stem, field_context, getattr(description, "shapeType", ""), source["source_name"])
    row = {
        "source_name": source["source_name"],
        "source_path": source["source_path"],
        "source_format": source["source_format"],
        "feature_dataset": feature_dataset,
        "layer_name": layer_path.stem,
        "layer_path": str(layer_path),
        "geometry_type": getattr(description, "shapeType", ""),
        "record_count": int(arcpy.management.GetCount(str(layer_path))[0]),
        "spatial_reference": getattr(getattr(description, "spatialReference", None), "name", ""),
        "fields": [field_info(field) for field in fields],
        "field_names": field_names,
        "extent": extent_info(description),
        "has_domains": any(getattr(field, "domain", "") for field in fields),
        "has_subtypes": bool(arcpy.da.ListSubtypes(str(layer_path))),
        "has_relationships": bool(getattr(description, "relationshipClassNames", [])),
        "has_attachments": bool(getattr(description, "hasAttachments", False)),
        "editor_tracking_enabled": bool(getattr(description, "editorTrackingEnabled", False)),
        "has_z": bool(getattr(description, "hasZ", False)),
        "has_m": bool(getattr(description, "hasM", False)),
        "indexes": [index.name for index in arcpy.ListIndexes(str(layer_path))],
    }
    row.update(classification)
    row.update(match_common_fields(row["fields"]))
    row["notes"] = row.get("classification_notes", "")
    row["sensitivity_level"] = sensitivity_for(row)
    row["recommended_action"] = recommended_action(row)
    return row


def extent_info(description: Any) -> dict[str, float] | None:
    extent = getattr(description, "extent", None)
    if not extent:
        return None
    return {
        "xmin": float(extent.XMin),
        "ymin": float(extent.YMin),
        "xmax": float(extent.XMax),
        "ymax": float(extent.YMax),
    }


def field_info(field: Any) -> dict[str, Any]:
    return {
        "name": field.name,
        "alias": field.aliasName,
        "type": field.type,
        "required": bool(field.required),
        "nullable": bool(field.isNullable),
        "domain": field.domain or "",
    }


def match_common_fields(fields: list[dict[str, Any]]) -> dict[str, str]:
    names = {field["name"]: f"{field['name']} {field.get('alias', '')}".lower() for field in fields}
    patterns = {
        "unique_id_field": ["globalid", "assetid", "asset_id", "facilityid", "facility_id", "new_id", "objectid", "fid"],
        "status_field": ["status", "active", "condition"],
        "material_field": ["material", "matl", "pipe_mat", " ma "],
        "diameter_field": ["diameter", "diam", "size", "width", " sz "],
        "install_date_field": ["install", "installed", "in_service", "date_inst"],
        "inspection_date_field": ["inspect", "lastinsp"],
        "owner_field": ["owner", "owned"],
        "project_id_field": ["project", "proj_id"],
        "work_order_field": ["work", "wo_", "workorder"],
    }
    result: dict[str, str] = {}
    for output, keywords in patterns.items():
        result[output] = next((name for keyword in keywords for name, text in names.items() if keyword in f" {text} "), "")
    return result


def sensitivity_for(layer: dict[str, Any]) -> str:
    if layer["utility_system"] in {"water", "wastewater", "stormwater", "telecom", "electric", "gas", "review_required"}:
        return "restricted"
    if layer["utility_system"] in {"reference", "shared_reference"}:
        return "internal"
    return "restricted"


def recommended_action(layer: dict[str, Any]) -> str:
    if layer["utility_system"] == "review_required":
        return "review_required"
    if layer["classification_confidence"] == "high" and layer["spatial_reference"] and not layer["notes"]:
        return "candidate_for_staging_review"
    if layer["classification_confidence"] in {"unknown", "low"}:
        return "manual_review"
    return "defer_until_reviewed"


def extents_intersect(left: dict[str, float] | None, right: dict[str, float] | None) -> bool:
    if not left or not right:
        return False
    return not (
        left["xmax"] < right["xmin"]
        or left["xmin"] > right["xmax"]
        or left["ymax"] < right["ymin"]
        or left["ymin"] > right["ymax"]
    )


def apply_contextual_review_recommendations(layers: list[dict[str, Any]]) -> None:
    wastewater_layers = [layer for layer in layers if layer.get("utility_system") == "wastewater"]
    for layer in layers:
        if layer.get("utility_system") != "review_required" or layer.get("asset_subcategory") != "subbasin":
            continue
        evidence = []
        context = " ".join([layer.get("source_name", ""), layer.get("layer_name", ""), *layer.get("field_names", [])]).lower()
        if "wsacc" in context or "sewer" in context or "wastewater" in context:
            evidence.append("source or attribute context references a water/sewer utility context")
        if any(
            other.get("spatial_reference") == layer.get("spatial_reference")
            and extents_intersect(layer.get("extent"), other.get("extent"))
            for other in wastewater_layers
        ):
            evidence.append("layer extent overlaps inventoried wastewater infrastructure")
        if evidence:
            layer["recommended_classification"] = "wastewater / operational_areas / sewer_basin / subbasin"
            layer["notes"] = (
                "Review required; most likely wastewater sewer basin based on "
                + "; ".join(evidence)
                + ". Stormwater drainage basin remains a candidate until confirmed."
            )
        else:
            layer["notes"] = "Review required; subbasin could be wastewater sewer basin or stormwater drainage basin."
        layer["sensitivity_level"] = sensitivity_for(layer)
        layer["recommended_action"] = recommended_action(layer)


def inventory_sources(sources: list[dict[str, str]]) -> list[dict[str, Any]]:
    arcpy = load_arcpy()
    layers: list[dict[str, Any]] = []
    for source in sources:
        if source["source_format"] == "shapefile" and source["can_inspect"] == "true":
            layers.append(describe_layer(arcpy, source, Path(source["source_path"])))
        elif source["source_format"] == "file_geodatabase" and source["can_inspect"] == "true":
            layers.extend(inventory_file_geodatabase(arcpy, source))
    return layers


def inventory_file_geodatabase(arcpy: Any, source: dict[str, str]) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    root = Path(source["source_path"])
    arcpy.env.workspace = str(root)
    for dirpath, _, filenames in arcpy.da.Walk(str(root), datatype=["FeatureClass"]):
        feature_dataset = "" if Path(dirpath) == root else Path(dirpath).name
        for filename in filenames:
            layers.append(describe_layer(arcpy, source, Path(dirpath) / filename, feature_dataset))
    return layers


def profile_fields(arcpy: Any, layers: list[dict[str, Any]], limit: int = 10) -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    for layer in layers:
        if layer["classification_confidence"] not in {"high", "medium"} or layer["utility_system"] in {"reference", "shared_reference", "unknown", "review_required"}:
            continue
        fields = [field for field in layer["fields"] if field["type"] not in {"Geometry", "OID", "Blob", "Raster"}]
        cursor_fields = [field["name"] for field in fields]
        if not cursor_fields:
            continue
        stats = {
            field["name"]: {"nulls": 0, "values": Counter(), "distinct": set(), "min_date": None, "max_date": None, "type": field["type"]}
            for field in fields
        }
        with arcpy.da.SearchCursor(layer["layer_path"], cursor_fields) as cursor:
            for record in cursor:
                for field_name, value in zip(cursor_fields, record):
                    item = stats[field_name]
                    if value in (None, ""):
                        item["nulls"] += 1
                        continue
                    item["distinct"].add(value)
                    if len(item["values"]) < 5000:
                        item["values"][str(value)] += 1
                    if isinstance(value, (dt.datetime, dt.date)):
                        item["min_date"] = value if item["min_date"] is None or value < item["min_date"] else item["min_date"]
                        item["max_date"] = value if item["max_date"] is None or value > item["max_date"] else item["max_date"]
        total = max(int(layer["record_count"]), 1)
        id_field = layer.get("unique_id_field", "")
        for field_name, item in stats.items():
            duplicate_count = 0
            if field_name == id_field:
                duplicate_count = sum(count - 1 for count in item["values"].values() if count > 1)
            profiles.append(
                {
                    "dataset_id": layer["dataset_id"],
                    "layer_name": layer["layer_name"],
                    "field_name": field_name,
                    "field_type": item["type"],
                    "null_count": str(item["nulls"]),
                    "null_percentage": f"{(item['nulls'] / total) * 100:.2f}",
                    "distinct_count": str(len(item["distinct"])),
                    "duplicate_count": str(duplicate_count),
                    "min_date": str(item["min_date"] or ""),
                    "max_date": str(item["max_date"] or ""),
                    "common_values": json.dumps(item["values"].most_common(limit)),
                }
            )
    return profiles


def register_layers(layers: list[dict[str, Any]], dry_run: bool = False) -> None:
    config = load_config()
    existing = read_catalog(config)
    existing_keys = {(row.get("dataset_name"), row.get("source_path"), row.get("source_layer_name")): row for row in existing}
    changed = False
    for layer in layers:
        key = (layer["layer_name"], layer["source_path"], layer["layer_name"])
        if key in existing_keys:
            row = existing_keys[key]
            layer["dataset_id"] = row.get("dataset_id", "")
            for column, value in catalog_values(layer).items():
                if row.get(column, "") != str(value):
                    row[column] = str(value)
                    changed = True
            continue
        row = {column: "" for column in DATA_CATALOG_COLUMNS}
        row.update(catalog_values(layer))
        if dry_run:
            layer["dataset_id"] = ""
        else:
            layer["dataset_id"] = append_catalog_row(config, row)
    if changed and not dry_run:
        write_csv(config.data_catalog, existing, DATA_CATALOG_COLUMNS)


def catalog_values(layer: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_name": layer["layer_name"],
        "utility_system": layer["utility_system"],
        "network_group": layer["network_group"],
        "asset_category": layer["asset_category"],
        "asset_subcategory": layer["asset_subcategory"],
        "source_format": layer["source_format"],
        "source_path": layer["source_path"],
        "source_layer_name": layer["layer_name"],
        "geometry_type": layer["geometry_type"],
        "coordinate_system": layer["spatial_reference"],
        "unique_id_field": layer["unique_id_field"],
        "record_count": layer["record_count"],
        "sensitivity_level": layer["sensitivity_level"],
        "date_inventoried": dt.datetime.now().date().isoformat(),
        "current_stage": "raw",
        "approved_for_analysis": "false",
        "approved_for_export": "false",
        "approved_for_public_use": "false",
        "notes": layer.get("notes") or "Registered by read-only inventory workflow.",
    }


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_reports(report_root: Path, sources: list[dict[str, str]], layers: list[dict[str, Any]], profiles: list[dict[str, str]]) -> None:
    write_csv(report_root / "source_discovery.csv", sources, DISCOVERY_COLUMNS)
    (report_root / "source_discovery.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    write_csv(report_root / "utility_data_inventory.csv", layers, REPORT_COLUMNS)
    (report_root / "utility_data_inventory.json").write_text(json.dumps({"layers": layers}, indent=2, default=str), encoding="utf-8")
    write_csv(report_root / "field_profile_summary.csv", profiles, FIELD_PROFILE_COLUMNS)
    write_allowlist(report_root.parents[1] / "00_admin" / "staging_allowlist.csv", layers)
    write_markdown(report_root / "utility_data_inventory.md", sources, layers)
    write_recommendation(report_root / "staging_recommendation.md", layers)


def write_allowlist(path: Path, layers: list[dict[str, Any]]) -> None:
    existing: dict[tuple[str, str], dict[str, str]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                existing[(row.get("dataset_id", ""), row.get("source_layer_name", ""))] = row
    rows = []
    for layer in layers:
        if layer["recommended_action"] == "candidate_for_staging_review":
            previous = existing.get((layer["dataset_id"], layer["layer_name"]), {})
            target_layer_name = f"{layer['utility_system']}_{safe_name(layer.get('asset_subcategory') or layer['asset_category'])}"
            rows.append(
                {
                    "dataset_id": layer["dataset_id"],
                    "source_layer_name": layer["layer_name"],
                    "target_layer_name": target_layer_name,
                    "utility_system": layer["utility_system"],
                    "network_group": layer["network_group"],
                    "asset_category": layer["asset_category"],
                    "asset_subcategory": layer["asset_subcategory"],
                    "approved_to_stage": previous.get("approved_to_stage", "false"),
                    "reason": previous.get("reason") or "High-confidence read-only inventory candidate; awaiting human approval.",
                    "reviewed_by": previous.get("reviewed_by", ""),
                    "reviewed_at": previous.get("reviewed_at", ""),
                }
            )
    write_csv(path, rows, ALLOWLIST_COLUMNS)


def write_markdown(path: Path, sources: list[dict[str, str]], layers: list[dict[str, Any]]) -> None:
    by_system = defaultdict(list)
    records = Counter()
    spatial_refs = Counter(layer["spatial_reference"] or "Unknown" for layer in layers)
    for layer in layers:
        by_system[layer["utility_system"]].append(layer)
        records[layer["utility_system"]] += int(layer["record_count"] or 0)
    high = [layer for layer in layers if layer["classification_confidence"] == "high"]
    ambiguous = [
        layer
        for layer in layers
        if layer["utility_system"] in {"unknown", "review_required"} or layer["classification_confidence"] in {"unknown", "low"}
    ]
    candidates = [layer for layer in layers if layer["recommended_action"] == "candidate_for_staging_review"]
    lines = [
        "# Utility Data Inventory",
        "",
        f"Generated: {dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Sources Discovered",
        *[f"- {source['source_name']} ({source['source_format']})" for source in sources],
        "",
        "## Utility Systems Found",
        *[f"- {system}: {len(items)} layer(s), {records[system]} record(s)" for system, items in sorted(by_system.items())],
        "",
        "## Coordinate Systems Found",
        *[f"- {name}: {count} layer(s)" for name, count in spatial_refs.items()],
        "",
        "## High-Confidence Utility Layers",
        *[f"- {layer['layer_name']}: {taxonomy_label(layer)} ({layer['record_count']} records)" for layer in high],
        "",
        "## Unknown Or Ambiguous Layers",
        *(
            [
                f"- {layer['layer_name']}: {layer['recommended_action']}; likely {layer.get('likely_classifications', '') or 'not identified'}"
                for layer in ambiguous
            ]
            or ["- None identified."]
        ),
        "",
        "## Missing Expected Utility Components",
        "- Service lines, valves, pumps, and treatment or lift station layers were not identified in this raw dataset.",
        "",
        "## Potential Duplicate Layers",
        *potential_duplicate_lines(layers),
        "",
        "## Data-Quality Warnings",
        *quality_warning_lines(layers),
        "",
        "## Recommended Staging Candidates",
        *[f"- {layer['layer_name']} -> {layer['utility_system']}_{safe_name(layer.get('asset_subcategory') or layer['asset_category'])}" for layer in candidates],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def taxonomy_label(layer: dict[str, Any]) -> str:
    return " / ".join(
        [
            layer.get("utility_system", ""),
            layer.get("network_group", ""),
            layer.get("asset_category", ""),
            layer.get("asset_subcategory", ""),
        ]
    )


def potential_duplicate_lines(layers: list[dict[str, Any]]) -> list[str]:
    counts = Counter(
        (
            layer["utility_system"],
            layer["network_group"],
            layer["asset_category"],
            layer["asset_subcategory"],
            layer["geometry_type"],
        )
        for layer in layers
    )
    duplicates = [key for key, count in counts.items() if count > 1 and key[0] not in {"unknown", "review_required"}]
    return [
        f"- {system} / {group} / {category} / {subcategory} / {geometry}: {counts[(system, group, category, subcategory, geometry)]} layers"
        for system, group, category, subcategory, geometry in duplicates
    ] or ["- None identified."]


def quality_warning_lines(layers: list[dict[str, Any]]) -> list[str]:
    warnings = []
    for layer in layers:
        if not layer["spatial_reference"]:
            warnings.append(f"- {layer['layer_name']}: missing spatial reference.")
        if not layer["unique_id_field"]:
            warnings.append(f"- {layer['layer_name']}: no likely unique ID field identified.")
        if layer["classification_confidence"] in {"low", "unknown", "review_required"}:
            warnings.append(f"- {layer['layer_name']}: classification needs review.")
    return warnings or ["- No blocking warnings from inventory metadata."]


def write_recommendation(path: Path, layers: list[dict[str, Any]]) -> None:
    system_scores = Counter()
    for layer in layers:
        if layer["utility_system"] in {"review_required", "unknown", "reference", "shared_reference"}:
            continue
        if layer["classification_confidence"] == "high":
            system_scores[layer["utility_system"]] += 3
        elif layer["classification_confidence"] == "medium":
            system_scores[layer["utility_system"]] += 1
        if layer.get("unique_id_field"):
            system_scores[layer["utility_system"]] += 1
        if layer.get("spatial_reference"):
            system_scores[layer["utility_system"]] += 1
    primary = system_scores.most_common(1)[0][0] if system_scores else "unknown"
    candidates = [layer for layer in layers if layer["utility_system"] == primary and layer["recommended_action"] == "candidate_for_staging_review"]
    defer = [layer for layer in layers if layer not in candidates]
    lines = [
        "# Staging Recommendation",
        "",
        f"Primary system to start with: **{primary}**",
        "",
        "## Exact Layers To Stage After Approval",
        *(
            [
                f"- {layer['layer_name']} as `{primary}_{safe_name(layer.get('asset_subcategory') or layer['asset_category'])}`"
                for layer in candidates
            ]
            or ["- None yet."]
        ),
        "",
        "## Reference Layers Needed",
        "- Service boundaries or subbasins if needed for QA context.",
        "",
        "## Layers To Defer",
        *(
            [
                f"- {layer['layer_name']}: {layer['recommended_action']}; {layer.get('recommended_classification') or layer.get('notes') or taxonomy_label(layer)}"
                for layer in defer
            ]
            or ["- None."]
        ),
        "",
        "## Known Risks",
        *quality_warning_lines(layers),
        "",
        "## Suggested QA Checks",
        "- Duplicate IDs",
        "- Missing required fields",
        "- Geometry validity",
        "- Coordinate-system consistency",
        "- Connectivity review for line and point layers",
        "",
        "## Suggested Target Naming Convention",
        "- `{utility_system}_{asset_subcategory}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only inventory of approved raw utility sources.")
    parser.add_argument("--raw-root", default=str(load_config().raw_root))
    parser.add_argument("--report-root", default=str(load_config().qa_root / "reports"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config()
    write_csv_header_if_missing(config.data_catalog, DATA_CATALOG_COLUMNS, config)
    sources = discover_sources(Path(args.raw_root))
    layers = inventory_sources(sources)
    apply_contextual_review_recommendations(layers)
    register_layers(layers, dry_run=args.dry_run)
    profiles = profile_fields(load_arcpy(), layers)
    write_reports(Path(args.report_root), sources, layers, profiles)
    logging.info("Discovered %s source(s), inventoried %s layer(s).", len(sources), len(layers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
