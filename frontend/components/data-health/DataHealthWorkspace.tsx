"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { CalibrationRow, ComponentRow, Issue, IssuesResponse, MapData, MappingRow, NetworkResponse, Readiness, RuleRow } from "../../lib/api-types";
import { fetchJson, patchJson } from "../../lib/api-client";
import { compactNumber, label, percent, safeText, shortDate } from "../../lib/formatters";
import { dispositions, workflowStatuses } from "../../lib/statuses";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, SeverityBadge, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import { UtilityMap } from "../maps/UtilityMap";
import styles from "./data-health.module.css";

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
};

type Filters = {
  severity: string;
  category: string;
  rule_code: string;
  review_status: string;
  disposition: string;
  source_layer: string;
  asset: string;
};

const defaultFilters: Filters = { severity: "", category: "", rule_code: "", review_status: "", disposition: "", source_layer: "", asset: "" };
const emptyIssues: IssuesResponse = { items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false }, message: "" };
const emptyMap: MapData = { pipes: [], manholes: [], issues: [] };
const tabs = ["Issues", "Network", "Rules", "Calibration", "Standardization"] as const;

export function DataHealthWorkspace() {
  const [summary, setSummary] = useState<Summary>({});
  const [rules, setRules] = useState<RuleRow[]>([]);
  const [issues, setIssues] = useState<IssuesResponse>(emptyIssues);
  const [network, setNetwork] = useState<NetworkResponse>({ summary: {}, limitations: [] });
  const [mapData, setMapData] = useState<MapData>(emptyMap);
  const [queue, setQueue] = useState<Issue[]>([]);
  const [calibration, setCalibration] = useState<CalibrationRow[]>([]);
  const [components, setComponents] = useState<ComponentRow[]>([]);
  const [readiness, setReadiness] = useState<Readiness>({});
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [sampleTotal, setSampleTotal] = useState(0);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [selectedIssueIds, setSelectedIssueIds] = useState<string[]>([]);
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [offset, setOffset] = useState(0);
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>("Issues");
  const [layoutMode, setLayoutMode] = useState<"split" | "table" | "map">("split");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadIssue = useCallback(async (issueId: string) => {
    const issue = await fetchJson<Issue>(`/api/data-health/wastewater/issues/${encodeURIComponent(issueId)}`);
    setSelectedIssue(issue);
  }, []);

  const loadIssues = useCallback(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    fetchJson<IssuesResponse>(`/api/data-health/wastewater/issues?${params}`, controller.signal)
      .then(setIssues)
      .catch(() => setError("Could not load wastewater QA issues."));
    return () => controller.abort();
  }, [filters, offset]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchJson<Summary>("/api/data-health/wastewater/summary", controller.signal),
      fetchJson<{ rules: RuleRow[] }>("/api/data-health/wastewater/rules", controller.signal),
      fetchJson<NetworkResponse>("/api/data-health/wastewater/network", controller.signal),
      fetchJson<MapData>("/api/data-health/wastewater/map", controller.signal),
      fetchJson<IssuesResponse>("/api/review/wastewater/queue?limit=12", controller.signal),
      fetchJson<{ rows: CalibrationRow[] }>("/api/review/wastewater/calibration", controller.signal),
      fetchJson<{ total: number }>("/api/review/wastewater/sample", controller.signal),
      fetchJson<{ items: ComponentRow[] }>("/api/data-health/wastewater/components?limit=100", controller.signal),
      fetchJson<Readiness>("/api/standardization/wastewater/readiness", controller.signal),
      fetchJson<{ mappings: MappingRow[] }>("/api/standardization/wastewater/mappings", controller.signal),
    ])
      .then(([summaryData, rulesData, networkData, mapLayers, queueData, calibrationData, sampleData, componentData, readinessData, mappingData]) => {
        setSummary(summaryData);
        setRules(rulesData.rules ?? []);
        setNetwork(networkData);
        setMapData(mapLayers);
        setQueue(queueData.items ?? []);
        setCalibration(calibrationData.rows ?? []);
        setSampleTotal(sampleData.total ?? 0);
        setComponents(componentData.items ?? []);
        setReadiness(readinessData);
        setMappings(mappingData.mappings ?? []);
        setLoading(false);
        const requestedIssue = new URLSearchParams(window.location.search).get("issue");
        if (requestedIssue) loadIssue(requestedIssue).catch(() => undefined);
      })
      .catch(() => {
        setLoading(false);
        setError("Data Health API is unavailable. Confirm the FastAPI backend is running and QA reports exist.");
      });
    return () => controller.abort();
  }, [loadIssue]);

  useEffect(loadIssues, [loadIssues]);

  const categories = useMemo(() => Object.keys(summary.issues_by_category ?? {}).sort(), [summary.issues_by_category]);
  const severities = useMemo(() => Object.keys(summary.issues_by_severity ?? {}).sort(), [summary.issues_by_severity]);
  const ruleCodes = useMemo(() => rules.map((rule) => rule.rule_code).sort(), [rules]);

  function updateFilter(key: keyof Filters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setOffset(0);
  }

  async function saveReview(update: Partial<Issue>) {
    if (!selectedIssue) return;
    const updated = await patchJson<Issue>(`/api/data-health/wastewater/issues/${selectedIssue.issue_id}`, update);
    setSelectedIssue(updated);
    loadIssues();
  }

  async function applyBatch(update: Partial<Issue>) {
    if (selectedIssueIds.length === 0 || !window.confirm(`Apply review update to ${selectedIssueIds.length} selected issue(s)?`)) return;
    await patchJson("/api/review/wastewater/issues/batch", { issue_ids: selectedIssueIds, ...update });
    setSelectedIssueIds([]);
    loadIssues();
  }

  if (error && !summary.run_id) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <OfflineState service="Wastewater Data Health API" />
      </div>
    );
  }

  if (loading) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <div className={ws.workspace}>
      <PageIntro summary={summary} onRefresh={() => window.location.reload()} />
      {error ? <OfflineState service={error} /> : null}
      <HeaderMetrics summary={summary} />
      <FilterToolbar
        filters={filters}
        categories={categories}
        severities={severities}
        ruleCodes={ruleCodes}
        resultCount={issues.pagination.total}
        layoutMode={layoutMode}
        onFilter={updateFilter}
        onClear={() => setFilters(defaultFilters)}
        onLayout={setLayoutMode}
      />
      <div className={styles.tabBar} role="tablist" aria-label="Data Health workspace">
        {tabs.map((tab) => (
          <button className={styles.tabButton} role="tab" aria-selected={activeTab === tab} key={tab} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Issues" ? (
        <IssuesTab
          issues={issues}
          mapData={mapData}
          categories={categories}
          selectedIssue={selectedIssue}
          selectedIssueIds={selectedIssueIds}
          layoutMode={layoutMode}
          queue={queue}
          sampleTotal={sampleTotal}
          offset={offset}
          onOffset={setOffset}
          onSelectIssue={(issue) => setSelectedIssue(issue)}
          onLoadIssue={(issueId) => loadIssue(issueId).catch(() => undefined)}
          onSelectedIds={setSelectedIssueIds}
        />
      ) : null}
      {activeTab === "Network" ? <NetworkTab summary={summary} network={network} components={components} /> : null}
      {activeTab === "Rules" ? <RulesTab rules={rules} /> : null}
      {activeTab === "Calibration" ? <CalibrationTab rows={calibration} /> : null}
      {activeTab === "Standardization" ? <StandardizationTab readiness={readiness} mappings={mappings} /> : null}

      {selectedIssue ? <IssueDrawer issue={selectedIssue} onClose={() => setSelectedIssue(null)} onSave={saveReview} /> : null}
      {selectedIssueIds.length ? <BatchActionBar selectedCount={selectedIssueIds.length} onApply={applyBatch} onClear={() => setSelectedIssueIds([])} /> : null}
    </div>
  );
}

