"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import styles from "../page.module.css";

type Summary = {
  sources_discovered: number;
  layer_count: number;
  by_utility_type: Record<string, number>;
  record_totals_by_system: Record<string, number>;
  recommended_staging_layers: number;
  unknown_layers: number;
};

type Layer = {
  dataset_id: string;
  utility_type: string;
  classification_confidence: string;
  asset_category: string;
  layer_name: string;
  geometry_type: string;
  record_count: string;
  spatial_reference: string;
  sensitivity_level: string;
  recommended_action: string;
};

type LayersResponse = {
  layers: Layer[];
  message: string;
};

type Recommendation = {
  allowlist: {
    dataset_id: string;
    source_layer_name: string;
    target_layer_name: string;
    utility_type: string;
    asset_category: string;
    approved_to_stage: string;
    reason: string;
  }[];
  message: string;
};

function sortedEntries(value: Record<string, number>) {
  return Object.entries(value).sort(([a], [b]) => a.localeCompare(b));
}

export default function InventoryPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [layers, setLayers] = useState<LayersResponse | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    async function loadInventory() {
      try {
        const [summaryResponse, layersResponse, recommendationResponse] = await Promise.all([
          fetch(`${apiUrl}/api/inventory/summary`),
          fetch(`${apiUrl}/api/inventory/layers`),
          fetch(`${apiUrl}/api/inventory/recommendation`),
        ]);
        if (!summaryResponse.ok || !layersResponse.ok || !recommendationResponse.ok) {
          throw new Error("Inventory API request failed.");
        }
        setSummary(await summaryResponse.json());
        setLayers(await layersResponse.json());
        setRecommendation(await recommendationResponse.json());
      } catch {
        setError("Inventory API is unavailable. Confirm the FastAPI backend is running.");
      }
    }

    loadInventory();
  }, []);

  const layerRows = layers?.layers ?? [];
  const unknownRows = layerRows.filter((row) => row.utility_type === "unknown" || row.classification_confidence === "low");

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/data-sources" className={styles.backLink}>
          Data Sources
        </Link>
        <h1>Utility Source Inventory</h1>
        <p>Safe inventory summaries and staging recommendations from external QA reports.</p>
      </header>

      {error ? <div className={styles.warning}>{error}</div> : null}

      <section className={styles.grid}>
        {[
          ["Discovered sources", summary?.sources_discovered ?? 0],
          ["Layer count", summary?.layer_count ?? 0],
          ["Recommended staging layers", summary?.recommended_staging_layers ?? 0],
          ["Unknown layers", summary?.unknown_layers ?? 0],
        ].map(([label, value]) => (
          <article className={styles.statusCard} key={label as string}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className={styles.section}>
        <h2>Utility systems found</h2>
        <div className={styles.workflow}>
          {sortedEntries(summary?.by_utility_type ?? {}).map(([system, count]) => (
            <div className={styles.workflowItem} key={system}>
              <strong>{system}</strong>
              <p>
                {count} layer(s), {summary?.record_totals_by_system[system] ?? 0} record(s)
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2>Inventory layers</h2>
        {layerRows.length === 0 ? (
          <p className={styles.empty}>{layers?.message ?? "No inventory report has been generated yet."}</p>
        ) : (
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>Layer</th>
                  <th>System</th>
                  <th>Asset category</th>
                  <th>Confidence</th>
                  <th>Geometry</th>
                  <th>Records</th>
                  <th>Spatial reference</th>
                  <th>Sensitivity</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {layerRows.map((row) => (
                  <tr key={row.dataset_id}>
                    <td>{row.layer_name}</td>
                    <td>{row.utility_type}</td>
                    <td>{row.asset_category}</td>
                    <td>{row.classification_confidence}</td>
                    <td>{row.geometry_type}</td>
                    <td>{row.record_count}</td>
                    <td>{row.spatial_reference}</td>
                    <td>{row.sensitivity_level}</td>
                    <td>{row.recommended_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h2>Recommended staging layers</h2>
        {recommendation?.allowlist.length ? (
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>Source layer</th>
                  <th>Target layer</th>
                  <th>System</th>
                  <th>Asset category</th>
                  <th>Approved</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {recommendation.allowlist.map((row) => (
                  <tr key={`${row.dataset_id}-${row.source_layer_name}`}>
                    <td>{row.source_layer_name}</td>
                    <td>{row.target_layer_name}</td>
                    <td>{row.utility_type}</td>
                    <td>{row.asset_category}</td>
                    <td>{row.approved_to_stage}</td>
                    <td>{row.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.empty}>{recommendation?.message ?? "No staging recommendation has been generated yet."}</p>
        )}
      </section>

      <section className={styles.section}>
        <h2>Unknown layers</h2>
        <p className={styles.empty}>
          {unknownRows.length
            ? unknownRows.map((row) => row.layer_name).join(", ")
            : "No unknown or low-confidence layers in the latest inventory."}
        </p>
      </section>
    </main>
  );
}
