"use client";

import { useEffect, useMemo, useState } from "react";
import type { CommandCenterResponse, MapData, MapFeature } from "../../lib/api-types";
import { fetchJson } from "../../lib/api-client";
import { compactNumber, label, safeText } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import { UtilityMap } from "../maps/UtilityMap";
import styles from "./asset-inventory.module.css";

const emptyMap: MapData = { pipes: [], manholes: [], issues: [] };

export function AssetInventoryWorkspace() {
  const [command, setCommand] = useState<CommandCenterResponse | null>(null);
  const [mapData, setMapData] = useState<MapData>(emptyMap);
  const [assetType, setAssetType] = useState("");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"map_list" | "list" | "map">("map_list");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchJson<CommandCenterResponse>("/api/platform/command-center?utility_system=wastewater", controller.signal),
      fetchJson<MapData>("/api/data-health/wastewater/map", controller.signal),
    ])
      .then(([commandData, mapLayers]) => {
        setCommand(commandData);
        setMapData(mapLayers);
      })
      .catch(() => setError("Asset inventory API is unavailable."));
    return () => controller.abort();
  }, []);

  const assets = useMemo(() => [
    ...mapData.pipes.map((feature) => ({ ...feature, type: "gravity_main" })),
    ...mapData.manholes.map((feature) => ({ ...feature, type: "manhole" })),
  ], [mapData]);
  const filtered = assets.filter((asset) => (!assetType || asset.type === assetType) && (!search || safeAsset(asset).toLowerCase().includes(search.toLowerCase())));

  if (error) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <OfflineState service="Asset Inventory API" />
      </div>
    );
  }

  if (!command) {
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
        <div className={ws.span3}><MetricTile labelText="Assets" value={compactNumber(command.assets.total)} detail="Safe wastewater map features." /></div>
        <div className={ws.span3}><MetricTile labelText="Gravity network" value={compactNumber(command.assets.by_network_group.gravity_network)} detail="Gravity main count." /></div>
        <div className={ws.span3}><MetricTile labelText="Structures" value={compactNumber(command.assets.by_network_group.structures)} detail="Manhole count." /></div>
        <div className={ws.span3}><MetricTile labelText="QA findings" value={compactNumber(command.qa.total_findings)} detail="Review-ready candidates." /></div>
      </section>
      <Panel title="Asset Filter" description="Safe ID, system, and asset-type filtering.">
        <div className={styles.toolbar}>
          <select className={ws.select} value="wastewater" aria-label="Utility system" disabled><option>Wastewater</option></select>
          <select className={ws.select} value={assetType} onChange={(event) => setAssetType(event.target.value)} aria-label="Asset type">
            <option value="">All asset types</option>
            <option value="gravity_main">Gravity mains</option>
            <option value="manhole">Manholes</option>
          </select>
          <input className={ws.input} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Safe asset ID search" />
          <select className={`${ws.select} ${styles.viewToggle}`} value={view} onChange={(event) => setView(event.target.value as typeof view)} aria-label="View mode">
            <option value="map_list">Map + list</option>
            <option value="list">List only</option>
            <option value="map">Map only</option>
          </select>
        </div>
      </Panel>
      <section className={styles.layout}>
        {view !== "list" ? <Panel title="Asset Map" description="Existing safe geometry only."><UtilityMap mapData={mapData} showOpenLink={false} /></Panel> : null}
        {view !== "map" ? <AssetTable assets={filtered} /> : null}
      </section>
    </div>
  );
}

function PageIntro() {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>Utilities · Inventory</span>
      <h1>Asset Inventory</h1>
      <p>Map and list view of onboarded wastewater assets using safe API fields. Source-only attributes and internal paths stay hidden.</p>
    </header>
  );
}

function AssetTable({ assets }: { assets: (MapFeature & { type: string })[] }) {
  return (
    <Panel title="Asset List" description={`${compactNumber(assets.length)} safe asset row(s).`}>
      {assets.length ? (
        <div className={ws.tableWrap}>
          <table className={ws.table}>
            <thead><tr><th>Safe asset ID</th><th>Type</th><th>Object ID</th><th>Layer</th><th>Geometry</th><th>QA context</th></tr></thead>
            <tbody>
              {assets.slice(0, 500).map((asset, index) => (
                <tr key={`${asset.type}-${asset.objectid}-${index}`}>
                  <td className={styles.assetId}>{safeAsset(asset)}</td>
                  <td>{label(asset.type)}</td>
                  <td className={styles.assetId}>{safeText(asset.objectid)}</td>
                  <td>{label(asset.source_layer ?? (asset.type === "manhole" ? "wastewater_manhole" : "wastewater_gravity_main"))}</td>
                  <td>{label(asset.geometry.type)}</td>
                  <td><StatusBadge value={asset.issue_id ? "has_issue" : "asset"} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <EmptyState title="No assets match" message="Adjust the asset type or search filter." />}
    </Panel>
  );
}

function safeAsset(asset: MapFeature) {
  return safeText(asset.asset_id || asset.source_objectid || asset.objectid, "No safe asset ID");
}