function PageIntro({ summary, onRefresh }: { summary?: Summary; onRefresh?: () => void }) {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>Utilities · Wastewater · Data Health</span>
      <h1>Wastewater Data Health</h1>
      <p>Transparent GIS quality, connectivity, and source-readiness review for wastewater assets. Run {safeText(summary?.run_status, "status unavailable")} completed {shortDate(summary?.completed_at)}.</p>
      {onRefresh ? <button className={ws.button} onClick={onRefresh}>Refresh API data</button> : null}
    </header>
  );
}

function HeaderMetrics({ summary }: { summary: Summary }) {
  const counts = summary.input_feature_counts ?? {};
  return (
    <section className={styles.summaryStrip} aria-label="Wastewater run summary">
      <MetricTile labelText="Gravity mains" value={compactNumber(counts.wastewater_gravity_main)} detail="Staged pipe features." />
      <MetricTile labelText="Manholes" value={compactNumber(counts.wastewater_manhole)} detail="Staged structure features." />
      <MetricTile labelText="Endpoint match" value={percent(summary.endpoint_match_rate)} detail={`${compactNumber(summary.unmatched_endpoints)} unmatched endpoint(s).`} />
      <MetricTile labelText="Spatial reference" value={safeText(summary.spatial_reference)} detail={(summary.limitations ?? []).slice(0, 1).join(" ") || "Safe summary only."} />
    </section>
  );
}

