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
import commandCenter from "../../demo-data/command-center.json";
import components from "../../demo-data/components.json";
import dataHealthSummary from "../../demo-data/data-health-summary.json";
import inventory from "../../demo-data/inventory.json";
import intakeCapabilities from "../../demo-data/intake-capabilities.json";
import intakeEvents from "../../demo-data/intake-events.json";
import intakeSubmissions from "../../demo-data/intake-submissions.json";
import sourceInspectionStatus from "../../demo-data/source-inspection-status.json";
import submissionLayers from "../../demo-data/submission-layers.json";
import layerClassificationCandidates from "../../demo-data/layer-classification-candidates.json";
import duplicateGroupsFixture from "../../demo-data/duplicate-groups.json";
import stagingPlanFixture from "../../demo-data/staging-plan.json";
import issues from "../../demo-data/issues.json";
import lineage from "../../demo-data/lineage.json";
import map from "../../demo-data/map.json";
import processingHistory from "../../demo-data/processing-history.json";
import reviewQueue from "../../demo-data/review-queue.json";
import rules from "../../demo-data/rules.json";
import stageItems from "../../demo-data/stage-items.json";
import stageSummary from "../../demo-data/stage-summary.json";
import standardization from "../../demo-data/standardization.json";
import trustPipeline from "../../demo-data/trust-pipeline.json";
import network from "../../demo-data/network.json";
import calibration from "../../demo-data/calibration.json";
import { applyDemoDuplicateGroup, applyDemoLayerReview, applyDemoStagingPlanItem, applyDemoReview, batchUpdateDemoIssues, batchUpdateDemoLayers, createDemoIntakeSubmission, demoIntakeEvents, readDemoIntake, readDemoStagedOutputs, stageDemoApprovedLayers, updateDemoDuplicateGroup, updateDemoIntakeInventory, updateDemoIssue, updateDemoLayerReview, updateDemoStagingPlanItem } from "./demo-review-store";
import type { CatalogResponse, ClassificationCandidate, ClassificationCandidatesResponse, DataSourceItem, DataSourceItemsResponse, DuplicateGroup, DuplicateGroupsResponse, IntakeCapabilities, IntakeEvent, IntakeSubmission, IntakeSubmissionResponse, IntakeSubmissionsResponse, InventorySummary, PlatformDataProvider, RunsResponse, SourceInspectionStatus, StageManifest, StagingPlanItem, StagingPlanResponse, StorageStatus, SubmissionLayer, SubmissionLayersResponse, TrustPipeline } from "./types";

const demoIssues = issues.items as unknown as Issue[];

export class DemoDataProvider implements PlatformDataProvider {
  readonly mode = "demo" as const;

