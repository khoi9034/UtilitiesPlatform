from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = Path(os.getenv("UTILITY_DATA_ROOT", r"C:\UtilitiesPlatform_Data"))

DATA_CATALOG_COLUMNS = [
    "dataset_id",
    "dataset_name",
    "utility_system",
    "network_group",
    "asset_category",
    "asset_subcategory",
    "source_format",
    "source_path",
    "source_owner",
    "source_system",
    "source_layer_name",
    "geometry_type",
    "coordinate_system",
    "unique_id_field",
    "record_count",
    "sensitivity_level",
    "access_level",
    "refresh_frequency",
    "date_received",
    "date_inventoried",
    "last_processed",
    "current_stage",
    "approved_for_analysis",
    "approved_for_export",
    "approved_for_public_use",
    "notes",
]

PROCESSING_HISTORY_COLUMNS = [
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

EXPORT_REGISTRY_COLUMNS = [
    "export_id",
    "dataset_id",
    "export_name",
    "export_format",
    "export_path",
    "created_at",
    "created_by",
    "sanitized",
    "approved_for_public_use",
    "purpose",
    "notes",
]

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

ROOT_DIRS = [
    "00_admin",
    "01_raw",
    "02_staging",
    "03_standardized",
    "04_curated",
    "05_qa",
    "06_exports",
    "07_samples",
    "08_archive",
    "09_backups",
    "logs",
    "temp",
]

RAW_DIRS = [
    "geodatabases",
    "enterprise_exports",
    "cad",
    "pdf",
    "spreadsheets",
    "shapefiles",
    "geopackages",
    "rasters",
    "submissions",
    "other",
]

UTILITY_DIRS = ["water", "wastewater", "stormwater", "telecom", "electric", "gas", "reference", "general"]
QA_DIRS = ["reports", "issues", "geometry", "attributes", "connectivity", "resolved"]
EXPORT_DIRS = ["geodatabases", "geopackages", "shapefiles", "csv", "geojson", "reports", "maps", "sanitized_portfolio"]
SAMPLE_DIRS = ["sanitized", "synthetic", "templates"]
BACKUP_DIRS = ["catalog", "configurations", "database", "processed_data"]


@dataclass(frozen=True)
class StorageConfig:
    master_data_root: Path
    admin_root: Path
    raw_root: Path
    staging_root: Path
    standardized_root: Path
    curated_root: Path
    qa_root: Path
    exports_root: Path
    samples_root: Path
    archive_root: Path
    backup_root: Path
    logs_root: Path
    temp_root: Path
    staging_geodatabase: Path
    standardized_geodatabase: Path
    master_geodatabase: Path
    data_catalog: Path
    processing_history: Path
    export_registry: Path


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def storage_structure(year: int | None = None) -> list[Path]:
    year = year or datetime.now().year
    paths = [Path(item) for item in ROOT_DIRS]
    paths += [Path("00_admin") / "intake", Path("temp") / "uploads", Path("logs") / "intake"]
    paths += [Path("01_raw") / item for item in RAW_DIRS]
    for stage in ["02_staging", "03_standardized", "04_curated"]:
        paths += [Path(stage) / item for item in UTILITY_DIRS]
    paths += [Path("05_qa") / item for item in QA_DIRS]
    paths += [Path("06_exports") / item for item in EXPORT_DIRS]
    paths += [Path("07_samples") / item for item in SAMPLE_DIRS]
    paths += [Path("08_archive") / str(year), Path("08_archive") / str(year + 1)]
    paths += [Path("09_backups") / item for item in BACKUP_DIRS]
    return paths


def default_config(root: Path | None = None) -> StorageConfig:
    root = (root or DEFAULT_ROOT).resolve()
    return StorageConfig(
        master_data_root=root,
        admin_root=root / "00_admin",
        raw_root=root / "01_raw",
        staging_root=root / "02_staging",
        standardized_root=root / "03_standardized",
        curated_root=root / "04_curated",
        qa_root=root / "05_qa",
        exports_root=root / "06_exports",
        samples_root=root / "07_samples",
        archive_root=root / "08_archive",
        backup_root=root / "09_backups",
        logs_root=root / "logs",
        temp_root=root / "temp",
        staging_geodatabase=root / "02_staging" / "Utility_Staging.gdb",
        standardized_geodatabase=root / "03_standardized" / "Utility_Standardized.gdb",
        master_geodatabase=root / "04_curated" / "Utility_Master.gdb",
        data_catalog=root / "00_admin" / "data_catalog.csv",
        processing_history=root / "00_admin" / "processing_history.csv",
        export_registry=root / "00_admin" / "export_registry.csv",
    )


def load_config(config_path: Path | None = None) -> StorageConfig:
    env_root = os.getenv("UTILITY_DATA_ROOT")
    if env_root:
        return default_config(Path(env_root))

    config_path = config_path or REPO_ROOT / "config" / "data_storage.local.json"
    if not config_path.exists():
        config_path = REPO_ROOT / "config" / "data_storage.example.json"
    if not config_path.exists():
        return default_config()

    data = json.loads(config_path.read_text(encoding="utf-8"))
    return StorageConfig(**{key: Path(value) for key, value in data.items()})


def ensure_under_root(path: Path, root: Path) -> Path:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    try:
        if os.path.commonpath([str(resolved_path), str(resolved_root)]) != str(resolved_root):
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"Refusing to operate outside {resolved_root}: {resolved_path}") from exc
    return resolved_path


