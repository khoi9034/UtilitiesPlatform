import type { CatalogResponse, InventorySummary, PlatformDataProvider, RunsResponse, StorageStatus, TrustPipeline } from "./types";
import type { CalibrationRow, CommandCenterResponse, ComponentRow, IssuesResponse, MapData, MappingRow, NetworkResponse, Readiness, RuleRow } from "../api-types";

export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiDataProvider implements PlatformDataProvider {
  readonly mode = "local" as const;

  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${apiUrl}${path}`, { signal });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json() as Promise<T>;
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${apiUrl}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json() as Promise<T>;
  }

  commandCenter(signal?: AbortSignal) { return this.get<CommandCenterResponse>("/api/platform/command-center?utility_system=wastewater", signal); }
  storageStatus(signal?: AbortSignal) { return this.get<StorageStatus>("/api/storage/status", signal); }
  stageItems(signal?: AbortSignal) { return this.get<CatalogResponse>("/api/storage/catalog", signal); }
  itemDetails(path: string, signal?: AbortSignal) { return this.get<Record<string, unknown>>(path, signal); }
  lineage(signal?: AbortSignal) { return this.get<Record<string, unknown>>("/api/trust-pipeline/wastewater", signal); }
  inventory(signal?: AbortSignal) { return this.get<InventorySummary>("/api/inventory/summary", signal); }
  processingHistory(signal?: AbortSignal) { return this.get<RunsResponse>("/api/data-health/wastewater/runs", signal); }
  dataHealthSummary(signal?: AbortSignal) { return this.get<Record<string, unknown>>("/api/data-health/wastewater/summary", signal); }
  qaIssues(path: string, signal?: AbortSignal) { return this.get<IssuesResponse>(path, signal); }
  qaRules(signal?: AbortSignal) { return this.get<{ rules: RuleRow[] }>("/api/data-health/wastewater/rules", signal); }
  reviewQueue(signal?: AbortSignal) { return this.get<IssuesResponse>("/api/review/wastewater/queue", signal); }
  reviewCalibration(signal?: AbortSignal) { return this.get<{ rows: CalibrationRow[] }>("/api/review/wastewater/calibration", signal); }
  networkSummary(signal?: AbortSignal) { return this.get<NetworkResponse>("/api/data-health/wastewater/network", signal); }
  networkComponents(signal?: AbortSignal) { return this.get<{ items: ComponentRow[] }>("/api/data-health/wastewater/components", signal); }
  standardizationReadiness(signal?: AbortSignal) { return this.get<Readiness>("/api/standardization/wastewater/readiness", signal); }
  standardizationMappings(signal?: AbortSignal) { return this.get<{ mappings: MappingRow[] }>("/api/standardization/wastewater/mappings", signal); }
  trustPipeline(signal?: AbortSignal) { return this.get<TrustPipeline>("/api/trust-pipeline/wastewater", signal); }
  map(signal?: AbortSignal) { return this.get<MapData>("/api/data-health/wastewater/map", signal); }
}
