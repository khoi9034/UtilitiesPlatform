"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import type { DataSourceItem, DataSourceStage, InventorySummary, RunsResponse, StorageStatus, StageManifest, PrimaryDataStage } from "../../lib/data-provider/types";
import { compactNumber, label, safeText, shortDate } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./data-sources.module.css";

const stages: PrimaryDataStage[] = ["raw", "staging", "standardized", "curated", "export"];
const workflow = [
  ["Raw", "Untouched source copy"],
  ["Staging", "Temporary imported or converted data"],
  ["Standardized", "Schema-normalized working data"],
  ["Curated", "Approved analysis-ready data"],
  ["Export", "Controlled output packages"],
];
type RawView = "all_raw" | "uploaded_packages" | "registered_layers" | "needs_attention" | "duplicates";

export function DataSourcesWorkspace({ initialTab: _initialTab }: { initialTab?: string } = {}) {
  void _initialTab;
  const provider = getDataProvider();
  const [activeStage, setActiveStage] = useState<PrimaryDataStage>(() => initialStage());
  const [manifest, setManifest] = useState<StageManifest | null>(null);
  const [items, setItems] = useState<DataSourceItem[]>([]);
  const [status, setStatus] = useState<StorageStatus | null>(null);
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [runs, setRuns] = useState<RunsResponse["runs"]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [rawView, setRawView] = useState<RawView>("all_raw");
  const [showTestRecords, setShowTestRecords] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStage]);

  async function load() {
    setLoading(true);
    const controller = new AbortController();
    const results = await Promise.allSettled([
      provider.storageStatus(controller.signal),
      provider.getDataSourceStages(controller.signal),
      provider.getDataSourceItems(`/api/data-sources/items?stage=${activeStage}&limit=200`, controller.signal),
      provider.inventory(controller.signal),
      provider.processingHistory(controller.signal),
    ]);
    const nextErrors: string[] = [];
    if (results[0].status === "fulfilled") setStatus(results[0].value); else nextErrors.push("Storage status");
    if (results[1].status === "fulfilled") setManifest(results[1].value); else nextErrors.push("Stage manifest");
    if (results[2].status === "fulfilled") {
      const loadedItems = results[2].value.items;
      setItems(loadedItems);
      setSelectedId((current) => loadedItems.some((item) => item.item_id === current) ? current : loadedItems[0]?.item_id ?? "");
    } else {
      nextErrors.push("Stage items");
    }
    if (results[3].status === "fulfilled") setSummary(results[3].value); else nextErrors.push("Inventory summary");
    if (results[4].status === "fulfilled") setRuns(results[4].value.runs ?? []); else nextErrors.push("Processing history");
    setErrors(nextErrors);
    setLoading(false);
  }

  function selectStage(stage: PrimaryDataStage) {
    setActiveStage(stage);
    const url = new URL(window.location.href);
    url.searchParams.set("stage", stage);
    window.history.replaceState(null, "", url);
  }

  async function runInspection(item: DataSourceItem) {
    const submissionId = String(item.submission_id ?? "");
    if (!submissionId) return;
    setMessage("Source inspection started against the existing inspection copy.");
    try {
      const result = await provider.startSourceInspection(submissionId);
      setMessage(String(result.message ?? "Source inspection finished."));
      await load();
      setSelectedId(item.item_id);
    } catch {
      setMessage("Source inspection could not start. Raw registration remains intact.");
    }
  }

  const systems = useMemo(() => Array.from(new Set(items.map((item) => item.utility_system).filter(Boolean))).sort(), [items]);
  const stageRows = manifest?.stages ?? stages.map((stage) => ({ stage, label: label(stage), item_count: 0, description: "" }));
  const activity = manifest?.activity_counts ?? {};
  const visibleItems = useMemo(
    () => activeStage === "raw" ? filterRawItems(items, rawView, showTestRecords) : items,
    [activeStage, items, rawView, showTestRecords],
  );
  const visibleSelectedItem = visibleItems.find((item) => item.item_id === selectedId) ?? visibleItems[0];
  const allFailed = !loading && errors.length >= 5 && !manifest && !status && !summary;

  if (allFailed) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <OfflineState service="Data Sources API" />
      </div>
    );
  }

  return (
    <div className={ws.workspace}>
      <PageIntro />
      {errors.length ? <DegradedBanner errors={errors} onRetry={load} /> : null}
      {message ? <div className={styles.degradedBanner} role="status"><span>{message}</span></div> : null}
      {loading && !manifest ? <LoadingSkeleton /> : null}

      <section className={ws.grid12}>
        <div className={ws.span3}><MetricTile labelText="Raw registered sources" value={compactNumber(activity.raw_registered_sources ?? stageCount(stageRows, "raw"))} detail="Operational packages and registered layers." /></div>
        <div className={ws.span3}><MetricTile labelText="Uploaded packages" value={compactNumber(activity.uploaded_packages)} detail="Raw packages with an immutable source copy." /></div>
        <div className={ws.span3}><MetricTile labelText="Inspected layers" value={compactNumber(activity.inspected_layers)} detail="Child layers discovered in uploaded packages." /></div>
        <div className={ws.span3}><MetricTile labelText="Needs classification review" value={compactNumber(activity.needs_classification_review)} detail="Inspection candidates awaiting a person." /></div>
        <div className={ws.span3}><MetricTile labelText="Duplicate attempts" value={compactNumber(activity.duplicate_attempts)} detail="Audit attempts without another Raw copy." /></div>
        <div className={ws.span3}><MetricTile labelText="Inspection failures" value={compactNumber(activity.inspection_failures)} detail="Retryable blockers on operational sources." /></div>
        <div className={ws.span3}><MetricTile labelText="Test submissions" value={compactNumber(activity.test_submissions)} detail="Hidden from the default operational view." /></div>
        <div className={ws.span3}><MetricTile labelText="Staging items" value={compactNumber(activity.staging_items ?? stageCount(stageRows, "staging"))} detail="No uploaded child layer is staged automatically." /></div>
      </section>

      <Panel
        title="Storage Workflow"
        description="Primary utility data stages. Derived QA, review, and inventory artifacts stay separate."
        action={<Link className={`${ws.button} ${ws.buttonPrimary}`} href="/data-sources/upload">Upload Data</Link>}
      >
        <div className={styles.workflow}>
          {workflow.map(([stage, description]) => <div className={styles.workflowStep} key={stage}><strong>{stage}</strong><span className={styles.muted}>{description}</span></div>)}
        </div>
      </Panel>

      <div className={styles.tabBar} role="tablist" aria-label="Primary data stages">
        {stages.map((stage) => (
          <button className={styles.tabButton} role="tab" aria-selected={activeStage === stage} key={stage} onClick={() => selectStage(stage)}>
            {label(stage)} <span className={styles.muted}>{compactNumber(stageCount(stageRows, stage))}</span>
          </button>
        ))}
      </div>

      <section className={styles.layout}>
        <Panel title="Utility Tree" description="System > network group > asset category.">
          <div className={styles.tree}>
            <div className={styles.treeButton} data-selected="true">
              <strong>{label(activeStage)}</strong>
              <span className={styles.muted}>{compactNumber(items.length)} visible item(s)</span>
            </div>
            {systems.map((system) => (
              <div className={styles.treeButton} key={system}>
                <strong>{label(system)}</strong>
                <span className={styles.muted}>{compactNumber(items.filter((item) => item.utility_system === system).length)} item(s)</span>
              </div>
            ))}
          </div>
        </Panel>

        <StagePanel stage={activeStage} items={visibleItems} selectedId={visibleSelectedItem?.item_id ?? ""} onSelect={setSelectedId} rawView={rawView} showTestRecords={showTestRecords} onRawView={setRawView} onShowTestRecords={setShowTestRecords} onInspect={runInspection} />

        <Inspector item={visibleSelectedItem} status={status} runs={runs} onInspect={runInspection} />
      </section>
    </div>
  );
}