function FilterToolbar({
  filters,
  severities,
  categories,
  ruleCodes,
  resultCount,
  layoutMode,
  onFilter,
  onClear,
  onLayout,
}: {
  filters: Filters;
  severities: string[];
  categories: string[];
  ruleCodes: string[];
  resultCount: number;
  layoutMode: "split" | "table" | "map";
  onFilter: (key: keyof Filters, value: string) => void;
  onClear: () => void;
  onLayout: (mode: "split" | "table" | "map") => void;
}) {
  const active = Object.entries(filters).filter(([, value]) => value);
  return (
    <section className={styles.toolbar} aria-label="Issue filters">
      <div className={styles.filterGrid}>
        <Select labelText="Severity" value={filters.severity} options={severities} onChange={(value) => onFilter("severity", value)} />
        <Select labelText="Category" value={filters.category} options={categories} onChange={(value) => onFilter("category", value)} />
        <Select labelText="Rule" value={filters.rule_code} options={ruleCodes} onChange={(value) => onFilter("rule_code", value)} />
        <Select labelText="Workflow" value={filters.review_status} options={workflowStatuses} onChange={(value) => onFilter("review_status", value)} />
        <Select labelText="Disposition" value={filters.disposition} options={dispositions} onChange={(value) => onFilter("disposition", value)} />
        <Select labelText="Layer" value={filters.source_layer} options={["wastewater_gravity_main", "wastewater_manhole", "network"]} onChange={(value) => onFilter("source_layer", value)} />
        <input className={ws.input} value={filters.asset} placeholder="Asset search" onChange={(event) => onFilter("asset", event.target.value)} />
      </div>
      <div className={styles.chipRow}>
        <StatusBadge value={`${compactNumber(resultCount)} results`} />
        {active.map(([key, value]) => (
          <button className={ws.button} key={key} onClick={() => onFilter(key as keyof Filters, "")}>
            {label(key)}: {label(value)}
          </button>
        ))}
        {active.length ? <button className={ws.button} onClick={onClear}>Clear filters</button> : null}
        <span className={styles.layoutToggle} aria-label="Layout mode">
          {(["split", "table", "map"] as const).map((mode) => (
            <button className={styles.tabButton} data-selected={layoutMode === mode} key={mode} onClick={() => onLayout(mode)}>
              {label(mode === "split" ? "map_table" : mode)}
            </button>
          ))}
        </span>
      </div>
    </section>
  );
}