  async get<T>(path: string): Promise<T> {
    const url = new URL(path, "https://demo.local");
    const pathname = url.pathname;
    const params = url.searchParams;
    if (pathname === "/api/platform/command-center") return clone(commandCenter) as T;
    if (pathname === "/api/storage/status") return clone(stageSummary) as T;
    if (pathname === "/api/storage/catalog") return clone(stageItems) as T;
    if (pathname === "/api/storage/catalog/summary") return clone({ counts: { wastewater: 2 }, message: "Sanitized demo catalog summary loaded." }) as T;
    if (pathname === "/api/inventory/summary") return clone(inventory.summary) as T;
    if (pathname === "/api/inventory/layers") return clone({ layers: inventory.layers, message: "Sanitized demo inventory loaded." }) as T;
    if (pathname === "/api/inventory/recommendation") return clone(inventory.recommendation) as T;
    if (pathname === "/api/data-health/wastewater/runs") return clone(processingHistory) as T;
    if (pathname === "/api/data-health/wastewater/summary") return clone(dataHealthSummary) as T;
    if (pathname === "/api/data-health/wastewater/rules") return clone(rules) as T;
    if (pathname === "/api/data-health/wastewater/network") return clone(network) as T;
    if (pathname === "/api/data-health/wastewater/map") return clone(map) as T;
    if (pathname === "/api/review/wastewater/queue") return clone(pageIssues(priorityIssues(), params, "Sanitized demo review queue loaded.")) as T;
    if (pathname === "/api/review/wastewater/calibration") return clone(calibration) as T;
    if (pathname === "/api/review/wastewater/sample") return clone({ ...reviewQueue, items: priorityIssues(), total: reviewQueue.total }) as T;
    if (pathname === "/api/review/wastewater/data-owner-questions") return clone({ markdown: "Demo data owner worksheet is not connected to private source documents." }) as T;
    if (pathname === "/api/data-health/wastewater/components") return clone(pageItems(components.items, params)) as T;
    if (pathname.startsWith("/api/data-health/wastewater/components/")) return clone(components.items.find((item) => item.component_id === pathname.split("/").pop()) ?? {}) as T;
    if (pathname === "/api/standardization/wastewater/readiness") return clone(standardization.readiness) as T;
    if (pathname === "/api/standardization/wastewater/mappings") return clone({ mappings: standardization.mappings }) as T;
    if (pathname === "/api/trust-pipeline/wastewater") return clone(trustPipeline) as T;
    if (pathname === "/api/data-health/wastewater/issues") return clone(filteredIssues(params)) as T;
    if (pathname.startsWith("/api/data-health/wastewater/issues/")) {
      const issueId = decodeURIComponent(pathname.split("/").pop() ?? "");
      return clone(allIssues().find((issue) => issue.issue_id === issueId) ?? {}) as T;
    }
    if (pathname === "/api/data-sources") return clone({ data_sources: [], message: "Demo snapshot loaded." }) as T;
    if (pathname === "/api/intake/capabilities") return clone(intakeCapabilities) as T;
    if (pathname === "/api/intake/submissions") return clone(pageDemoSubmissions(params)) as T;
    if (pathname.startsWith("/api/intake/submissions/")) return clone(demoSubmissionPath(pathname, params)) as T;
    if (pathname === "/api/data-sources/stages") return clone(demoStageManifest()) as T;
    if (pathname === "/api/data-sources/items") return clone(demoStageItems(params)) as T;
    if (pathname.startsWith("/api/data-sources/items/")) return clone(demoStageItemPath(pathname)) as T;
    if (pathname === "/api/data-sources/diagnostics") return clone({ stage_manifest_item_count: demoStageManifest().items.length, message: "Demo diagnostics loaded from sanitized fixtures." }) as T;
    if (pathname === "/api/assets/summary") return clone({ total_assets: commandCenter.assets.total, values_connected: false, message: "Demo snapshot loaded." }) as T;
    if (pathname === "/api/qa/summary") return clone({ values_connected: false, message: "Demo snapshot loaded." }) as T;
    if (pathname === "/api/lineage") return clone(lineage) as T;
    throw new Error(`No demo data for ${pathname}`);
  }