function PageIntro() {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>Utilities - Data Sources</span>
      <h1>Data Sources</h1>
      <p>Stage-aware source intake, catalog, lineage, and storage workspace. Local file paths stay behind the provider and API boundary.</p>
    </header>
  );
}

function DegradedBanner({ errors, onRetry }: { errors: string[]; onRetry: () => void }) {
  return (
    <div className={styles.degradedBanner} role="status">
      <strong>Degraded service</strong>
      <span>Unavailable: {errors.join(", ")}. Loaded resources remain visible.</span>
      <button className={ws.button} onClick={onRetry}>Retry</button>
    </div>
  );
}

function StagePanel({ stage, items, selectedId, onSelect, rawView, showTestRecords, onRawView, onShowTestRecords, onInspect }: { stage: PrimaryDataStage; items: DataSourceItem[]; selectedId: string; onSelect: (id: string) => void; rawView: RawView; showTestRecords: boolean; onRawView: (view: RawView) => void; onShowTestRecords: (show: boolean) => void; onInspect: (item: DataSourceItem) => void }) {
  const emptyMessages = {
    raw: "No utility source packages have been registered in Raw yet.",
    staging: "No staging layers are available for the selected filter.",
    standardized: "Awaiting data-owner confirmation and approved standardization mappings.",
    curated: "No approved curated utility layers exist.",
    export: "No controlled export packages are registered.",
  };
  return (
    <Panel
      title={`${label(stage)} Stage`}
      description={stage === "raw" ? "Immutable source packages and web-uploaded submissions." : "Safe stage metadata only."}
      action={stage === "raw" ? <Link className={ws.button} href="/data-sources/upload">Upload Data</Link> : null}
    >
      {stage === "raw" ? (
        <div className={ws.buttonRow} aria-label="Raw source filters">
          {(["all_raw", "uploaded_packages", "registered_layers", "needs_attention", "duplicates"] as RawView[]).map((view) => (
            <button className={ws.button} aria-pressed={rawView === view} key={view} onClick={() => onRawView(view)}>{label(view)}</button>
          ))}
          <label><input type="checkbox" checked={showTestRecords} onChange={(event) => onShowTestRecords(event.target.checked)} /> Show Test Records</label>
        </div>
      ) : null}
      {items.length ? (
        <div className={ws.tableWrap}>
          <table className={ws.table}>
            <thead><tr><th>Name</th><th>Type</th><th>System</th><th>Network</th><th>Category</th><th>Format</th><th>Sensitivity</th><th>Records</th><th>Status</th><th>Next Action</th><th>Action</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.item_id} className={selectedId === item.item_id ? styles.selectedRow : ""} onClick={() => onSelect(item.item_id)}>
                  <td><button className={styles.rowButton} onClick={() => onSelect(item.item_id)}>{item.name}</button></td>
                  <td><StatusBadge value={item.is_test_data ? "test_data" : String(item.item_type ?? "registered_layer")} /></td>
                  <td>{label(item.utility_system)}</td>
                  <td>{label(item.network_group)}</td>
                  <td>{label(item.asset_category)}</td>
                  <td>{label(item.source_format)}</td>
                  <td><StatusBadge value={item.sensitivity_level} /></td>
                  <td>{recordDisplay(item)}</td>
                  <td><StageBadge value={item.status} /></td>
                  <td>{safeText(item.next_required_action)}</td>
                  <td><ItemAction item={item} onInspect={onInspect} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <EmptyState title={`No ${label(stage)} items`} message={emptyMessages[stage]} />}
    </Panel>
  );
}

