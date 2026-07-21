from __future__ import annotations

import csv
import hashlib
import json
import os
import secrets
import shutil
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.services.archive_validation_service import validate_zip_archive
from app.services import data_storage_service as storage
from app.services import intake_registry_service as registry
from app.services.upload_validation_service import (
    ALLOWED_SINGLE_EXTENSIONS,
    SENSITIVITY_LEVELS,
    UTILITY_SYSTEMS,
    UploadValidationError,
    sanitize_filename,
    validate_metadata,
    validate_uploaded_file,
)

DEFAULT_UPLOAD_MAX_BYTES = 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class IntakeMetadata:
    submission_name: str
    utility_system: str
    source_type: str
    source_owner: str
    source_description: str
    sensitivity_level: str
    project_id: str
    submitted_by: str
    authorization_confirmed: bool
    register_duplicate_as_version: bool
    run_inventory_after_upload: bool

    def as_validation_dict(self) -> dict[str, object]:
        return {
            "submission_name": self.submission_name,
            "utility_system": self.utility_system,
            "source_type": self.source_type,
            "source_owner": self.source_owner,
            "source_description": self.source_description,
            "sensitivity_level": self.sensitivity_level,
            "authorization_confirmed": self.authorization_confirmed,
        }


def max_upload_bytes() -> int:
    try:
        return int(os.getenv("UTILITY_UPLOAD_MAX_BYTES", str(DEFAULT_UPLOAD_MAX_BYTES)))
    except ValueError:
        return DEFAULT_UPLOAD_MAX_BYTES


def capabilities() -> dict[str, object]:
    try:
        import arcpy  # type: ignore  # noqa: F401

        arcpy_available = True
    except ImportError:
        arcpy_available = False
    return {
        "accepted_formats": [
            {"source_format": "shapefile", "extensions": [".zip"], "packaging": "ZIP containing .shp, .shx, .dbf, and preferably .prj."},
            {"source_format": "file_geodatabase", "extensions": [".zip"], "packaging": "ZIP containing exactly one .gdb directory."},
            {"source_format": "cad", "extensions": [".dwg", ".dxf"], "packaging": "Single CAD drawing file."},
            {"source_format": "geopackage", "extensions": [".gpkg"], "packaging": "Single GeoPackage file."},
            {"source_format": "spreadsheet", "extensions": [".csv", ".xlsx"], "packaging": "Single spreadsheet file."},
            {"source_format": "pdf", "extensions": [".pdf"], "packaging": "Single PDF; V1 inventory is metadata-only."},
        ],
        "maximum_upload_bytes": max_upload_bytes(),
        "packaging_requirements": {
            "loose_shapefile": "not_supported",
            "nested_archives": "rejected",
            "sde_connections": "rejected",
            "password_protected_archives": "rejected",
        },
        "arcpy_available": arcpy_available,
        "inventory_support": {
            "shapefile": "package and sidecar inventory; feature counts require ArcPy.",
            "file_geodatabase": "package inventory; geodatabase schema inventory requires ArcPy.",
            "cad": "basic metadata only unless ArcPy is available.",
            "geopackage": "basic metadata in V1.",
            "spreadsheet": "safe row and column summary.",
            "pdf": "metadata-only.",
        },
        "upload_enabled": True,
        "mode": "local",
    }


async def create_submissions(files: list[UploadFile], metadata: IntakeMetadata) -> dict[str, object]:
    if not files:
        raise UploadValidationError("Select at least one package.")
    validate_metadata(metadata.as_validation_dict())
    submissions = [await _create_single_submission(file, metadata) for file in files]
    storage.build_stage_manifest()
    return {"submissions": submissions, "message": f"{len(submissions)} package(s) processed."}


