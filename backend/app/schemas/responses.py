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
    by_utility_system: dict[str, int]
    by_network_group: dict[str, int]
    by_asset_category: dict[str, int]
    review_required_layers: int
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
    utility_system: str
    network_group: str
    asset_category: str
    asset_subcategory: str
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
    by_utility_system: dict[str, int]
    by_network_group: dict[str, int]
    by_asset_category: dict[str, int]
    by_stage: dict[str, int]
    by_source_format: dict[str, int]
    by_sensitivity_level: dict[str, int]
    message: str


class InventoryLayerRow(BaseModel):
    dataset_id: str
    source_name: str
    source_format: str
    utility_system: str
    network_group: str
    asset_category: str
    asset_subcategory: str
    classification_confidence: str
    likely_classifications: str
    recommended_classification: str
    layer_name: str
    geometry_type: str
    record_count: str
    spatial_reference: str
    sensitivity_level: str
    recommended_action: str


class InventorySummaryResponse(BaseModel):
    sources_discovered: int
    layer_count: int
    by_utility_system: dict[str, int]
    by_network_group: dict[str, int]
    by_asset_category: dict[str, int]
    by_confidence: dict[str, int]
    record_totals_by_system: dict[str, int]
    spatial_references: dict[str, int]
    recommended_staging_layers: int
    unknown_layers: int
    review_required_layers: int
    message: str


class InventoryLayersResponse(BaseModel):
    layers: list[InventoryLayerRow]
    message: str


class InventoryRecommendationResponse(BaseModel):
    recommendation_markdown: str
    allowlist: list[dict[str, str]]
    message: str