function Inspector({ item, status, runs, onInspect }: { item?: DataSourceItem; status: StorageStatus | null; runs: RunsResponse["runs"]; onInspect: (item: DataSourceItem) => void }) {
  if (!item) {
    return (
      <Panel title="Inspector" description="Safe metadata only.">
        <EmptyState title="No item selected" message="Select a stage item to inspect identity, trust state, lineage, blockers, and next action." />
      </Panel>
    );
  }
  const trustState = (item.trust_state ?? {}) as Record<string, string>;
  return (
    <Panel title="Inspector" description="Full local paths, source records, and sensitive notes are not exposed.">
      <dl className={styles.metadataList}>
        <div><dt>Name</dt><dd>{item.name}</dd></div>
        <div><dt>Utility hierarchy</dt><dd>{label(item.utility_system)} / {label(item.network_group)} / {label(item.asset_category)} / {label(item.asset_subcategory)}</dd></div>
        <div><dt>Stage</dt><dd><StageBadge value={item.stage} /></dd></div>
        <div><dt>Format</dt><dd>{label(item.source_format)}</dd></div>
        <div><dt>Geometry</dt><dd>{label(String(item.geometry_type ?? ""))}</dd></div>
        <div><dt>Type</dt><dd><StatusBadge value={item.is_test_data ? "test_data" : String(item.item_type ?? "registered_layer")} /></dd></div>
        <div><dt>Records</dt><dd>{recordDisplay(item)}</dd></div>
        {item.item_type === "source_package" ? <div><dt>Package contents</dt><dd>{compactNumber(item.child_layer_count)} child layers; {compactNumber(item.table_count)} tables</dd></div> : null}
        <div><dt>Spatial reference</dt><dd>{safeText(item.coordinate_system)}</dd></div>
        <div><dt>Sensitivity</dt><dd><StatusBadge value={item.sensitivity_level} /></dd></div>
        <div><dt>Trust state</dt><dd>{Object.entries(trustState).map(([key, value]) => `${label(key)}: ${label(value)}`).join(" | ") || "Unavailable"}</dd></div>
        <div><dt>Lineage</dt><dd>{Array.isArray(item.lineage) ? item.lineage.join(" -> ") : "Unavailable"}</dd></div>
        <div><dt>Blockers</dt><dd>{Array.isArray(item.blockers) && item.blockers.length ? item.blockers.join("; ") : "None recorded"}</dd></div>
        <div><dt>Next required action</dt><dd>{safeText(item.next_required_action)}</dd></div>
        <div><dt>Storage</dt><dd>{isDemoMode ? "Portfolio demo snapshot" : status?.master_root_available ? "Local storage connected" : "Local storage unavailable"}</dd></div>
        <div><dt>Recent processing</dt><dd>{runs[0] ? `${safeText(runs[0].process_name)} (${shortDate(runs[0].completed_at)})` : "No safe run history available"}</dd></div>
      </dl>
      <div className={ws.buttonRow}><ItemAction item={item} onInspect={onInspect} /><ItemEventsLink item={item} /></div>
    </Panel>
  );
}