  async post<T>(path: string, body?: BodyInit | Record<string, unknown>): Promise<T> {
    const pathname = new URL(path, "https://demo.local").pathname;
    if (pathname === "/api/intake/submissions") {
      const submission = createDemoIntakeSubmission(body as FormData);
      return clone({ submissions: [submission], message: "Demo mode does not upload or inspect your file. The workflow is simulated using synthetic results." }) as T;
    }
    if (pathname.endsWith("/inventory")) {
      const submissionId = decodeURIComponent(pathname.split("/").at(-2) ?? "");
      return clone(updateDemoIntakeInventory(submissionId)) as T;
    }
    if (pathname.endsWith("/inspect")) {
      const submissionId = decodeURIComponent(pathname.split("/").at(-2) ?? "");
      return clone(demoInspectionStatus(submissionId)) as T;
    }
    if (pathname.endsWith("/staging-plan")) {
      const submissionId = decodeURIComponent(pathname.split("/").at(-2) ?? "");
      return clone(demoStagingPlan(submissionId)) as T;
    }
    if (pathname.endsWith("/stage-approved")) {
      const submissionId = decodeURIComponent(pathname.split("/").at(-2) ?? "");
      return clone(stageDemoApprovedLayers(demoStagingPlan(submissionId).items)) as T;
    }
    return this.get<T>(path);
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    const pathname = new URL(path, "https://demo.local").pathname;
    if (pathname === "/api/review/wastewater/issues/batch") {
      const update = body as Partial<Issue> & { issue_ids?: string[] };
      return batchUpdateDemoIssues(demoIssues, update.issue_ids ?? [], update) as T;
    }
    if (pathname.startsWith("/api/data-health/wastewater/issues/")) {
      const issueId = decodeURIComponent(pathname.split("/").pop() ?? "");
      const issue = demoIssues.find((item) => item.issue_id === issueId);
      if (!issue) throw new Error("Demo issue not found.");
      return updateDemoIssue(issue, body as Partial<Issue>) as T;
    }
    if (pathname.endsWith("/batch-review")) {
      const submissionId = decodeURIComponent(pathname.split("/").at(-2) ?? "");
      const update = body as Record<string, unknown> & { layer_ids?: string[] };
      return batchUpdateDemoLayers(demoSubmissionLayers(submissionId), update.layer_ids ?? [], update) as T;
    }
    if (pathname.includes("/duplicate-groups/")) {
      const groupId = decodeURIComponent(pathname.split("/").pop() ?? "");
      const group = allDemoDuplicateGroups().find((item) => item.duplicate_group_id === groupId);
      if (!group) throw new Error("Demo duplicate group not found.");
      return updateDemoDuplicateGroup(group, body as Record<string, unknown>) as T;
    }
    if (pathname.includes("/staging-plan/")) {
      const itemId = decodeURIComponent(pathname.split("/").pop() ?? "");
      const item = allDemoStagingPlanItems().find((planItem) => planItem.staging_plan_item_id === itemId);
      if (!item) throw new Error("Demo staging plan item not found.");
      return updateDemoStagingPlanItem(item, body as Record<string, unknown>) as T;
    }
    if (pathname.includes("/layers/") && pathname.endsWith("/review")) {
      const parts = pathname.split("/");
      const layerId = decodeURIComponent(parts[6] ?? "");
      const layer = allDemoLayers().find((item) => item.layer_id === layerId);
      if (!layer) throw new Error("Demo layer not found.");
      return updateDemoLayerReview(layer, body as Record<string, unknown>) as T;
    }
    return this.get<T>(path);
  }

