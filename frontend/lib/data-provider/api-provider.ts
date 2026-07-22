import type { CatalogResponse, ClassificationCandidatesResponse, DataSourceItem, DataSourceItemsResponse, DuplicateGroup, DuplicateGroupsResponse, IntakeCapabilities, IntakeEvent, IntakeSubmission, IntakeSubmissionResponse, IntakeSubmissionsResponse, InventorySummary, PlatformDataProvider, RunsResponse, SourceInspectionStatus, StageManifest, StagingPlanItem, StagingPlanResponse, StorageStatus, SubmissionLayer, SubmissionLayersResponse, TrustPipeline, UploadProgress } from "./types";
import type { CalibrationRow, CommandCenterResponse, ComponentRow, IssuesResponse, MapData, MappingRow, NetworkResponse, Readiness, RuleRow } from "../api-types";

export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly errorCode: string,
    public readonly detail: string,
    public readonly retryable: boolean,
    public readonly safeContext: Record<string, string | number | boolean>,
  ) {
    super(detail);
    this.name = "ApiRequestError";
  }
}

const safeContextKeys = new Set(["files_count", "relative_paths_count", "aggregate_size", "root_name", "raw_source_created", "request_id"]);

function safeApiText(value: unknown): string {
  const text = String(value ?? "").replace(/[A-Za-z]:[\\/][^\s"']+/g, "[local path hidden]").replace(/\\\\[^\s"']+/g, "[local path hidden]");
  return /traceback|stack trace|\bat\s+\S+\s*\(/i.test(text) ? "The backend rejected the request safely." : text.slice(0, 500);
}

function validationDetail(detail: unknown[]): string {
  const messages = detail.slice(0, 5).map((item) => {
    if (!item || typeof item !== "object") return "Invalid request field.";
    const row = item as Record<string, unknown>;
    const loc = Array.isArray(row.loc) ? safeApiText(row.loc.at(-1)) : "request";
    return `${loc}: ${safeApiText(row.msg || "Invalid value.")}`;
  });
  return `Request validation failed. ${messages.join("; ")}`;
}

export function parseApiRequestError(status: number, statusText: string, responseText: string, requestId = ""): ApiRequestError {
  let payload: unknown;
  try { payload = JSON.parse(responseText); } catch { payload = null; }
  const body = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
  const detail = body.detail;
  const structured = detail && typeof detail === "object" && !Array.isArray(detail) ? detail as Record<string, unknown> : {};
  const safeContext: Record<string, string | number | boolean> = {};
  if (structured.safe_context && typeof structured.safe_context === "object") {
    for (const [key, value] of Object.entries(structured.safe_context as Record<string, unknown>)) {
      if (safeContextKeys.has(key) && ["string", "number", "boolean"].includes(typeof value)) safeContext[key] = value as string | number | boolean;
    }
  }
  const safeItem = safeApiText(structured.safe_item);
  const message = Array.isArray(detail)
    ? validationDetail(detail)
    : safeApiText(typeof detail === "string" ? detail : structured.message) || `${status} ${statusText || "Request failed"}`;
  const responseRequestId = safeApiText(structured.request_id || requestId);
  if (responseRequestId) safeContext.request_id = responseRequestId;
  return new ApiRequestError(
    status,
    statusText,
    safeApiText(structured.code) || `http_${status || "network"}`,
    safeItem ? `${message} Item: ${safeItem}.` : message,
    typeof structured.retryable === "boolean" ? structured.retryable : status === 0 || status >= 500,
    safeContext,
  );
}

async function errorFromResponse(response: Response): Promise<ApiRequestError> {
  return parseApiRequestError(response.status, response.statusText, await response.text(), response.headers.get("X-Request-ID") ?? "");
}

export class ApiDataProvider implements PlatformDataProvider {
  readonly mode = "local" as const;

  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${apiUrl}${path}`, { signal });
    if (!response.ok) throw await errorFromResponse(response);
    return response.json() as Promise<T>;
  }

  async uploadForm<T>(path: string, body: FormData, onProgress?: (progress: UploadProgress) => void): Promise<T> {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("POST", `${apiUrl}${path}`);
      request.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress?.({ loaded: event.loaded, total: event.total, percent: Math.round((event.loaded / event.total) * 100) });
      };
      request.onload = () => {
        if (request.status >= 200 && request.status < 300) {
          resolve(JSON.parse(request.responseText) as T);
        } else {
          reject(parseApiRequestError(request.status, request.statusText, request.responseText, request.getResponseHeader("X-Request-ID") ?? ""));
        }
      };
      request.onerror = () => reject(new ApiRequestError(0, "Network Error", "network_error", "Backend unavailable or upload interrupted.", true, {}));
      request.send(body);
    });
  }

  async post<T>(path: string, body?: BodyInit | Record<string, unknown>): Promise<T> {
    const isForm = typeof FormData !== "undefined" && body instanceof FormData;
    const response = await fetch(`${apiUrl}${path}`, {
      method: "POST",
      headers: isForm || body === undefined ? undefined : { "Content-Type": "application/json" },
      body: isForm || body === undefined ? body as BodyInit | undefined : JSON.stringify(body),
    });
    if (!response.ok) throw await errorFromResponse(response);
    return response.json() as Promise<T>;
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${apiUrl}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw await errorFromResponse(response);
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
  getIntakeCapabilities(signal?: AbortSignal) { return this.get<IntakeCapabilities>("/api/intake/capabilities", signal); }
  createIntakeSubmission(formData: FormData) { return this.post<IntakeSubmissionResponse>("/api/intake/submissions", formData); }
  createDirectoryIntakeSubmission(formData: FormData, onProgress?: (progress: UploadProgress) => void) { return this.uploadForm<IntakeSubmissionResponse>("/api/intake/submissions/directory", formData, onProgress); }
  getIntakeSubmissions(path = "/api/intake/submissions", signal?: AbortSignal) { return this.get<IntakeSubmissionsResponse>(path, signal); }
  getIntakeSubmission(submissionId: string, signal?: AbortSignal) { return this.get<IntakeSubmission>(`/api/intake/submissions/${encodeURIComponent(submissionId)}`, signal); }
  getIntakeEvents(submissionId: string, signal?: AbortSignal) { return this.get<{ events: IntakeEvent[] }>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/events`, signal); }
  startIntakeInventory(submissionId: string) { return this.post<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inventory`); }
  getIntakeInventoryStatus(submissionId: string, signal?: AbortSignal) { return this.get<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inventory-status`, signal); }
  startSourceInspection(submissionId: string) { return this.post<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inspect`); }
  getSourceInspectionStatus(submissionId: string, signal?: AbortSignal) { return this.get<SourceInspectionStatus>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inspection-status`, signal); }
  getSubmissionLayers(submissionId: string, path?: string, signal?: AbortSignal) { return this.get<SubmissionLayersResponse>(path ?? `/api/intake/submissions/${encodeURIComponent(submissionId)}/layers`, signal); }
  getSubmissionLayer(submissionId: string, layerId: string, signal?: AbortSignal) { return this.get<SubmissionLayer>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/${encodeURIComponent(layerId)}`, signal); }
  getLayerClassificationCandidates(submissionId: string, layerId: string, signal?: AbortSignal) { return this.get<ClassificationCandidatesResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/${encodeURIComponent(layerId)}/candidates`, signal); }
  reviewSubmissionLayer(submissionId: string, layerId: string, body: Record<string, unknown>) { return this.patch<SubmissionLayer>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/${encodeURIComponent(layerId)}/review`, body); }
  batchReviewSubmissionLayers(submissionId: string, body: Record<string, unknown>) { return this.patch<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/batch-review`, body); }
  getDuplicateGroups(submissionId: string, signal?: AbortSignal) { return this.get<DuplicateGroupsResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/duplicate-groups`, signal); }
  getDuplicateGroup(submissionId: string, groupId: string, signal?: AbortSignal) { return this.get<DuplicateGroup>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/duplicate-groups/${encodeURIComponent(groupId)}`, signal); }
  reviewDuplicateGroup(submissionId: string, groupId: string, body: Record<string, unknown>) { return this.patch<DuplicateGroup>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/duplicate-groups/${encodeURIComponent(groupId)}`, body); }
  createStagingPlan(submissionId: string) { return this.post<StagingPlanResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/staging-plan`); }
  getStagingPlan(submissionId: string, signal?: AbortSignal) { return this.get<StagingPlanResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/staging-plan`, signal); }
  reviewStagingPlanItem(submissionId: string, itemId: string, body: Record<string, unknown>) { return this.patch<StagingPlanItem>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/staging-plan/${encodeURIComponent(itemId)}`, body); }
  stageApprovedLayers(submissionId: string) { return this.post<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/stage-approved`); }
  getDataSourceStages(signal?: AbortSignal) { return this.get<StageManifest>("/api/data-sources/stages", signal); }
  getDataSourceItems(path = "/api/data-sources/items", signal?: AbortSignal) { return this.get<DataSourceItemsResponse>(path, signal); }
  getDataSourceItem(itemId: string, signal?: AbortSignal) { return this.get<DataSourceItem>(`/api/data-sources/items/${encodeURIComponent(itemId)}`, signal); }
  getDataSourceLineage(itemId: string, signal?: AbortSignal) { return this.get<Record<string, unknown>>(`/api/data-sources/items/${encodeURIComponent(itemId)}/lineage`, signal); }
  getDataSourceDiagnostics(signal?: AbortSignal) { return this.get<Record<string, unknown>>("/api/data-sources/diagnostics", signal); }
}
