"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import styles from "./page.module.css";

type Stage = { stage: string; state: string };
type Pipeline = { utility_system?: string; stages?: Stage[]; message?: string };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const sourceTypes = ["CAD", "Shapefile", "Geodatabase", "Spreadsheet", "PDF", "Service"];

function label(value = "") {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function TrustPipelinePage() {
  const [pipeline, setPipeline] = useState<Pipeline>({});
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadPipeline() {
      try {
        const response = await fetch(`${apiUrl}/api/trust-pipeline/wastewater`);
        if (!response.ok) throw new Error("Pipeline request failed.");
        setPipeline(await response.json());
      } catch {
        setError("Trust Pipeline API is unavailable.");
      }
    }
    loadPipeline();
  }, []);

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/" className={styles.backLink}>Utilities Platform</Link>
        <h1>Trust Pipeline</h1>
        <p>Reusable intake, QA, review, standardization, curation, and publishing gates for utility data.</p>
      </header>

      {error ? <div className={styles.warning}>{error}</div> : null}

      <section className={styles.pipeline}>
        {(pipeline.stages ?? []).map((stage, index) => (
          <article className={styles.stage} key={stage.stage}>
            <span>{index + 1}</span>
            <strong>{stage.stage}</strong>
            <p>{label(stage.state)}</p>
          </article>
        ))}
      </section>

      <section className={styles.panel}>
        <h2>Current Wastewater State</h2>
        <p>{pipeline.message ?? "Datasets cannot skip stages because each stage records authorization, lineage, QA evidence, human decisions, and controlled output readiness."}</p>
      </section>

      <section className={styles.panel}>
        <h2>Reusable Sources</h2>
        <div className={styles.sourceGrid}>
          {sourceTypes.map((source) => (
            <span key={source}>{source}</span>
          ))}
        </div>
        <p>Every source type follows the same gates before it can become standardized, curated, or exported.</p>
      </section>
    </main>
  );
}