function ItemAction({ item, onInspect }: { item: DataSourceItem; onInspect: (item: DataSourceItem) => void }) {
  const submissionId = String(item.submission_id ?? "");
  if (!submissionId) return <span className={styles.muted}>Select layer</span>;
  if (item.status === "duplicate_detected") {
    const prior = String(item.duplicate_of_submission_id ?? "");
    return <><Link className={ws.button} href={`/data-sources/submission?id=${encodeURIComponent(prior)}`}>View Prior Submission</Link><Link className={ws.button} href="/data-sources/upload?mode=new-version">Register as New Version</Link></>;
  }
  if (item.raw_registered === false) return <Link className={ws.button} href={`/data-sources/submission?id=${encodeURIComponent(submissionId)}&tab=Events`}>View Intake Event</Link>;
  if (item.status === "inspection_blocked") return <button className={ws.button} onClick={(event) => { event.stopPropagation(); void onInspect(item); }}>Retry Inspection</button>;
  if (item.status === "inspection_complete") return <Link className={ws.button} href={`/data-sources/submission?id=${encodeURIComponent(submissionId)}&tab=Layers`}>Review Child Layers</Link>;
  if (item.status === "inspection_running") return <span className={styles.muted}>Inspection running</span>;
  return <button className={ws.button} onClick={(event) => { event.stopPropagation(); void onInspect(item); }}>Run Source Inspection</button>;
}

function ItemEventsLink({ item }: { item: DataSourceItem }) {
  const submissionId = String(item.submission_id ?? "");
  return submissionId ? <Link className={ws.button} href={`/data-sources/submission?id=${encodeURIComponent(submissionId)}&tab=Events`}>View Events</Link> : null;
}

function stageCount(rows: DataSourceStage[], stage: PrimaryDataStage) {
  return rows.find((row) => row.stage === stage)?.item_count ?? undefined;
}

export function filterRawItems(items: DataSourceItem[], view: RawView, showTestRecords: boolean) {
  return items.filter((item) => {
    if (item.is_test_data && !showTestRecords) return false;
    const operational = item.raw_registered !== false && item.status !== "duplicate_detected" && item.item_type !== "intake_attempt";
    if (view === "uploaded_packages") return operational && item.item_type === "source_package";
    if (view === "registered_layers") return operational && item.item_type === "registered_layer";
    if (view === "needs_attention") return item.status === "inspection_blocked" || item.status === "duplicate_detected" || !operational;
    if (view === "duplicates") return item.status === "duplicate_detected";
    return operational;
  });
}

export function recordDisplay(item: DataSourceItem) {
  if (item.item_type === "source_package") return String(item.record_label || "Layer and record counts pending inspection");
  return compactNumber(String(item.record_count ?? ""));
}

function initialStage(): PrimaryDataStage {
  if (typeof window === "undefined") return "raw";
  const requested = new URLSearchParams(window.location.search).get("stage") as PrimaryDataStage | null;
  return requested && stages.includes(requested) ? requested : "raw";
}
