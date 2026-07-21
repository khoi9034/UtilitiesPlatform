from __future__ import annotations

import csv
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import intake_registry_service as intake_registry

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
    processing_history: Path
    export_registry: Path
    stage_manifest: Path
    intake_registry: Path
    raw_submissions: Path
    temp_uploads: Path
    intake_logs: Path
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
        processing_history=root / "00_admin" / "processing_history.csv",
        export_registry=root / "00_admin" / "export_registry.csv",
        stage_manifest=root / "00_admin" / "data_stage_manifest.json",
        intake_registry=root / "00_admin" / "intake" / "utility_intake.sqlite",
        raw_submissions=root / "01_raw" / "submissions",
        temp_uploads=root / "temp" / "uploads",
        intake_logs=root / "logs" / "intake",
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
        "intake_registry_available": paths.intake_registry.exists(),
        "stage_manifest_available": paths.stage_manifest.exists(),
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


def append_catalog_row(row: dict[str, Any]) -> str:
    paths = get_storage_paths()
    ensure_catalog_file(paths.catalog, DATA_CATALOG_COLUMNS)
    dataset_id = str(row.get("dataset_id") or f"UPD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}")
    source_path = str(row.get("source_path", ""))
    source_layer = str(row.get("source_layer_name", ""))
    for existing in read_csv(paths.catalog):
        if existing.get("source_path") == source_path and existing.get("source_layer_name", "") == source_layer:
            return existing.get("dataset_id", dataset_id)
    output = {column: "" for column in DATA_CATALOG_COLUMNS}
    output.update({key: "" if value is None else str(value) for key, value in row.items()})
    output["dataset_id"] = dataset_id
    with paths.catalog.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=DATA_CATALOG_COLUMNS).writerow(output)
    return dataset_id


def append_processing_history(row: dict[str, Any]) -> None:
    paths = get_storage_paths()
    ensure_catalog_file(paths.processing_history, PROCESSING_HISTORY_COLUMNS)
    output = {column: "" for column in PROCESSING_HISTORY_COLUMNS}
    output.update({key: "" if value is None else str(value) for key, value in row.items()})
    with paths.processing_history.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=PROCESSING_HISTORY_COLUMNS).writerow(output)


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


def read_processing_history() -> list[dict[str, str]]:
    safe_fields = ["run_id", "dataset_id", "process_name", "started_at", "completed_at", "status", "records_read", "records_written", "notes"]
    return [{field: row.get(field, "") for field in safe_fields} for row in read_csv(get_storage_paths().processing_history)]


def read_export_registry() -> list[dict[str, str]]:
    safe_fields = ["export_id", "dataset_id", "export_name", "export_format", "created_at", "sanitized", "approved_for_public_use", "purpose", "notes"]
    return [{field: row.get(field, "") for field in safe_fields} for row in read_csv(get_storage_paths().export_registry)]


def build_stage_manifest(write: bool = True) -> dict[str, object]:
    paths = get_storage_paths()
    intake_registry.ensure_intake_storage(paths.root)
    catalog_rows = read_safe_catalog()
    inventory_rows = read_inventory_layers()
    export_rows = read_export_registry()
    raw_items = raw_stage_items(paths, catalog_rows)
    staging_items = staging_stage_items(catalog_rows, inventory_rows)
    standardized_items = primary_stage_items(catalog_rows, "standardized")
    curated_items = primary_stage_items(catalog_rows, "curated")
    export_items = export_stage_items(export_rows)
    items = raw_items + staging_items + standardized_items + curated_items + export_items
    stages = [
        stage_summary("raw", raw_items, "Immutable source packages registered for inventory and staging review."),
        stage_summary("staging", staging_items, "Temporary imported or converted working layers."),
        stage_summary("standardized", standardized_items, "Schema-normalized working data awaiting approved mappings."),
        stage_summary("curated", curated_items, "Approved analysis-ready utility layers."),
        stage_summary("export", export_items, "Controlled output packages from the export registry."),
    ]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stages": stages,
        "items": items,
        "counts": {str(stage["stage"]): stage["item_count"] for stage in stages},
        "message": "Stage manifest generated from safe catalog, intake registry, inventory, and export metadata.",
    }
    if write:
        paths.stage_manifest.parent.mkdir(parents=True, exist_ok=True)
        paths.stage_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def data_source_items(
    *,
    stage: str | None = None,
    utility_system: str | None = None,
    network_group: str | None = None,
    asset_category: str | None = None,
    asset_subcategory: str | None = None,
    source_format: str | None = None,
    sensitivity: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, object]:
    items = list(build_stage_manifest()["items"])
    filters = {
        "stage": stage,
        "utility_system": utility_system,
        "network_group": network_group,
        "asset_category": asset_category,
        "asset_subcategory": asset_subcategory,
        "source_format": source_format,
        "sensitivity_level": sensitivity,
        "status": status,
    }
    for field, value in filters.items():
        if value:
            items = [item for item in items if str(item.get(field, "")).lower() == value.lower()]
    if search:
        needle = search.lower()
        items = [item for item in items if needle in " ".join(str(item.get(field, "")) for field in ["name", "item_id", "source_format"]).lower()]
    total = len(items)
    page = items[offset : offset + limit]
    return {"items": page, "pagination": {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total}}


