from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from app.services import data_storage_service as storage
from app.services import intake_registry_service as intake_registry
from app.services.source_inspection import inspector_registry
from app.services.source_inspection.base import InspectionContext
from app.services.source_inspection.models import SourceContainer
from app.services.source_inspection.normalization import apply_coordinate_status, classify_layers, create_plan_items, detect_duplicate_groups, utc_now
from app.services.source_inspection import registry as inspection_registry
from app.services.source_inspection.file_gdb_inspector import arcpy_available, requires_arcpy
from app.services.upload_validation_service import UploadValidationError

ARCGIS_PRO_PYTHON = Path(r"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe")
WORKER_RESULT_PREFIX = "UTILITY_INSPECTION_RESULT="
SUBMISSION_ID_PATTERN = re.compile(r"^UPL-\d{8}-[A-F0-9]{8}$")


def inspect_submission(submission_id: str, *, actor: str = "") -> dict[str, object]:
    paths = storage.get_storage_paths()
    submission = intake_registry.get_submission(paths.root, submission_id)
    if not submission:
        raise KeyError("Submission not found.")
    inspection_dir = paths.raw_submissions / submission_id / "inspection"
    if (
        submission.get("source_format") == "file_geodatabase"
        and not os.environ.get("UTILITY_INSPECTION_ARCGIS_WORKER")
        and not arcpy_available()
        and requires_arcpy(inspection_dir)
    ):
        return inspect_with_arcgis_pro(submission_id, actor=actor)
    return _inspect_submission_in_process(submission_id, actor=actor)