async def _create_single_submission(file: UploadFile, metadata: IntakeMetadata) -> dict[str, object]:
    paths = storage.get_storage_paths()
    intake_paths = registry.ensure_intake_storage(paths.root)
    submission_id = new_submission_id()
    safe_name = sanitize_filename(file.filename or "upload.bin")
    stored_filename = f"{submission_id}_{safe_name}"
    temp_path = intake_paths["temp_uploads"] / stored_filename
    actor = _safe_actor(metadata.submitted_by)
    started_at = utc_now()
    sha256 = hashlib.sha256()
    size = 0
    try:
        if temp_path.exists():
            raise UploadValidationError("Temporary upload filename collision.")
        with temp_path.open("xb") as handle:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_upload_bytes():
                    raise UploadValidationError("Upload exceeds configured size limit.")
                sha256.update(chunk)
                handle.write(chunk)
        digest = sha256.hexdigest()
        validation = validate_uploaded_file(temp_path, safe_name, size)
        duplicate_of = registry.find_duplicate(paths.root, digest)
        if duplicate_of and not metadata.register_duplicate_as_version:
            row = submission_row(submission_id, metadata, safe_name, stored_filename, validation.source_format, size, digest, file.content_type, validation.extension, "duplicate_detected", duplicate_of)
            registry.insert_submission(paths.root, row)
            add_standard_events(paths.root, submission_id, actor, duplicate=True, duplicate_of=duplicate_of)
            registry.add_file(paths.root, file_row(submission_id, safe_name, "temporary_upload", validation.extension, size, digest, "duplicate_detected", "Temporary duplicate removed before Raw registration."))
            temp_path.unlink(missing_ok=True)
            return safe_submission(submission_id)

        submission_root = intake_paths["raw_submissions"] / submission_id
        original_dir = submission_root / "original"
        inspection_dir = submission_root / "inspection"
        reports_dir = submission_root / "reports"
        original_dir.mkdir(parents=True, exist_ok=False)
        inspection_dir.mkdir()
        reports_dir.mkdir()
        raw_path = original_dir / stored_filename
        os.replace(temp_path, raw_path)
        _prepare_inspection_copy(raw_path, inspection_dir, validation.source_format)
        row = submission_row(submission_id, metadata, safe_name, stored_filename, validation.source_format, size, digest, file.content_type, validation.extension, "registered_raw", duplicate_of)
        registry.insert_submission(paths.root, row)
        add_standard_events(paths.root, submission_id, actor)
        registry.add_file(paths.root, file_row(submission_id, safe_name, "original", validation.extension, size, digest, "passed", "Untouched Raw package."))
        for member in validation.files:
            registry.add_file(paths.root, file_row(submission_id, str(member["safe_filename"]), "inspection", str(member.get("extension", "")), int(member.get("size_bytes", 0)), "", "passed", "Package member recorded without raw attributes."))
        _write_manifest(submission_root / "submission_manifest.json", submission_id, metadata, safe_name, stored_filename, validation.source_format, size, digest, validation.files, validation.warnings)
        dataset_id = storage.append_catalog_row(
            {
                "dataset_id": submission_id,
                "dataset_name": metadata.submission_name,
                "utility_system": metadata.utility_system,
                "network_group": "pending_inventory",
                "asset_category": "pending_inventory",
                "asset_subcategory": "pending_inventory",
                "source_format": validation.source_format,
                "source_path": str(raw_path),
                "source_owner": metadata.source_owner,
                "source_system": "web_intake",
                "source_layer_name": "",
                "geometry_type": "pending_inventory",
                "coordinate_system": "pending_inventory",
                "record_count": "pending_inventory",
                "sensitivity_level": metadata.sensitivity_level,
                "access_level": metadata.sensitivity_level,
                "date_received": started_at,
                "current_stage": "raw",
                "approved_for_analysis": "false",
                "approved_for_export": "false",
                "approved_for_public_use": "false",
                "notes": f"submission_id={submission_id}; inventory pending",
            }
        )
        storage.append_processing_history(
            {
                "run_id": str(uuid.uuid4()),
                "dataset_id": dataset_id,
                "process_name": "intake_raw_registration",
                "input_path": "browser_upload",
                "output_path": f"raw_submission:{submission_id}",
                "started_at": started_at,
                "completed_at": utc_now(),
                "status": "registered_raw",
                "records_read": 1,
                "records_written": 1,
                "operator": actor,
                "script_version": "intake_v1",
                "notes": "Raw package registered; no staging, standardization, or curation performed.",
            }
        )
        if metadata.run_inventory_after_upload:
            run_inventory(submission_id, actor=actor)
        return safe_submission(submission_id)
    except Exception:
        temp_path.unlink(missing_ok=True)
        if "submission_root" in locals() and submission_root.exists():
            shutil.rmtree(submission_root, ignore_errors=True)
        raise
    finally:
        await file.close()


