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

  const selectedItem = items.find((item) => item.item_id === selectedId) ?? items[0];
  const systems = useMemo(() => Array.from(new Set(items.map((item) => item.utility_system).filter(Boolean))).sort(), [items]);
  const stageRows = manifest?.stages ?? stages.map((stage) => ({ stage, label: label(stage), item_count: 0, description: "" }));
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
      {loading && !manifest ? <LoadingSkeleton /> : null}

      <section className={ws.grid12}>
        <div className={ws.span3}><MetricTile labelText="Raw sources" value={compactNumber(stageCount(stageRows, "raw"))} detail="Registered source packages." /></div>
        <div className={ws.span3}><MetricTile labelText="Staging items" value={compactNumber(stageCount(stageRows, "staging"))} detail="Working layers and candidates." /></div>
        <div className={ws.span3}><MetricTile labelText="Inventory layers" value={compactNumber(summary?.layer_count as string | number | undefined)} detail="From safe inventory reports." /></div>
        <div className={ws.span3}><MetricTile labelText="Review required" value={compactNumber(summary?.review_required_layers as string | number | undefined)} detail="Not replaced by zeros when offline." /></div>
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

        <StagePanel stage={activeStage} items={items} selectedId={selectedItem?.item_id ?? ""} onSelect={setSelectedId} />

        <Inspector item={selectedItem} status={status} runs={runs} />
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

function StagePanel({ stage, items, selectedId, onSelect }: { stage: PrimaryDataStage; items: DataSourceItem[]; selectedId: string; onSelect: (id: string) => void }) {
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
      {items.length ? (
        <div className={ws.tableWrap}>
          <table className={ws.table}>
            <thead><tr><th>Name</th><th>System</th><th>Network</th><th>Category</th><th>Format</th><th>Sensitivity</th><th>Records</th><th>Status</th><th>Next Action</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.item_id} className={selectedId === item.item_id ? styles.selectedRow : ""} onClick={() => onSelect(item.item_id)}>
                  <td><button className={styles.rowButton} onClick={() => onSelect(item.item_id)}>{item.name}</button></td>
                  <td>{label(item.utility_system)}</td>
                  <td>{label(item.network_group)}</td>
                  <td>{label(item.asset_category)}</td>
                  <td>{label(item.source_format)}</td>
                  <td><StatusBadge value={item.sensitivity_level} /></td>
                  <td>{compactNumber(String(item.record_count ?? ""))}</td>
                  <td><StageBadge value={item.status} /></td>
                  <td>{safeText(item.next_required_action)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <EmptyState title={`No ${label(stage)} items`} message={emptyMessages[stage]} />}
    </Panel>
  );
}

function Inspector({ item, status, runs }: { item?: DataSourceItem; status: StorageStatus | null; runs: RunsResponse["runs"] }) {
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
        <div><dt>Records</dt><dd>{compactNumber(String(item.record_count ?? ""))}</dd></div>
        <div><dt>Spatial reference</dt><dd>{safeText(item.coordinate_system)}</dd></div>
        <div><dt>Sensitivity</dt><dd><StatusBadge value={item.sensitivity_level} /></dd></div>
        <div><dt>Trust state</dt><dd>{Object.entries(trustState).map(([key, value]) => `${label(key)}: ${label(value)}`).join(" | ") || "Unavailable"}</dd></div>
        <div><dt>Lineage</dt><dd>{Array.isArray(item.lineage) ? item.lineage.join(" -> ") : "Unavailable"}</dd></div>
        <div><dt>Blockers</dt><dd>{Array.isArray(item.blockers) && item.blockers.length ? item.blockers.join("; ") : "None recorded"}</dd></div>
        <div><dt>Next required action</dt><dd>{safeText(item.next_required_action)}</dd></div>
        <div><dt>Storage</dt><dd>{isDemoMode ? "Portfolio demo snapshot" : status?.master_root_available ? "Local storage connected" : "Local storage unavailable"}</dd></div>
        <div><dt>Recent processing</dt><dd>{runs[0] ? `${safeText(runs[0].process_name)} (${shortDate(runs[0].completed_at)})` : "No safe run history available"}</dd></div>
      </dl>
    </Panel>
  );
}

function stageCount(rows: DataSourceStage[], stage: PrimaryDataStage) {
  return rows.find((row) => row.stage === stage)?.item_count ?? undefined;
}

function initialStage(): PrimaryDataStage {
  if (typeof window === "undefined") return "raw";
  const requested = new URLSearchParams(window.location.search).get("stage") as PrimaryDataStage | null;
  return requested && stages.includes(requested) ? requested : "raw";
}
