from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SAFE_CATALOG_FIELDS = [
    "dataset_id",
    "dataset_name",
    "utility_system",
    "network_group",
    "asset_category",
    "asset_subcategory",
    "source_format",
    "geometry_type",
    "coordinate_system",
    "record_count",
    "sensitivity_level",
    "current_stage",
    "approved_for_analysis",
    "approved_for_export",
    "approved_for_public_use",
    "date_inventoried",
    "last_processed",
]

LEGACY_TAXONOMY = {
    ("wastewater", "gravity_main"): {
        "network_group": "gravity_network",
        "asset_category": "pipe",
        "asset_subcategory": "gravity_main",
    },
    ("wastewater", "manhole"): {
        "network_group": "structures",
        "asset_category": "access_structure",
        "asset_subcategory": "manhole",
    },
    ("stormwater", "subbasin"): {
        "utility_system": "review_required",
        "network_group": "review_required",
        "asset_category": "review_required",
        "asset_subcategory": "subbasin",
    },
}


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    raw: Path
    staging: Path
    standardized: Path
    curated: Path
    exports: Path
    catalog: Path
    staging_gdb: Path
    standardized_gdb: Path
    master_gdb: Path


def get_storage_paths() -> StoragePaths:
    root = Path(os.getenv("UTILITY_DATA_ROOT", r"C:\UtilitiesPlatform_Data"))
    return StoragePaths(
        root=root,
        raw=Path(os.getenv("UTILITY_RAW_ROOT", str(root / "01_raw"))),
        staging=Path(os.getenv("UTILITY_STAGING_ROOT", str(root / "02_staging"))),
        standardized=Path(os.getenv("UTILITY_STANDARDIZED_ROOT", str(root / "03_standardized"))),
        curated=Path(os.getenv("UTILITY_CURATED_ROOT", str(root / "04_curated"))),
        exports=Path(os.getenv("UTILITY_EXPORT_ROOT", str(root / "06_exports"))),
        catalog=root / "00_admin" / "data_catalog.csv",
        staging_gdb=Path(os.getenv("UTILITY_STAGING_GDB", str(root / "02_staging" / "Utility_Staging.gdb"))),
        standardized_gdb=Path(os.getenv("UTILITY_STANDARDIZED_GDB", str(root / "03_standardized" / "Utility_Standardized.gdb"))),
        master_gdb=Path(os.getenv("UTILITY_MASTER_GDB", str(root / "04_curated" / "Utility_Master.gdb"))),
    )


def storage_status() -> dict[str, object]:
    paths = get_storage_paths()
    return {
        "configured": bool(paths.root),
        "master_root_available": paths.root.exists(),
        "raw_folder_available": paths.raw.exists(),
        "staging_folder_available": paths.staging.exists(),
        "standardized_folder_available": paths.standardized.exists(),
        "curated_folder_available": paths.curated.exists(),
        "export_folder_available": paths.exports.exists(),
        "catalog_available": paths.catalog.exists(),
        "geodatabases": {
            "staging": "exists" if paths.staging_gdb.exists() else "pending",
            "standardized": "exists" if paths.standardized_gdb.exists() else "pending",
            "master": "exists" if paths.master_gdb.exists() else "pending",
        },
    }


def read_safe_catalog() -> list[dict[str, str]]:
    paths = get_storage_paths()
    if not paths.catalog.exists():
        return []
    with paths.catalog.open(newline="", encoding="utf-8") as handle:
        return [{field: normalize_taxonomy(row).get(field, "") for field in SAFE_CATALOG_FIELDS} for row in csv.DictReader(handle)]


def catalog_summary() -> dict[str, object]:
    rows = read_safe_catalog()
    if not rows:
        return {
            "total_datasets": 0,
            "by_utility_system": {},
            "by_network_group": {},
            "by_asset_category": {},
            "by_stage": {},
            "by_source_format": {},
            "by_sensitivity_level": {},
            "message": "No utility datasets have been registered yet.",
        }
    return {
        "total_datasets": len(rows),
        "by_utility_system": count_by(rows, "utility_system"),
        "by_network_group": count_by(rows, "network_group"),
        "by_asset_category": count_by(rows, "asset_category"),
        "by_stage": dict(Counter(row.get("current_stage", "") for row in rows if row.get("current_stage"))),
        "by_source_format": dict(Counter(row.get("source_format", "") for row in rows if row.get("source_format"))),
        "by_sensitivity_level": dict(Counter(row.get("sensitivity_level", "") for row in rows if row.get("sensitivity_level"))),
        "message": "Dataset catalog summary generated from registered metadata.",
    }