def run_inventory(submission_id: str, *, actor: str = "") -> dict[str, object]:
    paths = storage.get_storage_paths()
    submission = registry.get_submission(paths.root, submission_id)
    if not submission:
        raise KeyError("Submission not found.")
    if submission["current_status"] == "duplicate_detected":
        raise UploadValidationError("Duplicate submissions must be registered as a new version before inventory.")
    submission_root = paths.raw_submissions / submission_id
    inspection_dir = submission_root / "inspection"
    reports_dir = submission_root / "reports"
    previous = submission.get("current_status", "")
    registry.update_submission(paths.root, submission_id, current_status="inventory_running", inventory_status="running", inventory_started_at=utc_now())
    registry.add_event(paths.root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="inventory_started", previous_status=previous, new_status="inventory_running", message="Safe inventory started against inspection files only.", actor=actor)
    report = _basic_inventory_report(submission, inspection_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "inventory_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    status = "inventory_complete"
    registry.update_submission(paths.root, submission_id, current_status=status, inventory_status="complete", classification_status=report["classification_status"], inventory_completed_at=utc_now())
    registry.add_event(paths.root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="inventory_completed", previous_status="inventory_running", new_status=status, message="Safe inventory report created. Human approval is still required before staging.", actor=actor)
    registry.add_event(paths.root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="ready_for_staging_review", previous_status=status, new_status=status, message="Inventory is ready for classification and staging review.", actor=actor)
    storage.build_stage_manifest()
    return {"submission_id": submission_id, "inventory_status": "complete", "classification_status": report["classification_status"], "run_id": report["run_id"]}


def list_submissions(**filters: Any) -> dict[str, object]:
    paths = storage.get_storage_paths()
    registry.ensure_intake_storage(paths.root)
    rows, total = registry.list_submissions(paths.root, **filters)
    return {
        "items": [safe_submission(row["submission_id"], row=row) for row in rows],
        "pagination": {"total": total, "limit": filters.get("limit", 100), "offset": filters.get("offset", 0), "has_more": filters.get("offset", 0) + filters.get("limit", 100) < total},
        "message": "No intake submissions have been registered yet." if total == 0 else "Intake submissions loaded.",
    }


def get_submission(submission_id: str) -> dict[str, object] | None:
    return safe_submission(submission_id)


def get_events(submission_id: str) -> dict[str, object]:
    paths = storage.get_storage_paths()
    return {"events": registry.list_events(paths.root, submission_id)}


def inventory_status(submission_id: str) -> dict[str, object] | None:
    item = safe_submission(submission_id)
    if not item:
        return None
    return {
        "submission_id": submission_id,
        "inventory_status": item["inventory_status"],
        "classification_status": item["classification_status"],
        "staging_status": item["staging_status"],
        "current_status": item["current_status"],
        "next_required_action": item["next_required_action"],
    }


def new_submission_id() -> str:
    return f"UPL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def submission_row(
    submission_id: str,
    metadata: IntakeMetadata,
    original_filename: str,
    stored_filename: str,
    source_format: str,
    size: int,
    sha256: str,
    mime_type: str | None,
    extension: str,
    current_status: str,
    duplicate_of: str | None,
) -> dict[str, object]:
    now = utc_now()
    return {
        "submission_id": submission_id,
        "submission_name": metadata.submission_name,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "utility_system": metadata.utility_system,
        "source_type": metadata.source_type,
        "source_format": source_format,
        "source_owner": metadata.source_owner,
        "source_description": metadata.source_description,
        "sensitivity_level": metadata.sensitivity_level,
        "project_id": metadata.project_id,
        "submitted_by": _safe_actor(metadata.submitted_by),
        "authorization_confirmed": int(metadata.authorization_confirmed),
        "file_size_bytes": size,
        "sha256": sha256,
        "mime_type": mime_type or "",
        "extension": extension,
        "current_status": current_status,
        "current_stage": "raw",
        "inventory_status": "not_started",
        "classification_status": "not_started",
        "staging_status": "not_approved",
        "duplicate_of_submission_id": duplicate_of or "",
        "created_at": now,
        "updated_at": now,
        "raw_registered_at": now if current_status == "registered_raw" else "",
        "inventory_started_at": "",
        "inventory_completed_at": "",
        "error_category": "",
        "safe_error_message": "",
        "notes": "",
    }


