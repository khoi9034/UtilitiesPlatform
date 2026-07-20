"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import styles from "./page.module.css";

type SafeGeometry =
  | { type: "point"; x: number; y: number; spatial_reference_wkid?: number }
  | { type: "polyline"; paths: number[][][]; spatial_reference_wkid?: number; length?: number }
  | Record<string, never>;

type Issue = {
  issue_id: string;
  issue_fingerprint: string;
  rule_code: string;
  rule_name: string;
  category: string;
  finding_class: string;
  severity: string;
  utility_system: string;
  network_group: string;
  asset_category: string;
  asset_subcategory: string;
  source_layer: string;
  source_asset_id: string;
  source_objectid: string;
  related_asset_id: string;
  related_objectid: string;
  description: string;
  why_it_matters: string;
  recommended_action: string;
  detection_method: string;
  threshold_used: string;
  confidence: string;
  review_status: string;
  workflow_status: string;
  disposition: string;
  reviewer: string;
  assigned_to: string;
  review_priority: string;
  review_notes: string;
  evidence_notes: string;
  reviewed_at: string;
  resolved_at: string;
  due_date: string;
  source_confirmation: string;
  field_verification_required: boolean;
  engineering_review_required: boolean;
  rule_adjustment_candidate: boolean;
  resolution_notes: string;
  possible_missing_dependency: string;
  dependency_explanation: string;
  first_seen_run_id: string;
  latest_seen_run_id: string;
  first_seen_at: string;
  latest_seen_at: string;
  occurrence_count: number;
  currently_present: boolean;
  run_id: string;
  created_at: string;
  safe_geometry: SafeGeometry;
};

type Summary = {
  run_id?: string;
  started_at?: string;
  completed_at?: string;
  run_status?: string;
  staged_input_layers?: string[];
  input_feature_counts?: Record<string, number>;
  spatial_reference?: string;
  endpoint_match_rate?: number;
  connected_component_count?: number;
  largest_component_size?: number;
  isolated_pipes?: number;
  isolated_manholes?: number;
  unmatched_endpoints?: number;
  total_issues?: number;
  issues_by_severity?: Record<string, number>;
  issues_by_category?: Record<string, number>;
  category_metrics?: Record<string, { numerator: number; denominator: number; summary: string; skipped_checks: number }>;
  limitations?: string[];
  rule_results?: { rule_code: string; status: string; skip_reason: string; issue_count: number }[];
};

type Rule = {
  rule_code: string;
  name: string;
  category: string;
  severity: string;
  enabled: boolean;
  status?: string;
  issue_count?: number;
  skip_reason?: string;
  parameters: Record<string, unknown>;
  detection_method: string;
  limitation: string;
};

type IssuesResponse = {
  items: Issue[];
  pagination: { total: number; limit: number; offset: number; has_more: boolean };
  message: string;
};

type NetworkResponse = {
  summary: Record<string, number>;
  limitations: string[];
};

type MapFeature = { objectid?: number; asset_id?: string; issue_id?: string; rule_code?: string; category?: string; severity?: string; source_layer?: string; source_objectid?: string; geometry: SafeGeometry };
type MapData = { pipes: MapFeature[]; manholes: MapFeature[]; issues: MapFeature[] };
type CalibrationRow = { rule_code: string; total_findings: number; reviewed_findings: number; confirmed_defects: number; false_positives: number; source_limitations: number; confirmation_rate: number; false_positive_rate: number; review_coverage: number; threshold: string; calibration_status: string };
type ComponentRow = { component_id: string; pipe_count: number; manhole_count: number; total_asset_count: number; approximate_network_length: number; bounding_extent: string; nearest_other_component_distance: number | string; unmatched_endpoints: number; isolated_status: string; likely_classification: string; review_status: string; review_classification: string; reviewer_notes: string };
type Readiness = { standardization_status?: string; fields_ready_to_map_directly?: string[]; fields_requiring_unit_confirmation?: string[]; fields_requiring_code_translation?: string[]; fields_unavailable?: string[]; fields_blocked?: string[]; dependencies_still_missing?: string[]; records_eligible_for_preview?: number; records_requiring_review?: number; writes_to_standardized_gdb?: boolean; writes_to_curated_gdb?: boolean };
type MappingRow = { source_layer: string; source_field: string; target_field: string; confidence: string; unit_conversion: string; code_translation: string; approved_to_standardize: string; blocked_reason: string };
type ArcGisConstructor = new (properties?: Record<string, unknown>) => unknown;
type ArcGisLayer = { addMany: (items: unknown[]) => void };
type ArcGisView = {
  destroy: () => void;
  goTo: (target: unknown) => Promise<unknown>;
  on: (eventName: string, callback: (event: unknown) => void) => void;
  hitTest: (event: unknown) => Promise<{ results: { graphic?: { attributes?: Record<string, string> } }[] }>;
};
type ArcGisModules = {
  Map: ArcGisConstructor;
  MapView: ArcGisConstructor;
  GraphicsLayer: ArcGisConstructor;
  Graphic: ArcGisConstructor;
  Point: ArcGisConstructor;
  Polyline: ArcGisConstructor;
};