  commandCenter() { return this.get<CommandCenterResponse>("/api/platform/command-center?utility_system=wastewater"); }
  storageStatus() { return this.get<StorageStatus>("/api/storage/status"); }
  stageItems() { return this.get<CatalogResponse>("/api/storage/catalog"); }
  itemDetails(path: string) { return this.get<Record<string, unknown>>(path); }
  lineage() { return this.get<Record<string, unknown>>("/api/lineage"); }
  inventory() { return this.get<InventorySummary>("/api/inventory/summary"); }
  processingHistory() { return this.get<RunsResponse>("/api/data-health/wastewater/runs"); }
  dataHealthSummary() { return this.get<Record<string, unknown>>("/api/data-health/wastewater/summary"); }
  qaIssues(path: string) { return this.get<IssuesResponse>(path); }
  qaRules() { return this.get<{ rules: RuleRow[] }>("/api/data-health/wastewater/rules"); }
  reviewQueue() { return this.get<IssuesResponse>("/api/review/wastewater/queue"); }
  reviewCalibration() { return this.get<{ rows: CalibrationRow[] }>("/api/review/wastewater/calibration"); }
  networkSummary() { return this.get<NetworkResponse>("/api/data-health/wastewater/network"); }
  networkComponents() { return this.get<{ items: ComponentRow[] }>("/api/data-health/wastewater/components"); }
  standardizationReadiness() { return this.get<Readiness>("/api/standardization/wastewater/readiness"); }
  standardizationMappings() { return this.get<{ mappings: MappingRow[] }>("/api/standardization/wastewater/mappings"); }
  trustPipeline() { return this.get<TrustPipeline>("/api/trust-pipeline/wastewater"); }
  map() { return this.get<MapData>("/api/data-health/wastewater/map"); }
  getIntakeCapabilities() { return this.get<IntakeCapabilities>("/api/intake/capabilities"); }
  createIntakeSubmission(formData: FormData) { return this.post<IntakeSubmissionResponse>("/api/intake/submissions", formData); }
  getIntakeSubmissions(path = "/api/intake/submissions") { return this.get<IntakeSubmissionsResponse>(path); }
  getIntakeSubmission(submissionId: string) { return this.get<IntakeSubmission>(`/api/intake/submissions/${encodeURIComponent(submissionId)}`); }
  getIntakeEvents(submissionId: string) { return this.get<{ events: IntakeEvent[] }>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/events`); }
  startIntakeInventory(submissionId: string) { return this.post<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inventory`); }
  getIntakeInventoryStatus(submissionId: string) { return this.get<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inventory-status`); }
  startSourceInspection(submissionId: string) { return this.post<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inspect`); }
  getSourceInspectionStatus(submissionId: string) { return this.get<SourceInspectionStatus>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/inspection-status`); }
  getSubmissionLayers(submissionId: string, path?: string) { return this.get<SubmissionLayersResponse>(path ?? `/api/intake/submissions/${encodeURIComponent(submissionId)}/layers`); }
  getSubmissionLayer(submissionId: string, layerId: string) { return this.get<SubmissionLayer>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/${encodeURIComponent(layerId)}`); }
  getLayerClassificationCandidates(submissionId: string, layerId: string) { return this.get<ClassificationCandidatesResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/${encodeURIComponent(layerId)}/candidates`); }
  reviewSubmissionLayer(submissionId: string, layerId: string, body: Record<string, unknown>) { return this.patch<SubmissionLayer>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/${encodeURIComponent(layerId)}/review`, body); }
  batchReviewSubmissionLayers(submissionId: string, body: Record<string, unknown>) { return this.patch<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/batch-review`, body); }
  getDuplicateGroups(submissionId: string) { return this.get<DuplicateGroupsResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/duplicate-groups`); }
  getDuplicateGroup(submissionId: string, groupId: string) { return this.get<DuplicateGroup>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/duplicate-groups/${encodeURIComponent(groupId)}`); }
  reviewDuplicateGroup(submissionId: string, groupId: string, body: Record<string, unknown>) { return this.patch<DuplicateGroup>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/duplicate-groups/${encodeURIComponent(groupId)}`, body); }
  createStagingPlan(submissionId: string) { return this.post<StagingPlanResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/staging-plan`); }
  getStagingPlan(submissionId: string) { return this.get<StagingPlanResponse>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/staging-plan`); }
  reviewStagingPlanItem(submissionId: string, itemId: string, body: Record<string, unknown>) { return this.patch<StagingPlanItem>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/staging-plan/${encodeURIComponent(itemId)}`, body); }
  stageApprovedLayers(submissionId: string) { return this.post<Record<string, unknown>>(`/api/intake/submissions/${encodeURIComponent(submissionId)}/stage-approved`); }
  getDataSourceStages() { return this.get<StageManifest>("/api/data-sources/stages"); }
  getDataSourceItems(path = "/api/data-sources/items") { return this.get<DataSourceItemsResponse>(path); }
  getDataSourceItem(itemId: string) { return this.get<DataSourceItem>(`/api/data-sources/items/${encodeURIComponent(itemId)}`); }
  getDataSourceLineage(itemId: string) { return this.get<Record<string, unknown>>(`/api/data-sources/items/${encodeURIComponent(itemId)}/lineage`); }
  getDataSourceDiagnostics() { return this.get<Record<string, unknown>>("/api/data-sources/diagnostics"); }
}

function allIssues(): Issue[] {
  return demoIssues.map(applyDemoReview);
}

function priorityIssues() {
  return allIssues().sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
}

function filteredIssues(params: URLSearchParams): IssuesResponse {
  const filtered = allIssues().filter((issue) =>
    matches(issue.severity, params.get("severity"))
    && matches(issue.category, params.get("category"))
    && matches(issue.rule_code, params.get("rule_code"))
    && matches(issue.source_layer, params.get("source_layer"))
    && matches(issue.disposition, params.get("disposition"))
    && matchesReview(issue, params.get("review_status"))
    && matchesAsset(issue, params.get("asset")),
  );
  return pageIssues(filtered, params, filtered.length ? "Sanitized demo QA issues loaded." : "No demo issues matched the filters.");
}

function pageIssues(items: Issue[], params: URLSearchParams, message: string): IssuesResponse {
  const page = pageItems(items, params);
  return { ...page, message };
}

function pageItems<T>(items: T[], params: URLSearchParams) {
  const limit = Number(params.get("limit") ?? 100);
  const offset = Number(params.get("offset") ?? 0);
  return { items: items.slice(offset, offset + limit), pagination: { total: items.length, limit, offset, has_more: offset + limit < items.length } };
}

function allDemoSubmissions(): IntakeSubmission[] {
  return [...readDemoIntake(), ...(intakeSubmissions.items as IntakeSubmission[])];
}

function pageDemoSubmissions(params: URLSearchParams): IntakeSubmissionsResponse {
  const items = allDemoSubmissions().filter((item) =>
    matches(item.current_status, params.get("status"))
    && matches(item.utility_system, params.get("utility_system"))
    && matches(item.source_format, params.get("source_format"))
    && matches(item.current_stage, params.get("current_stage"))
    && matchesSearch([item.submission_name, item.original_filename, item.submission_id], params.get("search")),
  );
  const page = pageItems(items, params);
  return { ...page, message: items.length ? "Sanitized demo intake submissions loaded." : "No demo intake submissions matched the filters." };
}

function demoSubmissionPath(pathname: string, params: URLSearchParams) {
  const parts = pathname.split("/");
  const submissionId = decodeURIComponent(parts[4] ?? "");
  if (pathname.endsWith("/inspection-status")) return demoInspectionStatus(submissionId);
  if (pathname.endsWith("/layers")) return pageDemoLayers(submissionId, params);
  if (pathname.includes("/layers/") && pathname.endsWith("/candidates")) {
    const layerId = decodeURIComponent(parts[6] ?? "");
    return demoLayerCandidates(layerId);
  }
  if (pathname.includes("/layers/")) {
    const layerId = decodeURIComponent(parts[6] ?? "");
    return demoSubmissionLayers(submissionId).find((layer) => layer.layer_id === layerId) ?? {};
  }
  if (pathname.endsWith("/duplicate-groups")) return demoDuplicateGroups(submissionId);
  if (pathname.includes("/duplicate-groups/")) {
    const groupId = decodeURIComponent(parts[6] ?? "");
    return demoDuplicateGroups(submissionId).items.find((group) => group.duplicate_group_id === groupId) ?? {};
  }
  if (pathname.endsWith("/staging-plan")) return demoStagingPlan(submissionId);
  if (pathname.endsWith("/events")) {
    const fixture = (intakeEvents as Record<string, IntakeEvent[]>)[submissionId] ?? [];
    return { events: [...demoIntakeEvents(submissionId), ...fixture] };
  }
  if (pathname.endsWith("/inventory-status")) {
    const item = allDemoSubmissions().find((submission) => submission.submission_id === submissionId);
    return item ? { submission_id: submissionId, inventory_status: item.inventory_status, classification_status: item.classification_status, staging_status: item.staging_status, current_status: item.current_status, next_required_action: item.next_required_action } : {};
  }
  return allDemoSubmissions().find((submission) => submission.submission_id === submissionId) ?? {};
}

function demoInspectionStatus(submissionId: string): SourceInspectionStatus {
  return clone((sourceInspectionStatus as Record<string, SourceInspectionStatus>)[submissionId] ?? {
    submission_id: submissionId,
    inspection_status: "not_started",
    child_layer_count: 0,
    table_count: 0,
    spatial_reference_count: 0,
    warnings: [],
    blockers: [],
    message: "Demo source inspection has not been started.",
  });
}

function allDemoLayers(): SubmissionLayer[] {
  return Object.values(submissionLayers as Record<string, SubmissionLayer[]>).flat().map(applyDemoLayerReview);
}

function demoSubmissionLayers(submissionId: string): SubmissionLayer[] {
  return ((submissionLayers as Record<string, SubmissionLayer[]>)[submissionId] ?? []).map(applyDemoLayerReview);
}

function pageDemoLayers(submissionId: string, params: URLSearchParams): SubmissionLayersResponse {
  let items = demoSubmissionLayers(submissionId);
  for (const field of ["utility_system", "network_group", "asset_category", "asset_subcategory", "operational_role", "lifecycle_representation", "classification_status", "duplicate_status", "coordinate_status", "staging_status", "confidence"] as const) {
    const expected = params.get(field);
    if (expected) items = items.filter((item) => matches(String(item[field] ?? ""), expected));
  }
  if (params.get("search")) items = items.filter((item) => matchesSearch([item.source_layer_name, item.source_layer_alias, item.owner_or_jurisdiction], params.get("search")));
  const page = pageItems(items, params);
  return { ...page, message: items.length ? "Synthetic inspected child layers loaded." : "No demo child layers matched the filters." };
}

function demoLayerCandidates(layerId: string): ClassificationCandidatesResponse {
  const configured = (layerClassificationCandidates as Record<string, ClassificationCandidate[]>)[layerId];
  const layer = allDemoLayers().find((item) => item.layer_id === layerId);
  const items = configured ?? (layer ? [candidateFromLayer(layer)] : []);
  return { items: clone(items), message: items.length ? "Synthetic classification candidates loaded." : "No synthetic candidates are available." };
}

function candidateFromLayer(layer: SubmissionLayer): ClassificationCandidate {
  return {
    candidate_id: `${layer.layer_id}-candidate-1`,
    layer_id: layer.layer_id,
    rank: 1,
    utility_system: layer.utility_system,
    network_group: layer.network_group,
    asset_category: layer.asset_category,
    asset_subcategory: layer.asset_subcategory,
    operational_role: layer.operational_role,
    lifecycle_representation: layer.lifecycle_representation,
    owner_or_jurisdiction: String(layer.owner_or_jurisdiction ?? "unknown"),
    confidence: layer.confidence,
    score: layer.confidence === "high" ? 0.9 : layer.confidence === "medium" ? 0.7 : 0.4,
    evidence: [`Synthetic rule matched ${layer.source_layer_name}.`],
    warnings: layer.confidence === "high" ? [] : ["Human confirmation required before staging."],
  };
}

function allDemoDuplicateGroups(): DuplicateGroup[] {
  return Object.values(duplicateGroupsFixture as Record<string, DuplicateGroup[]>).flat().map((group) => applyDemoDuplicateGroup({ ...group }));
}

function demoDuplicateGroups(submissionId: string): DuplicateGroupsResponse {
  const items = ((duplicateGroupsFixture as Record<string, DuplicateGroup[]>)[submissionId] ?? []).map((group) => applyDemoDuplicateGroup({ ...group }));
  return { items, message: items.length ? "Synthetic duplicate candidates loaded." : "No duplicate candidates detected." };
}

function allDemoStagingPlanItems(): StagingPlanItem[] {
  return Object.values(stagingPlanFixture as Record<string, StagingPlanItem[]>).flat().map(applyDemoStagingPlanItem);
}

function demoStagingPlan(submissionId: string): StagingPlanResponse {
  const items = ((stagingPlanFixture as Record<string, StagingPlanItem[]>)[submissionId] ?? []).map(applyDemoStagingPlanItem);
  return { items, message: items.length ? "Synthetic staging plan loaded." : "No staging plan has been created yet." };
}

function demoStageManifest(): StageManifest {
  const fixtureItems = [
    ...(stageItems.raw ?? []).map((item) => rawStageItem(item.name, item.format ?? "", item.state)),
    ...(stageItems.staging ?? []).map((item) => ({
      item_id: `demo-staging:${item.name}`,
      name: item.name,
      stage: "staging",
      utility_system: "wastewater",
      network_group: item.name.includes("manhole") ? "structures" : "gravity_network",
      asset_category: item.name.includes("manhole") ? "access_structure" : "pipe",
      asset_subcategory: item.name.includes("manhole") ? "manhole" : "gravity_main",
      source_format: "sanitized_demo_json",
      sensitivity_level: "public_demo",
      status: item.state,
      inventory_status: "complete",
      classification_status: "complete",
      staging_status: "approved",
      geometry_type: item.name.includes("manhole") ? "point" : "polyline",
      record_count: item.records,
      next_required_action: "QA review is complete in the sanitized demo snapshot.",
      lineage: ["Synthetic Raw source", "Synthetic staging layer", "QA evaluated"],
      trust_state: {},
      blockers: [],
    })),
    ...readDemoStagedOutputs(),
  ] as DataSourceItem[];
  const submissionItems = allDemoSubmissions().map((submission) => ({
    item_id: `submission:${submission.submission_id}`,
    name: submission.submission_name,
    stage: "raw",
    utility_system: submission.utility_system,
    network_group: "pending_inventory",
    asset_category: "pending_inventory",
    asset_subcategory: "pending_inventory",
    source_format: submission.source_format,
    sensitivity_level: submission.sensitivity_level,
    status: submission.current_status,
    inventory_status: submission.inventory_status,
    classification_status: submission.classification_status,
    staging_status: submission.staging_status,
    geometry_type: "synthetic",
    record_count: "synthetic",
    next_required_action: submission.next_required_action,
    lineage: submission.lineage,
    trust_state: {},
    blockers: submission.blockers,
  })) as DataSourceItem[];
  const items = [...submissionItems, ...fixtureItems];
  const counts = {
    raw: items.filter((item) => item.stage === "raw").length,
    staging: items.filter((item) => item.stage === "staging").length,
    standardized: 0,
    curated: 0,
    export: 0,
  };
  return {
    generated_at: String(stageItems.generated_at),
    stages: [
      { stage: "raw", label: "Raw", item_count: counts.raw, description: "Sanitized and session-only Raw demo sources." },
      { stage: "staging", label: "Staging", item_count: counts.staging, description: "Sanitized demo staging layers." },
      { stage: "standardized", label: "Standardized", item_count: counts.standardized, description: "Awaiting approved mappings." },
      { stage: "curated", label: "Curated", item_count: counts.curated, description: "No curated demo utility layers exist." },
      { stage: "export", label: "Export", item_count: counts.export, description: "No demo export packages are registered." },
    ],
    items,
    counts,
    message: "Sanitized demo stage manifest loaded.",
  };
}

function demoStageItems(params: URLSearchParams): DataSourceItemsResponse {
  let items = demoStageManifest().items;
  for (const [field, param] of [["stage", "stage"], ["utility_system", "utility_system"], ["network_group", "network_group"], ["asset_category", "asset_category"], ["asset_subcategory", "asset_subcategory"], ["source_format", "source_format"], ["sensitivity_level", "sensitivity"], ["status", "status"]] as const) {
    const expected = params.get(param);
    if (expected) items = items.filter((item) => matches(String(item[field] ?? ""), expected));
  }
  if (params.get("search")) items = items.filter((item) => matchesSearch([item.name, item.item_id, item.source_format], params.get("search")));
  return pageItems(items, params);
}

function demoStageItemPath(pathname: string) {
  const encoded = pathname.split("/")[4] ?? "";
  const itemId = decodeURIComponent(encoded);
  const item = demoStageManifest().items.find((stageItem) => stageItem.item_id === itemId);
  if (pathname.endsWith("/lineage")) return { item_id: itemId, lineage: item?.lineage ?? [], blockers: item?.blockers ?? [], next_required_action: item?.next_required_action ?? "" };
  return item ?? {};
}

function rawStageItem(name: string, format: string, state: string): DataSourceItem {
  return {
    item_id: `demo-raw:${name}`,
    name,
    stage: "raw",
    utility_system: "wastewater",
    network_group: "pending_inventory",
    asset_category: "pending_inventory",
    asset_subcategory: "pending_inventory",
    source_format: format,
    sensitivity_level: "public_demo",
    status: state,
    inventory_status: "complete",
    classification_status: "complete",
    staging_status: "not_approved",
    next_required_action: "Synthetic source is already represented in the demo staging snapshot.",
  };
}

function matches(actual: string | undefined, expected: string | null) {
  return !expected || String(actual ?? "").toLowerCase() === expected.toLowerCase();
}

function matchesReview(issue: Issue, expected: string | null) {
  if (!expected) return true;
  return [issue.workflow_status, issue.review_status].map((value) => String(value ?? "").toLowerCase()).includes(expected.toLowerCase());
}

function matchesAsset(issue: Issue, expected: string | null) {
  if (!expected) return true;
  const needle = expected.toLowerCase();
  return [issue.source_asset_id, issue.related_asset_id, issue.source_objectid, issue.related_objectid].some((value) => String(value ?? "").toLowerCase().includes(needle));
}

function matchesSearch(values: unknown[], expected: string | null) {
  if (!expected) return true;
  const needle = expected.toLowerCase();
  return values.some((value) => String(value ?? "").toLowerCase().includes(needle));
}

function severityRank(severity: string) {
  return severity === "high" ? 0 : severity === "medium" ? 1 : 2;
}

function clone<T>(data: T): T {
  return JSON.parse(JSON.stringify(data)) as T;
}
