"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import styles from "../page.module.css";

type Summary = {
  sources_discovered: number;
  layer_count: number;
  by_utility_system: Record<string, number>;
  by_network_group: Record<string, number>;
  by_asset_category: Record<string, number>;
  record_totals_by_system: Record<string, number>;
  recommended_staging_layers: number;
  unknown_layers: number;
  review_required_layers: number;
};

type Layer = {
  dataset_id: string;
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

type LayersResponse = {
  layers: Layer[];
  message: string;
};

type Recommendation = {
  allowlist: {
    dataset_id: string;
    source_layer_name: string;
    target_layer_name: string;
    utility_system: string;
    network_group: string;
    asset_category: string;
    asset_subcategory: string;
    approved_to_stage: string;
    reason: string;
  }[];
  message: string;
};

function sortedEntries(value: Record<string, number>) {
  return Object.entries(value).sort(([a], [b]) => a.localeCompare(b));
}

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
}

function label(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function groupLayers(rows: Layer[]) {
  const systems = new Map<string, Map<string, Map<string, Layer[]>>>();
  for (const row of rows) {
    const system = row.utility_system || "unknown";
    const network = row.network_group || "unknown";
    const category = row.asset_category || "unknown";
    if (!systems.has(system)) {
      systems.set(system, new Map());
    }
    const networks = systems.get(system)!;
    if (!networks.has(network)) {
      networks.set(network, new Map());
    }
    const categories = networks.get(network)!;
    categories.set(category, [...(categories.get(category) ?? []), row]);
  }
  return Array.from(systems.entries()).sort(([a], [b]) => a.localeCompare(b));
}

export default function InventoryPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [layers, setLayers] = useState<LayersResponse | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [systemFilter, setSystemFilter] = useState("");
  const [networkFilter, setNetworkFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
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
  const filteredRows = layerRows.filter((row) => {
    return (
      (!systemFilter || row.utility_system === systemFilter) &&
      (!networkFilter || row.network_group === networkFilter) &&
      (!categoryFilter || row.asset_category === categoryFilter)
    );
  });
  const systems = unique(layerRows.map((row) => row.utility_system));
  const networks = unique(layerRows.filter((row) => !systemFilter || row.utility_system === systemFilter).map((row) => row.network_group));
  const categories = unique(
    layerRows
      .filter((row) => (!systemFilter || row.utility_system === systemFilter) && (!networkFilter || row.network_group === networkFilter))
      .map((row) => row.asset_category),
  );
  const taxonomyGroups = useMemo(() => groupLayers(filteredRows), [filteredRows]);
  const reviewRows = filteredRows.filter(
    (row) => row.utility_system === "unknown" || row.utility_system === "review_required" || row.classification_confidence === "low",
  );

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
          ["Review required", summary?.review_required_layers ?? 0],
        ].map(([labelText, value]) => (
          <article className={styles.statusCard} key={labelText as string}>
            <span>{labelText}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className={styles.section}>
        <h2>Utility systems found</h2>
        <div className={styles.workflow}>
          {sortedEntries(summary?.by_utility_system ?? {}).map(([system, count]) => (
            <div className={styles.workflowItem} key={system}>
              <strong>{label(system)}</strong>
              <p>
                {count} layer(s), {summary?.record_totals_by_system[system] ?? 0} record(s)
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2>Taxonomy navigation</h2>
        <div className={styles.filters}>
          <select value={systemFilter} onChange={(event) => setSystemFilter(event.target.value)} aria-label="Filter by utility system">
            <option value="">All systems</option>
            {systems.map((system) => (
              <option value={system} key={system}>
                {label(system)}
              </option>
            ))}
          </select>
          <select value={networkFilter} onChange={(event) => setNetworkFilter(event.target.value)} aria-label="Filter by network group">
            <option value="">All network groups</option>
            {networks.map((network) => (
              <option value={network} key={network}>
                {label(network)}
              </option>
            ))}
          </select>
          <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} aria-label="Filter by asset category">
            <option value="">All asset categories</option>
            {categories.map((category) => (
              <option value={category} key={category}>
                {label(category)}
              </option>
            ))}
          </select>
        </div>
        {taxonomyGroups.length === 0 ? (
          <p className={styles.empty}>{layers?.message ?? "No inventory report has been generated yet."}</p>
        ) : (
          <div className={styles.taxonomyList}>
            {taxonomyGroups.map(([system, networkMap]) => (
              <div className={styles.taxonomySystem} key={system}>
                <h3>{label(system)}</h3>
                {Array.from(networkMap.entries()).map(([network, categoryMap]) => (
                  <div className={styles.taxonomyGroup} key={`${system}-${network}`}>
                    <h4>{label(network)}</h4>
                    {Array.from(categoryMap.entries()).map(([category, rows]) => (
                      <div className={styles.taxonomyCategory} key={`${system}-${network}-${category}`}>
                        <strong>{label(category)}</strong>
                        <p>
                          {unique(rows.map((row) => row.asset_subcategory)).map(label).join(", ")} - {rows.length} layer(s)
                        </p>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h2>Inventory layers</h2>
        {filteredRows.length === 0 ? (
          <p className={styles.empty}>{layers?.message ?? "No inventory report has been generated yet."}</p>
        ) : (
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>Layer</th>
                  <th>System</th>
                  <th>Network group</th>
                  <th>Asset category</th>
                  <th>Asset subcategory</th>
                  <th>Confidence</th>
                  <th>Geometry</th>
                  <th>Records</th>
                  <th>Spatial reference</th>
                  <th>Sensitivity</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.dataset_id || row.layer_name}>
                    <td>{row.layer_name}</td>
                    <td>{row.utility_system}</td>
                    <td>{row.network_group}</td>
                    <td>{row.asset_category}</td>
                    <td>{row.asset_subcategory}</td>
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
                  <th>Network group</th>
                  <th>Asset category</th>
                  <th>Asset subcategory</th>
                  <th>Approved</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {recommendation.allowlist.map((row) => (
                  <tr key={`${row.dataset_id}-${row.source_layer_name}`}>
                    <td>{row.source_layer_name}</td>
                    <td>{row.target_layer_name}</td>
                    <td>{row.utility_system}</td>
                    <td>{row.network_group}</td>
                    <td>{row.asset_category}</td>
                    <td>{row.asset_subcategory}</td>
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
        <h2>Review-required layers</h2>
        {reviewRows.length ? (
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>Layer</th>
                  <th>Likely classifications</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {reviewRows.map((row) => (
                  <tr key={`review-${row.dataset_id || row.layer_name}`}>
                    <td>{row.layer_name}</td>
                    <td>{row.likely_classifications}</td>
                    <td>{row.recommended_classification || row.recommended_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.empty}>No unknown, low-confidence, or review-required layers in the latest inventory.</p>
        )}
      </section>
    </main>
  );
}
