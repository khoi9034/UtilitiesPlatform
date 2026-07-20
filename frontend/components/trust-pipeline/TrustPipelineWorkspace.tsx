"use client";

import { useEffect, useState } from "react";
import type { CommandCenterResponse, MappingRow, Readiness } from "../../lib/api-types";
import { fetchJson } from "../../lib/api-client";
import { compactNumber, label, percent, safeText, shortDate } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./trust-pipeline.module.css";

type Stage = { stage: string; state: string };
type Pipeline = { utility_system?: string; stages?: Stage[]; message?: string };
type Runs = { runs: Record<string, string>[] };

const sourceFormats = [
  ["CAD", "architecture supported", "intake planned"],
  ["Shapefile", "architecture supported", "inventory available"],
  ["Geodatabase", "architecture supported", "staging available"],
  ["Spreadsheet", "architecture supported", "catalog available"],
  ["PDF", "architecture supported", "document intake planned"],
  ["Service", "architecture supported", "connection planned"],
];

const purposes: Record<string, string> = {
  Raw: "Authorized source copy remains unchanged outside Git.",
  Inventoried: "Safe metadata, taxonomy, and source readiness are recorded.",
  Staged: "Approved layers are converted into a temporary working geodatabase.",
  "QA Evaluated": "Rules generate candidate findings without repairing geometry.",
  "Human Review": "Reviewers separate defects, limitations, expected conditions, and deferred findings.",
  "Standardization Ready": "Confirmed mappings and approvals are ready for a future transform.",
  Standardized: "Schema-normalized utility data after approval.",
  Curated: "Analysis-ready data accepted for the master workspace.",
  Exported: "Controlled output packages created only when approved.",
};

