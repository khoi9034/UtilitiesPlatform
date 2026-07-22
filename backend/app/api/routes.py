import logging
import os

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from app.schemas.responses import (
    AssetSummaryResponse,
    BatchIssueReviewUpdate,
    ComponentReviewUpdate,
    DatasetCatalogResponse,
    DatasetCatalogSummaryResponse,
    DataSourcesResponse,
    InventoryLayersResponse,
    InventoryRecommendationResponse,
    InventorySummaryResponse,
    IssueReviewUpdate,
    PlatformStatusResponse,
    QaSummaryResponse,
    StorageStatusResponse,
)
from app.services import wastewater_data_health_service as wastewater_health
from app.services import intake_service
from app.services import source_inspection
from app.services.upload_validation_service import UploadValidationError
from app.services.data_storage_service import (
    catalog_summary,
    build_stage_manifest,
    data_source_diagnostics,
    data_source_item,
    data_source_items,
    data_source_lineage,
    inventory_recommendation,
    inventory_summary,
    read_inventory_layers,
    read_safe_catalog,
    storage_status,
)

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

NO_DATABASE_MESSAGE = "No production utility database has been connected."


@router.get("/platform/status", response_model=PlatformStatusResponse)
def platform_status() -> PlatformStatusResponse:
    return PlatformStatusResponse(
        application="Utilities Platform",
        status="foundation-ready",
        database_connected=False,
        production_data_connected=False,
        message=NO_DATABASE_MESSAGE,
    )


@router.get("/platform/command-center")
def platform_command_center(utility_system: str = "wastewater") -> dict[str, object]:
    if utility_system not in {"wastewater", "all"}:
        return {
            "utility_system": utility_system,
            "generated_at": "",
            "platform_status": "not_onboarded",
            "assets": {"total": None, "by_network_group": {}, "by_asset_category": {}},
            "qa": {"total_findings": None, "by_severity": {}, "open_reviews": None, "reviewed_findings": None, "review_sample": None, "high_priority": None},
            "network": {"endpoint_match_rate": None, "connected_components": None, "isolated_pipes": None, "isolated_manholes": None, "unmatched_endpoints": None},
            "pipeline": {"current_stage": "Not onboarded", "stages": []},
            "dependencies": {"available": 0, "total": 0, "missing": []},
            "recent_runs": [],
            "storage": {},
            "module_status": [],
        }
    return wastewater_health.command_center()


@router.get("/data-sources", response_model=DataSourcesResponse)
def data_sources() -> DataSourcesResponse:
    return DataSourcesResponse(data_sources=[], message=NO_DATABASE_MESSAGE)


@router.get("/assets/summary", response_model=AssetSummaryResponse)
def assets_summary() -> AssetSummaryResponse:
    return AssetSummaryResponse(
        total_assets=None,
        network_mileage=None,
        values_connected=False,
        message=NO_DATABASE_MESSAGE,
    )


@router.get("/qa/summary", response_model=QaSummaryResponse)
def qa_summary() -> QaSummaryResponse:
    summary = inventory_summary()
    return QaSummaryResponse(
        open_issues=None,
        assets_requiring_review=summary.get("review_required_layers", 0),
        by_utility_system=summary.get("by_utility_system", {}),
        by_network_group=summary.get("by_network_group", {}),
        by_asset_category=summary.get("by_asset_category", {}),
        review_required_layers=summary.get("review_required_layers", 0),
        values_connected=False,
        message=NO_DATABASE_MESSAGE,
    )


@router.get("/storage/status", response_model=StorageStatusResponse)
def get_storage_status() -> dict[str, object]:
    return storage_status()


@router.get("/storage/catalog", response_model=DatasetCatalogResponse)
def get_storage_catalog() -> DatasetCatalogResponse:
    rows = read_safe_catalog()
    message = "No utility datasets have been registered yet." if not rows else "Dataset catalog loaded."
    return DatasetCatalogResponse(datasets=rows, message=message)


@router.get("/storage/catalog/summary", response_model=DatasetCatalogSummaryResponse)
def get_storage_catalog_summary() -> dict[str, object]:
    return catalog_summary()


@router.get("/inventory/summary", response_model=InventorySummaryResponse)
def get_inventory_summary() -> dict[str, object]:
    return inventory_summary()


@router.get("/inventory/layers", response_model=InventoryLayersResponse)
def get_inventory_layers() -> InventoryLayersResponse:
    layers = read_inventory_layers()
    message = "No inventory report has been generated yet." if not layers else "Inventory layers loaded."
    return InventoryLayersResponse(layers=layers, message=message)