declare global {
  interface Window {
    require?: (modules: string[], callback: (...loaded: ArcGisConstructor[]) => void) => void;
  }
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const workflowStatuses = ["open", "assigned", "in_review", "decision_recorded", "resolved", "reopened", "deferred"];
const dispositions = ["unreviewed", "under_review", "confirmed_defect", "likely_defect", "false_positive", "source_data_limitation", "expected_condition", "missing_dependent_data", "needs_field_verification", "needs_engineering_review", "deferred", "resolved"];

function label(value = "") {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function pct(value = 0) {
  return `${(value * 100).toFixed(1)}%`;
}

export default function DataHealthPage() {
  const [summary, setSummary] = useState<Summary>({});
  const [rules, setRules] = useState<Rule[]>([]);
  const [issues, setIssues] = useState<IssuesResponse>({ items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false }, message: "" });
  const [network, setNetwork] = useState<NetworkResponse>({ summary: {}, limitations: [] });
  const [mapData, setMapData] = useState<MapData>({ pipes: [], manholes: [], issues: [] });
  const [queue, setQueue] = useState<Issue[]>([]);
  const [selectedIssueIds, setSelectedIssueIds] = useState<string[]>([]);
  const [calibration, setCalibration] = useState<CalibrationRow[]>([]);
  const [sampleTotal, setSampleTotal] = useState(0);
  const [components, setComponents] = useState<ComponentRow[]>([]);
  const [readiness, setReadiness] = useState<Readiness>({});
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ severity: "", category: "", rule_code: "", review_status: "", source_layer: "", asset: "" });
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    async function loadStaticData() {
      try {
        const [summaryResponse, rulesResponse, networkResponse, mapResponse, queueResponse, calibrationResponse, sampleResponse, componentsResponse, readinessResponse, mappingsResponse] = await Promise.all([
          fetch(`${apiUrl}/api/data-health/wastewater/summary`),
          fetch(`${apiUrl}/api/data-health/wastewater/rules`),
          fetch(`${apiUrl}/api/data-health/wastewater/network`),
          fetch(`${apiUrl}/api/data-health/wastewater/map`),
          fetch(`${apiUrl}/api/review/wastewater/queue?limit=12`),
          fetch(`${apiUrl}/api/review/wastewater/calibration`),
          fetch(`${apiUrl}/api/review/wastewater/sample`),
          fetch(`${apiUrl}/api/data-health/wastewater/components?limit=77`),
          fetch(`${apiUrl}/api/standardization/wastewater/readiness`),
          fetch(`${apiUrl}/api/standardization/wastewater/mappings`),
        ]);
        if (!summaryResponse.ok || !rulesResponse.ok || !networkResponse.ok || !mapResponse.ok || !queueResponse.ok || !calibrationResponse.ok || !sampleResponse.ok || !componentsResponse.ok || !readinessResponse.ok || !mappingsResponse.ok) {
          throw new Error("Data Health API request failed.");
        }
        setSummary(await summaryResponse.json());
        setRules((await rulesResponse.json()).rules ?? []);
        setNetwork(await networkResponse.json());
        setMapData(await mapResponse.json());
        setQueue((await queueResponse.json()).items ?? []);
        setCalibration((await calibrationResponse.json()).rows ?? []);
        setSampleTotal((await sampleResponse.json()).total ?? 0);
        setComponents((await componentsResponse.json()).items ?? []);
        setReadiness(await readinessResponse.json());
        setMappings((await mappingsResponse.json()).mappings ?? []);
      } catch {
        setError("Data Health API is unavailable. Confirm the FastAPI backend is running and QA reports exist.");
      }
    }
    loadStaticData();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    async function loadIssues() {
      try {
        const response = await fetch(`${apiUrl}/api/data-health/wastewater/issues?${params}`);
        if (!response.ok) throw new Error("Issue request failed.");
        setIssues(await response.json());
      } catch {
        setError("Could not load wastewater QA issues.");
      }
    }
    loadIssues();
  }, [filters, offset]);

  const categories = useMemo(() => Object.keys(summary.issues_by_category ?? {}).sort(), [summary.issues_by_category]);
  const severities = useMemo(() => Object.keys(summary.issues_by_severity ?? {}).sort(), [summary.issues_by_severity]);
  const ruleCodes = useMemo(() => rules.map((rule) => rule.rule_code).sort(), [rules]);

  function updateFilter(key: keyof typeof filters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setOffset(0);
  }

  async function loadIssue(issueId: string) {
    const response = await fetch(`${apiUrl}/api/data-health/wastewater/issues/${issueId}`);
    if (response.ok) {
      setSelectedIssue(await response.json());
    }
  }

  async function saveReview(workflow_status: string, disposition: string, reviewer: string, review_notes: string) {
    if (!selectedIssue) return;
    const response = await fetch(`${apiUrl}/api/data-health/wastewater/issues/${selectedIssue.issue_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow_status, disposition, reviewer, review_notes }),
    });
    if (response.ok) {
      const updated = await response.json();
      setSelectedIssue(updated);
      setOffset((value) => value);
    }
  }

  async function applyBatchReview(update: Record<string, string | boolean>) {
    if (selectedIssueIds.length === 0 || !confirm(`Apply review update to ${selectedIssueIds.length} selected issue(s)?`)) return;
    const response = await fetch(`${apiUrl}/api/review/wastewater/issues/batch`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ issue_ids: selectedIssueIds, ...update }),
    });
    if (response.ok) {
      setSelectedIssueIds([]);
      setOffset((value) => value);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.backLink}>
          Utilities Platform
        </Link>
        <h1>Wastewater Data Health</h1>
        <p>Transparent GIS quality, connectivity, and source-readiness review for wastewater assets.</p>
      </header>

      {error ? <div className={styles.warning}>{error}</div> : null}

      <UtilityContextBreadcrumb />
      <UtilityHealthSummary summary={summary} />

      <div className={styles.layout}>
        <div>
          <CategoryMetrics summary={summary} />
          <PriorityReviewQueue queue={queue} sampleTotal={sampleTotal} onSelect={setSelectedIssue} />
          <BatchReview selectedCount={selectedIssueIds.length} onApply={applyBatchReview} />
          <IssueExplorer
            issues={issues}
            filters={filters}
            severities={severities}
            categories={categories}
            ruleCodes={ruleCodes}
            onFilter={updateFilter}
            onSelect={(issue) => setSelectedIssue(issue)}
            selectedIssueIds={selectedIssueIds}
            setSelectedIssueIds={setSelectedIssueIds}
            offset={offset}
            setOffset={setOffset}
          />
          <RuleCalibrationView rows={calibration} />
          <RuleCatalog rules={rules} />
        </div>

        <aside>
          <UtilityMap mapData={mapData} selectedIssue={selectedIssue} categories={categories} onSelectIssue={loadIssue} />
          <IssueDetail issue={selectedIssue} onSave={saveReview} />
          <NetworkMetrics network={network} summary={summary} />
          <ComponentExplorer components={components} />
          <StandardizationReadiness readiness={readiness} mappings={mappings} />
        </aside>
      </div>
    </main>
  );
}

function UtilityContextBreadcrumb() {
  return (
    <section className={styles.panel}>
      <div className={styles.breadcrumb}>
        <span>Utilities</span>
        <span>&gt;</span>
        <strong>Wastewater</strong>
        <span>&gt;</span>
        <span>Gravity Network / Structures</span>
      </div>
    </section>
  );
}

function UtilityHealthSummary({ summary }: { summary: Summary }) {
  const counts = summary.input_feature_counts ?? {};
  return (
    <section className={styles.grid}>
      <Metric labelText="Latest run" value={summary.started_at ?? "Not run"} detail={summary.run_status ?? ""} />
      <Metric labelText="Source layers" value={(summary.staged_input_layers ?? []).join(", ") || "None"} detail={`${counts.wastewater_gravity_main ?? 0} pipes, ${counts.wastewater_manhole ?? 0} manholes`} />
      <Metric labelText="Spatial reference" value={summary.spatial_reference ?? "Unknown"} detail={(summary.limitations ?? []).slice(0, 1).join(" ")} />
      <Metric labelText="Open QA issues" value={String(summary.total_issues ?? 0)} detail="Generated from staged wastewater data." />
    </section>
  );
}

function CategoryMetrics({ summary }: { summary: Summary }) {
  return (
    <section className={styles.panel}>
      <h2>Category metrics</h2>
      <div className={styles.grid}>
        {["Identity", "Attributes", "Geometry", "Connectivity", "Lineage"].map((category) => {
          const metric = summary.category_metrics?.[category];
          return (
            <article className={styles.metric} key={category}>
              <span>{category}</span>
              <strong>{metric ? `${metric.numerator} / ${metric.denominator}` : "Unavailable"}</strong>
              <p className={styles.muted}>{metric?.summary ?? "No generated metric yet."}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function Metric({ labelText, value, detail }: { labelText: string; value: string; detail: string }) {
  return (
    <article className={styles.metric}>
      <span>{labelText}</span>
      <strong>{value}</strong>
      <p className={styles.muted}>{detail}</p>
    </article>
  );
}

function PriorityReviewQueue({ queue, sampleTotal, onSelect }: { queue: Issue[]; sampleTotal: number; onSelect: (issue: Issue) => void }) {
  return (
    <section className={styles.panel}>
      <h2>Priority review queue</h2>
      <p className={styles.muted}>Review sample contains {sampleTotal} finding(s). Default ordering favors high-confidence severe findings, unmatched endpoints, isolated assets, identity, geometry, then completeness gaps.</p>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr><th>Priority</th><th>Rule</th><th>Finding</th><th>Class</th><th>Disposition</th></tr>
          </thead>
          <tbody>
            {queue.map((issue) => (
              <tr key={issue.issue_id} onClick={() => onSelect(issue)}>
                <td>{label(issue.review_priority)}</td>
                <td>{issue.rule_code}</td>
                <td>{issue.description}</td>
                <td>{label(issue.finding_class)}</td>
                <td>{label(issue.disposition)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BatchReview({ selectedCount, onApply }: { selectedCount: number; onApply: (update: Record<string, string | boolean>) => void }) {
  const [assignedTo, setAssignedTo] = useState("");
  const [workflowStatus, setWorkflowStatus] = useState("");
  const [disposition, setDisposition] = useState("");
  const [note, setNote] = useState("");
  const [fieldVerification, setFieldVerification] = useState(false);
  const [engineeringReview, setEngineeringReview] = useState(false);

  return (
    <section className={styles.panel}>
      <h2>Batch review</h2>
      <div className={styles.filters}>
        <input value={assignedTo} onChange={(event) => setAssignedTo(event.target.value)} placeholder="Assign reviewer" />
        <Select labelText="Workflow" value={workflowStatus} options={workflowStatuses} onChange={setWorkflowStatus} />
        <Select labelText="Disposition" value={disposition} options={dispositions} onChange={setDisposition} />
        <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Shared note" />
        <label><input type="checkbox" checked={fieldVerification} onChange={(event) => setFieldVerification(event.target.checked)} /> Field verification</label>
        <label><input type="checkbox" checked={engineeringReview} onChange={(event) => setEngineeringReview(event.target.checked)} /> Engineering review</label>
      </div>
      <div className={styles.buttonRow}>
        <button
          className={styles.button}
          disabled={selectedCount === 0}
          onClick={() => onApply({ assigned_to: assignedTo, workflow_status: workflowStatus, disposition, review_notes: note, field_verification_required: fieldVerification, engineering_review_required: engineeringReview })}
        >
          Apply to {selectedCount} selected
        </button>
        <button className={styles.button} disabled={selectedCount === 0} onClick={() => onApply({ workflow_status: "deferred", disposition: "deferred", review_notes: note })}>Defer</button>
      </div>
    </section>
  );
}

function RuleCalibrationView({ rows }: { rows: CalibrationRow[] }) {
  return (
    <section className={styles.panel}>
      <h2>Rule calibration</h2>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr><th>Rule</th><th>Total</th><th>Reviewed</th><th>Confirmed</th><th>False positives</th><th>Source limitations</th><th>Confirmation rate</th><th>False-positive rate</th><th>Threshold</th><th>Status</th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.rule_code}>
                <td>{row.rule_code}</td>
                <td>{row.total_findings}</td>
                <td>{row.reviewed_findings}</td>
                <td>{row.confirmed_defects}</td>
                <td>{row.false_positives}</td>
                <td>{row.source_limitations}</td>
                <td>{pct(row.confirmation_rate)}</td>
                <td>{pct(row.false_positive_rate)}</td>
                <td>{row.threshold || "None"}</td>
                <td>{label(row.calibration_status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function IssueExplorer({
  issues,
  filters,
  severities,
  categories,
  ruleCodes,
  onFilter,
  onSelect,
  selectedIssueIds,
  setSelectedIssueIds,
  offset,
  setOffset,
}: {
  issues: IssuesResponse;
  filters: Record<string, string>;
  severities: string[];
  categories: string[];
  ruleCodes: string[];
  onFilter: (key: "severity" | "category" | "rule_code" | "review_status" | "source_layer" | "asset", value: string) => void;
  onSelect: (issue: Issue) => void;
  selectedIssueIds: string[];
  setSelectedIssueIds: (value: string[]) => void;
  offset: number;
  setOffset: (value: number) => void;
}) {
  function toggleIssue(issueId: string, checked: boolean) {
    setSelectedIssueIds(checked ? [...selectedIssueIds, issueId] : selectedIssueIds.filter((id) => id !== issueId));
  }

  return (
    <section className={styles.panel}>
      <h2>QA issue explorer</h2>
      <div className={styles.filters}>
        <Select labelText="Severity" value={filters.severity} options={severities} onChange={(value) => onFilter("severity", value)} />
        <Select labelText="Category" value={filters.category} options={categories} onChange={(value) => onFilter("category", value)} />
        <Select labelText="Rule" value={filters.rule_code} options={ruleCodes} onChange={(value) => onFilter("rule_code", value)} />
        <Select labelText="Status" value={filters.review_status} options={workflowStatuses} onChange={(value) => onFilter("review_status", value)} />
        <Select labelText="Layer" value={filters.source_layer} options={["wastewater_gravity_main", "wastewater_manhole", "network"]} onChange={(value) => onFilter("source_layer", value)} />
        <input value={filters.asset} placeholder="Asset search" onChange={(event) => onFilter("asset", event.target.value)} />
      </div>
      {issues.items.length === 0 ? (
        <p className={styles.muted}>{issues.message || "No wastewater QA issues matched the filters."}</p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Select</th>
                <th>Severity</th>
                <th>Rule</th>
                <th>Asset</th>
                <th>Layer</th>
                <th>Description</th>
                <th>Class</th>
                <th>Confidence</th>
                <th>Workflow</th>
                <th>Disposition</th>
              </tr>
            </thead>
            <tbody>
              {issues.items.map((issue) => (
                <tr key={issue.issue_id} onClick={() => onSelect(issue)}>
                  <td onClick={(event) => event.stopPropagation()}>
                    <input aria-label={`Select ${issue.issue_id}`} type="checkbox" checked={selectedIssueIds.includes(issue.issue_id)} onChange={(event) => toggleIssue(issue.issue_id, event.target.checked)} />
                  </td>
                  <td className={styles.severity}>{issue.severity}</td>
                  <td>{issue.rule_code}</td>
                  <td>{issue.source_asset_id || issue.source_objectid}</td>
                  <td>{label(issue.source_layer)}</td>
                  <td>{issue.description}</td>
                  <td>{label(issue.finding_class)}</td>
                  <td>{issue.confidence}</td>
                  <td>{label(issue.workflow_status || issue.review_status)}</td>
                  <td>{label(issue.disposition)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className={styles.buttonRow}>
        <button className={styles.button} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - issues.pagination.limit))}>
          Previous
        </button>
        <button className={styles.button} disabled={!issues.pagination.has_more} onClick={() => setOffset(offset + issues.pagination.limit)}>
          Next
        </button>
        <span className={styles.muted}>{issues.pagination.total} issue(s)</span>
      </div>
    </section>
  );
}

function Select({ labelText, value, options, onChange }: { labelText: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} aria-label={labelText}>
      <option value="">All {labelText.toLowerCase()}</option>
      {options.map((option) => (
        <option value={option} key={option}>
          {label(option)}
        </option>
      ))}
    </select>
  );
}

function UtilityMap({ mapData, selectedIssue, categories, onSelectIssue }: { mapData: MapData; selectedIssue: Issue | null; categories: string[]; onSelectIssue: (issueId: string) => void }) {
  const mapNode = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<ArcGisView | null>(null);
  const [showPipes, setShowPipes] = useState(true);
  const [showManholes, setShowManholes] = useState(true);
  const [hiddenCategories, setHiddenCategories] = useState<string[]>([]);
  const visibleCategories = categories.filter((category) => !hiddenCategories.includes(category));

  useEffect(() => {
    let cancelled = false;
    async function drawMap() {
      if (!mapNode.current) return;
      const { Map, MapView, GraphicsLayer, Graphic, Point, Polyline } = await loadArcGisSdk();
      if (cancelled || !mapNode.current) return;
      viewRef.current?.destroy();
      const map = new Map({ basemap: "streets-vector" });
      const layer = new GraphicsLayer() as ArcGisLayer;
      (map as { add: (item: unknown) => void }).add(layer);
      const graphics = [
        ...(showPipes ? mapData.pipes.map((item) => featureGraphic(Graphic, Polyline, Point, item, "pipe", selectedIssue)) : []),
        ...(showManholes ? mapData.manholes.map((item) => featureGraphic(Graphic, Polyline, Point, item, "manhole", selectedIssue)) : []),
        ...mapData.issues
          .filter((item) => visibleCategories.includes(item.category ?? ""))
          .map((item) => featureGraphic(Graphic, Polyline, Point, item, "issue", selectedIssue)),
      ].filter(Boolean);
      layer.addMany(graphics);
      const firstPoint = mapData.manholes[0]?.geometry;
      const center = "x" in firstPoint ? [firstPoint.x, firstPoint.y] : [-8968000, 4214000];
      const view = new MapView({ container: mapNode.current, map, center, zoom: 12, spatialReference: { wkid: 3857 } }) as ArcGisView;
      view.on("click", async (event) => {
        const hit = await view.hitTest(event);
        const result = hit.results.find((item) => "graphic" in item);
        const issueId = result?.graphic?.attributes?.issue_id;
        if (issueId) onSelectIssue(issueId);
      });
      viewRef.current = view;
    }
    drawMap();
    return () => {
      cancelled = true;
      viewRef.current?.destroy();
      viewRef.current = null;
    };
  }, [mapData, showPipes, showManholes, visibleCategories, selectedIssue, onSelectIssue]);

  useEffect(() => {
    if (!selectedIssue?.safe_geometry || !viewRef.current) return;
    const geometry = selectedIssue.safe_geometry;
    if ("x" in geometry) {
      viewRef.current.goTo({ center: [geometry.x, geometry.y], zoom: 16 }).catch(() => undefined);
    }
  }, [selectedIssue]);

  return (
    <section className={styles.panel}>
      <h2>Map</h2>
      <div className={styles.toggles}>
        <label><input type="checkbox" checked={showPipes} onChange={(event) => setShowPipes(event.target.checked)} /> Pipes</label>
        <label><input type="checkbox" checked={showManholes} onChange={(event) => setShowManholes(event.target.checked)} /> Manholes</label>
        {categories.map((category) => (
          <label key={category}>
            <input
              type="checkbox"
              checked={visibleCategories.includes(category)}
              onChange={(event) => setHiddenCategories((current) => event.target.checked ? current.filter((item) => item !== category) : [...current, category])}
            />
            {label(category)}
          </label>
        ))}
      </div>
      <div className={styles.map} ref={mapNode} />
    </section>
  );
}

function loadArcGisSdk(): Promise<ArcGisModules> {
  return new Promise((resolve, reject) => {
    const finish = () => {
      const arcgisRequire = Reflect.get(window, "require") as Window["require"] | undefined;
      if (typeof arcgisRequire !== "function") {
        reject(new Error("ArcGIS loader unavailable."));
        return;
      }
      arcgisRequire(
        ["esri/Map", "esri/views/MapView", "esri/layers/GraphicsLayer", "esri/Graphic", "esri/geometry/Point", "esri/geometry/Polyline"],
        (Map, MapView, GraphicsLayer, Graphic, Point, Polyline) => resolve({ Map, MapView, GraphicsLayer, Graphic, Point, Polyline }),
      );
    };
    if (typeof Reflect.get(window, "require") === "function") {
      finish();
      return;
    }
    if (!document.getElementById("arcgis-css")) {
      const link = document.createElement("link");
      link.id = "arcgis-css";
      link.rel = "stylesheet";
      link.href = "https://js.arcgis.com/4.31/esri/themes/light/main.css";
      document.head.appendChild(link);
    }
    const existing = document.getElementById("arcgis-js") as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", finish, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.id = "arcgis-js";
    script.src = "https://js.arcgis.com/4.31/";
    script.async = true;
    script.onload = finish;
    script.onerror = () => reject(new Error("ArcGIS SDK failed to load."));
    document.body.appendChild(script);
  });
}

function featureGraphic(Graphic: ArcGisConstructor, Polyline: ArcGisConstructor, Point: ArcGisConstructor, item: MapFeature, kind: string, selectedIssue: Issue | null) {
  const geometry = item.geometry;
  const isSelected = selectedIssue?.issue_id && item.issue_id === selectedIssue.issue_id;
  if ("paths" in geometry) {
    return new Graphic({
      geometry: new Polyline({ paths: geometry.paths, spatialReference: { wkid: geometry.spatial_reference_wkid ?? 3857 } }),
      attributes: item,
      symbol: { type: "simple-line", color: kind === "issue" ? [196, 85, 33, 0.95] : [36, 95, 143, 0.65], width: isSelected ? 4 : 1.5 },
    });
  }
  if ("x" in geometry) {
    const issueColor = item.severity === "high" ? [178, 54, 39, 0.9] : item.severity === "medium" ? [194, 127, 31, 0.9] : [36, 107, 80, 0.85];
    return new Graphic({
      geometry: new Point({ x: geometry.x, y: geometry.y, spatialReference: { wkid: geometry.spatial_reference_wkid ?? 3857 } }),
      attributes: item,
      symbol: { type: "simple-marker", color: kind === "issue" ? issueColor : [36, 107, 80, 0.7], outline: { color: [255, 255, 255, 0.9], width: 1 }, size: isSelected ? 13 : kind === "issue" ? 9 : 5 },
    });
  }
  return null;
}

function IssueDetail({ issue, onSave }: { issue: Issue | null; onSave: (workflowStatus: string, disposition: string, reviewer: string, notes: string) => void }) {
  if (!issue) {
    return (
      <section className={styles.detailPanel}>
        <h2>Issue detail</h2>
        <p className={styles.muted}>Select an issue to review detection details and update review status.</p>
      </section>
    );
  }

  return <IssueReviewForm key={issue.issue_id} issue={issue} onSave={onSave} />;
}

function IssueReviewForm({ issue, onSave }: { issue: Issue; onSave: (workflowStatus: string, disposition: string, reviewer: string, notes: string) => void }) {
  const [workflowStatus, setWorkflowStatus] = useState(issue.workflow_status || issue.review_status || "open");
  const [disposition, setDisposition] = useState(issue.disposition || "unreviewed");
  const [reviewer, setReviewer] = useState(issue.reviewer || "");
  const [notes, setNotes] = useState(issue.review_notes || issue.resolution_notes || "");

  return (
    <section className={styles.detailPanel}>
      <h2>Issue detail</h2>
      <dl className={styles.detailGrid}>
        <div><dt>Detected condition</dt><dd>{issue.description}</dd></div>
        <div><dt>Why it matters</dt><dd>{issue.why_it_matters}</dd></div>
        <div><dt>Recommended action</dt><dd>{issue.recommended_action}</dd></div>
        <div><dt>Detection method</dt><dd>{issue.detection_method}</dd></div>
        <div><dt>Threshold</dt><dd>{issue.threshold_used || "Not applicable"}</dd></div>
        <div><dt>Finding class</dt><dd>{label(issue.finding_class)}</dd></div>
        <div><dt>Possible missing dependency</dt><dd>{label(issue.possible_missing_dependency) || "None"}</dd></div>
        <div><dt>Dependency context</dt><dd>{issue.dependency_explanation || "No dependency warning."}</dd></div>
        <div><dt>Fingerprint</dt><dd>{issue.issue_fingerprint}</dd></div>
        <div><dt>Related asset</dt><dd>{issue.related_asset_id || issue.related_objectid || "None"}</dd></div>
        <div><dt>Run ID</dt><dd>{issue.run_id}</dd></div>
        <div><dt>Seen</dt><dd>{issue.occurrence_count} occurrence(s), latest run {issue.latest_seen_run_id}</dd></div>
      </dl>
      <div className={styles.buttonRow}>
        <select value={workflowStatus} onChange={(event) => setWorkflowStatus(event.target.value)} aria-label="Workflow status">
          {workflowStatuses.map((status) => <option value={status} key={status}>{label(status)}</option>)}
        </select>
        <select value={disposition} onChange={(event) => setDisposition(event.target.value)} aria-label="Disposition">
          {dispositions.map((value) => <option value={value} key={value}>{label(value)}</option>)}
        </select>
        <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Reviewer" />
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Review notes" />
        <button className={styles.button} onClick={() => onSave(workflowStatus, disposition, reviewer, notes)}>Save review</button>
      </div>
    </section>
  );
}

function NetworkMetrics({ network, summary }: { network: NetworkResponse; summary: Summary }) {
  return (
    <section className={styles.panel}>
      <h2>Network analysis</h2>
      <div className={styles.grid}>
        <Metric labelText="Components" value={String(summary.connected_component_count ?? network.summary.total_connected_components ?? 0)} detail="Proximity components." />
        <Metric labelText="Largest component" value={String(summary.largest_component_size ?? network.summary.largest_component_size ?? 0)} detail="Pipes plus manholes." />
        <Metric labelText="Endpoint match rate" value={pct(summary.endpoint_match_rate ?? 0)} detail={`${summary.unmatched_endpoints ?? 0} unmatched endpoints.`} />
        <Metric labelText="Isolated assets" value={`${summary.isolated_pipes ?? 0} / ${summary.isolated_manholes ?? 0}`} detail="Pipes / manholes." />
      </div>
      <p className={styles.muted}>{network.limitations.join(" ")}</p>
    </section>
  );
}

function ComponentExplorer({ components }: { components: ComponentRow[] }) {
  return (
    <section className={styles.panel}>
      <h2>Component explorer</h2>
      <p className={styles.muted}>{components.length} proximity component(s). Classifications are review metadata, not automatic defects.</p>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr><th>ID</th><th>Assets</th><th>Pipes</th><th>Manholes</th><th>Unmatched</th><th>Nearest</th><th>Likely reason</th><th>Review</th></tr>
          </thead>
          <tbody>
            {components.map((component) => (
              <tr key={component.component_id}>
                <td>{component.component_id}</td>
                <td>{component.total_asset_count}</td>
                <td>{component.pipe_count}</td>
                <td>{component.manhole_count}</td>
                <td>{component.unmatched_endpoints}</td>
                <td>{component.nearest_other_component_distance}</td>
                <td>{label(component.likely_classification)}</td>
                <td>{label(component.review_classification || component.review_status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StandardizationReadiness({ readiness, mappings }: { readiness: Readiness; mappings: MappingRow[] }) {
  const awaiting = mappings.filter((row) => row.approved_to_standardize !== "true" && !row.blocked_reason).length;
  return (
    <section className={styles.panel}>
      <h2>Standardization readiness</h2>
      <div className={styles.grid}>
        <Metric labelText="Status" value={label(readiness.standardization_status ?? "pending")} detail="No standardized writes are enabled." />
        <Metric labelText="Awaiting confirmation" value={String(awaiting)} detail="Mappings default to not approved." />
        <Metric labelText="Unavailable fields" value={String(readiness.fields_unavailable?.length ?? 0)} detail="No source mapping proposed." />
        <Metric labelText="Missing dependencies" value={String(readiness.dependencies_still_missing?.length ?? 0)} detail="Additional utility layers needed for context." />
      </div>
      <p className={styles.muted}>Writes to standardized GDB: {String(readiness.writes_to_standardized_gdb)}. Writes to curated GDB: {String(readiness.writes_to_curated_gdb)}.</p>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr><th>Source</th><th>Field</th><th>Target</th><th>Confidence</th><th>Unit</th><th>Codes</th><th>Approved</th></tr>
          </thead>
          <tbody>
            {mappings.slice(0, 12).map((row) => (
              <tr key={`${row.source_layer}-${row.source_field}-${row.target_field}`}>
                <td>{label(row.source_layer)}</td>
                <td>{row.source_field}</td>
                <td>{row.target_field}</td>
                <td>{row.confidence}</td>
                <td>{row.unit_conversion}</td>
                <td>{row.code_translation}</td>
                <td>{row.approved_to_standardize}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RuleCatalog({ rules }: { rules: Rule[] }) {
  return (
    <section className={styles.panel}>
      <h2>Rule catalog</h2>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Rule</th>
              <th>Category</th>
              <th>Severity</th>
              <th>Enabled</th>
              <th>Status</th>
              <th>Issues</th>
              <th>Threshold</th>
              <th>Method</th>
              <th>Limitation</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule) => (
              <tr key={rule.rule_code}>
                <td>{rule.rule_code}</td>
                <td>{rule.category}</td>
                <td>{rule.severity}</td>
                <td>{String(rule.enabled)}</td>
                <td>{rule.status === "skipped" ? `Skipped: ${rule.skip_reason}` : rule.status}</td>
                <td>{rule.issue_count ?? 0}</td>
                <td>{JSON.stringify(rule.parameters)}</td>
                <td>{rule.detection_method}</td>
                <td>{rule.limitation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
