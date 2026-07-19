from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    application: str


class PlatformStatusResponse(BaseModel):
    application: str
    status: str
    database_connected: bool
    production_data_connected: bool
    message: str


class DataSourcesResponse(BaseModel):
    data_sources: list[dict[str, str]]
    message: str


class AssetSummaryResponse(BaseModel):
    total_assets: int | None
    network_mileage: float | None
    values_connected: bool
    message: str


class QaSummaryResponse(BaseModel):
    open_issues: int | None
    assets_requiring_review: int | None
    values_connected: bool
    message: str
