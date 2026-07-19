from fastapi import APIRouter

from app.schemas.responses import (
    AssetSummaryResponse,
    DatasetCatalogResponse,
    DatasetCatalogSummaryResponse,
    DataSourcesResponse,
    InventoryLayersResponse,
    InventoryRecommendationResponse,
    InventorySummaryResponse,
    PlatformStatusResponse,
    QaSummaryResponse,
    StorageStatusResponse,
)
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
    return QaSummaryResponse(
        open_issues=None,
        assets_requiring_review=None,
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
