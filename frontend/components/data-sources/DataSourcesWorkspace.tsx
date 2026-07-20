"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../../lib/api-client";
import { compactNumber, label, safeText, shortDate } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./data-sources.module.css";

type Tab = "Catalog" | "Inventory" | "Storage" | "Processing History";
type StorageStatus = {
  master_root_available: boolean;
  raw_folder_available: boolean;
  staging_folder_available: boolean;
  standardized_folder_available: boolean;
  curated_folder_available: boolean;
  export_folder_available: boolean;
  catalog_available: boolean;
  geodatabases: Record<string, string>;
};
type Dataset = {
  dataset_id: string;
  dataset_name: string;
  utility_system: string;
  network_group: string;
  asset_category: string;
  asset_subcategory: string;
  source_format: string;
  geometry_type: string;
  coordinate_system: string;
  record_count: string;
  sensitivity_level: string;
  current_stage: string;
  approved_for_analysis: string;
  approved_for_export: string;
  approved_for_public_use: string;
  last_processed: string;
};
type CatalogResponse = { datasets: Dataset[]; message: string };
type InventorySummary = {
  sources_discovered: number;
  layer_count: number;
  by_utility_system: Record<string, number>;
  by_network_group: Record<string, number>;
  by_asset_category: Record<string, number>;
  record_totals_by_system: Record<string, number>;
  recommended_staging_layers: number;
  review_required_layers: number;
};
type Layer = {
  dataset_id: string;
  source_name: string;
  source_format: string;
  utility_system: string;
  network_group: string;
  asset_category: string;
  asset_subcategory: string;
  classification_confidence: string;
  likely_classifications: string;
  recommended_classification: string;
  layer_name: string;
  geometry_type: string;
  record_count: string;
  spatial_reference: string;
  sensitivity_level: string;
  recommended_action: string;
};
type Recommendation = { allowlist: { source_layer_name: string; target_layer_name: string; utility_system: string; network_group: string; asset_category: string; asset_subcategory: string; approved_to_stage: string; reason: string }[]; message: string };
type Runs = { runs: Record<string, string>[] };

const tabs: Tab[] = ["Catalog", "Inventory", "Storage", "Processing History"];
const workflow = [
  ["Raw", "Untouched source copy"],
  ["Staging", "Temporary imported or converted data"],
  ["Standardized", "Schema-normalized working data"],
  ["Curated", "Approved analysis-ready data"],
  ["Export", "Controlled output packages"],
];