function IssuesTab({
  issues,
  mapData,
  categories,
  selectedIssue,
  selectedIssueIds,
  layoutMode,
  queue,
  sampleTotal,
  offset,
  onOffset,
  onSelectIssue,
  onLoadIssue,
  onSelectedIds,
}: {
  issues: IssuesResponse;
  mapData: MapData;
  categories: string[];
  selectedIssue: Issue | null;
  selectedIssueIds: string[];
  layoutMode: "split" | "table" | "map";
  queue: Issue[];
  sampleTotal: number;
  offset: number;
  onOffset: (offset: number) => void;
  onSelectIssue: (issue: Issue) => void;
  onLoadIssue: (issueId: string) => void;
  onSelectedIds: (ids: string[]) => void;
}) {
  return (
    <>
      <section className={`${styles.issueWorkspace} ${layoutMode === "table" ? styles.tableOnly : ""} ${layoutMode === "map" ? styles.mapOnly : ""}`}>
        {layoutMode !== "table" ? (
          <Panel title="Map Review" description="Road context, assets, and filtered issue geometry.">
            <UtilityMap mapData={mapData} selectedIssue={selectedIssue} categories={categories} onIssueSelect={onLoadIssue} showOpenLink={false} />
          </Panel>
        ) : null}
        {layoutMode !== "map" ? (
          <Panel title="Issue Explorer" description="Paginated review candidates with safe fields only.">
            <IssueTable issues={issues} selectedIssueIds={selectedIssueIds} onSelectedIds={onSelectedIds} onSelectIssue={onSelectIssue} />
            <Pagination issues={issues} offset={offset} onOffset={onOffset} />
          </Panel>
        ) : null}
      </section>
      <Panel title="Priority Review Queue" description={`Review sample contains ${compactNumber(sampleTotal)} finding(s).`}>
        {queue.length ? <IssueTable compact issues={{ ...emptyIssues, items: queue, pagination: { total: queue.length, limit: queue.length, offset: 0, has_more: false } }} selectedIssueIds={[]} onSelectedIds={() => undefined} onSelectIssue={onSelectIssue} /> : <EmptyState title="No priority queue" message="No sampled review findings are available." />}
      </Panel>
    </>
  );
}

