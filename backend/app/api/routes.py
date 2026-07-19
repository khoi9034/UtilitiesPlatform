from fastapi import APIRouter

from app.schemas.responses import (
    AssetSummaryResponse,
    DataSourcesResponse,
    PlatformStatusResponse,
    QaSummaryResponse,
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
