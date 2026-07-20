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
  rule_code: string;
  rule_name: string;
  category: string;
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
  reviewer: string;
  reviewed_at: string;
  resolution_notes: string;
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
const reviewStatuses = ["open", "under_review", "confirmed_issue", "false_positive", "needs_field_verification", "needs_engineering_review", "resolved", "deferred"];

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
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ severity: "", category: "", rule_code: "", review_status: "", source_layer: "", asset: "" });
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    async function loadStaticData() {
      try {
        const [summaryResponse, rulesResponse, networkResponse, mapResponse] = await Promise.all([
          fetch(`${apiUrl}/api/data-health/wastewater/summary`),
          fetch(`${apiUrl}/api/data-health/wastewater/rules`),
          fetch(`${apiUrl}/api/data-health/wastewater/network`),
          fetch(`${apiUrl}/api/data-health/wastewater/map`),
        ]);
        if (!summaryResponse.ok || !rulesResponse.ok || !networkResponse.ok || !mapResponse.ok) {
          throw new Error("Data Health API request failed.");
        }
        setSummary(await summaryResponse.json());
        setRules((await rulesResponse.json()).rules ?? []);
        setNetwork(await networkResponse.json());
        setMapData(await mapResponse.json());
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

  async function saveReview(review_status: string, reviewer: string, resolution_notes: string) {
    if (!selectedIssue) return;
    const response = await fetch(`${apiUrl}/api/data-health/wastewater/issues/${selectedIssue.issue_id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_status, reviewer, resolution_notes }),
    });
    if (response.ok) {
      const updated = await response.json();
      setSelectedIssue(updated);
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
          <IssueExplorer
            issues={issues}
            filters={filters}
            severities={severities}
            categories={categories}
            ruleCodes={ruleCodes}
            onFilter={updateFilter}
            onSelect={(issue) => setSelectedIssue(issue)}
            offset={offset}
            setOffset={setOffset}
          />
          <RuleCatalog rules={rules} />
        </div>

        <aside>
          <UtilityMap mapData={mapData} selectedIssue={selectedIssue} categories={categories} onSelectIssue={loadIssue} />
          <IssueDetail issue={selectedIssue} onSave={saveReview} />
          <NetworkMetrics network={network} summary={summary} />
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

function IssueExplorer({
  issues,
  filters,
  severities,
  categories,
  ruleCodes,
  onFilter,
  onSelect,
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
  offset: number;
  setOffset: (value: number) => void;
}) {
  return (
    <section className={styles.panel}>
      <h2>QA issue explorer</h2>
      <div className={styles.filters}>
        <Select labelText="Severity" value={filters.severity} options={severities} onChange={(value) => onFilter("severity", value)} />
        <Select labelText="Category" value={filters.category} options={categories} onChange={(value) => onFilter("category", value)} />
        <Select labelText="Rule" value={filters.rule_code} options={ruleCodes} onChange={(value) => onFilter("rule_code", value)} />
        <Select labelText="Status" value={filters.review_status} options={reviewStatuses} onChange={(value) => onFilter("review_status", value)} />
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
                <th>Severity</th>
                <th>Rule</th>
                <th>Asset</th>
                <th>Layer</th>
                <th>Description</th>
                <th>Confidence</th>
                <th>Review Status</th>
              </tr>
            </thead>
            <tbody>
              {issues.items.map((issue) => (
                <tr key={issue.issue_id} onClick={() => onSelect(issue)}>
                  <td className={styles.severity}>{issue.severity}</td>
                  <td>{issue.rule_code}</td>
                  <td>{issue.source_asset_id || issue.source_objectid}</td>
                  <td>{label(issue.source_layer)}</td>
                  <td>{issue.description}</td>
                  <td>{issue.confidence}</td>
                  <td>{label(issue.review_status)}</td>
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

function IssueDetail({ issue, onSave }: { issue: Issue | null; onSave: (reviewStatus: string, reviewer: string, notes: string) => void }) {
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

function IssueReviewForm({ issue, onSave }: { issue: Issue; onSave: (reviewStatus: string, reviewer: string, notes: string) => void }) {
  const [reviewStatus, setReviewStatus] = useState(issue.review_status || "open");
  const [reviewer, setReviewer] = useState(issue.reviewer || "");
  const [notes, setNotes] = useState(issue.resolution_notes || "");

  return (
    <section className={styles.detailPanel}>
      <h2>Issue detail</h2>
      <dl className={styles.detailGrid}>
        <div><dt>Detected condition</dt><dd>{issue.description}</dd></div>
        <div><dt>Why it matters</dt><dd>{issue.why_it_matters}</dd></div>
        <div><dt>Recommended action</dt><dd>{issue.recommended_action}</dd></div>
        <div><dt>Detection method</dt><dd>{issue.detection_method}</dd></div>
        <div><dt>Threshold</dt><dd>{issue.threshold_used || "Not applicable"}</dd></div>
        <div><dt>Related asset</dt><dd>{issue.related_asset_id || issue.related_objectid || "None"}</dd></div>
        <div><dt>Run ID</dt><dd>{issue.run_id}</dd></div>
      </dl>
      <div className={styles.buttonRow}>
        <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)} aria-label="Review status">
          {reviewStatuses.map((status) => <option value={status} key={status}>{label(status)}</option>)}
        </select>
        <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Reviewer" />
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Resolution notes" />
        <button className={styles.button} onClick={() => onSave(reviewStatus, reviewer, notes)}>Save review</button>
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