export function DataSourcesWorkspace({ initialTab = "Catalog" }: { initialTab?: Tab }) {
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [status, setStatus] = useState<StorageStatus | null>(null);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [layers, setLayers] = useState<Layer[]>([]);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [runs, setRuns] = useState<Record<string, string>[]>([]);
  const [selectedSystem, setSelectedSystem] = useState("wastewater");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchJson<StorageStatus>("/api/storage/status", controller.signal),
      fetchJson<CatalogResponse>("/api/storage/catalog", controller.signal),
      fetchJson<InventorySummary>("/api/inventory/summary", controller.signal),
      fetchJson<{ layers: Layer[] }>("/api/inventory/layers", controller.signal),
      fetchJson<Recommendation>("/api/inventory/recommendation", controller.signal),
      fetchJson<Runs>("/api/data-health/wastewater/runs", controller.signal),
    ])
      .then(([storageStatus, catalogRows, inventorySummary, inventoryLayers, stagingRecommendation, runRows]) => {
        setStatus(storageStatus);
        setCatalog(catalogRows);
        setSummary(inventorySummary);
        setLayers(inventoryLayers.layers ?? []);
        setRecommendation(stagingRecommendation);
        setRuns(runRows.runs ?? []);
      })
      .catch(() => setError("Storage or inventory API is unavailable. Start FastAPI to load safe catalog data."));
    return () => controller.abort();
  }, []);

  const systems = useMemo(() => Array.from(new Set([...layers.map((row) => row.utility_system), ...(catalog?.datasets ?? []).map((row) => row.utility_system)].filter(Boolean))).sort(), [layers, catalog]);
  const visibleLayers = layers.filter((row) => !selectedSystem || row.utility_system === selectedSystem);
  const visibleCatalog = (catalog?.datasets ?? []).filter((row) => !selectedSystem || row.utility_system === selectedSystem);
  const selectedLayer = visibleLayers[0];

  if (error) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <OfflineState service="Data Sources API" />
      </div>
    );
  }

  if (!status || !summary) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <div className={ws.workspace}>
      <PageIntro />
      <section className={ws.grid12}>
        <div className={ws.span3}><MetricTile labelText="Sources discovered" value={compactNumber(summary.sources_discovered)} detail="From safe inventory reports." /></div>
        <div className={ws.span3}><MetricTile labelText="Layer count" value={compactNumber(summary.layer_count)} detail="Inventory layers only." /></div>
        <div className={ws.span3}><MetricTile labelText="Recommended staging" value={compactNumber(summary.recommended_staging_layers)} detail="Allowlist-driven candidates." /></div>
        <div className={ws.span3}><MetricTile labelText="Review required" value={compactNumber(summary.review_required_layers)} detail="Low-confidence or unknown taxonomy." /></div>
      </section>

      <div className={styles.tabBar} role="tablist" aria-label="Data source workspace">
        {tabs.map((tab) => <button className={styles.tabButton} role="tab" aria-selected={activeTab === tab} key={tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}
      </div>

      <section className={styles.layout}>
        <Panel title="Utility Tree" description="System > network group > asset category.">
          <div className={styles.tree}>
            <button className={styles.treeButton} aria-pressed={!selectedSystem} onClick={() => setSelectedSystem("")}>
              <strong>All utilities</strong>
              <span className={styles.muted}>{compactNumber(layers.length)} layer(s)</span>
            </button>
            {systems.map((system) => (
              <button className={styles.treeButton} aria-pressed={selectedSystem === system} key={system} onClick={() => setSelectedSystem(system)}>
                <strong>{label(system)}</strong>
                <span className={styles.muted}>{compactNumber(summary.record_totals_by_system?.[system])} record(s)</span>
              </button>
            ))}
          </div>
        </Panel>

        <div className={ws.workspace}>
          {activeTab === "Catalog" ? <CatalogTable rows={visibleCatalog} message={catalog?.message} /> : null}
          {activeTab === "Inventory" ? <InventoryTable rows={visibleLayers} recommendation={recommendation} /> : null}
          {activeTab === "Storage" ? <StorageStatus status={status} /> : null}
          {activeTab === "Processing History" ? <ProcessingHistory runs={runs} /> : null}
        </div>

        <Panel title="Inspector" description="Safe metadata only.">
          {selectedLayer ? (
            <dl className={styles.metadataList}>
              <div><dt>Layer</dt><dd>{selectedLayer.layer_name}</dd></div>
              <div><dt>Source identifier</dt><dd>{safeText(selectedLayer.source_name)}</dd></div>
              <div><dt>Taxonomy</dt><dd>{label(selectedLayer.utility_system)} / {label(selectedLayer.network_group)} / {label(selectedLayer.asset_category)}</dd></div>
              <div><dt>Geometry</dt><dd>{label(selectedLayer.geometry_type)}</dd></div>
              <div><dt>Records</dt><dd>{compactNumber(selectedLayer.record_count)}</dd></div>
              <div><dt>Spatial reference</dt><dd>{selectedLayer.spatial_reference}</dd></div>
              <div><dt>Sensitivity</dt><dd><StatusBadge value={selectedLayer.sensitivity_level} /></dd></div>
              <div><dt>Recommended next action</dt><dd>{selectedLayer.recommended_action}</dd></div>
            </dl>
          ) : (
            <EmptyState title="No layer selected" message="No inventory layer is available for the selected system." />
          )}
        </Panel>
      </section>
    </div>
  );
}

function PageIntro() {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>Utilities · Data Sources</span>
      <h1>Data Sources</h1>
      <p>Professional catalog, inventory, storage, and lineage workspace. Local file paths stay behind the API boundary.</p>
    </header>
  );
}

