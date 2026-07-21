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

export interface PlatformDataProvider {
  readonly mode: ProviderMode;
  get<T>(path: string, signal?: AbortSignal): Promise<T>;
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
}