@router.get("/inventory/recommendation", response_model=InventoryRecommendationResponse)
def get_inventory_recommendation() -> dict[str, object]:
    return inventory_recommendation()


@router.get("/intake/capabilities")
def intake_capabilities() -> dict[str, object]:
    return intake_service.capabilities()


@router.post("/intake/submissions")
async def create_intake_submission(
    files: list[UploadFile] = File(...),
    submission_name: str = Form(...),
    utility_system: str = Form(...),
    source_type: str = Form(...),
    source_owner: str = Form(...),
    source_description: str = Form(...),
    sensitivity_level: str = Form("restricted"),
    project_id: str = Form(""),
    submitted_by: str = Form(""),
    authorization_confirmed: bool = Form(False),
    register_duplicate_as_version: bool = Form(False),
    run_inventory_after_upload: bool = Form(False),
) -> dict[str, object]:
    try:
        metadata = intake_service.IntakeMetadata(
            submission_name=submission_name,
            utility_system=utility_system,
            source_type=source_type,
            source_owner=source_owner,
            source_description=source_description,
            sensitivity_level=sensitivity_level,
            project_id=project_id,
            submitted_by=submitted_by,
            authorization_confirmed=authorization_confirmed,
            register_duplicate_as_version=register_duplicate_as_version,
            run_inventory_after_upload=run_inventory_after_upload,
        )
        return await intake_service.create_submissions(files, metadata)
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/intake/submissions/directory")
async def create_directory_intake_submission(
    request: Request,
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
    omitted_relative_paths: list[str] = Form(default=[]),
    submission_name: str = Form(...),
    utility_system: str = Form(...),
    source_type: str = Form(...),
    source_owner: str = Form(...),
    source_description: str = Form(...),
    sensitivity_level: str = Form("restricted"),
    project_id: str = Form(""),
    submitted_by: str = Form(""),
    authorization_confirmed: bool = Form(False),
    register_duplicate_as_version: bool = Form(False),
    run_inventory_after_upload: bool = Form(False),
) -> dict[str, object]:
    request_id = str(getattr(request.state, "request_id", ""))
    if os.getenv("UTILITY_INTAKE_DIAGNOSTICS") == "1":
        metadata_present = [
            name
            for name, value in {
                "submission_name": submission_name,
                "utility_system": utility_system,
                "source_type": source_type,
                "source_owner": source_owner,
                "source_description": source_description,
                "sensitivity_level": sensitivity_level,
                "submitted_by": submitted_by,
                "authorization_confirmed": authorization_confirmed,
            }.items()
            if value not in {None, "", False}
        ]
        logger.info(
            "Directory intake request request_id=%s files_count=%d relative_paths_count=%d metadata_fields_present=%s aggregate_declared_size=%d",
            request_id,
            len(files),
            len(relative_paths),
            metadata_present,
            sum(int(file.size or 0) for file in files),
        )
    try:
        metadata = intake_service.IntakeMetadata(
            submission_name=submission_name,
            utility_system=utility_system,
            source_type=source_type,
            source_owner=source_owner,
            source_description=source_description,
            sensitivity_level=sensitivity_level,
            project_id=project_id,
            submitted_by=submitted_by,
            authorization_confirmed=authorization_confirmed,
            register_duplicate_as_version=register_duplicate_as_version,
            run_inventory_after_upload=run_inventory_after_upload,
        )
        return await intake_service.create_directory_submission(files, relative_paths, metadata, omitted_relative_paths)
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.as_detail(request_id=request_id)) from exc