function IssueTable({ issues, selectedIssueIds, onSelectedIds, onSelectIssue, compact = false }: { issues: IssuesResponse; selectedIssueIds: string[]; onSelectedIds: (ids: string[]) => void; onSelectIssue: (issue: Issue) => void; compact?: boolean }) {
  if (!issues.items.length) return <EmptyState title="No matching findings" message={issues.message || "No wastewater QA issues matched the filters."} />;
  function toggle(issueId: string, checked: boolean) {
    onSelectedIds(checked ? [...selectedIssueIds, issueId] : selectedIssueIds.filter((id) => id !== issueId));
  }
  return (
    <div className={ws.tableWrap}>
      <table className={`${ws.table} ${styles.issueTable}`}>
        <thead>
          <tr>
            {!compact ? <th>Select</th> : null}
            <th>Severity</th>
            <th>Rule</th>
            <th>Asset</th>
            <th>Layer</th>
            <th>Description</th>
            <th>Finding Class</th>
            <th>Confidence</th>
            <th>Workflow</th>
            <th>Disposition</th>
          </tr>
        </thead>
        <tbody>
          {issues.items.map((issue) => (
            <tr key={issue.issue_id} onClick={() => onSelectIssue(issue)}>
              {!compact ? (
                <td onClick={(event) => event.stopPropagation()}>
                  <input aria-label={`Select issue ${issue.issue_id}`} type="checkbox" checked={selectedIssueIds.includes(issue.issue_id)} onChange={(event) => toggle(issue.issue_id, event.target.checked)} />
                </td>
              ) : null}
              <td><SeverityBadge value={issue.severity} /></td>
              <td className="technical">{issue.rule_code}</td>
              <td className="technical">{issue.source_asset_id || issue.source_objectid || "Unavailable"}</td>
              <td>{label(issue.source_layer)}</td>
              <td>{issue.description}</td>
              <td><StatusBadge value={issue.finding_class ?? "finding"} /></td>
              <td>{label(issue.confidence)}</td>
              <td><StageBadge value={issue.workflow_status || issue.review_status || "open"} /></td>
              <td>{label(issue.disposition ?? "unreviewed")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({ issues, offset, onOffset }: { issues: IssuesResponse; offset: number; onOffset: (offset: number) => void }) {
  return (
    <div className={ws.buttonRow}>
      <button className={ws.button} disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - issues.pagination.limit))}>Previous</button>
      <button className={ws.button} disabled={!issues.pagination.has_more} onClick={() => onOffset(offset + issues.pagination.limit)}>Next</button>
      <span className={styles.muted}>{compactNumber(issues.pagination.total)} issue(s)</span>
    </div>
  );
}

function IssueDrawer({ issue, onClose, onSave }: { issue: Issue; onClose: () => void; onSave: (update: Partial<Issue>) => void }) {
  const [workflowStatus, setWorkflowStatus] = useState(issue.workflow_status || issue.review_status || "open");
  const [disposition, setDisposition] = useState(issue.disposition || "unreviewed");
  const [reviewer, setReviewer] = useState(issue.reviewer || "");
  const [notes, setNotes] = useState(issue.review_notes || "");
  const [fieldVerification, setFieldVerification] = useState(Boolean(issue.field_verification_required));
  const [engineeringReview, setEngineeringReview] = useState(Boolean(issue.engineering_review_required));

  return (
    <aside className={styles.drawer} aria-label="Issue detail">
      <div className={styles.drawerHeader}>
        <div>
          <span className={ws.eyebrow}>{issue.rule_code}</span>
          <h2>{issue.source_asset_id || issue.source_objectid || "Issue detail"}</h2>
          <div className={ws.badgeRow}>
            <SeverityBadge value={issue.severity} />
            <StatusBadge value={issue.finding_class ?? "finding"} />
            <StageBadge value={workflowStatus} />
          </div>
        </div>
        <button className={ws.button} onClick={onClose}>Close</button>
      </div>
      <div className={styles.drawerBody}>
        <DetailGroup title="Finding" rows={[
          ["Detected condition", issue.description],
          ["Why it matters", issue.why_it_matters],
          ["Recommended action", issue.recommended_action],
          ["Related asset", issue.related_asset_id || issue.related_objectid],
        ]} />
        <DetailGroup title="Evidence" rows={[
          ["Detection method", issue.detection_method],
          ["Threshold", issue.threshold_used],
          ["Dependency explanation", issue.dependency_explanation],
          ["Possible missing dependency", label(issue.possible_missing_dependency ?? "")],
        ]} />
        <DetailGroup title="History" rows={[
          ["Fingerprint", issue.issue_fingerprint],
          ["First seen", `${shortDate(issue.first_seen_at)} (${safeText(issue.first_seen_run_id)})`],
          ["Latest seen", `${shortDate(issue.latest_seen_at)} (${safeText(issue.latest_seen_run_id)})`],
          ["Occurrences", String(issue.occurrence_count ?? 1)],
        ]} />
        <div className={styles.detailGroup}>
          <h3>Review Decision</h3>
          <div className={styles.reviewForm}>
            <label>Workflow status<SelectControl value={workflowStatus} options={workflowStatuses} onChange={setWorkflowStatus} /></label>
            <label>Disposition<SelectControl value={disposition} options={dispositions} onChange={setDisposition} /></label>
            <label>Reviewer<input className={ws.input} value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></label>
            <label>Notes<textarea className={ws.input} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
            <label><span><input type="checkbox" checked={fieldVerification} onChange={(event) => setFieldVerification(event.target.checked)} /> Needs field verification</span></label>
            <label><span><input type="checkbox" checked={engineeringReview} onChange={(event) => setEngineeringReview(event.target.checked)} /> Needs engineering review</span></label>
            <button className={`${ws.button} ${ws.buttonPrimary}`} onClick={() => onSave({ workflow_status: workflowStatus, disposition, reviewer, review_notes: notes, field_verification_required: fieldVerification, engineering_review_required: engineeringReview })}>Save review</button>
          </div>
        </div>
      </div>
    </aside>
  );
}

function DetailGroup({ title, rows }: { title: string; rows: [string, unknown][] }) {
  return (
    <div className={styles.detailGroup}>
      <h3>{title}</h3>
      <dl className={styles.detailGrid}>
        {rows.map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd className={key === "Fingerprint" ? "technical" : undefined}>{safeText(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function BatchActionBar({ selectedCount, onApply, onClear }: { selectedCount: number; onApply: (update: Partial<Issue>) => void; onClear: () => void }) {
  const [assignedTo, setAssignedTo] = useState("");
  const [workflowStatus, setWorkflowStatus] = useState("assigned");
  const [disposition, setDisposition] = useState("under_review");
  return (
    <div className={styles.batchBar} role="region" aria-label="Batch review actions">
      <strong>{selectedCount} selected</strong>
      <input className={ws.input} value={assignedTo} placeholder="Assign reviewer" onChange={(event) => setAssignedTo(event.target.value)} />
      <SelectControl value={workflowStatus} options={workflowStatuses} onChange={setWorkflowStatus} />
      <SelectControl value={disposition} options={dispositions} onChange={setDisposition} />
      <button className={ws.button} onClick={() => onApply({ assigned_to: assignedTo, workflow_status: workflowStatus, disposition })}>Apply</button>
      <button className={ws.button} onClick={() => onApply({ field_verification_required: true })}>Field verification</button>
      <button className={ws.button} onClick={() => onApply({ engineering_review_required: true })}>Engineering review</button>
      <button className={ws.button} onClick={() => onApply({ workflow_status: "deferred", disposition: "deferred" })}>Defer</button>
      <button className={ws.button} onClick={onClear}>Clear</button>
    </div>
  );
}

function NetworkTab({ summary, network, components }: { summary: Summary; network: NetworkResponse; components: ComponentRow[] }) {
  return (
    <section className={ws.grid12}>
      <div className={ws.span4}><MetricTile labelText="Endpoint match" value={percent(summary.endpoint_match_rate)} detail={`${compactNumber(summary.unmatched_endpoints)} unmatched endpoint(s).`} /></div>
      <div className={ws.span4}><MetricTile labelText="Components" value={compactNumber(summary.connected_component_count ?? network.summary.total_connected_components)} detail="Proximity graph components." /></div>
      <div className={ws.span4}><MetricTile labelText="Largest component" value={compactNumber(summary.largest_component_size ?? network.summary.largest_component_size)} detail="Assets in largest group." /></div>
      <div className={ws.span12}>
        <Panel title="Component Explorer" description="Component classifications are review metadata, not automatic defects.">
          <div className={ws.tableWrap}>
            <table className={ws.table}>
              <thead><tr><th>ID</th><th>Assets</th><th>Pipes</th><th>Manholes</th><th>Length</th><th>Unmatched</th><th>Nearest</th><th>Likely reason</th><th>Review</th></tr></thead>
              <tbody>
                {components.map((component) => (
                  <tr key={component.component_id}>
                    <td className="technical">{component.component_id}</td>
                    <td>{component.total_asset_count}</td>
                    <td>{component.pipe_count}</td>
                    <td>{component.manhole_count}</td>
                    <td>{compactNumber(component.approximate_network_length)}</td>
                    <td>{component.unmatched_endpoints}</td>
                    <td>{safeText(component.nearest_other_component_distance)}</td>
                    <td>{label(component.likely_classification)}</td>
                    <td>{label(component.review_classification || component.review_status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className={styles.muted}>{network.limitations.join(" ")}</p>
        </Panel>
      </div>
    </section>
  );
}

function RulesTab({ rules }: { rules: RuleRow[] }) {
  const [query, setQuery] = useState("");
  const filtered = rules.filter((rule) => `${rule.rule_code} ${rule.name} ${rule.category}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <Panel title="Rule Catalog" description="Rules execute only when the real schema supports their required fields.">
      <input className={ws.input} value={query} placeholder="Search rules" onChange={(event) => setQuery(event.target.value)} />
      <div className={styles.ruleList}>
        {filtered.map((rule) => (
          <article className={styles.ruleCard} key={rule.rule_code}>
            <div className={ws.badgeRow}>
              <strong className="technical">{rule.rule_code}</strong>
              <StatusBadge value={rule.category} />
              <SeverityBadge value={rule.severity} />
              <StageBadge value={rule.status ?? "not_run"} />
            </div>
            <h3>{rule.name}</h3>
            <p className={styles.muted}>{rule.detection_method}</p>
            <p className={styles.muted}>{rule.status === "skipped" ? `Skipped: ${rule.skip_reason}` : rule.limitation}</p>
          </article>
        ))}
      </div>
    </Panel>
  );
}

function CalibrationTab({ rows }: { rows: CalibrationRow[] }) {
  return (
    <section className={styles.calibrationGrid}>
      {rows.map((row) => (
        <Panel title={row.rule_code} description={label(row.calibration_status)} key={row.rule_code}>
          <MetricTile labelText="Findings" value={compactNumber(row.total_findings)} detail={`${compactNumber(row.reviewed_findings)} reviewed.`} />
          <MetricTile labelText="Confirmation" value={percent(row.confirmation_rate)} detail={`${compactNumber(row.confirmed_defects)} confirmed or likely defects.`} />
          <MetricTile labelText="False positive" value={percent(row.false_positive_rate)} detail={`${compactNumber(row.false_positives)} marked false positive.`} />
          <p className={styles.muted}>Threshold: {row.threshold || "None"}. Source limitations: {compactNumber(row.source_limitations)}.</p>
        </Panel>
      ))}
    </section>
  );
}

function StandardizationTab({ readiness, mappings }: { readiness: Readiness; mappings: MappingRow[] }) {
  return (
    <section className={styles.mappingGrid}>
      <Panel title="Readiness" description="No standardized or curated writes are available in this phase.">
        <MetricTile labelText="Status" value={label(readiness.standardization_status ?? "pending")} detail="Approval remains separate from staging." />
        <MetricTile labelText="Preview eligible" value={compactNumber(readiness.records_eligible_for_preview)} detail={`${compactNumber(readiness.records_requiring_review)} record(s) still need review.`} />
        <p className={styles.muted}>Standardized writes: {String(readiness.writes_to_standardized_gdb)}. Curated writes: {String(readiness.writes_to_curated_gdb)}.</p>
        <p className={styles.muted}>Missing dependencies: {(readiness.dependencies_still_missing ?? []).map(label).join(", ") || "None listed"}.</p>
      </Panel>
      <Panel title="Proposed Mappings" description="Mappings default to not approved until owner confirmation.">
        <div className={ws.tableWrap}>
          <table className={ws.table}>
            <thead><tr><th>Source</th><th>Field</th><th>Target</th><th>Confidence</th><th>Unit</th><th>Codes</th><th>Approved</th></tr></thead>
            <tbody>
              {mappings.map((row) => (
                <tr key={`${row.source_layer}-${row.source_field}-${row.target_field}`}>
                  <td>{label(row.source_layer)}</td>
                  <td className="technical">{row.source_field}</td>
                  <td className="technical">{row.target_field}</td>
                  <td>{label(row.confidence)}</td>
                  <td>{safeText(row.unit_conversion)}</td>
                  <td>{safeText(row.code_translation)}</td>
                  <td>{label(row.approved_to_standardize)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </section>
  );
}

function Select({ labelText, value, options, onChange }: { labelText: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <SelectControl ariaLabel={labelText} value={value} options={options} placeholder={`All ${labelText.toLowerCase()}`} onChange={onChange} />;
}

function SelectControl({ ariaLabel, value, options, onChange, placeholder = "Select" }: { ariaLabel?: string; value: string; options: string[]; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <select className={ws.select} value={value} onChange={(event) => onChange(event.target.value)} aria-label={ariaLabel}>
      <option value="">{placeholder}</option>
      {options.map((option) => <option value={option} key={option}>{label(option)}</option>)}
    </select>
  );
}
