import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from app.schemas.responses import (
    AssetSummaryResponse,
    AutomatedReviewRequest,
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
from app.services import review_automation
from app.services.connectivity_qa import ConnectivityQaError, service as connectivity_qa
from app.services.network_trace import NetworkTraceError, service as network_trace
from app.services.proposed_edits import ProposedEditError, service as proposed_edits
from app.services.utility_assets import UtilityAssetError, service as utility_assets
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


def _connectivity_call(callback: Callable[..., dict[str, Any]], *args: object) -> dict[str, Any]:
    try:
        return callback(*args)
    except ConnectivityQaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _trace_call(callback: Callable[..., dict[str, Any]], *args: object) -> dict[str, Any]:
    try:
        return callback(*args)
    except NetworkTraceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _proposal_call(callback: Callable[..., Any], *args: object) -> Any:
    try:
        return callback(*args)
    except ProposedEditError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


@router.get("/utility-assets/taxonomy")
def utility_asset_taxonomy() -> dict[str, object]:
    return utility_assets.taxonomy()


@router.get("/utility-assets/taxonomy/{utility_vertical}")
def utility_asset_vertical_taxonomy(utility_vertical: str) -> dict[str, object]:
    try:
        return utility_assets.taxonomy(utility_vertical)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/utility-assets")
def canonical_utility_assets(
    utility_vertical: str | None = None,
    asset_class: str | None = None,
    asset_subtype: str | None = None,
    lifecycle_status: str | None = None,
    operational_status: str | None = None,
    qa_status: str | None = None,
    review_status: str | None = None,
    owner_status: str | None = None,
    source_layer_id: str | None = None,
    provisional_relationships: bool | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return utility_assets.list_assets(locals())


@router.get("/utility-assets/canonicalization-plans")
def canonicalization_plans() -> dict[str, object]:
    return utility_assets.list_plans()


@router.get("/utility-assets/{asset_id}")
def canonical_utility_asset(asset_id: str) -> dict[str, object]:
    asset = utility_assets.asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return asset


@router.get("/utility-assets/{asset_id}/relationships")
def canonical_utility_asset_relationships(asset_id: str) -> dict[str, object]:
    if not utility_assets.asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found.")
    return utility_assets.relationships(asset_id)


@router.get("/utility-assets/{asset_id}/lineage")
def canonical_utility_asset_lineage(asset_id: str) -> dict[str, object]:
    try:
        return utility_assets.lineage(asset_id)
    except UtilityAssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/connectivity-qa/rules")
def connectivity_qa_rules() -> dict[str, object]:
    return connectivity_qa.rules()


@router.get("/connectivity-qa/rules/{utility_vertical}")
def connectivity_qa_vertical_rules(utility_vertical: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.rules, utility_vertical)


@router.post("/connectivity-qa/{utility_vertical}/runs")
def run_connectivity_qa(utility_vertical: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.run, utility_vertical, payload)


@router.post("/connectivity-qa/{utility_vertical}/runs/{qa_run_id}/calibrate")
def calibrate_connectivity_qa(
    utility_vertical: str,
    qa_run_id: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.calibrate, utility_vertical, qa_run_id, payload)


@router.get("/connectivity-qa/{utility_vertical}/calibration/status")
def connectivity_qa_calibration_status(utility_vertical: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.calibration_status, utility_vertical)


@router.get("/connectivity-qa/{utility_vertical}/calibration/runs")
def connectivity_qa_calibration_runs(
    utility_vertical: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.calibration_runs, utility_vertical, limit, offset)


@router.get("/connectivity-qa/{utility_vertical}/calibration/runs/{calibration_run_id}")
def connectivity_qa_calibration_run(utility_vertical: str, calibration_run_id: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.calibration_run, utility_vertical, calibration_run_id)


@router.get("/connectivity-qa/{utility_vertical}/issue-groups")
def connectivity_qa_issue_groups(
    utility_vertical: str,
    issue_family: str | None = None,
    severity: str | None = None,
    effective_blocking: bool | None = None,
    display_priority: str | None = None,
    trace_impact: str | None = None,
    review_status: str | None = None,
    asset_id: str | None = None,
    relationship_id: str | None = None,
    primary_rule_code: str | None = None,
    calibration_run_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.issue_groups, utility_vertical, locals())


@router.get("/connectivity-qa/{utility_vertical}/issue-groups/{issue_group_id}")
def connectivity_qa_issue_group(utility_vertical: str, issue_group_id: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.issue_group, utility_vertical, issue_group_id)


@router.post("/connectivity-qa/{utility_vertical}/issue-groups/{issue_group_id}/{action}")
def review_connectivity_qa_issue_group(
    utility_vertical: str,
    issue_group_id: str,
    action: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.review_issue_group, utility_vertical, issue_group_id, action, payload)


@router.get("/connectivity-qa/{utility_vertical}/calibrated-summary")
def connectivity_qa_calibrated_summary(utility_vertical: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.calibrated_summary, utility_vertical)


@router.get("/connectivity-qa/{utility_vertical}/status")
def connectivity_qa_status(utility_vertical: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.status, utility_vertical)


@router.get("/connectivity-qa/{utility_vertical}/runs")
def connectivity_qa_runs(
    utility_vertical: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.runs, utility_vertical, limit, offset)


@router.get("/connectivity-qa/{utility_vertical}/runs/{qa_run_id}")
def connectivity_qa_run(utility_vertical: str, qa_run_id: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.run_detail, utility_vertical, qa_run_id)


@router.get("/connectivity-qa/{utility_vertical}/summary")
def connectivity_qa_summary(utility_vertical: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.summary, utility_vertical)


@router.get("/connectivity-qa/{utility_vertical}/findings")
def connectivity_qa_findings(
    utility_vertical: str,
    qa_run_id: str | None = None,
    severity: str | None = None,
    blocking: bool | None = None,
    review_status: str | None = None,
    rule_code: str | None = None,
    asset_class: str | None = None,
    asset_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.findings, utility_vertical, locals())


@router.get("/connectivity-qa/{utility_vertical}/findings/{finding_id}")
def connectivity_qa_finding(utility_vertical: str, finding_id: str) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.finding, utility_vertical, finding_id)


@router.post("/connectivity-qa/{utility_vertical}/findings/{finding_id}/{action}")
def review_connectivity_qa_finding(
    utility_vertical: str,
    finding_id: str,
    action: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _connectivity_call(connectivity_qa.review, utility_vertical, finding_id, action, payload)


@router.get("/network-trace/types")
def network_trace_types() -> dict[str, object]:
    return _trace_call(network_trace.types)


@router.get("/network-trace/types/{utility_vertical}")
def network_trace_vertical_types(utility_vertical: str) -> dict[str, object]:
    return _trace_call(network_trace.types, utility_vertical)


@router.post("/network-trace/{utility_vertical}/runs")
def create_network_trace_run(
    utility_vertical: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _trace_call(network_trace.run, utility_vertical, payload)


@router.get("/network-trace/{utility_vertical}/status")
def network_trace_status(utility_vertical: str) -> dict[str, object]:
    return _trace_call(network_trace.status, utility_vertical)


@router.get("/network-trace/{utility_vertical}/calibration/status")
def network_trace_calibration_status(utility_vertical: str) -> dict[str, object]:
    return _trace_call(network_trace.calibration_status, utility_vertical)


@router.get("/network-trace/{utility_vertical}/calibration/runs")
def network_trace_calibration_runs(
    utility_vertical: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return _trace_call(network_trace.calibration_runs, utility_vertical, limit, offset)


@router.get("/network-trace/{utility_vertical}/calibration/runs/{calibration_run_id}")
def network_trace_calibration_run(
    utility_vertical: str,
    calibration_run_id: str,
) -> dict[str, object]:
    return _trace_call(network_trace.calibration_run, utility_vertical, calibration_run_id)


@router.get("/network-trace/{utility_vertical}/runs")
def network_trace_runs(
    utility_vertical: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    return _trace_call(network_trace.runs, utility_vertical, limit, offset)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}")
def network_trace_run(utility_vertical: str, trace_run_id: str) -> dict[str, object]:
    return _trace_call(network_trace.run_detail, utility_vertical, trace_run_id)


@router.post("/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrate")
def calibrate_network_trace_run(
    utility_vertical: str,
    trace_run_id: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _trace_call(network_trace.calibrate, utility_vertical, trace_run_id, payload)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}/paths")
def network_trace_paths(utility_vertical: str, trace_run_id: str) -> dict[str, object]:
    return _trace_call(network_trace.paths, utility_vertical, trace_run_id)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}/steps")
def network_trace_steps(utility_vertical: str, trace_run_id: str) -> dict[str, object]:
    return _trace_call(network_trace.steps, utility_vertical, trace_run_id)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}/events")
def network_trace_events(utility_vertical: str, trace_run_id: str) -> dict[str, object]:
    return _trace_call(network_trace.events, utility_vertical, trace_run_id)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrated-result")
def network_trace_calibrated_result(
    utility_vertical: str,
    trace_run_id: str,
) -> dict[str, object]:
    return _trace_call(network_trace.calibrated_result, utility_vertical, trace_run_id)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrated-events")
def network_trace_calibrated_events(
    utility_vertical: str,
    trace_run_id: str,
    scope: str | None = None,
    category: str | None = None,
    priority: int | None = Query(default=None, ge=0, le=9),
    primary: bool | None = None,
    path_id: str | None = None,
    asset_id: str | None = None,
    relationship_id: str | None = None,
    issue_group_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    filters = {
        key: value for key, value in {
            "scope": scope, "category": category, "priority": priority, "primary": primary,
            "path_id": path_id, "asset_id": asset_id, "relationship_id": relationship_id,
            "issue_group_id": issue_group_id, "limit": limit, "offset": offset,
        }.items() if value is not None
    }
    return _trace_call(network_trace.calibrated_events, utility_vertical, trace_run_id, filters)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}/safe-summary")
def network_trace_safe_summary(utility_vertical: str, trace_run_id: str) -> dict[str, object]:
    return _trace_call(network_trace.safe_summary, utility_vertical, trace_run_id)


@router.get("/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrated-safe-summary")
def network_trace_calibrated_safe_summary(
    utility_vertical: str,
    trace_run_id: str,
) -> dict[str, object]:
    return _trace_call(network_trace.calibrated_safe_summary, utility_vertical, trace_run_id)


@router.get("/network-trace/assets/{asset_id}/readiness")
def network_trace_asset_readiness(asset_id: str) -> dict[str, object]:
    return _trace_call(network_trace.readiness, asset_id)


@router.get("/proposed-edits/types")
def proposed_edit_types() -> dict[str, object]:
    return _proposal_call(proposed_edits.types)


@router.get("/proposed-edits/types/{utility_vertical}")
def proposed_edit_vertical_types(utility_vertical: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.types, utility_vertical)


@router.get("/proposed-edits/operation-types")
def proposed_edit_operation_types() -> dict[str, object]:
    return _proposal_call(proposed_edits.operation_types)


@router.get("/proposed-edits/{utility_vertical}")
def proposed_edit_list(
    utility_vertical: str,
    status: str | None = None,
    proposal_type: str | None = None,
    validation_status: str | None = None,
    approval_status: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    filters = {
        key: value for key, value in {
            "status": status, "proposal_type": proposal_type,
            "validation_status": validation_status, "approval_status": approval_status,
            "search": search, "limit": limit, "offset": offset,
        }.items() if value is not None
    }
    return _proposal_call(proposed_edits.list_proposals, utility_vertical, filters)


@router.post("/proposed-edits/{utility_vertical}")
def create_proposed_edit(utility_vertical: str, payload: dict[str, object]) -> dict[str, object]:
    return _proposal_call(proposed_edits.create_proposal, utility_vertical, payload)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}")
def proposed_edit_detail(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.proposal, utility_vertical, proposal_id)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/clone")
def clone_proposed_edit(
    utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.clone, utility_vertical, proposal_id, payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/new-version")
def version_proposed_edit(
    utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.new_version, utility_vertical, proposal_id, payload)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/operations")
def proposed_edit_operations(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.operations, utility_vertical, proposal_id)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/operations")
def add_proposed_edit_operation(
    utility_vertical: str, proposal_id: str, payload: dict[str, object],
) -> dict[str, object]:
    return _proposal_call(proposed_edits.add_operation, utility_vertical, proposal_id, payload)


@router.put("/proposed-edits/{utility_vertical}/{proposal_id}/operations/{operation_id}")
def update_proposed_edit_operation(
    utility_vertical: str, proposal_id: str, operation_id: str, payload: dict[str, object],
) -> dict[str, object]:
    return _proposal_call(proposed_edits.update_operation, utility_vertical, proposal_id, operation_id, payload)


@router.delete("/proposed-edits/{utility_vertical}/{proposal_id}/operations/{operation_id}")
def delete_proposed_edit_operation(
    utility_vertical: str, proposal_id: str, operation_id: str,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.delete_operation, utility_vertical, proposal_id, operation_id)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/validate")
def validate_proposed_edit(
    utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.validate, utility_vertical, proposal_id, payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/analyze")
def analyze_proposed_edit(
    utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.analyze, utility_vertical, proposal_id, payload)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/validation")
def proposed_edit_validation(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.validation, utility_vertical, proposal_id)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/overlay")
def proposed_edit_overlay(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.overlay, utility_vertical, proposal_id)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/qa-comparison")
def proposed_edit_qa_comparison(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.qa_comparison, utility_vertical, proposal_id)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/trace-comparisons")
def proposed_edit_trace_comparisons(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.trace_comparisons, utility_vertical, proposal_id)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/impact-summary")
def proposed_edit_impact(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.impact, utility_vertical, proposal_id)


def _review_proposed_edit(
    utility_vertical: str, proposal_id: str, action: str, payload: dict[str, object] | None,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.review, utility_vertical, proposal_id, action, payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/submit")
def submit_proposed_edit(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "submit", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/start-review")
def start_proposed_edit_review(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "start-review", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/request-revision")
def revise_proposed_edit(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "request-revision", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/approve")
def approve_proposed_edit(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "approve", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/reject")
def reject_proposed_edit(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "reject", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/defer")
def defer_proposed_edit(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "defer", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/withdraw")
def withdraw_proposed_edit(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "withdraw", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/reopen")
def reopen_proposed_edit(utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return _review_proposed_edit(utility_vertical, proposal_id, "reopen", payload)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/supersede")
def supersede_proposed_edit(
    utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.supersede, utility_vertical, proposal_id, payload)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/safe-summary")
def proposed_edit_safe_summary(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.safe_summary, utility_vertical, proposal_id)


@router.post("/proposed-edits/{utility_vertical}/{proposal_id}/implementation-package")
def create_proposed_edit_package(
    utility_vertical: str, proposal_id: str, payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return _proposal_call(proposed_edits.create_package, utility_vertical, proposal_id, payload)


@router.get("/proposed-edits/{utility_vertical}/{proposal_id}/implementation-package")
def proposed_edit_package(utility_vertical: str, proposal_id: str) -> dict[str, object]:
    return _proposal_call(proposed_edits.package, utility_vertical, proposal_id)


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


@router.post("/intake/submissions/{submission_id}/automated-review")
def run_intake_submission_automated_review(
    submission_id: str,
    request: AutomatedReviewRequest = AutomatedReviewRequest(),
) -> dict[str, object]:
    try:
        return review_automation.run_automated_review(submission_id, **request.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Submission not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Automated review failed safely; inspection results remain intact.") from exc


@router.post("/intake/submissions/{submission_id}/automated-review/rerun")
def rerun_intake_submission_automated_review(
    submission_id: str,
    request: AutomatedReviewRequest = AutomatedReviewRequest(force_recalculate=True),
) -> dict[str, object]:
    try:
        payload = request.model_dump()
        payload["force_recalculate"] = True
        return review_automation.run_automated_review(submission_id, **payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Submission not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Automated review failed safely; inspection results remain intact.") from exc


@router.get("/intake/submissions/{submission_id}/automated-review/status")
def intake_submission_automated_review_status(submission_id: str) -> dict[str, object]:
    return review_automation.status(submission_id)


@router.get("/intake/submissions/{submission_id}/automated-review/runs")
def intake_submission_automated_review_runs(submission_id: str) -> dict[str, object]:
    return review_automation.runs(submission_id)


@router.get("/intake/submissions/{submission_id}/automated-review/runs/{automation_run_id}")
def intake_submission_automated_review_run(submission_id: str, automation_run_id: str) -> dict[str, object]:
    run = review_automation.run_detail(submission_id, automation_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Automation run not found.")
    return run


@router.get("/intake/submissions/{submission_id}/automated-review/summary")
def intake_submission_automated_review_summary(submission_id: str) -> dict[str, object]:
    return review_automation.summary(submission_id)


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


@router.post("/intake/submissions/{submission_id}/layers/{layer_id}/canonicalization-plan")
def create_canonicalization_plan(submission_id: str, layer_id: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        return utility_assets.create_plan(submission_id, layer_id, payload)
    except UtilityAssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/intake/submissions/{submission_id}/layers/{layer_id}/canonicalization-plan")
def canonicalization_plan(submission_id: str, layer_id: str) -> dict[str, object]:
    return utility_assets.get_plan(submission_id, layer_id)


@router.put("/intake/submissions/{submission_id}/layers/{layer_id}/canonicalization-plan/field-mappings")
def update_canonicalization_field_mappings(
    submission_id: str, layer_id: str, payload: dict[str, object],
) -> dict[str, object]:
    try:
        return utility_assets.update_mappings(submission_id, layer_id, payload)
    except UtilityAssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/intake/submissions/{submission_id}/layers/{layer_id}/canonicalization-plan/approve")
def approve_canonicalization_plan(submission_id: str, layer_id: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        return utility_assets.approve_plan(submission_id, layer_id, payload)
    except UtilityAssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/intake/submissions/{submission_id}/layers/{layer_id}/canonicalization-plan/defer")
def defer_canonicalization_plan(submission_id: str, layer_id: str, payload: dict[str, object]) -> dict[str, object]:
    try:
        return utility_assets.defer_plan(submission_id, layer_id, payload)
    except UtilityAssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/intake/submissions/{submission_id}/layers/{layer_id}/canonicalization-plan/create-assets")
def create_assets_from_canonicalization_plan(
    submission_id: str, layer_id: str, payload: dict[str, object],
) -> dict[str, object]:
    try:
        return utility_assets.create_assets(submission_id, layer_id, payload)
    except UtilityAssetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


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