def file_row(submission_id: str, safe_filename: str, role: str, extension: str, size: int, sha256: str, status: str, notes: str) -> dict[str, object]:
    return {
        "file_id": str(uuid.uuid4()),
        "submission_id": submission_id,
        "safe_filename": sanitize_filename(safe_filename) if "/" not in safe_filename else safe_filename,
        "relative_role": role,
        "extension": extension,
        "size_bytes": size,
        "sha256": sha256,
        "validation_status": status,
        "notes": notes,
    }


def add_standard_events(root: Path, submission_id: str, actor: str, *, duplicate: bool = False, duplicate_of: str = "") -> None:
    registry.add_event(root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="upload_started", new_status="uploading", message="Upload stream received by local FastAPI intake.", actor=actor)
    registry.add_event(root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="upload_completed", previous_status="uploading", new_status="validating", message="Upload stream completed and checksum calculated.", actor=actor)
    if duplicate:
        registry.add_event(root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="duplicate_detected", previous_status="validating", new_status="duplicate_detected", message=f"Duplicate SHA-256 matched prior submission {duplicate_of}. Raw copy was not created.", actor=actor)
        return
    registry.add_event(root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="validation_passed", previous_status="validating", new_status="registered_raw", message="Package validation passed.", actor=actor)
    registry.add_event(root, event_id=str(uuid.uuid4()), submission_id=submission_id, event_type="raw_registered", previous_status="validating", new_status="registered_raw", message="Package moved into immutable Raw submission storage.", actor=actor)


def safe_submission(submission_id: str, *, row: dict[str, Any] | None = None) -> dict[str, object] | None:
    paths = storage.get_storage_paths()
    row = row or registry.get_submission(paths.root, submission_id)
    if not row:
        return None
    files = registry.list_files(paths.root, submission_id)
    return {
        "submission_id": row.get("submission_id", ""),
        "submission_name": row.get("submission_name", ""),
        "original_filename": row.get("original_filename", ""),
        "utility_system": row.get("utility_system", ""),
        "source_type": row.get("source_type", ""),
        "source_format": row.get("source_format", ""),
        "source_owner": row.get("source_owner", ""),
        "source_description": row.get("source_description", ""),
        "sensitivity_level": row.get("sensitivity_level", ""),
        "project_id": row.get("project_id", ""),
        "authorization_confirmed": bool(row.get("authorization_confirmed")),
        "file_size_bytes": row.get("file_size_bytes", 0),
        "sha256_prefix": str(row.get("sha256", ""))[:12],
        "mime_type": row.get("mime_type", ""),
        "extension": row.get("extension", ""),
        "current_status": row.get("current_status", ""),
        "current_stage": row.get("current_stage", ""),
        "inventory_status": row.get("inventory_status", ""),
        "classification_status": row.get("classification_status", ""),
        "staging_status": row.get("staging_status", ""),
        "duplicate_of_submission_id": row.get("duplicate_of_submission_id", ""),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
        "raw_registered_at": row.get("raw_registered_at", ""),
        "inventory_started_at": row.get("inventory_started_at", ""),
        "inventory_completed_at": row.get("inventory_completed_at", ""),
        "error_category": row.get("error_category", ""),
        "safe_error_message": row.get("safe_error_message", ""),
        "files": files,
        "lineage": ["Selected package", "Validated upload", "Raw registered source"] if row.get("current_status") != "duplicate_detected" else ["Selected package", "Duplicate detected"],
        "blockers": ["Duplicate requires explicit version registration"] if row.get("current_status") == "duplicate_detected" else [],
        "next_required_action": storage.next_action_for_submission(row),
    }