def ensure_directory(path: Path, config: StorageConfig, dry_run: bool = False) -> None:
    safe_path = ensure_under_root(path, config.master_data_root)
    if dry_run:
        logging.info("Would create directory %s", safe_path)
        return
    safe_path.mkdir(parents=True, exist_ok=True)


def write_csv_header_if_missing(path: Path, columns: list[str], config: StorageConfig, dry_run: bool = False) -> bool:
    safe_path = ensure_under_root(path, config.master_data_root)
    if safe_path.exists() and safe_path.stat().st_size > 0:
        logging.info("Keeping existing catalog file %s", safe_path)
        return False
    if dry_run:
        logging.info("Would create catalog file %s", safe_path)
        return True
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    with safe_path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=columns).writeheader()
    return True


def read_catalog(config: StorageConfig) -> list[dict[str, str]]:
    if not config.data_catalog.exists():
        return []
    with config.data_catalog.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def append_catalog_row(config: StorageConfig, row: dict[str, Any], allow_duplicate: bool = False) -> str:
    ensure_under_root(Path(row["source_path"]), config.master_data_root)
    row = normalize_catalog_row(row)
    existing = read_catalog(config)
    duplicate = any(
        item.get("dataset_name") == row["dataset_name"]
        and item.get("source_path") == row["source_path"]
        and item.get("source_layer_name") == row.get("source_layer_name", "")
        for item in existing
    )
    if duplicate and not allow_duplicate:
        raise ValueError("Duplicate dataset registration refused. Use --allow-duplicate to override.")

    dataset_id = str(uuid.uuid4())
    output = {column: "" for column in DATA_CATALOG_COLUMNS}
    output.update({key: "" if value is None else str(value) for key, value in row.items()})
    output["dataset_id"] = dataset_id
    with config.data_catalog.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=DATA_CATALOG_COLUMNS).writerow(output)
    return dataset_id


def safe_catalog_rows(config: StorageConfig) -> list[dict[str, str]]:
    return [{field: normalize_catalog_row(row).get(field, "") for field in SAFE_CATALOG_FIELDS} for row in read_catalog(config)]


def normalize_catalog_row(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    if "utility_system" not in output and "utility_type" in output:
        output["utility_system"] = output.get("utility_type", "")
    output.setdefault("network_group", "")
    output.setdefault("asset_subcategory", "")
    legacy = LEGACY_TAXONOMY.get((str(output.get("utility_system", "")).lower(), str(output.get("asset_category", "")).lower()))
    if legacy and (not output.get("network_group") or not output.get("asset_subcategory")):
        output.update(legacy)
    return output


def append_export_row(config: StorageConfig, row: dict[str, Any]) -> str:
    export_id = str(uuid.uuid4())
    output = {column: "" for column in EXPORT_REGISTRY_COLUMNS}
    output.update({key: "" if value is None else str(value) for key, value in row.items()})
    output["export_id"] = export_id
    with config.export_registry.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=EXPORT_REGISTRY_COLUMNS).writerow(output)
    return export_id


def create_readme(config: StorageConfig, dry_run: bool = False) -> None:
    path = config.master_data_root / "README.md"
    if path.exists():
        return
    text = """# Utilities Platform Local Master Data Storage

This directory is intentionally outside the Git repository.

Place only approved data here. Preserve raw source files unchanged, register datasets in `00_admin/data_catalog.csv`, process working copies through staging and standardized folders, and create exports only when authorized.

Do not commit this directory to Git.
"""
    if dry_run:
        logging.info("Would create %s", path)
        return
    path.write_text(text, encoding="utf-8")


