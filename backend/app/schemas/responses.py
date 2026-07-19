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


class StorageStatusResponse(BaseModel):
    configured: bool
    master_root_available: bool
    raw_folder_available: bool
    staging_folder_available: bool
    standardized_folder_available: bool
    curated_folder_available: bool
    export_folder_available: bool
    catalog_available: bool
    geodatabases: dict[str, str]


class DatasetCatalogRow(BaseModel):
    dataset_id: str
    dataset_name: str
    utility_type: str
    asset_category: str
    source_format: str
    geometry_type: str
    coordinate_system: str
    record_count: str
    sensitivity_level: str
    current_stage: str
    approved_for_analysis: str
    approved_for_export: str
    approved_for_public_use: str
    date_inventoried: str
    last_processed: str


class DatasetCatalogResponse(BaseModel):
    datasets: list[DatasetCatalogRow]
    message: str


class DatasetCatalogSummaryResponse(BaseModel):
    total_datasets: int
    by_utility_type: dict[str, int]
    by_stage: dict[str, int]
    by_source_format: dict[str, int]
    by_sensitivity_level: dict[str, int]
    message: str
