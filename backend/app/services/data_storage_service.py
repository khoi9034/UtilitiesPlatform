from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SAFE_CATALOG_FIELDS = [
    "dataset_id",
    "dataset_name",
    "utility_type",
    "asset_category",
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
        return [{field: row.get(field, "") for field in SAFE_CATALOG_FIELDS} for row in csv.DictReader(handle)]


def catalog_summary() -> dict[str, object]:
    rows = read_safe_catalog()
    if not rows:
        return {
            "total_datasets": 0,
            "by_utility_type": {},
            "by_stage": {},
            "by_source_format": {},
            "by_sensitivity_level": {},
            "message": "No utility datasets have been registered yet.",
        }
    return {
        "total_datasets": len(rows),
        "by_utility_type": dict(Counter(row.get("utility_type", "") for row in rows if row.get("utility_type"))),
        "by_stage": dict(Counter(row.get("current_stage", "") for row in rows if row.get("current_stage"))),
        "by_source_format": dict(Counter(row.get("source_format", "") for row in rows if row.get("source_format"))),
        "by_sensitivity_level": dict(Counter(row.get("sensitivity_level", "") for row in rows if row.get("sensitivity_level"))),
        "message": "Dataset catalog summary generated from registered metadata.",
    }