def create_file_geodatabases(config: StorageConfig, dry_run: bool = False) -> dict[str, str]:
    targets = {
        "Utility_Staging.gdb": config.staging_geodatabase,
        "Utility_Standardized.gdb": config.standardized_geodatabase,
        "Utility_Master.gdb": config.master_geodatabase,
    }
    statuses: dict[str, str] = {}
    missing: dict[str, Path] = {}
    for name, path in targets.items():
        ensure_under_root(path, config.master_data_root)
        if path.exists():
            statuses[name] = "exists"
        else:
            missing[name] = path
    if not missing:
        return statuses
    try:
        import arcpy  # type: ignore
    except ImportError:
        return {**statuses, **{name: "pending_arcpy_unavailable" for name in missing}}

    for name, path in missing.items():
        if dry_run:
            statuses[name] = "would_create"
            continue
        arcpy.management.CreateFileGDB(str(path.parent), path.stem)
        statuses[name] = "created"
    return statuses


def initialize_storage(config: StorageConfig, dry_run: bool = False) -> dict[str, Any]:
    for relative_path in storage_structure():
        ensure_directory(config.master_data_root / relative_path, config, dry_run=dry_run)
    create_readme(config, dry_run=dry_run)
    catalogs = {
        "data_catalog": write_csv_header_if_missing(config.data_catalog, DATA_CATALOG_COLUMNS, config, dry_run=dry_run),
        "processing_history": write_csv_header_if_missing(
            config.processing_history, PROCESSING_HISTORY_COLUMNS, config, dry_run=dry_run
        ),
        "export_registry": write_csv_header_if_missing(config.export_registry, EXPORT_REGISTRY_COLUMNS, config, dry_run=dry_run),
    }
    return {"catalogs_created": catalogs, "geodatabases": create_file_geodatabases(config, dry_run=dry_run)}


def git_tracked_data_files() -> list[str]:
    patterns = [
        "*.gdb",
        "*.sde",
        "*.dwg",
        "*.dxf",
        "*.shp",
        "*.shx",
        "*.dbf",
        "*.prj",
        "*.cpg",
        "*.gpkg",
        "*.sqlite",
        "*.tif",
        "*.tiff",
        "*.pdf",
        "*.xlsx",
        "*.xls",
        "*.csv",
        "*.zip",
        "*.7z",
    ]
    files: list[str] = []
    for pattern in patterns:
        result = subprocess.run(["git", "ls-files", pattern], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        files.extend(result.stdout.splitlines())
    return sorted(set(files))


def validate_storage(config: StorageConfig) -> dict[str, Any]:
    required_dirs = [config.master_data_root / item for item in storage_structure()]
    missing_dirs = [str(path) for path in required_dirs if not path.exists()]
    catalogs = [config.data_catalog, config.processing_history, config.export_registry]
    missing_catalogs = [str(path) for path in catalogs if not path.exists()]
    geodatabases = {
        "staging": "exists" if config.staging_geodatabase.exists() else "pending",
        "standardized": "exists" if config.standardized_geodatabase.exists() else "pending",
        "master": "exists" if config.master_geodatabase.exists() else "pending",
    }
    write_test = config.temp_root / ".write_test"
    writable = False
    try:
        ensure_under_root(write_test, config.master_data_root)
        config.temp_root.mkdir(parents=True, exist_ok=True)
        write_test.write_text("ok", encoding="utf-8")
        write_test.unlink()
        writable = True
    except OSError:
        writable = False

    repo = REPO_ROOT.resolve()
    root = config.master_data_root.resolve(strict=False)
    data_inside_repo = os.path.commonpath([str(root), str(repo)]) == str(repo)
    tracked_data = git_tracked_data_files()
    return {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "master_data_root": str(config.master_data_root),
        "missing_directories": missing_dirs,
        "missing_catalogs": missing_catalogs,
        "geodatabases": geodatabases,
        "writable": writable,
        "data_inside_git_repository": data_inside_repo,
        "tracked_production_data_files": tracked_data,
        "valid": not missing_dirs and not missing_catalogs and writable and not data_inside_repo and not tracked_data,
    }


def write_validation_report(config: StorageConfig, report: dict[str, Any]) -> Path:
    config.logs_root.mkdir(parents=True, exist_ok=True)
    path = config.logs_root / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def backup_file(source: Path, destination_dir: Path, dry_run: bool = False) -> Path | None:
    if not source.exists():
        return None
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{source.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{source.suffix}"
    if dry_run:
        logging.info("Would back up %s to %s", source, destination)
        return destination
    shutil.copy2(source, destination)
    return destination
