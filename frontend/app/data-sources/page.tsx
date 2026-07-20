"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import styles from "./page.module.css";

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
  record_count: string;
  sensitivity_level: string;
  current_stage: string;
  approved_for_analysis: string;
  approved_for_export: string;
  last_processed: string;
};

type CatalogResponse = {
  datasets: Dataset[];
  message: string;
};

const workflow = [
  ["Raw", "untouched source copy"],
  ["Staging", "temporary imported or converted data"],
  ["Standardized", "schema-normalized working data"],
  ["Curated", "approved analysis-ready data"],
  ["Export", "controlled output packages"],
];

function yesNo(value: boolean | undefined) {
  return value ? "Available" : "Not available";
}

export default function DataSourcesPage() {
  const [status, setStatus] = useState<StorageStatus | null>(null);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    async function loadStorage() {
      try {
        const [statusResponse, catalogResponse] = await Promise.all([
          fetch(`${apiUrl}/api/storage/status`),
          fetch(`${apiUrl}/api/storage/catalog`),
        ]);
        if (!statusResponse.ok || !catalogResponse.ok) {
          throw new Error("Storage API request failed.");
        }
        setStatus(await statusResponse.json());
        setCatalog(await catalogResponse.json());
      } catch {
        setError("Storage API is unavailable. Confirm the FastAPI backend is running.");
      }
    }

    loadStorage();
  }, []);

  const rows = catalog?.datasets ?? [];

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.backLink}>
          Utilities Platform
        </Link>
        <Link href="/data-sources/inventory" className={styles.backLink}>
          Inventory
        </Link>
        <h1>Data Sources</h1>
        <p>Local master storage, dataset catalog, and controlled export workflow.</p>
      </header>

      {error ? <div className={styles.warning}>{error}</div> : null}

      <section className={styles.grid} aria-label="Storage status">
        {[
          ["Master storage connected", status?.master_root_available],
          ["Raw storage", status?.raw_folder_available],
          ["Staging storage", status?.staging_folder_available],
          ["Standardized storage", status?.standardized_folder_available],
          ["Curated storage", status?.curated_folder_available],
          ["Export storage", status?.export_folder_available],
          ["Master geodatabase status", status?.geodatabases?.master === "exists"],
          ["Data catalog status", status?.catalog_available],
        ].map(([label, value]) => (
          <article className={styles.statusCard} key={label as string}>
            <span>{label}</span>
            <strong>{yesNo(value as boolean | undefined)}</strong>
          </article>
        ))}
      </section>

      <section className={styles.section}>
        <h2>Dataset catalog</h2>
        {rows.length === 0 ? (
          <p className={styles.empty}>{catalog?.message ?? "No utility datasets have been registered yet."}</p>
        ) : (
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>System</th>
                  <th>Network group</th>
                  <th>Asset category</th>
                  <th>Asset subcategory</th>
                  <th>Format</th>
                  <th>Geometry</th>
                  <th>Stage</th>
                  <th>Sensitivity</th>
                  <th>Record count</th>
                  <th>Analysis approval</th>
                  <th>Export approval</th>
                  <th>Last processed</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.dataset_id}>
                    <td>{row.dataset_name}</td>
                    <td>{row.utility_system}</td>
                    <td>{row.network_group}</td>
                    <td>{row.asset_category}</td>
                    <td>{row.asset_subcategory}</td>
                    <td>{row.source_format}</td>
                    <td>{row.geometry_type}</td>
                    <td>{row.current_stage}</td>
                    <td>{row.sensitivity_level}</td>
                    <td>{row.record_count}</td>
                    <td>{row.approved_for_analysis}</td>
                    <td>{row.approved_for_export}</td>
                    <td>{row.last_processed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h2>Storage workflow</h2>
        <div className={styles.workflow}>
          {workflow.map(([stage, description], index) => (
            <div className={styles.workflowItem} key={stage}>
              <strong>{stage}</strong>
              <p>{description}</p>
              {index < workflow.length - 1 ? <span aria-hidden="true">-&gt;</span> : null}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