function CatalogTable({ rows, message }: { rows: Dataset[]; message?: string }) {
  return (
    <Panel title="Dataset Catalog" description="Registered datasets with safe catalog fields.">
      {rows.length ? (
        <div className={ws.tableWrap}>
          <table className={ws.table}>
            <thead><tr><th>Dataset</th><th>System</th><th>Network</th><th>Category</th><th>Subcategory</th><th>Format</th><th>Geometry</th><th>Stage</th><th>Sensitivity</th><th>Records</th><th>Analysis</th><th>Export</th><th>Last processed</th></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.dataset_id}>
                  <td>{row.dataset_name}</td>
                  <td>{label(row.utility_system)}</td>
                  <td>{label(row.network_group)}</td>
                  <td>{label(row.asset_category)}</td>
                  <td>{label(row.asset_subcategory)}</td>
                  <td>{label(row.source_format)}</td>
                  <td>{label(row.geometry_type)}</td>
                  <td><StageBadge value={row.current_stage} /></td>
                  <td><StatusBadge value={row.sensitivity_level} /></td>
                  <td>{compactNumber(row.record_count)}</td>
                  <td>{label(row.approved_for_analysis)}</td>
                  <td>{label(row.approved_for_export)}</td>
                  <td>{shortDate(row.last_processed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <EmptyState title="No catalog records" message={message ?? "No utility datasets have been registered yet."} />}
    </Panel>
  );
}

function InventoryTable({ rows, recommendation }: { rows: Layer[]; recommendation: Recommendation | null }) {
  return (
    <>
      <Panel title="Layer Inventory" description="Taxonomy and staging recommendations from the inventory system.">
        {rows.length ? (
          <div className={ws.tableWrap}>
            <table className={ws.table}>
              <thead><tr><th>Layer</th><th>System</th><th>Network</th><th>Category</th><th>Subcategory</th><th>Confidence</th><th>Geometry</th><th>Records</th><th>Spatial Reference</th><th>Sensitivity</th><th>Recommendation</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.dataset_id || row.layer_name}>
                    <td>{row.layer_name}</td>
                    <td>{label(row.utility_system)}</td>
                    <td>{label(row.network_group)}</td>
                    <td>{label(row.asset_category)}</td>
                    <td>{label(row.asset_subcategory)}</td>
                    <td>{label(row.classification_confidence)}</td>
                    <td>{label(row.geometry_type)}</td>
                    <td>{compactNumber(row.record_count)}</td>
                    <td>{row.spatial_reference}</td>
                    <td><StatusBadge value={row.sensitivity_level} /></td>
                    <td>{row.recommended_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <EmptyState title="No inventory rows" message="No inventory report has been generated for the selected utility system." />}
      </Panel>
      <Panel title="Recommended Staging" description="Allowlist rows only; no source data is moved by the frontend.">
        {recommendation?.allowlist.length ? (
          <div className={ws.tableWrap}>
            <table className={ws.table}>
              <thead><tr><th>Source layer</th><th>Target layer</th><th>System</th><th>Network</th><th>Category</th><th>Subcategory</th><th>Approved</th><th>Reason</th></tr></thead>
              <tbody>{recommendation.allowlist.map((row) => <tr key={row.source_layer_name}><td>{row.source_layer_name}</td><td>{row.target_layer_name}</td><td>{label(row.utility_system)}</td><td>{label(row.network_group)}</td><td>{label(row.asset_category)}</td><td>{label(row.asset_subcategory)}</td><td>{label(row.approved_to_stage)}</td><td>{row.reason}</td></tr>)}</tbody>
            </table>
          </div>
        ) : <EmptyState title="No staging recommendation" message={recommendation?.message ?? "No staging recommendation has been generated yet."} />}
      </Panel>
    </>
  );
}

function StorageStatus({ status }: { status: StorageStatus }) {
  return (
    <Panel title="Storage Workflow" description="The master data root remains outside Git.">
      <div className={styles.workflow}>
        {workflow.map(([stage, description]) => <div className={styles.workflowStep} key={stage}><strong>{stage}</strong><span className={styles.muted}>{description}</span></div>)}
      </div>
      <section className={ws.grid12}>
        {[
          ["Master storage", status.master_root_available],
          ["Raw storage", status.raw_folder_available],
          ["Staging storage", status.staging_folder_available],
          ["Standardized storage", status.standardized_folder_available],
          ["Curated storage", status.curated_folder_available],
          ["Export storage", status.export_folder_available],
          ["Catalog", status.catalog_available],
          ["Master geodatabase", status.geodatabases?.master === "exists"],
        ].map(([name, available]) => (
          <div className={ws.span3} key={String(name)}>
            <MetricTile labelText={String(name)} value={available ? "Available" : "Pending"} detail="Verified by storage status API." />
          </div>
        ))}
      </section>
    </Panel>
  );
}

function ProcessingHistory({ runs }: { runs: Record<string, string>[] }) {
  return (
    <Panel title="Processing History" description="Safe run metadata with internal paths stripped.">
      {runs.length ? (
        <div className={ws.tableWrap}>
          <table className={ws.table}>
            <thead><tr><th>Run</th><th>Process</th><th>Input layer</th><th>Output workspace</th><th>Status</th><th>Records read</th><th>Completed</th></tr></thead>
            <tbody>{runs.map((run) => <tr key={run.run_id}><td className="technical">{run.run_id}</td><td>{run.process_name}</td><td>{run.input_layer}</td><td>{run.output_workspace}</td><td><StageBadge value={run.status} /></td><td>{compactNumber(run.records_read)}</td><td>{shortDate(run.completed_at)}</td></tr>)}</tbody>
          </table>
        </div>
      ) : <EmptyState title="No run history" message="No processing history rows are available through the safe API." />}
    </Panel>
  );
}