def inventory_report_paths() -> dict[str, Path]:
    root = Path(os.getenv("UTILITY_DATA_ROOT", r"C:\UtilitiesPlatform_Data"))
    report_root = root / "05_qa" / "reports"
    return {
        "inventory": report_root / "utility_data_inventory.csv",
        "recommendation": report_root / "staging_recommendation.md",
        "allowlist": root / "00_admin" / "staging_allowlist.csv",
    }


def read_inventory_layers() -> list[dict[str, str]]:
    path = inventory_report_paths()["inventory"]
    if not path.exists():
        return []
    safe_fields = [
        "dataset_id",
        "source_name",
        "source_format",
        "utility_system",
        "network_group",
        "asset_category",
        "asset_subcategory",
        "classification_confidence",
        "likely_classifications",
        "recommended_classification",
        "layer_name",
        "geometry_type",
        "record_count",
        "spatial_reference",
        "sensitivity_level",
        "recommended_action",
    ]
    with path.open(newline="", encoding="utf-8") as handle:
        return [{field: normalize_taxonomy(row).get(field, "") for field in safe_fields} for row in csv.DictReader(handle)]


def inventory_summary() -> dict[str, object]:
    layers = read_inventory_layers()
    if not layers:
        return {
            "sources_discovered": 0,
            "layer_count": 0,
            "by_utility_system": {},
            "by_network_group": {},
            "by_asset_category": {},
            "by_confidence": {},
            "record_totals_by_system": {},
            "spatial_references": {},
            "recommended_staging_layers": 0,
            "unknown_layers": 0,
            "review_required_layers": 0,
            "message": "No inventory report has been generated yet.",
        }
    return {
        "sources_discovered": len({row.get("source_name", "") for row in layers if row.get("source_name")}),
        "layer_count": len(layers),
        "by_utility_system": count_by(layers, "utility_system"),
        "by_network_group": count_by(layers, "network_group"),
        "by_asset_category": count_by(layers, "asset_category"),
        "by_confidence": dict(Counter(row.get("classification_confidence", "") for row in layers if row.get("classification_confidence"))),
        "record_totals_by_system": record_totals_by_system(layers),
        "spatial_references": dict(Counter(row.get("spatial_reference", "") for row in layers if row.get("spatial_reference"))),
        "recommended_staging_layers": sum(1 for row in layers if row.get("recommended_action") == "candidate_for_staging_review"),
        "unknown_layers": sum(1 for row in layers if row.get("utility_system") == "unknown"),
        "review_required_layers": sum(1 for row in layers if row.get("utility_system") == "review_required"),
        "message": "Inventory summary loaded from generated QA reports.",
    }


def record_totals_by_system(layers: list[dict[str, str]]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for row in layers:
        try:
            totals[row.get("utility_system", "")] += int(row.get("record_count") or 0)
        except ValueError:
            continue
    return dict(totals)


def inventory_recommendation() -> dict[str, object]:
    paths = inventory_report_paths()
    recommendation = paths["recommendation"].read_text(encoding="utf-8") if paths["recommendation"].exists() else ""
    allowlist_rows = []
    if paths["allowlist"].exists():
        with paths["allowlist"].open(newline="", encoding="utf-8") as handle:
            allowlist_rows = [
                {
                    "dataset_id": row.get("dataset_id", ""),
                    "source_layer_name": row.get("source_layer_name", ""),
                    "target_layer_name": row.get("target_layer_name", ""),
                    "utility_system": normalized.get("utility_system", ""),
                    "network_group": normalized.get("network_group", ""),
                    "asset_category": normalized.get("asset_category", ""),
                    "asset_subcategory": normalized.get("asset_subcategory", ""),
                    "approved_to_stage": row.get("approved_to_stage", ""),
                    "reason": row.get("reason", ""),
                }
                for row in csv.DictReader(handle)
                for normalized in [normalize_taxonomy(row)]
            ]
    return {
        "recommendation_markdown": recommendation,
        "allowlist": allowlist_rows,
        "message": "No staging recommendation has been generated yet." if not recommendation else "Staging recommendation loaded.",
    }


def normalize_taxonomy(row: dict[str, str]) -> dict[str, str]:
    output = dict(row)
    if not output.get("utility_system") and output.get("utility_type"):
        output["utility_system"] = output.get("utility_type", "")
    output.setdefault("network_group", "")
    output.setdefault("asset_subcategory", "")
    legacy = LEGACY_TAXONOMY.get((output.get("utility_system", "").lower(), output.get("asset_category", "").lower()))
    if legacy and (not output.get("network_group") or not output.get("asset_subcategory")):
        output.update(legacy)
    return output


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(Counter(row.get(field, "") for row in rows if row.get(field)))
