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
import { applyDemoReview, batchUpdateDemoIssues, updateDemoIssue } from "./demo-review-store";
import type { CatalogResponse, InventorySummary, PlatformDataProvider, RunsResponse, StorageStatus, TrustPipeline } from "./types";

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
    if (pathname === "/api/assets/summary") return clone({ total_assets: commandCenter.assets.total, values_connected: false, message: "Demo snapshot loaded." }) as T;
    if (pathname === "/api/qa/summary") return clone({ values_connected: false, message: "Demo snapshot loaded." }) as T;
    if (pathname === "/api/lineage") return clone(lineage) as T;
    throw new Error(`No demo data for ${pathname}`);
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

function severityRank(severity: string) {
  return severity === "high" ? 0 : severity === "medium" ? 1 : 2;
}

function clone<T>(data: T): T {
  return JSON.parse(JSON.stringify(data)) as T;
}
