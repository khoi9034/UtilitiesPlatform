from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.schemas.responses import (
    AssetSummaryResponse,
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
from app.services.data_storage_service import (
    catalog_summary,
    inventory_recommendation,
    inventory_summary,
    read_inventory_layers,
    read_safe_catalog,
    storage_status,
)

router = APIRouter(prefix="/api")

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


@router.get("/data-health/wastewater/network")
def wastewater_health_network() -> dict[str, object]:
    return wastewater_health.network()


@router.get("/data-health/wastewater/runs")
def wastewater_health_runs() -> dict[str, object]:
    return wastewater_health.runs()


@router.get("/data-health/wastewater/map", response_model=None)
def wastewater_health_map() -> object:
    path = wastewater_health.map_layers_path()
    if not path.exists():
        return {"pipes": [], "manholes": [], "issues": []}
    return FileResponse(path, media_type="application/json")
