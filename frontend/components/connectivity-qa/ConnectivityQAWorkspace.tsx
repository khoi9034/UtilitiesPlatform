"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  ConnectivityCalibrationRun,
  ConnectivityFinding,
  ConnectivityIssueGroup,
  ConnectivityIssueGroupDetail,
  ConnectivityRule,
  ConnectivityRun,
} from "../../lib/connectivity-qa";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import { label } from "../../lib/formatters";
import type { UtilityVerticalConfig } from "../../lib/utility-verticals";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, SeverityBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./connectivity-qa.module.css";

type FindingsResponse = {
  items: ConnectivityFinding[];
  pagination: { total: number; limit: number; offset: number; has_more: boolean };
  qa_run_id?: string;
};
type RuleResponse = { items: ConnectivityRule[]; profile_name: string; model_version: string; rule_version: string };
type RunResponse = { items: ConnectivityRun[]; pagination: { total: number } };
type CalibrationRunResponse = { items: ConnectivityCalibrationRun[]; pagination: { total: number } };
type GroupResponse = {
  items: ConnectivityIssueGroup[];
  pagination: { total: number; limit: number; offset: number; has_more: boolean };
  calibration_run_id?: string;
};
type GroupField = "severity" | "rule_code" | "asset_id" | "relationship_id" | "review_status" | "blocking";
type Section = "groups" | "findings" | "passed" | "history" | "rules";