export function TrustPipelineWorkspace() {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [command, setCommand] = useState<CommandCenterResponse | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [runs, setRuns] = useState<Record<string, string>[]>([]);
  const [selectedStage, setSelectedStage] = useState("Human Review");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchJson<Pipeline>("/api/trust-pipeline/wastewater", controller.signal),
      fetchJson<CommandCenterResponse>("/api/platform/command-center?utility_system=wastewater", controller.signal),
      fetchJson<Readiness>("/api/standardization/wastewater/readiness", controller.signal),
      fetchJson<{ mappings: MappingRow[] }>("/api/standardization/wastewater/mappings", controller.signal),
      fetchJson<Runs>("/api/data-health/wastewater/runs", controller.signal),
    ])
      .then(([pipelineData, commandData, readinessData, mappingData, runData]) => {
        setPipeline(pipelineData);
        setCommand(commandData);
        setReadiness(readinessData);
        setMappings(mappingData.mappings ?? []);
        setRuns(runData.runs ?? []);
        setSelectedStage(pipelineData.stages?.find((stage) => stage.state === "in_progress")?.stage ?? "Human Review");
      })
      .catch(() => setError("Trust Pipeline API is unavailable."));
    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <OfflineState service="Trust Pipeline API" />
      </div>
    );
  }

  if (!pipeline || !command || !readiness) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <LoadingSkeleton />
      </div>
    );
  }

  const selected = pipeline.stages?.find((stage) => stage.stage === selectedStage) ?? pipeline.stages?.[0];
  const approvedMappings = mappings.filter((row) => row.approved_to_standardize === "true").length;

  return (
    <div className={ws.workspace}>
      <PageIntro />
      <Panel title="Wastewater Trust Rail" description="Datasets cannot skip stages because authorization, lineage, QA evidence, and human approvals are recorded at different gates.">
        <div className={styles.stageRail} role="tablist" aria-label="Trust pipeline stages">
          {(pipeline.stages ?? []).map((stage, index) => (
            <button className={styles.stageButton} role="tab" aria-selected={selectedStage === stage.stage} key={stage.stage} onClick={() => setSelectedStage(stage.stage)}>
              <span className={styles.stageNumber}>{index + 1}</span>
              <strong>{stage.stage}</strong>
              <StageBadge value={stage.state} />
            </button>
          ))}
        </div>
      </Panel>

      <section className={styles.detailsGrid}>
        <Panel title={selected?.stage ?? "Stage"} description="Selected stage detail.">
          <MetricTile labelText="Status" value={label(selected?.state ?? "unknown")} detail={purposes[selected?.stage ?? ""] ?? "Stage purpose not configured."} />
          <p className={styles.muted}>Evidence or outputs: {stageEvidence(selected?.stage ?? "", command, readiness)}</p>
          <p className={styles.muted}>Next required action: {nextAction(selected?.stage ?? "", readiness)}</p>
        </Panel>
        <Panel title="Readiness Snapshot" description="Human review and standardization preparation.">
          <section className={ws.grid12}>
            <div className={ws.span6}><MetricTile labelText="Review sample" value={compactNumber(command.qa.review_sample)} detail="Generated review sample size." /></div>
            <div className={ws.span6}><MetricTile labelText="Approved mappings" value={`${approvedMappings}/${mappings.length}`} detail="Mappings default to false." /></div>
            <div className={ws.span6}><MetricTile labelText="Missing dependencies" value={compactNumber(readiness.dependencies_still_missing?.length)} detail="Context layers not onboarded." /></div>
            <div className={ws.span6}><MetricTile labelText="Endpoint match" value={compactNumber(command.network.unmatched_endpoints)} detail="Unmatched endpoints pending review." /></div>
          </section>
        </Panel>
      </section>

      <section className={ws.grid12}>
        <div className={ws.span4}>
          <Panel title="Supported Source Formats" description="Architecture support is separate from finished intake implementation.">
            <div className={styles.sourceChips}>
              {sourceFormats.map(([format, support, state]) => <StatusBadge value={`${format}: ${support} / ${state}`} key={format} />)}
            </div>
          </Panel>
        </div>
        <div className={ws.span4}>
          <Panel title="Dependencies" description="Missing wastewater layers can affect network interpretation.">
            <p className={styles.muted}>{command.dependencies.missing.map(label).join(", ") || "No missing dependencies listed."}</p>
          </Panel>
        </div>
        <div className={ws.span4}>
          <Panel title="Recent Audit Activity" description="Safe processing history only.">
            {runs.length ? (
              <div className={styles.activityList}>
                {runs.slice(0, 5).map((run) => <div className={styles.activityItem} key={run.run_id}><strong className="technical">{run.run_id}</strong><span>{label(run.status)}</span><span>{shortDate(run.completed_at)}</span></div>)}
              </div>
            ) : <EmptyState title="No audit rows" message="No processing history is available through the safe API." />}
          </Panel>
        </div>
      </section>
    </div>
  );
}

function PageIntro() {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>Utilities · Wastewater</span>
      <h1>Trust Pipeline</h1>
      <p>Lifecycle gates from raw approved source through human review, standardization readiness, curation, and controlled export.</p>
    </header>
  );
}

function stageEvidence(stage: string, command: CommandCenterResponse, readiness: Readiness) {
  if (stage === "QA Evaluated") return `${compactNumber(command.qa.total_findings)} QA finding(s), ${percent(command.network.endpoint_match_rate)} endpoint match.`;
  if (stage === "Human Review") return `${compactNumber(command.qa.open_reviews)} open review candidate(s), ${compactNumber(command.qa.review_sample)} sampled.`;
  if (stage === "Standardization Ready") return `Status: ${label(readiness.standardization_status ?? "pending")}.`;
  if (stage === "Staged") return `${compactNumber(command.assets.total)} staged wastewater asset(s).`;
  return "Evidence is retained through the storage catalog, reports, and processing history.";
}

function nextAction(stage: string, readiness: Readiness) {
  if (stage === "Human Review") return "Confirm priority findings and record dispositions without editing staged geometry.";
  if (stage === "Standardization Ready") return `Resolve blocked fields: ${(readiness.fields_blocked ?? []).map(label).join(", ") || "none listed"}.`;
  if (stage === "Curated" || stage === "Exported") return "Not available until standardization and curation are explicitly approved.";
  return safeText(purposes[stage], "Continue through the next controlled gate.");
}
