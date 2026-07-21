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
export type IntakeCapabilities = Record<string, unknown> & { accepted_formats: Record<string, unknown>[]; maximum_upload_bytes: number; maximum_upload_files?: number; upload_enabled: boolean; mode: string };
export type IntakeSubmissionsResponse = { items: IntakeSubmission[]; pagination: Pagination; message: string };
export type IntakeSubmissionResponse = { submissions: IntakeSubmission[]; message: string };
export type UploadProgress = { loaded: number; total: number; percent: number };
export type SourceInspectionStatus = Record<string, unknown> & { submission_id: string; inspection_status: string; child_layer_count: number; table_count: number; spatial_reference_count: number; warnings?: string[]; blockers?: string[] };
export type SubmissionLayer = Record<string, unknown> & {
  layer_id: string;
  submission_id: string;
  source_layer_name: string;
  source_layer_alias?: string;
  owner_or_jurisdiction?: string;
  utility_system: string;
  network_group: string;
  asset_category: string;
  asset_subcategory: string;
  operational_role: string;
  lifecycle_representation: string;
  geometry_type: string;
  record_count?: number | string | null;
  spatial_reference_name?: string;
  confidence: string;
  routing_state: string;
  classification_status: string;
  duplicate_status: string;
  coordinate_status: string;
  staging_status: string;
};
export type ClassificationCandidate = Record<string, unknown> & {
  candidate_id: string;
  layer_id: string;
  rank: number;
  utility_system: string;
  network_group: string;
  asset_category: string;
  asset_subcategory: string;
  operational_role: string;
  lifecycle_representation: string;
  owner_or_jurisdiction: string;
  confidence: string;
  score: number;
  evidence: string[];
  warnings: string[];
};
export type DuplicateGroup = Record<string, unknown> & { duplicate_group_id: string; status: string; confidence: string; members: Record<string, unknown>[]; recommended_action: string };
export type StagingPlanItem = Record<string, unknown> & { staging_plan_item_id: string; layer_id: string; proposed_target_name: string; approved_for_staging: boolean; approval_status: string; blocker?: string };
export type SubmissionLayersResponse = { items: SubmissionLayer[]; pagination: Pagination; message: string };
export type ClassificationCandidatesResponse = { items: ClassificationCandidate[]; message: string };
export type DuplicateGroupsResponse = { items: DuplicateGroup[]; message: string };
export type StagingPlanResponse = { items: StagingPlanItem[]; message: string };
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
  createDirectoryIntakeSubmission(formData: FormData, onProgress?: (progress: UploadProgress) => void): Promise<IntakeSubmissionResponse>;
  getIntakeSubmissions(path?: string, signal?: AbortSignal): Promise<IntakeSubmissionsResponse>;
  getIntakeSubmission(submissionId: string, signal?: AbortSignal): Promise<IntakeSubmission | null>;
  getIntakeEvents(submissionId: string, signal?: AbortSignal): Promise<{ events: IntakeEvent[] }>;
  startIntakeInventory(submissionId: string): Promise<Record<string, unknown>>;
  getIntakeInventoryStatus(submissionId: string, signal?: AbortSignal): Promise<Record<string, unknown>>;
  startSourceInspection(submissionId: string): Promise<Record<string, unknown>>;
  getSourceInspectionStatus(submissionId: string, signal?: AbortSignal): Promise<SourceInspectionStatus>;
  getSubmissionLayers(submissionId: string, path?: string, signal?: AbortSignal): Promise<SubmissionLayersResponse>;
  getSubmissionLayer(submissionId: string, layerId: string, signal?: AbortSignal): Promise<SubmissionLayer | null>;
  getLayerClassificationCandidates(submissionId: string, layerId: string, signal?: AbortSignal): Promise<ClassificationCandidatesResponse>;
  reviewSubmissionLayer(submissionId: string, layerId: string, body: Record<string, unknown>): Promise<SubmissionLayer>;
  batchReviewSubmissionLayers(submissionId: string, body: Record<string, unknown>): Promise<Record<string, unknown>>;
  getDuplicateGroups(submissionId: string, signal?: AbortSignal): Promise<DuplicateGroupsResponse>;
  getDuplicateGroup(submissionId: string, groupId: string, signal?: AbortSignal): Promise<DuplicateGroup | null>;
  reviewDuplicateGroup(submissionId: string, groupId: string, body: Record<string, unknown>): Promise<DuplicateGroup>;
  createStagingPlan(submissionId: string): Promise<StagingPlanResponse>;
  getStagingPlan(submissionId: string, signal?: AbortSignal): Promise<StagingPlanResponse>;
  reviewStagingPlanItem(submissionId: string, itemId: string, body: Record<string, unknown>): Promise<StagingPlanItem>;
  stageApprovedLayers(submissionId: string): Promise<Record<string, unknown>>;
  getDataSourceStages(signal?: AbortSignal): Promise<StageManifest>;
  getDataSourceItems(path?: string, signal?: AbortSignal): Promise<DataSourceItemsResponse>;
  getDataSourceItem(itemId: string, signal?: AbortSignal): Promise<DataSourceItem | null>;
  getDataSourceLineage(itemId: string, signal?: AbortSignal): Promise<Record<string, unknown>>;
  getDataSourceDiagnostics(signal?: AbortSignal): Promise<Record<string, unknown>>;
}