def _prepare_inspection_copy(raw_path: Path, inspection_dir: Path, source_format: str) -> None:
    if source_format in {"shapefile", "file_geodatabase"}:
        validate_zip_archive(str(raw_path))
        with zipfile.ZipFile(raw_path) as archive:
            archive.extractall(inspection_dir)
        return
    shutil.copy2(raw_path, inspection_dir / raw_path.name)


def _write_manifest(
    path: Path,
    submission_id: str,
    metadata: IntakeMetadata,
    original_filename: str,
    stored_filename: str,
    source_format: str,
    size: int,
    sha256: str,
    files: list[dict[str, object]],
    warnings: list[str],
) -> None:
    manifest = {
        "submission_id": submission_id,
        "submission_name": metadata.submission_name,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "utility_system": metadata.utility_system,
        "source_type": metadata.source_type,
        "source_format": source_format,
        "source_owner": metadata.source_owner,
        "source_description": metadata.source_description,
        "sensitivity_level": metadata.sensitivity_level,
        "project_id": metadata.project_id,
        "file_size_bytes": size,
        "sha256": sha256,
        "current_status": "registered_raw",
        "current_stage": "raw",
        "inventory_status": "not_started",
        "classification_status": "not_started",
        "staging_status": "not_approved",
        "authorization_confirmed": True,
        "created_at": utc_now(),
        "files": files,
        "lineage": ["browser_upload", "temporary_upload", "validated_package", "raw_registration"],
        "next_required_action": "Run inventory when ready; staging requires explicit human approval.",
        "blockers": warnings,
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _basic_inventory_report(submission: dict[str, Any], inspection_dir: Path) -> dict[str, object]:
    files = [path for path in inspection_dir.rglob("*") if path.is_file()]
    extension_counts: dict[str, int] = {}
    for path in files:
        extension_counts[path.suffix.lower() or "none"] = extension_counts.get(path.suffix.lower() or "none", 0) + 1
    report: dict[str, object] = {
        "run_id": str(uuid.uuid4()),
        "submission_id": submission["submission_id"],
        "source_format": submission["source_format"],
        "inventory_scope": "inspection_copy_only",
        "file_count": len(files),
        "extension_counts": extension_counts,
        "classification_status": "review_required",
        "layers": [],
        "limitations": ["V1 intake inventory does not convert, stage, repair, or publish source data."],
    }
    if submission["source_format"] == "spreadsheet" and str(submission.get("extension", "")).lower() == ".csv":
        report["tables"] = [_csv_summary(path) for path in files if path.suffix.lower() == ".csv"]
        report["classification_status"] = "pending_classification"
    elif submission["source_format"] == "pdf":
        report["pdf"] = {"page_count": "not_extracted", "readiness": "metadata_only"}
    return report


def _csv_summary(path: Path) -> dict[str, object]:
    with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        row_count = sum(1 for _ in reader)
    return {
        "table_name": path.stem,
        "row_count": row_count,
        "columns": header[:100],
        "potential_coordinate_fields": [column for column in header if column.lower() in {"x", "y", "lat", "latitude", "lon", "long", "longitude"}],
        "potential_id_fields": [column for column in header if "id" in column.lower()],
    }


def _safe_actor(value: str) -> str:
    value = (value or "").strip()
    if not value or "@" in value:
        return "local_operator"
    return value[:80]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
