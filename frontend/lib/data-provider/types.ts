import type {
  CalibrationRow,
  CommandCenterResponse,
  ComponentRow,
  Issue,
  IssuesResponse,
  MapData,
  MappingRow,
  NetworkResponse,
  Readiness,
  RuleRow,
} from "../api-types";

export type ProviderMode = "local" | "demo";

export type StorageStatus = Record<string, unknown>;
export type CatalogResponse = { datasets: Record<string, unknown>[]; message: string };
export type InventorySummary = Record<string, unknown>;
export type InventoryLayers = { layers: Record<string, unknown>[]; message?: string };
export type InventoryRecommendation = Record<string, unknown>;
export type RunsResponse = { runs: Record<string, string>[] };
export type TrustPipeline = Record<string, unknown>;
export type DemoPatchResult = Issue | { updated_count: number; updated_issue_ids: string[]; missing_issue_ids: string[] };
export type PrimaryDataStage = "raw" | "staging" | "standardized" | "curated" | "export";
export type IntakeSubmission = Record<string, unknown> & {
  submission_id: string;
  submission_name: string;
  original_filename: string;
  utility_system: string;
  source_format: string;
  sensitivity_level: string;
  current_status: string;
  current_stage: string;
  inventory_status: string;
  classification_status: string;
  staging_status: string;
  next_required_action: string;
};
export type IntakeEvent = { event_id: string; submission_id: string; event_type: string; message: string; created_at: string; previous_status?: string; new_status?: string; actor?: string };
export type IntakeCapabilities = Record<string, unknown> & { accepted_formats: Record<string, unknown>[]; maximum_upload_bytes: number; upload_enabled: boolean; mode: string };
export type IntakeSubmissionsResponse = { items: IntakeSubmission[]; pagination: Pagination; message: string };
export type IntakeSubmissionResponse = { submissions: IntakeSubmission[]; message: string };
export type DataSourceStage = { stage: PrimaryDataStage; label: string; item_count: number; description: string };
export type DataSourceItem = Record<string, unknown> & {
  item_id: string;
  name: string;
  stage: PrimaryDataStage;
  utility_system: string;
  network_group: string;
  asset_category: string;
  asset_subcategory: string;
  source_format: string;
  sensitivity_level: string;
  status: string;
  inventory_status: string;
  classification_status: string;
  staging_status: string;
  next_required_action: string;
};
export type StageManifest = { generated_at: string; stages: DataSourceStage[]; items: DataSourceItem[]; counts: Record<PrimaryDataStage, number>; message: string };
export type DataSourceItemsResponse = { items: DataSourceItem[]; pagination: Pagination };
export type Pagination = { total: number; limit: number; offset: number; has_more: boolean };

export interface PlatformDataProvider {
  readonly mode: ProviderMode;
  get<T>(path: string, signal?: AbortSignal): Promise<T>;
  post<T>(path: string, body?: BodyInit | Record<string, unknown>): Promise<T>;
  patch<T>(path: string, body: unknown): Promise<T>;
  commandCenter(signal?: AbortSignal): Promise<CommandCenterResponse>;
  storageStatus(signal?: AbortSignal): Promise<StorageStatus>;
  stageItems(signal?: AbortSignal): Promise<CatalogResponse>;
  itemDetails(path: string, signal?: AbortSignal): Promise<Record<string, unknown>>;
  lineage(signal?: AbortSignal): Promise<Record<string, unknown>>;
  inventory(signal?: AbortSignal): Promise<InventorySummary>;
  processingHistory(signal?: AbortSignal): Promise<RunsResponse>;
  dataHealthSummary(signal?: AbortSignal): Promise<Record<string, unknown>>;
  qaIssues(path: string, signal?: AbortSignal): Promise<IssuesResponse>;
  qaRules(signal?: AbortSignal): Promise<{ rules: RuleRow[] }>;
  reviewQueue(signal?: AbortSignal): Promise<IssuesResponse>;
  reviewCalibration(signal?: AbortSignal): Promise<{ rows: CalibrationRow[] }>;
  networkSummary(signal?: AbortSignal): Promise<NetworkResponse>;
  networkComponents(signal?: AbortSignal): Promise<{ items: ComponentRow[] }>;
  standardizationReadiness(signal?: AbortSignal): Promise<Readiness>;
  standardizationMappings(signal?: AbortSignal): Promise<{ mappings: MappingRow[] }>;
  trustPipeline(signal?: AbortSignal): Promise<TrustPipeline>;
  map(signal?: AbortSignal): Promise<MapData>;
  getIntakeCapabilities(signal?: AbortSignal): Promise<IntakeCapabilities>;
  createIntakeSubmission(formData: FormData): Promise<IntakeSubmissionResponse>;
  getIntakeSubmissions(path?: string, signal?: AbortSignal): Promise<IntakeSubmissionsResponse>;
  getIntakeSubmission(submissionId: string, signal?: AbortSignal): Promise<IntakeSubmission | null>;
  getIntakeEvents(submissionId: string, signal?: AbortSignal): Promise<{ events: IntakeEvent[] }>;
  startIntakeInventory(submissionId: string): Promise<Record<string, unknown>>;
  getIntakeInventoryStatus(submissionId: string, signal?: AbortSignal): Promise<Record<string, unknown>>;
  getDataSourceStages(signal?: AbortSignal): Promise<StageManifest>;
  getDataSourceItems(path?: string, signal?: AbortSignal): Promise<DataSourceItemsResponse>;
  getDataSourceItem(itemId: string, signal?: AbortSignal): Promise<DataSourceItem | null>;
  getDataSourceLineage(itemId: string, signal?: AbortSignal): Promise<Record<string, unknown>>;
  getDataSourceDiagnostics(signal?: AbortSignal): Promise<Record<string, unknown>>;
}