def _inspect_submission_in_process(submission_id: str, *, actor: str = "") -> dict[str, object]:
    paths = storage.get_storage_paths()
    intake_registry.ensure_intake_storage(paths.root)
    submission = intake_registry.get_submission(paths.root, submission_id)
    if not submission:
        raise KeyError("Submission not found.")
    if submission["current_status"] == "duplicate_detected":
        raise UploadValidationError("Duplicate submissions must be registered as a new version before inspection.")

    submission_root = paths.raw_submissions / submission_id
    inspection_dir = submission_root / "inspection"
    reports_dir = submission_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    inspected_at = utc_now()
    previous = str(submission.get("current_status", ""))
    if not os.environ.get("UTILITY_INSPECTION_PARENT_STARTED"):
        intake_registry.update_submission(paths.root, submission_id, current_status="inspection_running", inventory_status="running")
        intake_registry.add_event(
            paths.root,
            event_id=str(uuid.uuid4()),
            submission_id=submission_id,
            event_type="source_inspection_started",
            previous_status=previous,
            new_status="inspection_running",
            message="Child-layer source inspection started against the inspection copy only.",
            actor=actor,
        )

    inspector = inspector_registry.inspector_for(str(submission.get("source_format", "")))
    if not inspector:
        container = unsupported_container(submission, run_id, inspected_at)
        layers = []
    else:
        container, layers = inspector.inspect(InspectionContext(submission=submission, inspection_dir=inspection_dir, reports_dir=reports_dir, run_id=run_id, inspected_at=inspected_at))
    candidates_by_layer = classify_layers(layers, submission)
    apply_coordinate_status(layers)
    duplicate_groups = detect_duplicate_groups(submission_id, layers)
    staging_items = create_plan_items(submission_id, layers, candidates_by_layer)
    inspection_registry.save_inspection(paths.root, container, layers, candidates_by_layer, duplicate_groups, staging_items)

    report = safe_report(container, layers, candidates_by_layer, duplicate_groups, staging_items)
    (reports_dir / "source_inspection_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    status = "inspection_complete" if container.inspection_status != "blocked" else "inspection_blocked"
    inspection_registry.record_run(
        paths.root,
        run_id=run_id,
        submission_id=submission_id,
        status=container.inspection_status,
        started_at=inspected_at,
        completed_at=utc_now(),
        safe_error_code="inspection_blocked" if container.blockers else "",
        safe_message=container.blockers[0] if container.blockers else "Inspection completed.",
        retryable=bool(container.blockers),
        child_layer_count=container.child_layer_count,
        table_count=container.table_count,
    )
    intake_registry.update_submission(
        paths.root,
        submission_id,
        current_status=status,
        inventory_status="complete" if status == "inspection_complete" else "blocked",
        classification_status="review_required",
        staging_status="not_approved",
        inventory_completed_at=inspected_at,
        error_category="" if status == "inspection_complete" else "inspection_blocked",
        safe_error_message="" if status == "inspection_complete" else (container.blockers[0] if container.blockers else "Inspection is blocked."),
    )
    intake_registry.add_event(
        paths.root,
        event_id=str(uuid.uuid4()),
        submission_id=submission_id,
        event_type="source_inspection_completed",
        previous_status="inspection_running",
        new_status=status,
        message="Child-layer inspection, classification candidates, duplicate candidates, and staging plan metadata were recorded.",
        actor=actor,
    )
    storage.build_stage_manifest()
    return {
        "submission_id": submission_id,
        "inspection_status": container.inspection_status,
        "inspection_run_id": run_id,
        "child_layer_count": container.child_layer_count,
        "table_count": container.table_count,
        "duplicate_group_count": len(duplicate_groups),
        "staging_plan_item_count": len(staging_items),
        "warnings": container.warnings,
        "blockers": container.blockers,
        "message": "Inspection completed. Human review is required before staging." if status == "inspection_complete" else "Inspection remains blocked; Raw registration was preserved.",
    }


def inspect_with_arcgis_pro(submission_id: str, *, actor: str = "") -> dict[str, object]:
    if not SUBMISSION_ID_PATTERN.fullmatch(submission_id):
        raise UploadValidationError("Invalid submission identifier.")
    paths = storage.get_storage_paths()
    submission = intake_registry.get_submission(paths.root, submission_id)
    if not submission:
        raise KeyError("Submission not found.")

    inspection_registry.archive_current_run(paths.root, submission_id)
    run_id = str(uuid.uuid4())
    started_at = utc_now()
    previous = str(submission.get("current_status", ""))
    intake_registry.update_submission(paths.root, submission_id, current_status="inspection_running", inventory_status="running")
    intake_registry.add_event(
        paths.root,
        event_id=str(uuid.uuid4()),
        submission_id=submission_id,
        event_type="source_inspection_started",
        previous_status=previous,
        new_status="inspection_running",
        message="Controlled ArcGIS Pro child-layer inspection started against the inspection copy only.",
        actor=actor,
    )

    worker = Path(__file__).with_name("arcgis_worker.py")
    if not ARCGIS_PRO_PYTHON.is_file() or not worker.is_file():
        return record_worker_failure(paths.root, submission_id, run_id, started_at, "arcgis_worker_unavailable", "The verified ArcGIS Pro inspection worker is unavailable.")
    env = os.environ.copy()
    env["UTILITY_INSPECTION_PARENT_STARTED"] = "1"
    try:
        completed = subprocess.run(
            [str(ARCGIS_PRO_PYTHON), str(worker), "--submission-id", submission_id],
            cwd=str(Path(__file__).resolve().parents[4]),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return record_worker_failure(paths.root, submission_id, run_id, started_at, "arcgis_inspection_timeout", "ArcGIS Pro inspection exceeded the five-minute safety timeout.")

    payload = parse_worker_result(completed.stdout)
    if completed.returncode == 0 and isinstance(payload.get("result"), dict):
        return dict(payload["result"])
    return record_worker_failure(
        paths.root,
        submission_id,
        run_id,
        started_at,
        str(payload.get("safe_error_code") or "arcgis_worker_failed"),
        str(payload.get("safe_message") or "ArcGIS Pro inspection failed safely."),
    )


def parse_worker_result(stdout: str) -> dict[str, object]:
    for line in reversed(stdout.splitlines()):
        if line.startswith(WORKER_RESULT_PREFIX):
            try:
                value = json.loads(line.removeprefix(WORKER_RESULT_PREFIX))
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def record_worker_failure(root: Path, submission_id: str, run_id: str, started_at: str, code: str, message: str) -> dict[str, object]:
    completed_at = utc_now()
    inspection_registry.record_run(
        root,
        run_id=run_id,
        submission_id=submission_id,
        status="blocked",
        started_at=started_at,
        completed_at=completed_at,
        safe_error_code=code,
        safe_message=message,
        retryable=True,
    )
    intake_registry.update_submission(
        root,
        submission_id,
        current_status="inspection_blocked",
        inventory_status="blocked",
        inventory_completed_at=completed_at,
        error_category=code,
        safe_error_message=message,
    )
    intake_registry.add_event(
        root,
        event_id=str(uuid.uuid4()),
        submission_id=submission_id,
        event_type="source_inspection_failed",
        previous_status="inspection_running",
        new_status="inspection_blocked",
        message=message,
        actor="arcgis_pro_worker",
    )
    storage.build_stage_manifest()
    return {
        "submission_id": submission_id,
        "inspection_status": "blocked",
        "inspection_run_id": run_id,
        "safe_error_code": code,
        "safe_message": message,
        "retryable": True,
        "message": "Inspection is blocked; the existing Raw registration was preserved.",
    }


def inspection_status(submission_id: str) -> dict[str, object] | None:
    paths = storage.get_storage_paths()
    submission = intake_registry.get_submission(paths.root, submission_id)
    if not submission:
        return None
    status = inspection_registry.inspection_status(paths.root, submission_id)
    if status:
        return status
    return {
        "submission_id": submission_id,
        "inspection_status": "not_started",
        "child_layer_count": 0,
        "table_count": 0,
        "spatial_reference_count": 0,
        "warnings": [],
        "blockers": [],
        "message": "Source inspection has not been started for this submission.",
    }


def list_layers(submission_id: str, **filters: Any) -> dict[str, object]:
    paths = storage.get_storage_paths()
    rows, total = inspection_registry.list_layers(paths.root, submission_id, **filters)
    limit = int(filters.get("limit", 100))
    offset = int(filters.get("offset", 0))
    return {
        "items": rows,
        "pagination": {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total},
        "message": "No child layers have been inspected yet." if total == 0 else "Inspected child layers loaded.",
    }


def layer_detail(submission_id: str, layer_id: str) -> dict[str, object] | None:
    return inspection_registry.layer_detail(storage.get_storage_paths().root, submission_id, layer_id)


def layer_candidates(submission_id: str, layer_id: str) -> dict[str, object]:
    del submission_id
    candidates = inspection_registry.layer_candidates(storage.get_storage_paths().root, layer_id)
    return {"items": candidates, "message": "No classification candidates recorded." if not candidates else "Classification candidates loaded."}


def review_submission_layer(submission_id: str, layer_id: str, payload: dict[str, Any]) -> dict[str, object]:
    return inspection_registry.add_layer_review(storage.get_storage_paths().root, submission_id, layer_id, payload)


def batch_review_submission_layers(submission_id: str, payload: dict[str, Any]) -> dict[str, object]:
    layer_ids = [str(item) for item in payload.get("layer_ids", [])]
    update = {key: value for key, value in payload.items() if key != "layer_ids"}
    updated: list[str] = []
    missing: list[str] = []
    for layer_id in layer_ids:
        try:
            inspection_registry.add_layer_review(storage.get_storage_paths().root, submission_id, layer_id, update)
            updated.append(layer_id)
        except KeyError:
            missing.append(layer_id)
    return {"updated_count": len(updated), "updated_layer_ids": updated, "missing_layer_ids": missing}


def duplicate_groups(submission_id: str) -> dict[str, object]:
    groups = inspection_registry.duplicate_groups(storage.get_storage_paths().root, submission_id)
    return {"items": groups, "message": "No duplicate candidates were detected." if not groups else "Duplicate candidate groups loaded."}


def duplicate_group_detail(submission_id: str, group_id: str) -> dict[str, object] | None:
    return inspection_registry.duplicate_group_detail(storage.get_storage_paths().root, submission_id, group_id)


def review_duplicate_group(submission_id: str, group_id: str, payload: dict[str, Any]) -> dict[str, object]:
    return inspection_registry.update_duplicate_group(storage.get_storage_paths().root, submission_id, group_id, payload)


def create_staging_plan(submission_id: str) -> dict[str, object]:
    items = inspection_registry.staging_plan(storage.get_storage_paths().root, submission_id)
    return {"items": items, "message": "Staging plan is generated from the latest source inspection and still requires human approval."}


def staging_plan(submission_id: str) -> dict[str, object]:
    items = inspection_registry.staging_plan(storage.get_storage_paths().root, submission_id)
    return {"items": items, "message": "No classification-approved layers are eligible for a staging preview." if not items else "Staging plan loaded."}


def review_staging_plan_item(submission_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, object]:
    return inspection_registry.update_staging_plan_item(storage.get_storage_paths().root, submission_id, item_id, payload)


def stage_approved_layers(submission_id: str) -> dict[str, object]:
    paths = storage.get_storage_paths()
    approved = [item for item in inspection_registry.staging_plan(paths.root, submission_id) if item.get("approved_for_staging")]
    if not approved:
        return {"submission_id": submission_id, "status": "nothing_to_stage", "staged_count": 0, "message": "No staging plan items have explicit approval."}
    try:
        import arcpy  # type: ignore
    except ImportError:
        return {
            "submission_id": submission_id,
            "status": "blocked",
            "staged_count": 0,
            "message": "ArcPy is required for source-preserving staging. Run the local API from the ArcGIS Pro Python environment.",
        }
    submission_root = paths.raw_submissions / submission_id
    gdb = next((path for path in (submission_root / "inspection").rglob("*.gdb") if path.is_dir()), None)
    if not gdb:
        return {"submission_id": submission_id, "status": "blocked", "staged_count": 0, "message": "No inspected file geodatabase workspace is available for staging."}
    output_root = paths.staging / "submissions" / submission_id
    output_gdb = output_root / f"{submission_id}_Staging.gdb"
    output_root.mkdir(parents=True, exist_ok=True)
    if not output_gdb.exists():
        arcpy.management.CreateFileGDB(str(output_root), output_gdb.name)
    staged = 0
    for item in approved:
        layer = inspection_registry.layer_detail(paths.root, submission_id, str(item["layer_id"]))
        if not layer:
            continue
        target = str(output_gdb / str(item["proposed_target_name"]))
        if arcpy.Exists(target):
            continue
        arcpy.management.CopyFeatures(str(gdb / str(layer["source_layer_name"])), target)
        staged += 1
    storage.append_processing_history(
        {
            "run_id": str(uuid.uuid4()),
            "dataset_id": submission_id,
            "process_name": "submission_specific_staging",
            "input_path": f"raw_submission:{submission_id}",
            "output_path": "submission_specific_staging_workspace",
            "started_at": utc_now(),
            "completed_at": utc_now(),
            "status": "complete" if staged else "no_new_outputs",
            "records_read": "",
            "records_written": staged,
            "operator": "local_operator",
            "script_version": "source_inspection_v1",
            "notes": "Approved child layers copied without projection, repair, schema translation, standardization, or curation.",
        }
    )
    storage.build_stage_manifest()
    return {"submission_id": submission_id, "status": "complete", "staged_count": staged, "message": "Approved layers were copied into submission-specific staging."}


def unsupported_container(submission: dict[str, Any], run_id: str, inspected_at: str) -> SourceContainer:
    return SourceContainer(
        submission_id=str(submission["submission_id"]),
        container_id=f"container-{submission['submission_id']}",
        container_name=str(submission.get("original_filename", "")),
        source_format=str(submission.get("source_format", "")),
        source_type=str(submission.get("source_type", "")),
        package_utility_system=str(submission.get("utility_system", "")),
        source_owner=str(submission.get("source_owner", "")),
        project_id=str(submission.get("project_id", "")),
        sensitivity_level=str(submission.get("sensitivity_level", "")),
        inspection_status="unsupported",
        inspection_run_id=run_id,
        inspected_at=inspected_at,
        blockers=["No source inspector is registered for this source format."],
    )


def safe_report(container: SourceContainer, layers: list[Any], candidates_by_layer: dict[str, list[Any]], duplicate_groups: list[Any], staging_items: list[Any]) -> dict[str, object]:
    return {
        "container": container.to_row(),
        "layers": [
            {
                "layer_id": layer.layer_id,
                "source_layer_name": layer.source_layer_name,
                "object_type": layer.object_type,
                "geometry_type": layer.geometry_type,
                "record_count": layer.record_count,
                "spatial_reference_name": layer.spatial_reference_name,
                "field_count": layer.field_count,
                "routing_state": layer.routing_state,
                "duplicate_status": layer.duplicate_status,
                "coordinate_status": layer.coordinate_status,
                "top_candidate": candidates_by_layer[layer.layer_id][0].to_row() if candidates_by_layer.get(layer.layer_id) else {},
            }
            for layer in layers
        ],
        "duplicate_groups": [
            {
                "duplicate_group_id": group.duplicate_group_id,
                "comparison_type": group.comparison_type,
                "confidence": group.confidence,
                "status": group.status,
                "member_count": len(group.members),
            }
            for group in duplicate_groups
        ],
        "staging_plan": [
            {
                "staging_plan_item_id": item.staging_plan_item_id,
                "layer_id": item.layer_id,
                "proposed_target_name": item.proposed_target_name,
                "approval_status": item.approval_status,
                "blocker": item.blocker,
            }
            for item in staging_items
        ],
    }