export function ConnectivityQAWorkspace({
  config,
}: {
  config: UtilityVerticalConfig;
}) {
  const provider = getDataProvider();
  const vertical = config.canonicalValue;
  const [run, setRun] = useState<ConnectivityRun | null>(null);
  const [rules, setRules] = useState<ConnectivityRule[]>([]);
  const [findings, setFindings] = useState<ConnectivityFinding[]>([]);
  const [runs, setRuns] = useState<ConnectivityRun[]>([]);
  const [calibration, setCalibration] = useState<ConnectivityCalibrationRun | null>(null);
  const [calibrationRuns, setCalibrationRuns] = useState<ConnectivityCalibrationRun[]>([]);
  const [issueGroups, setIssueGroups] = useState<ConnectivityIssueGroup[]>([]);
  const [groupDetail, setGroupDetail] = useState<ConnectivityIssueGroupDetail | null>(null);
  const [detail, setDetail] = useState<(ConnectivityFinding & { rule?: ConnectivityRule; graph_context?: { assets?: Array<Record<string, unknown>>; relationship?: Record<string, unknown> | null }; history?: Array<Record<string, unknown>> }) | null>(null);
  const [section, setSection] = useState<Section>("groups");
  const [filters, setFilters] = useState({ severity: "", blocking: "", review_status: "", rule_code: "", asset_class: "", group: "severity" as GroupField });
  const [groupFilters, setGroupFilters] = useState({ issue_family: "", display_priority: "", trace_impact: "", review_status: "" });
  const [page, setPage] = useState(0);
  const [reviewer, setReviewer] = useState(isDemoMode ? "Demo Reviewer" : "Local Reviewer");
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [status, ruleData, findingData, runData, calibrationStatus, groupData, calibrationRunData] = await Promise.all([
      provider.get<ConnectivityRun | { status: string; message: string }>(`/api/connectivity-qa/${vertical}/status`),
      provider.get<RuleResponse>(`/api/connectivity-qa/rules/${vertical}`),
      provider.get<FindingsResponse>(`/api/connectivity-qa/${vertical}/findings?limit=500`),
      provider.get<RunResponse>(`/api/connectivity-qa/${vertical}/runs?limit=50`),
      provider.get<ConnectivityCalibrationRun | { status: string; message: string }>(`/api/connectivity-qa/${vertical}/calibration/status`),
      provider.get<GroupResponse>(`/api/connectivity-qa/${vertical}/issue-groups?limit=500`),
      provider.get<CalibrationRunResponse>(`/api/connectivity-qa/${vertical}/calibration/runs?limit=50`),
    ]);
    setRun("qa_run_id" in status ? status : null);
    setRules(ruleData.items);
    setFindings(findingData.items);
    setRuns(runData.items);
    setCalibration("calibration_run_id" in calibrationStatus ? calibrationStatus : null);
    setIssueGroups(groupData.items);
    setCalibrationRuns(calibrationRunData.items);
    setLoading(false);
  }, [provider, vertical]);

  useEffect(() => {
    Promise.resolve().then(load).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Connectivity QA service unavailable.");
      setLoading(false);
    });
  }, [load]);

  const filtered = useMemo(() => findings.filter((finding) =>
    (!filters.severity || finding.severity === filters.severity)
    && (!filters.blocking || finding.blocking === (filters.blocking === "true"))
    && (!filters.review_status || finding.review_status === filters.review_status)
    && (!filters.rule_code || finding.rule_code === filters.rule_code)
    && (!filters.asset_class || finding.asset_class === filters.asset_class)
  ), [filters, findings]);
  const pageSize = 25;
  const visible = filtered.slice(page * pageSize, page * pageSize + pageSize);
  const groups = useMemo(() => {
    const result = new Map<string, ConnectivityFinding[]>();
    visible.forEach((finding) => {
      const key = filters.group === "blocking" ? finding.blocking ? "Blocking" : "Non-blocking" : String(finding[filters.group] || "Not linked");
      result.set(key, [...(result.get(key) ?? []), finding]);
    });
    return result;
  }, [filters.group, visible]);
  const assetClasses = [...new Set(findings.map((item) => item.asset_class).filter(Boolean))].sort();
  const summary = run?.summary;
  const calibratedSummary = calibration?.summary;
  const filteredGroups = useMemo(() => issueGroups.filter((group) =>
    (!groupFilters.issue_family || group.issue_family === groupFilters.issue_family)
    && (!groupFilters.display_priority || group.display_priority === groupFilters.display_priority)
    && (!groupFilters.trace_impact || group.trace_impact === groupFilters.trace_impact)
    && (!groupFilters.review_status || group.review_status === groupFilters.review_status)
  ), [groupFilters, issueGroups]);
  const issueFamilies = [...new Set(issueGroups.map((item) => item.issue_family))].sort();

  async function execute(force: boolean) {
    setBusy(true);
    setError("");
    try {
      const result = await provider.post<ConnectivityRun>(`/api/connectivity-qa/${vertical}/runs`, { force_recalculate: force, actor: reviewer });
      await provider.post<ConnectivityCalibrationRun>(
        `/api/connectivity-qa/${vertical}/runs/${encodeURIComponent(result.qa_run_id)}/calibrate`,
        { preserve_review_decisions: true },
      );
      setMessage(result.reused ? "Unchanged graph detected; QA and calibration history were reused." : "Connectivity QA completed and findings were calibrated.");
      setDetail(null);
      setGroupDetail(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Connectivity QA run failed safely.");
    } finally {
      setBusy(false);
    }
  }

  async function calibrate(force: boolean) {
    if (!run) return;
    setBusy(true);
    setError("");
    try {
      const result = await provider.post<ConnectivityCalibrationRun>(
        `/api/connectivity-qa/${vertical}/runs/${encodeURIComponent(run.qa_run_id)}/calibrate`,
        { force_recalculate: force, preserve_review_decisions: true },
      );
      setMessage(result.reused ? "No QA findings or calibration rules changed." : "Actionable issue groups recalculated.");
      setGroupDetail(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Connectivity QA calibration failed safely.");
    } finally {
      setBusy(false);
    }
  }

  async function openGroup(issueGroupId: string) {
    try {
      setGroupDetail(await provider.get<ConnectivityIssueGroupDetail>(`/api/connectivity-qa/${vertical}/issue-groups/${encodeURIComponent(issueGroupId)}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Actionable issue detail unavailable.");
    }
  }

  async function reviewGroup(action: string) {
    if (!groupDetail) return;
    setBusy(true);
    setError("");
    try {
      const updated = await provider.post<ConnectivityIssueGroupDetail>(
        `/api/connectivity-qa/${vertical}/issue-groups/${encodeURIComponent(groupDetail.issue_group_id)}/${action}`,
        { reviewer, comment },
      );
      setGroupDetail(updated);
      setMessage(`Group review updated ${updated.member_finding_ids.length} technical finding${updated.member_finding_ids.length === 1 ? "" : "s"} without changing evidence.`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Issue-group review failed safely.");
    } finally {
      setBusy(false);
    }
  }

  async function openFinding(findingId: string) {
    try {
      setDetail(await provider.get<ConnectivityFinding & { rule?: ConnectivityRule; graph_context?: { assets?: Array<Record<string, unknown>>; relationship?: Record<string, unknown> | null }; history?: Array<Record<string, unknown>> }>(`/api/connectivity-qa/${vertical}/findings/${encodeURIComponent(findingId)}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Finding detail unavailable.");
    }
  }

  async function review(action: string) {
    if (!detail) return;
    setBusy(true);
    setError("");
    try {
      const updated = await provider.post<typeof detail>(
        `/api/connectivity-qa/${vertical}/findings/${encodeURIComponent(detail.finding_id)}/${action}`,
        { reviewer, comment },
      );
      setDetail(updated);
      setMessage("Review decision recorded in immutable history.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Review action failed safely.");
    } finally {
      setBusy(false);
    }
  }

  function downloadSummary() {
    if (!run || !summary) return;
    const content = {
      utility_vertical: vertical,
      profile_name: run.profile_name,
      model_version: run.model_version,
      rule_version: run.rule_version,
      qa_run_id: run.qa_run_id,
      started_at: run.started_at,
      completed_at: run.completed_at,
      calibration_run_id: calibration?.calibration_run_id ?? "",
      calibration_rule_version: calibration?.calibration_rule_version ?? "",
      raw_finding_count: summary.findings_count,
      actionable_issue_group_count: calibratedSummary?.actionable_issue_groups ?? 0,
      primary_blockers: calibratedSummary?.primary_blockers ?? 0,
      consequence_findings: calibratedSummary?.consequence_findings ?? 0,
      severity_distribution: calibratedSummary?.by_severity ?? summary.by_severity,
      issue_family_distribution: calibratedSummary?.by_issue_family ?? {},
      trace_impact_distribution: calibratedSummary?.by_trace_impact ?? {},
      affected_safe_asset_ids: [...new Set(issueGroups.flatMap((group) => group.affected_asset_ids))],
      review_statuses: calibratedSummary?.by_review_status ?? summary.by_review_status,
      recommended_actions: [...new Set(issueGroups.map((group) => group.recommended_action))],
      rule_runs: run.rule_runs,
      safety: "Safe canonical summary only; no source paths, geometry, customer, or subscriber records.",
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(content, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${config.id}-connectivity-qa-summary.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (loading) return <div className={ws.workspace}><LoadingSkeleton /></div>;
  if (error && !run && !rules.length) return <div className={ws.workspace}><OfflineState service="Connectivity QA API" /><p role="alert" className={styles.error}>{error}</p></div>;

  return (
    <div className={styles.workspace}>
      {isDemoMode ? <div className={styles.demoNotice} role="status"><strong>PORTFOLIO DEMO</strong> All utility assets, QA findings, issue groups, and review decisions in this demo are synthetic and reset with the demo session.</div> : null}
      <header className={styles.header}>
        <div>
          <span>{config.shortTitle} network readiness</span>
          <h2>{config.shortTitle} Connectivity QA</h2>
          <p>Validate canonical assets and explicit relationships before future tracing, proposed edits, or operational integration.</p>
        </div>
        <div className={ws.buttonRow}>
          <button className={ws.button} type="button" disabled={busy} onClick={() => execute(false)}><calcite-icon icon="play" scale="s" aria-hidden="true" />Run Connectivity QA</button>
          <button className={ws.button} type="button" disabled={busy} onClick={() => execute(true)}><calcite-icon icon="refresh" scale="s" aria-hidden="true" />Force Re-run</button>
          <button className={ws.button} type="button" disabled={busy || !run} onClick={() => calibrate(false)}><calcite-icon icon="organization" scale="s" aria-hidden="true" />Calibrate findings</button>
          <button className={ws.button} type="button" disabled={!summary} onClick={downloadSummary}><calcite-icon icon="download" scale="s" aria-hidden="true" />Download safe summary</button>
        </div>
      </header>

      {error ? <p role="alert" className={styles.error}>{error}</p> : null}
      {message ? <p role="status" className={styles.message}>{message}</p> : null}

      <div className={styles.runStrip}>
        <StatusBadge value={run?.status ?? "not_started"} tone={run?.status === "succeeded" ? "success" : "warning"} />
        <span>Profile <strong>{run?.profile_name ?? (vertical === "electric_distribution" ? "electric_distribution_v1" : "telecom_fiber_v1")}</strong></span>
        <span>Latest run <strong>{run?.completed_at ? new Date(run.completed_at).toLocaleString() : "Not run"}</strong></span>
        <span>Rule version <strong>{run?.rule_version ?? "connectivity-qa-rules-v2"}</strong></span>
        <span>Calibration <strong>{calibration?.calibration_rule_version ?? "Not run"}</strong></span>
      </div>

      <div className={styles.calibratedMetrics}>
        <MetricTile labelText="Actionable issues" value={String(calibratedSummary?.actionable_issue_groups ?? 0)} detail="Probable root problems" />
        <MetricTile labelText="Primary blockers" value={String(calibratedSummary?.primary_blockers ?? 0)} detail="Technical blocking preserved" />
        <MetricTile labelText="Trace-stopping" value={String(calibratedSummary?.trace_stopping_groups ?? 0)} detail="Future trace readiness" />
        <MetricTile labelText="Technical findings" value={String(summary?.findings_count ?? 0)} detail="Immutable raw evidence" />
        <MetricTile labelText="Consequences" value={String(calibratedSummary?.consequence_findings ?? 0)} detail="Shown under primary causes" />
        <MetricTile labelText="Affected assets" value={String(calibratedSummary?.affected_assets ?? 0)} detail="Safe canonical identifiers" />
        <MetricTile labelText="Reviewed groups" value={String((calibratedSummary?.actionable_issue_groups ?? 0) - (calibratedSummary?.unresolved_primary_groups ?? 0))} detail="Human decisions recorded" />
      </div>

      <Panel title="Evaluation pipeline" description="Each state reflects persisted run data; no timed progress is simulated.">
        <ol className={styles.pipeline}>
          {["Canonical Assets", "Relationship Build", "Rule Evaluation", "Finding Generation", "Summary"].map((stage, index) => (
            <li key={stage} data-complete={run?.status === "succeeded" || index === 0 && Boolean(run?.asset_count)}>
              <span>{index + 1}</span><strong>{stage}</strong><small>{run ? run.status === "succeeded" ? "Complete" : run.status : "Not started"}</small>
            </li>
          ))}
        </ol>
      </Panel>

      <nav className={styles.sectionNav} aria-label="Connectivity QA views">
        {([
          ["groups", "Actionable Issues"],
          ["findings", "All Technical Findings"],
          ["passed", "Passed Rules"],
          ["history", "Run History"],
          ["rules", "Rule Catalog"],
        ] as Array<[Section, string]>).map(([item, text]) => <button key={item} type="button" aria-current={section === item ? "page" : undefined} onClick={() => setSection(item)}>{text}</button>)}
      </nav>

      {section === "groups" ? (
        <IssueGroupExplorer
          groups={filteredGroups}
          allGroups={issueGroups}
          detail={groupDetail}
          families={issueFamilies}
          filters={groupFilters}
          reviewer={reviewer}
          comment={comment}
          busy={busy}
          config={config}
          onFilters={setGroupFilters}
          onOpen={openGroup}
          onReviewer={setReviewer}
          onComment={setComment}
          onReview={reviewGroup}
          onCalibrate={() => calibrate(false)}
        />
      ) : null}

      {section === "findings" ? (
        <>
          <Panel title="Finding explorer" description="Filter and group candidate issues; no finding is an automatic source edit.">
            <div className={styles.filters}>
              <label>Severity<select value={filters.severity} onChange={(event) => { setFilters({ ...filters, severity: event.target.value }); setPage(0); }}><option value="">All severities</option>{["critical", "error", "warning", "info"].map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Blocking<select value={filters.blocking} onChange={(event) => { setFilters({ ...filters, blocking: event.target.value }); setPage(0); }}><option value="">All findings</option><option value="true">Blocking</option><option value="false">Non-blocking</option></select></label>
              <label>Review status<select value={filters.review_status} onChange={(event) => { setFilters({ ...filters, review_status: event.target.value }); setPage(0); }}><option value="">All statuses</option>{["open", "acknowledged", "deferred", "accepted_risk", "resolved_externally", "false_positive", "superseded"].map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Rule<select aria-label="QA rule" value={filters.rule_code} onChange={(event) => { setFilters({ ...filters, rule_code: event.target.value }); setPage(0); }}><option value="">All rules</option>{rules.map((item) => <option key={item.rule_code}>{item.rule_code}</option>)}</select></label>
              <label>Asset class<select value={filters.asset_class} onChange={(event) => { setFilters({ ...filters, asset_class: event.target.value }); setPage(0); }}><option value="">All classes</option>{assetClasses.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Group by<select value={filters.group} onChange={(event) => setFilters({ ...filters, group: event.target.value as GroupField })}>{["severity", "rule_code", "asset_id", "relationship_id", "review_status", "blocking"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            </div>
          </Panel>
          {!filtered.length ? <EmptyState title="No connectivity findings" message={run ? "No findings match the current filters." : "Run Connectivity QA to evaluate the canonical graph."} /> : (
            <div className={styles.findingLayout}>
              <div className={styles.findingGroups}>
                {[...groups.entries()].map(([group, items]) => (
                  <Panel key={group} title={label(group)} description={`${items.length} finding${items.length === 1 ? "" : "s"} on this page`}>
                    <div className={styles.findingList}>
                      {items.map((finding) => (
                        <button className={styles.findingRow} type="button" key={finding.finding_id} aria-pressed={detail?.finding_id === finding.finding_id} onClick={() => openFinding(finding.finding_id)}>
                          <SeverityBadge value={finding.severity} />
                          <span><strong>{finding.rule_code} · {finding.short_title}</strong><small>{finding.asset_name || finding.asset_id || "Relationship finding"} · {label(finding.asset_class)}</small></span>
                          <span>{finding.blocking ? "Blocking" : "Review"}<small>{label(finding.review_status)}</small></span>
                        </button>
                      ))}
                    </div>
                  </Panel>
                ))}
                <div className={styles.pagination}>
                  <button className={ws.button} type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
                  <span>Page {page + 1} of {Math.max(1, Math.ceil(filtered.length / pageSize))}</span>
                  <button className={ws.button} type="button" disabled={(page + 1) * pageSize >= filtered.length} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </div>
              <FindingDetail detail={detail} config={config} reviewer={reviewer} comment={comment} busy={busy} onReviewer={setReviewer} onComment={setComment} onReview={review} />
            </div>
          )}
        </>
      ) : null}

      {section === "passed" ? <RuleCatalog rules={rules.filter((rule) => run?.rule_runs.find((item) => item.rule_code === rule.rule_code)?.status === "passed")} run={run} /> : null}
      {section === "rules" ? <RuleCatalog rules={rules} run={run} /> : null}
      {section === "history" ? <RunHistory runs={runs} calibrationRuns={calibrationRuns} /> : null}

      <Panel title="Operational boundary" description="Connectivity QA is a readiness check, not a vendor network model.">
        <ul className={styles.limitations}>{(summary?.limitations ?? [
          "The graph uses explicit canonical relationships only.",
          "No source or staged geometry is opened or modified.",
          "No tracing, snapping, topology repair, service publishing, or vendor integration occurs.",
        ]).map((item) => <li key={item}>{item}</li>)}</ul>
      </Panel>
    </div>
  );
}

function IssueGroupExplorer({
  groups,
  allGroups,
  detail,
  families,
  filters,
  reviewer,
  comment,
  busy,
  config,
  onFilters,
  onOpen,
  onReviewer,
  onComment,
  onReview,
  onCalibrate,
}: {
  groups: ConnectivityIssueGroup[];
  allGroups: ConnectivityIssueGroup[];
  detail: ConnectivityIssueGroupDetail | null;
  families: string[];
  filters: { issue_family: string; display_priority: string; trace_impact: string; review_status: string };
  reviewer: string;
  comment: string;
  busy: boolean;
  config: UtilityVerticalConfig;
  onFilters: (value: { issue_family: string; display_priority: string; trace_impact: string; review_status: string }) => void;
  onOpen: (issueGroupId: string) => void;
  onReviewer: (value: string) => void;
  onComment: (value: string) => void;
  onReview: (action: string) => void;
  onCalibrate: () => void;
}) {
  if (!allGroups.length) {
    return <Panel title="Actionable issue queue" description="Calibration has not been run for the latest technical findings."><EmptyState title="No actionable issue groups yet" message="Group the existing technical findings by deterministic root-cause evidence." /><button className={ws.button} type="button" onClick={onCalibrate}>Calibrate findings</button></Panel>;
  }
  return (
    <>
      <Panel
        title="Actionable issue queue"
        description={`Related findings are grouped by probable root cause so ${config.shortTitle.toLowerCase()} operators can address the underlying condition first.`}
      >
        <div className={styles.groupFilters}>
          <label>Issue family<select value={filters.issue_family} onChange={(event) => onFilters({ ...filters, issue_family: event.target.value })}><option value="">All families</option>{families.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
          <label>Priority<select value={filters.display_priority} onChange={(event) => onFilters({ ...filters, display_priority: event.target.value })}><option value="">All priorities</option>{["immediate", "high", "normal", "low", "informational"].map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Trace impact<select value={filters.trace_impact} onChange={(event) => onFilters({ ...filters, trace_impact: event.target.value })}><option value="">All impacts</option>{["stops_trace", "limits_trace", "introduces_ambiguity", "advisory", "no_trace_effect"].map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>Review status<select value={filters.review_status} onChange={(event) => onFilters({ ...filters, review_status: event.target.value })}><option value="">All statuses</option>{["open", "mixed", "acknowledged", "deferred", "accepted_risk", "false_positive"].map((item) => <option key={item}>{item}</option>)}</select></label>
        </div>
      </Panel>
      {!groups.length ? <EmptyState title="No actionable issues match" message="Clear one or more filters to restore the queue." /> : (
        <div className={styles.findingLayout}>
          <div className={styles.groupCards}>
            {groups.map((group) => (
              <button
                className={styles.groupCard}
                type="button"
                key={group.issue_group_id}
                aria-pressed={detail?.issue_group_id === group.issue_group_id}
                onClick={() => onOpen(group.issue_group_id)}
              >
                <div className={styles.groupCardTop}>
                  <span className={styles.priorityLabel}>{label(group.display_priority)} priority</span>
                  <SeverityBadge value={group.highest_severity} />
                </div>
                <strong>{group.group_title}</strong>
                <p>{group.group_summary}</p>
                <dl className={styles.groupFacts}>
                  <div><dt>Primary issue</dt><dd>{group.primary_rule_code}</dd></div>
                  <div><dt>Related consequences</dt><dd>{Math.max(0, group.technical_finding_count - 1)}</dd></div>
                  <div><dt>Affected assets</dt><dd>{group.affected_asset_ids.length}</dd></div>
                  <div><dt>Trace impact</dt><dd>{label(group.trace_impact)}</dd></div>
                </dl>
                <span className={styles.groupAction}>{group.recommended_action}</span>
                <span><StatusBadge value={group.review_status} /> {group.effective_blocking ? "Technical blocker" : "Advisory"}</span>
              </button>
            ))}
          </div>
          <IssueGroupDetail
            detail={detail}
            config={config}
            reviewer={reviewer}
            comment={comment}
            busy={busy}
            onReviewer={onReviewer}
            onComment={onComment}
            onReview={onReview}
          />
        </div>
      )}
    </>
  );
}

function IssueGroupDetail({
  detail,
  config,
  reviewer,
  comment,
  busy,
  onReviewer,
  onComment,
  onReview,
}: {
  detail: ConnectivityIssueGroupDetail | null;
  config: UtilityVerticalConfig;
  reviewer: string;
  comment: string;
  busy: boolean;
  onReviewer: (value: string) => void;
  onComment: (value: string) => void;
  onReview: (action: string) => void;
}) {
  if (!detail) return <Panel title="Issue-group detail" description="Select an actionable issue to inspect its preserved evidence."><EmptyState title="No issue selected" message="Choose an issue group from the queue." /></Panel>;
  const primary = detail.members.find((item) => item.finding_id === detail.primary_finding_id);
  return (
    <aside className={styles.detail}>
      <Panel title="Root problem" description={`${detail.primary_rule_code} · ${label(detail.issue_family)} · ${label(detail.display_priority)} priority`}>
        <dl className={styles.detailGrid}>
          <div><dt>Expected condition</dt><dd>Complete, internally consistent canonical relationships for future interpretation.</dd></div>
          <div><dt>Actual condition</dt><dd>{primary?.explanation ?? detail.group_summary}</dd></div>
          <div><dt>Why it matters</dt><dd>{detail.trace_impact_reason}</dd></div>
          <div><dt>Recommended action</dt><dd>{detail.recommended_action}</dd></div>
          <div><dt>Root-cause confidence</dt><dd>{label(detail.root_cause_confidence)}</dd></div>
          <div><dt>Technical blocking</dt><dd>{detail.effective_blocking ? "Yes" : "No"}</dd></div>
        </dl>
        {detail.affected_asset_ids[0] ? <Link className={ws.button} href={`${config.routeBase}/assets?asset_id=${encodeURIComponent(detail.affected_asset_ids[0])}`}>Open primary asset</Link> : null}
      </Panel>
      <Panel title="Related technical findings" description="Every original rule result remains inspectable.">
        <div className={styles.memberList}>
          {detail.members.map((member) => <div key={member.finding_id}><span>{label(member.finding_role)}</span><strong>{member.rule_code} · {member.short_title}</strong><small>{label(member.severity)} / {member.blocking ? "blocking" : "non-blocking"}</small><p>{member.grouping_reason}</p></div>)}
        </div>
      </Panel>
      <Panel title="Network context" description="Logical relationship view - not an engineering diagram.">
        <pre className={styles.json}>{JSON.stringify(detail.graph_context, null, 2)}</pre>
      </Panel>
      <Panel title="Trace readiness" description="Preparation metadata only; no trace is executed.">
        <dl className={styles.detailGrid}>
          <div><dt>Impact</dt><dd>{label(detail.trace_impact)}</dd></div>
          <div><dt>Future behavior</dt><dd>{detail.trace_impact === "stops_trace" ? "Stop at this evidence boundary." : detail.trace_impact === "limits_trace" ? "Warn and stop at confirmed evidence." : "Continue provisionally with a warning."}</dd></div>
          <div><dt>Vendor mapping</dt><dd>{label(detail.external_rule_mapping_status)}</dd></div>
          <div><dt>Conceptual hints</dt><dd>{detail.vendor_equivalent_hints.map(label).join(", ")}</dd></div>
        </dl>
        <p className={styles.vendorDisclaimer}>Vendor-equivalent hints describe general utility GIS concepts only. They do not represent direct ArcFM, Smallworld, Esri Utility Network, or proprietary telecom-system integration.</p>
      </Panel>
      <Panel title="Group review" description="Group actions update only listed member review states and append immutable history.">
        <p>Group status: <StatusBadge value={detail.review_status} /> · Member states remain visible above.</p>
        <div className={styles.reviewForm}>
          <label>Reviewer<input value={reviewer} onChange={(event) => onReviewer(event.target.value)} /></label>
          <label>Rationale<textarea rows={3} value={comment} onChange={(event) => onComment(event.target.value)} placeholder="Required for defer, accepted risk, and false positive" /></label>
        </div>
        <div className={styles.reviewButtons}>
          <button className={ws.button} type="button" disabled={busy} onClick={() => onReview("acknowledge")}>Acknowledge group</button>
          <button className={ws.button} type="button" disabled={busy || !comment.trim()} onClick={() => onReview("defer")}>Defer group</button>
          <button className={ws.button} type="button" disabled={busy || !comment.trim()} onClick={() => onReview("accept-risk")}>Accept risk</button>
          <button className={ws.button} type="button" disabled={busy || !comment.trim()} onClick={() => onReview("mark-false-positive")}>False positive</button>
          <button className={ws.button} type="button" disabled={busy} onClick={() => onReview("reopen")}>Reopen</button>
        </div>
      </Panel>
    </aside>
  );
}

function FindingDetail({
  detail,
  config,
  reviewer,
  comment,
  busy,
  onReviewer,
  onComment,
  onReview,
}: {
  detail: (ConnectivityFinding & { rule?: ConnectivityRule; graph_context?: { assets?: Array<Record<string, unknown>>; relationship?: Record<string, unknown> | null }; history?: Array<Record<string, unknown>> }) | null;
  config: UtilityVerticalConfig;
  reviewer: string;
  comment: string;
  busy: boolean;
  onReviewer: (value: string) => void;
  onComment: (value: string) => void;
  onReview: (action: string) => void;
}) {
  if (!detail) return <Panel title="Finding detail" description="Select a finding to inspect evidence and review controls."><EmptyState title="No finding selected" message="Select a candidate from the explorer." /></Panel>;
  return (
    <aside className={styles.detail}>
      <Panel title={detail.short_title} description={`${detail.rule_code} · ${label(detail.severity)} · ${detail.blocking ? "Blocking" : "Non-blocking"}`}>
        <dl className={styles.detailGrid}>
          <div><dt>Detected condition</dt><dd>{detail.explanation}</dd></div>
          <div><dt>Recommended action</dt><dd>{detail.recommended_action}</dd></div>
          <div><dt>Limitation</dt><dd>{detail.rule?.limitation ?? "Canonical graph evidence only."}</dd></div>
          <div><dt>Affected asset</dt><dd>{detail.asset_name || detail.asset_id || "Relationship only"}</dd></div>
          <div><dt>Related asset</dt><dd>{detail.related_asset_name || "None"}</dd></div>
          <div><dt>Relationship</dt><dd>{detail.relationship_id || "Not relationship-scoped"}</dd></div>
          <div><dt>Run ID</dt><dd>{detail.qa_run_id}</dd></div>
          <div><dt>Review status</dt><dd><StatusBadge value={detail.review_status} /></dd></div>
        </dl>
        {detail.asset_id ? <Link className={ws.button} href={`${config.routeBase}/assets?asset_id=${encodeURIComponent(detail.asset_id)}`}>Open canonical asset</Link> : null}
      </Panel>
      <Panel title="Logical graph context" description="Safe identifiers and explicit relationships only.">
        <pre className={styles.json}>{JSON.stringify(detail.graph_context ?? detail.evidence, null, 2)}</pre>
      </Panel>
      <Panel title="Human review" description="Decisions are audit history; they never edit source or staged assets.">
        <div className={styles.reviewForm}>
          <label>Reviewer<input value={reviewer} onChange={(event) => onReviewer(event.target.value)} /></label>
          <label>Comment or rationale<textarea rows={3} value={comment} onChange={(event) => onComment(event.target.value)} placeholder="Required for defer, accepted risk, and false positive" /></label>
        </div>
        <div className={styles.reviewButtons}>
          <button className={ws.button} type="button" disabled={busy} onClick={() => onReview("acknowledge")}>Acknowledge</button>
          <button className={ws.button} type="button" disabled={busy || !comment.trim()} onClick={() => onReview("defer")}>Defer</button>
          <button className={ws.button} type="button" disabled={busy || !comment.trim()} onClick={() => onReview("accept-risk")}>Accept risk</button>
          <button className={ws.button} type="button" disabled={busy || !comment.trim()} onClick={() => onReview("mark-false-positive")}>False positive</button>
          <button className={ws.button} type="button" disabled={busy} onClick={() => onReview("reopen")}>Reopen</button>
        </div>
      </Panel>
    </aside>
  );
}

function RuleCatalog({ rules, run }: { rules: ConnectivityRule[]; run: ConnectivityRun | null }) {
  const statuses = new Map(run?.rule_runs.map((item) => [item.rule_code, item]) ?? []);
  return (
    <Panel title="Rule catalog" description="Built-in, versioned, allowlisted rules; executable user rules are not accepted.">
      <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Rule</th><th>Severity</th><th>Scope</th><th>Blocking</th><th>Status</th><th>Findings</th><th>Logic and limitation</th></tr></thead>
        <tbody>{rules.map((rule) => {
          const status = statuses.get(rule.rule_code);
          return <tr key={rule.rule_code}><td><strong>{rule.rule_code}</strong><small className={styles.tableSub}>{rule.name}</small></td><td><SeverityBadge value={rule.severity} /></td><td>{label(rule.scope)}</td><td>{rule.blocking ? "Yes" : "No"}</td><td><StatusBadge value={status?.status ?? "not_run"} /></td><td>{status?.finding_count ?? 0}</td><td>{rule.description}<small className={styles.tableSub}>{rule.limitation}</small></td></tr>;
        })}</tbody>
      </table></div>
    </Panel>
  );
}

function RunHistory({ runs, calibrationRuns }: { runs: ConnectivityRun[]; calibrationRuns: ConnectivityCalibrationRun[] }) {
  if (!runs.length) return <EmptyState title="No connectivity runs" message="Run the versioned profile to create immutable history." />;
  return (
    <>
    <Panel title="Run history" description="Unchanged graphs reuse a prior run unless Force Re-run is explicit.">
      <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Run</th><th>Status</th><th>Started</th><th>Assets</th><th>Relationships</th><th>Findings</th><th>Blocking</th><th>Forced</th></tr></thead>
        <tbody>{runs.map((run) => <tr key={run.qa_run_id}><td>{run.qa_run_id}</td><td><StatusBadge value={run.status} tone={run.status === "succeeded" ? "success" : "warning"} /></td><td>{new Date(run.started_at).toLocaleString()}</td><td>{run.asset_count}</td><td>{run.relationship_count}</td><td>{run.findings_count}</td><td>{run.blocking_findings_count}</td><td>{run.force_recalculate ? "Yes" : "No"}</td></tr>)}</tbody>
      </table></div>
    </Panel>
    <Panel title="Calibration history" description="Forced recalculation preserves compatible group review decisions and supersedes changed memberships.">
      <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Calibration run</th><th>Status</th><th>QA run</th><th>Technical findings</th><th>Issue groups</th><th>Consequences</th><th>Completed</th></tr></thead>
        <tbody>{calibrationRuns.map((run) => <tr key={run.calibration_run_id}><td>{run.calibration_run_id}</td><td><StatusBadge value={run.status} /></td><td>{run.qa_run_id}</td><td>{run.technical_findings_read}</td><td>{run.issue_groups_created}</td><td>{run.consequence_findings}</td><td>{new Date(run.completed_at).toLocaleString()}</td></tr>)}</tbody>
      </table></div>
    </Panel>
    </>
  );
}