@router.get("/intake/submissions")
def intake_submissions(
    status: str | None = None,
    utility_system: str | None = None,
    source_format: str | None = None,
    current_stage: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return intake_service.list_submissions(status=status, utility_system=utility_system, source_format=source_format, current_stage=current_stage, search=search, limit=limit, offset=offset)


@router.get("/intake/submissions/{submission_id}")
def intake_submission(submission_id: str) -> dict[str, object]:
    submission = intake_service.get_submission(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return submission


@router.get("/intake/submissions/{submission_id}/events")
def intake_submission_events(submission_id: str) -> dict[str, object]:
    return intake_service.get_events(submission_id)


@router.post("/intake/submissions/{submission_id}/inventory")
def intake_submission_inventory(submission_id: str) -> dict[str, object]:
    try:
        return intake_service.run_inventory(submission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Submission not found.") from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/intake/submissions/{submission_id}/inventory-status")
def intake_submission_inventory_status(submission_id: str) -> dict[str, object]:
    status = intake_service.inventory_status(submission_id)
    if not status:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return status


@router.post("/intake/submissions/{submission_id}/inspect")
def inspect_intake_submission(submission_id: str) -> dict[str, object]:
    try:
        return source_inspection.inspect_submission(submission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Submission not found.") from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/intake/submissions/{submission_id}/inspection-status")
def intake_submission_inspection_status(submission_id: str) -> dict[str, object]:
    status = source_inspection.inspection_status(submission_id)
    if not status:
        raise HTTPException(status_code=404, detail="Submission not found.")
    return status


@router.get("/intake/submissions/{submission_id}/layers")
def intake_submission_layers(
    submission_id: str,
    utility_system: str | None = None,
    network_group: str | None = None,
    asset_category: str | None = None,
    asset_subcategory: str | None = None,
    operational_role: str | None = None,
    lifecycle_representation: str | None = None,
    classification_status: str | None = None,
    duplicate_status: str | None = None,
    coordinate_status: str | None = None,
    staging_status: str | None = None,
    confidence: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return source_inspection.list_layers(
        submission_id,
        utility_system=utility_system,
        network_group=network_group,
        asset_category=asset_category,
        asset_subcategory=asset_subcategory,
        operational_role=operational_role,
        lifecycle_representation=lifecycle_representation,
        classification_status=classification_status,
        duplicate_status=duplicate_status,
        coordinate_status=coordinate_status,
        staging_status=staging_status,
        confidence=confidence,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/intake/submissions/{submission_id}/layers/{layer_id}")
def intake_submission_layer(submission_id: str, layer_id: str) -> dict[str, object]:
    layer = source_inspection.layer_detail(submission_id, layer_id)
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found.")
    return layer


@router.get("/intake/submissions/{submission_id}/layers/{layer_id}/candidates")
def intake_submission_layer_candidates(submission_id: str, layer_id: str) -> dict[str, object]:
    return source_inspection.layer_candidates(submission_id, layer_id)


@router.patch("/intake/submissions/{submission_id}/layers/{layer_id}/review")
def review_intake_submission_layer(submission_id: str, layer_id: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        return source_inspection.review_submission_layer(submission_id, layer_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Layer not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/intake/submissions/{submission_id}/layers/batch-review")
def batch_review_intake_submission_layers(submission_id: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        return source_inspection.batch_review_submission_layers(submission_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/intake/submissions/{submission_id}/duplicate-groups")
def intake_submission_duplicate_groups(submission_id: str) -> dict[str, object]:
    return source_inspection.duplicate_groups(submission_id)


@router.get("/intake/submissions/{submission_id}/duplicate-groups/{group_id}")
def intake_submission_duplicate_group(submission_id: str, group_id: str) -> dict[str, object]:
    group = source_inspection.duplicate_group_detail(submission_id, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Duplicate group not found.")
    return group


@router.patch("/intake/submissions/{submission_id}/duplicate-groups/{group_id}")
def review_intake_submission_duplicate_group(submission_id: str, group_id: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        return source_inspection.review_duplicate_group(submission_id, group_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Duplicate group not found.") from exc


@router.post("/intake/submissions/{submission_id}/staging-plan")
def create_intake_submission_staging_plan(submission_id: str) -> dict[str, object]:
    return source_inspection.create_staging_plan(submission_id)


@router.get("/intake/submissions/{submission_id}/staging-plan")
def intake_submission_staging_plan(submission_id: str) -> dict[str, object]:
    return source_inspection.staging_plan(submission_id)


@router.patch("/intake/submissions/{submission_id}/staging-plan/{item_id}")
def review_intake_submission_staging_plan_item(submission_id: str, item_id: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        return source_inspection.review_staging_plan_item(submission_id, item_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Staging plan item not found.") from exc


@router.post("/intake/submissions/{submission_id}/stage-approved")
def stage_approved_intake_submission_layers(submission_id: str) -> dict[str, object]:
    return source_inspection.stage_approved_layers(submission_id)


@router.get("/data-sources/stages")
def data_source_stages() -> dict[str, object]:
    return build_stage_manifest()


@router.get("/data-sources/items")
def data_source_items_api(
    stage: str | None = None,
    utility_system: str | None = None,
    network_group: str | None = None,
    asset_category: str | None = None,
    asset_subcategory: str | None = None,
    source_format: str | None = None,
    sensitivity: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return data_source_items(stage=stage, utility_system=utility_system, network_group=network_group, asset_category=asset_category, asset_subcategory=asset_subcategory, source_format=source_format, sensitivity=sensitivity, status=status, search=search, limit=limit, offset=offset)


@router.get("/data-sources/items/{item_id}")
def data_source_item_api(item_id: str) -> dict[str, object]:
    item = data_source_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Data source item not found.")
    return item


@router.get("/data-sources/items/{item_id}/lineage")
def data_source_item_lineage_api(item_id: str) -> dict[str, object]:
    return data_source_lineage(item_id)


@router.get("/data-sources/diagnostics")
def data_source_diagnostics_api() -> dict[str, object]:
    return data_source_diagnostics()


@router.get("/data-health/wastewater/summary")
def wastewater_health_summary() -> dict[str, object]:
    return wastewater_health.summary()


@router.get("/data-health/wastewater/rules")
def wastewater_health_rules() -> dict[str, object]:
    return wastewater_health.rules()


@router.get("/data-health/wastewater/issues")
def wastewater_health_issues(
    severity: str | None = None,
    category: str | None = None,
    rule_code: str | None = None,
    review_status: str | None = None,
    disposition: str | None = None,
    source_layer: str | None = None,
    run_id: str | None = None,
    asset: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return wastewater_health.issues(
        severity=severity,
        category=category,
        rule_code=rule_code,
        review_status=review_status,
        disposition=disposition,
        source_layer=source_layer,
        run_id=run_id,
        asset=asset,
        limit=limit,
        offset=offset,
    )


@router.get("/data-health/wastewater/issues/{issue_id}")
def wastewater_health_issue(issue_id: str) -> dict[str, object]:
    issue = wastewater_health.issue_detail(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return issue


@router.patch("/data-health/wastewater/issues/{issue_id}")
def update_wastewater_health_issue(issue_id: str, update: IssueReviewUpdate) -> dict[str, object]:
    try:
        issue = wastewater_health.update_issue(issue_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return issue


@router.get("/review/wastewater/queue")
def wastewater_review_queue(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, object]:
    return wastewater_health.review_queue(limit=limit, offset=offset)


@router.patch("/review/wastewater/issues/batch")
def update_wastewater_issues_batch(update: BatchIssueReviewUpdate) -> dict[str, object]:
    try:
        issue_update = IssueReviewUpdate(**update.model_dump(exclude={"issue_ids"}))
        return wastewater_health.batch_update_issue_reviews(update.issue_ids, issue_update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/review/wastewater/calibration")
def wastewater_review_calibration() -> dict[str, object]:
    return wastewater_health.calibration()


@router.get("/review/wastewater/sample")
def wastewater_review_sample() -> dict[str, object]:
    return wastewater_health.review_sample()


@router.get("/review/wastewater/data-owner-questions")
def wastewater_data_owner_questions() -> dict[str, str]:
    return wastewater_health.data_owner_questions()


@router.get("/data-health/wastewater/network")
def wastewater_health_network() -> dict[str, object]:
    return wastewater_health.network()


@router.get("/data-health/wastewater/components")
def wastewater_components(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, object]:
    return wastewater_health.components(limit=limit, offset=offset)


@router.get("/data-health/wastewater/components/{component_id}")
def wastewater_component(component_id: str) -> dict[str, object]:
    component = wastewater_health.component_detail(component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found.")
    return component


@router.patch("/data-health/wastewater/components/{component_id}")
def update_wastewater_component(component_id: str, update: ComponentReviewUpdate) -> dict[str, object]:
    try:
        component = wastewater_health.update_component(component_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not component:
        raise HTTPException(status_code=404, detail="Component not found.")
    return component


@router.get("/data-health/wastewater/runs")
def wastewater_health_runs() -> dict[str, object]:
    return wastewater_health.runs()


@router.get("/data-health/wastewater/map", response_model=None)
def wastewater_health_map() -> object:
    path = wastewater_health.map_layers_path()
    if not path.exists():
        return {"pipes": [], "manholes": [], "issues": []}
    return FileResponse(path, media_type="application/json")


@router.get("/standardization/wastewater/readiness")
def wastewater_standardization_readiness() -> dict[str, object]:
    return wastewater_health.standardization_readiness()


@router.get("/standardization/wastewater/mappings")
def wastewater_standardization_mappings() -> dict[str, object]:
    return wastewater_health.standardization_mappings()


@router.get("/trust-pipeline/wastewater")
def wastewater_trust_pipeline() -> dict[str, object]:
    return wastewater_health.trust_pipeline()