def data_source_item(item_id: str) -> dict[str, object] | None:
    for item in build_stage_manifest()["items"]:
        if item.get("item_id") == item_id:
            return dict(item)
    return None


def data_source_lineage(item_id: str) -> dict[str, object]:
    item = data_source_item(item_id)
    if not item:
        return {"item_id": item_id, "lineage": [], "message": "Data source item not found."}
    return {"item_id": item_id, "lineage": item.get("lineage", []), "blockers": item.get("blockers", []), "next_required_action": item.get("next_required_action", "")}


def data_source_diagnostics() -> dict[str, object]:
    manifest = build_stage_manifest()
    return {
        "storage": storage_status(),
        "stage_manifest_item_count": len(manifest.get("items", [])),
        "message": "Diagnostics expose safe status only; local filesystem paths are not returned.",
    }


def raw_stage_items(paths: StoragePaths, catalog_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows, _ = intake_registry.list_submissions(paths.root, current_stage="raw", limit=10000)
    items = [submission_stage_item(row) for row in rows]
    submission_ids = {str(item.get("submission_id", "")) for item in items}
    for row in catalog_rows:
        if primary_stage(row.get("current_stage", "")) == "raw" and row.get("dataset_id") not in submission_ids:
            items.append(catalog_stage_item(row, "raw"))
    return items


def staging_stage_items(catalog_rows: list[dict[str, str]], inventory_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    items = [catalog_stage_item(row, "staging") for row in catalog_rows if primary_stage(row.get("current_stage", "")) == "staging"]
    seen_names = {str(item["name"]).lower() for item in items}
    for row in inventory_rows:
        if row.get("recommended_action") == "candidate_for_staging_review" and row.get("layer_name", "").lower() not in seen_names:
            items.append(inventory_stage_item(row))
    return items


def primary_stage_items(catalog_rows: list[dict[str, str]], stage: str) -> list[dict[str, object]]:
    return [catalog_stage_item(row, stage) for row in catalog_rows if primary_stage(row.get("current_stage", "")) == stage]


def export_stage_items(export_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "item_id": f"export:{row.get('export_id')}",
            "name": row.get("export_name", ""),
            "stage": "export",
            "utility_system": "",
            "network_group": "",
            "asset_category": "",
            "asset_subcategory": "",
            "source_format": row.get("export_format", ""),
            "geometry_type": "",
            "coordinate_system": "",
            "record_count": "",
            "sensitivity_level": "controlled_export",
            "status": "registered_export",
            "inventory_status": "not_applicable",
            "classification_status": "not_applicable",
            "staging_status": "not_applicable",
            "qa_state": "not_applicable",
            "next_required_action": "Review export authorization and package manifest.",
            "lineage": ["Controlled export package", "Export registry entry"],
            "trust_state": trust_state("export"),
            "blockers": [],
            "metadata": {"sanitized": row.get("sanitized", ""), "approved_for_public_use": row.get("approved_for_public_use", ""), "purpose": row.get("purpose", "")},
        }
        for row in export_rows
    ]


def submission_stage_item(row: dict[str, Any]) -> dict[str, object]:
    return {
        "item_id": f"submission:{row.get('submission_id')}",
        "submission_id": row.get("submission_id", ""),
        "name": row.get("submission_name", ""),
        "stage": "raw",
        "utility_system": row.get("utility_system", ""),
        "network_group": "pending_inventory",
        "asset_category": "pending_inventory",
        "asset_subcategory": "pending_inventory",
        "source_format": row.get("source_format", ""),
        "geometry_type": "pending_inventory",
        "coordinate_system": "pending_inventory",
        "record_count": "pending_inventory",
        "sensitivity_level": row.get("sensitivity_level", ""),
        "status": row.get("current_status", ""),
        "inventory_status": row.get("inventory_status", ""),
        "classification_status": row.get("classification_status", ""),
        "staging_status": row.get("staging_status", ""),
        "qa_state": "not_started",
        "next_required_action": next_action_for_submission(row),
        "lineage": ["Uploaded package", "Raw registered source"] if row.get("current_status") != "duplicate_detected" else ["Uploaded package", "Duplicate detected before Raw registration"],
        "trust_state": trust_state("raw", row),
        "blockers": ["Duplicate requires explicit version registration"] if row.get("current_status") == "duplicate_detected" else [],
        "metadata": {"original_filename": row.get("original_filename", ""), "sha256_prefix": str(row.get("sha256", ""))[:12], "file_size_bytes": row.get("file_size_bytes", 0)},
    }


def catalog_stage_item(row: dict[str, str], stage: str) -> dict[str, object]:
    return {
        "item_id": f"dataset:{row.get('dataset_id')}",
        "name": row.get("dataset_name", ""),
        "stage": stage,
        "utility_system": row.get("utility_system", ""),
        "network_group": row.get("network_group", ""),
        "asset_category": row.get("asset_category", ""),
        "asset_subcategory": row.get("asset_subcategory", ""),
        "source_format": row.get("source_format", ""),
        "geometry_type": row.get("geometry_type", ""),
        "coordinate_system": row.get("coordinate_system", ""),
        "record_count": row.get("record_count", ""),
        "sensitivity_level": row.get("sensitivity_level", ""),
        "status": row.get("current_stage", ""),
        "inventory_status": "complete" if row.get("date_inventoried") else "pending_inventory",
        "classification_status": "complete" if row.get("asset_category") else "pending_inventory",
        "staging_status": "approved" if stage == "staging" else "not_applicable",
        "qa_state": "evaluated" if row.get("current_stage") == "qa_evaluated" else "not_started",
        "next_required_action": "Continue human review before standardization." if stage == "staging" else "Follow stage gate requirements.",
        "lineage": ["Registered dataset", f"{stage.title()} stage metadata"],
        "trust_state": trust_state(stage),
        "blockers": [],
    }


def inventory_stage_item(row: dict[str, str]) -> dict[str, object]:
    return {
        "item_id": f"inventory:{row.get('dataset_id') or row.get('layer_name')}",
        "name": row.get("layer_name", ""),
        "stage": "staging",
        "utility_system": row.get("utility_system", ""),
        "network_group": row.get("network_group", ""),
        "asset_category": row.get("asset_category", ""),
        "asset_subcategory": row.get("asset_subcategory", ""),
        "source_format": row.get("source_format", ""),
        "geometry_type": row.get("geometry_type", ""),
        "coordinate_system": row.get("spatial_reference", ""),
        "record_count": row.get("record_count", ""),
        "sensitivity_level": row.get("sensitivity_level", ""),
        "status": "candidate_for_staging_review",
        "inventory_status": "complete",
        "classification_status": row.get("classification_confidence", ""),
        "staging_status": "requires_human_approval",
        "qa_state": "not_started",
        "next_required_action": "Review staging recommendation and approve explicitly before staging.",
        "lineage": ["Inventoried source layer", "Layer classified", "Staging candidate", "Human approval required"],
        "trust_state": trust_state("staging"),
        "blockers": ["Human staging approval required"],
    }


def stage_summary(stage: str, items: list[dict[str, object]], description: str) -> dict[str, object]:
    return {"stage": stage, "label": stage.replace("_", " ").title(), "item_count": len(items), "description": description}


def trust_state(stage: str, row: dict[str, Any] | None = None) -> dict[str, str]:
    if stage == "raw":
        return {
            "raw_registration": row.get("current_status", "registered_raw") if row else "registered",
            "inventory": row.get("inventory_status", "not_started") if row else "unknown",
            "classification": row.get("classification_status", "not_started") if row else "unknown",
            "staging_approval": row.get("staging_status", "not_approved") if row else "not_approved",
            "qa": "not_started",
            "review": "not_started",
            "standardization": "not_started",
            "curation": "not_started",
            "export": "not_started",
        }
    return {
        "raw_registration": "complete",
        "inventory": "complete",
        "classification": "complete",
        "staging_approval": "complete" if stage in {"staging", "standardized", "curated", "export"} else "pending",
        "qa": "evaluated" if stage in {"staging", "standardized", "curated", "export"} else "not_started",
        "review": "in_progress",
        "standardization": "complete" if stage in {"standardized", "curated", "export"} else "not_started",
        "curation": "complete" if stage in {"curated", "export"} else "not_started",
        "export": "complete" if stage == "export" else "not_started",
    }


def next_action_for_submission(row: dict[str, Any]) -> str:
    if row.get("current_status") == "duplicate_detected":
        return "Cancel the duplicate or register it as a new version explicitly."
    if row.get("inventory_status") == "not_started":
        return "Run inventory when ready; staging still requires human approval."
    if row.get("inventory_status") == "complete":
        return "Review classification and staging recommendation."
    return "Resolve validation or inventory blockers."


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


def ensure_catalog_file(path: Path, columns: list[str]) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=columns).writeheader()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def primary_stage(current_stage: str) -> str:
    value = (current_stage or "").lower()
    if value in {"staging", "staged", "qa_evaluated", "human_review", "standardization_ready"}:
        return "staging"
    if value.startswith("standardized"):
        return "standardized"
    if value.startswith("curated"):
        return "curated"
    if value.startswith("export"):
        return "export"
    return "raw"
