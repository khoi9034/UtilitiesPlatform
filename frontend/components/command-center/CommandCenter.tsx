"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CommandCenterResponse, IssuesResponse, MapData } from "../../lib/api-types";
import { fetchJson } from "../../lib/api-client";
import { compactNumber, label, percent, shortDate } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, SeverityBadge, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import { UtilityMap } from "../maps/UtilityMap";
import styles from "./command-center.module.css";

const emptyMap: MapData = { pipes: [], manholes: [], issues: [] };

export function CommandCenter() {
  const [command, setCommand] = useState<CommandCenterResponse | null>(null);
  const [mapData, setMapData] = useState<MapData>(emptyMap);
  const [queue, setQueue] = useState<IssuesResponse["items"]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchJson<CommandCenterResponse>("/api/platform/command-center?utility_system=wastewater", controller.signal),
      fetchJson<MapData>("/api/data-health/wastewater/map", controller.signal),
      fetchJson<IssuesResponse>("/api/review/wastewater/queue?limit=6", controller.signal),
    ])
      .then(([commandCenter, mapLayers, reviewQueue]) => {
        setCommand(commandCenter);
        setMapData(mapLayers);
        setQueue(reviewQueue.items);
      })
      .catch(() => setError("Backend API is unavailable. Start FastAPI to load live wastewater summaries."));
    return () => controller.abort();
  }, []);

  const reviewed = command?.qa.reviewed_findings ?? 0;
  const total = command?.qa.total_findings ?? null;
  const reviewProgress = total ? reviewed / total : null;
  const severityTotal = useMemo(() => Object.values(command?.qa.by_severity ?? {}).reduce((sum, value) => sum + Number(value || 0), 0), [command]);

  if (error) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <OfflineState service="Command Center API" />
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
      <PageIntro generatedAt={command.generated_at} />
      <section className={styles.kpiStrip} aria-label="Command Center metrics">
        <MetricTile labelText="Assets onboarded" value={compactNumber(command.assets.total)} detail="Staged wastewater gravity mains and manholes." />
        <MetricTile labelText="Open findings" value={compactNumber(command.qa.open_reviews)} detail={`${compactNumber(command.qa.high_priority)} high-priority review candidate(s).`} />
        <MetricTile labelText="Endpoint match" value={percent(command.network.endpoint_match_rate)} detail={`${compactNumber(command.network.unmatched_endpoints)} unmatched endpoint(s).`} />
        <MetricTile labelText="Review progress" value={reviewProgress === null ? "Unavailable" : percent(reviewProgress)} detail={`${compactNumber(reviewed)} of ${compactNumber(total)} finding(s) reviewed.`} />
        <MetricTile labelText="Current stage" value={command.pipeline.current_stage || "Unavailable"} detail="Wastewater trust lifecycle." />
      </section>

      <section className={styles.heroGrid}>
        <Panel title="Operational Map" description="Safe wastewater geometry, issue markers, and road context from existing API outputs.">
          <UtilityMap mapData={mapData} height={560} />
        </Panel>
        <Panel title="Trust Pipeline" description="Current lifecycle gate for the active utility context." action={<Link className={ws.button} href="/trust-pipeline">Open</Link>}>
          <div className={styles.stageRail}>
            {command.pipeline.stages.map((stage) => (
              <div className={styles.stage} key={stage.stage}>
                <i className={`${styles.stageDot} ${stage.state === "complete" ? styles.complete : stage.state === "in_progress" ? styles.active : ""}`} aria-hidden="true" />
                <strong>{stage.stage}</strong>
                <StageBadge value={stage.state} />
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className={ws.grid12}>
        <div className={ws.span8}>
          <Panel title="Priority Review Queue" description="Highest-value findings from the human review workflow." action={<Link className={ws.button} href="/data-health">Review</Link>}>
            {queue.length ? (
              <div className={styles.queue}>
                {queue.map((issue) => (
                  <Link className={styles.queueItem} href={`/data-health?issue=${encodeURIComponent(issue.issue_id)}`} key={issue.issue_id}>
                    <span className={styles.queueMeta}>
                      <SeverityBadge value={issue.severity} />
                      <StatusBadge value={issue.finding_class ?? "finding"} />
                      <span className="technical">{issue.rule_code}</span>
                    </span>
                    <strong>{issue.description}</strong>
                    <span className={styles.queueMeta}>{label(issue.source_layer)} · {issue.source_asset_id || issue.source_objectid || "No safe asset ID"}</span>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState title="No review items loaded" message="The queue endpoint returned no findings for the active utility context." />
            )}
          </Panel>
        </div>
        <div className={ws.span4}>
          <Panel title="Network Health" description="Proximity connectivity, not authoritative topology.">
            <div className={ws.grid12}>
              <div className={ws.span6}><MetricTile labelText="Components" value={compactNumber(command.network.connected_components)} detail="Connected component groups." /></div>
              <div className={ws.span6}><MetricTile labelText="Isolated pipes" value={compactNumber(command.network.isolated_pipes)} detail="Needs review, not automatic defect." /></div>
              <div className={ws.span6}><MetricTile labelText="Isolated manholes" value={compactNumber(command.network.isolated_manholes)} detail="May reflect missing layers." /></div>
              <div className={ws.span6}><MetricTile labelText="Dependencies" value={`${command.dependencies.available}/${command.dependencies.total}`} detail="Available context layers." /></div>
            </div>
          </Panel>
        </div>
      </section>

      <section className={ws.grid12}>
        <div className={ws.span4}>
          <Panel title="Issue Distribution" description="Current QA finding mix by severity.">
            <div className={styles.distribution}>
              {Object.entries(command.qa.by_severity).map(([severity, count]) => (
                <div className={styles.barRow} key={severity}>
                  <span>{label(severity)}</span>
                  <div className={styles.barTrack}>
                    <div className={styles.barFill} style={{ "--bar-width": `${severityTotal ? (Number(count) / severityTotal) * 100 : 0}%`, "--bar-color": severityColor(severity) } as React.CSSProperties} />
                  </div>
                  <strong>{compactNumber(count)}</strong>
                </div>
              ))}
            </div>
          </Panel>
        </div>
        <div className={ws.span4}>
          <Panel title="Dependency Readiness" description="Missing layers can explain candidate network breaks.">
            <p className={ws.muted}>{command.dependencies.missing.length ? `${command.dependencies.missing.map(label).join(", ")} are not onboarded.` : "All configured dependencies are available."}</p>
          </Panel>
        </div>
        <div className={ws.span4}>
          <Panel title="Recent Processing" description="Safe run metadata only.">
            <div className={styles.queue}>
              {command.recent_runs.length ? command.recent_runs.map((run) => (
                <div className={styles.activity} key={run.run_id}>
                  <strong className="technical">{run.run_id}</strong>
                  <span>{label(run.status ?? "")}</span>
                  <span>{shortDate(run.completed_at)}</span>
                </div>
              )) : <EmptyState title="No runs" message="No processing history is available through the safe API." />}
            </div>
          </Panel>
        </div>
      </section>

      <Panel title="Module Status" description="Every navigation target has a real route; planned modules stay honest about readiness.">
        <div className={styles.moduleGrid}>
          {command.module_status.map((module) => (
            <Link className={styles.moduleLink} href={module.href} key={module.href}>
              <strong>{module.label}</strong>
              <StatusBadge value={module.status} />
            </Link>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function PageIntro({ generatedAt }: { generatedAt?: string }) {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>Utilities · Wastewater</span>
      <h1>Command Center</h1>
      <p>Utility data trust, network condition, and operational review in one workspace. Latest aggregate refresh: {shortDate(generatedAt)}.</p>
    </header>
  );
}

function severityColor(severity: string) {
  if (severity === "high") return "var(--color-danger)";
  if (severity === "medium") return "var(--color-warning)";
  if (severity === "low") return "var(--color-info)";
  return "var(--color-accent)";
}
