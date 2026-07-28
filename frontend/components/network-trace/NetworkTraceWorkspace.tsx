"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import { label } from "../../lib/formatters";
import type {
  CalibratedTraceEvent,
  CalibratedTraceResult,
  TraceEvent,
  TracePath,
  TraceRun,
  TraceStep,
  TraceType,
} from "../../lib/network-trace";
import type { UtilityAsset } from "../../lib/utility-assets";
import type { UtilityVerticalConfig } from "../../lib/utility-verticals";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./network-trace.module.css";

type Readiness = {
  asset_id: string;
  canonical_name: string;
  asset_class: string;
  lifecycle_status: string;
  operational_status: string;
  eligible_trace_types: Array<{ trace_type: string; name: string; default_direction: string }>;
  trace_ready: boolean;
  qa_evaluated: boolean;
  calibration_available: boolean;
  blockers: Array<Record<string, string>>;
  warnings: Array<Record<string, string>>;
  provisional_relationships: number;
  available_relationships?: number;
  trace_count: number;
  recent_traces: Array<Record<string, string>>;
  relationship_trace_usage: Record<string, { traces_used: number; traces_stopped: number }>;
  confidence_notice: string;
  disclaimer: string;
};
type AssetResponse = { items: UtilityAsset[] };
type RunResponse = { items: TraceRun[] };
type ResultView = "summary" | "ordered" | "logical" | "primary" | "background" | "evidence" | "history" | "types";

export function NetworkTraceWorkspace({ config }: { config: UtilityVerticalConfig }) {
  const provider = getDataProvider();
  const searchParams = useSearchParams();
  const [types, setTypes] = useState<TraceType[]>([]);
  const [assets, setAssets] = useState<UtilityAsset[]>([]);
  const [runs, setRuns] = useState<TraceRun[]>([]);
  const [result, setResult] = useState<TraceRun | null>(null);
  const [calibrated, setCalibrated] = useState<CalibratedTraceResult | null>(null);
  const [calibratedEvents, setCalibratedEvents] = useState<CalibratedTraceEvent[]>([]);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [traceType, setTraceType] = useState("");
  const [startAssetId, setStartAssetId] = useState(searchParams.get("start_asset_id") ?? "");
  const [targetAssetId, setTargetAssetId] = useState("");
  const [startSearch, setStartSearch] = useState("");
  const [direction, setDirection] = useState("downstream");
  const [lifecycle, setLifecycle] = useState("active_only");
  const [provisional, setProvisional] = useState("include_with_warning");
  const [qaPolicy, setQaPolicy] = useState("conservative");
  const [maxDepth, setMaxDepth] = useState(40);
  const [maxAssets, setMaxAssets] = useState(250);
  const [view, setView] = useState<ResultView>("summary");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      provider.get<{ items: TraceType[] }>(`/api/network-trace/types/${config.canonicalValue}`, controller.signal),
      provider.get<AssetResponse>(`/api/utility-assets?utility_vertical=${config.canonicalValue}&limit=500`, controller.signal),
      provider.get<RunResponse>(`/api/network-trace/${config.canonicalValue}/runs?limit=50`, controller.signal),
    ]).then(async ([catalog, assetData, runData]) => {
      setTypes(catalog.items);
      setTraceType(catalog.items[0]?.trace_type ?? "");
      setDirection(catalog.items[0]?.default_direction ?? "downstream");
      setAssets(assetData.items.filter((item) => item.utility_vertical === config.canonicalValue));
      setRuns(runData.items);
      const requestedRunId = searchParams.get("trace_run_id");
      if (requestedRunId) await openRun(requestedRunId);
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Network Trace service unavailable."));
    return () => controller.abort();
    // Search params are intentionally read once; direct route state is restored on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.canonicalValue, provider]);

  const selectedType = types.find((item) => item.trace_type === traceType);
  const eligibleAssets = useMemo(() => {
    const classes = new Set(selectedType?.start_asset_classes ?? []);
    const needle = startSearch.toLowerCase();
    return assets.filter((item) =>
      classes.has(item.asset_class)
      && (!needle || `${item.canonical_name} ${item.asset_id} ${item.asset_class}`.toLowerCase().includes(needle)),
    );
  }, [assets, selectedType, startSearch]);
  const targetAssets = useMemo(() => {
    const classes = new Set(selectedType?.terminal_asset_classes ?? []);
    return classes.size ? assets.filter((item) => classes.has(item.asset_class)) : assets;
  }, [assets, selectedType]);
  const selectedStartAssetId = eligibleAssets.some((item) => item.asset_id === startAssetId)
    ? startAssetId : eligibleAssets[0]?.asset_id ?? "";

  useEffect(() => {
    if (!selectedStartAssetId) return;
    const controller = new AbortController();
    provider.get<Readiness>(`/api/network-trace/assets/${encodeURIComponent(selectedStartAssetId)}/readiness`, controller.signal)
      .then(setReadiness)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Readiness preview unavailable."));
    return () => controller.abort();
  }, [provider, selectedStartAssetId]);

  async function openRun(traceRunId: string) {
    const [run, stepData] = await Promise.all([
      provider.get<TraceRun>(`/api/network-trace/${config.canonicalValue}/runs/${encodeURIComponent(traceRunId)}`),
      provider.get<{ items: TraceStep[] }>(`/api/network-trace/${config.canonicalValue}/runs/${encodeURIComponent(traceRunId)}/steps`),
    ]);
    await provider.post(`/api/network-trace/${config.canonicalValue}/runs/${encodeURIComponent(traceRunId)}/calibrate`, {
      force_recalculate: false,
    });
    const [calibratedResult, eventData] = await Promise.all([
      provider.get<CalibratedTraceResult>(`/api/network-trace/${config.canonicalValue}/runs/${encodeURIComponent(traceRunId)}/calibrated-result`),
      provider.get<{ items: CalibratedTraceEvent[] }>(`/api/network-trace/${config.canonicalValue}/runs/${encodeURIComponent(traceRunId)}/calibrated-events?limit=500`),
    ]);
    setResult(run);
    setSteps(stepData.items);
    setCalibrated(calibratedResult);
    setCalibratedEvents(eventData.items);
    setView("summary");
    const routeIndex = window.location.pathname.indexOf(config.routeBase);
    const basePrefix = routeIndex >= 0 ? window.location.pathname.slice(0, routeIndex) : "";
    window.history.replaceState({}, "", `${basePrefix}${config.routeBase}/network-trace?trace_run_id=${encodeURIComponent(traceRunId)}`);
  }

  async function runTrace(force = false) {
    if (!selectedType || !selectedStartAssetId) return;
    setRunning(true);
    setError("");
    try {
      const run = await provider.post<TraceRun>(`/api/network-trace/${config.canonicalValue}/runs`, {
        trace_type: traceType,
        start_asset_id: selectedStartAssetId,
        optional_target_asset_id: targetAssetId,
        direction,
        lifecycle_mode: lifecycle,
        operational_mode: "respect_state",
        provisional_relationship_policy: provisional,
        qa_policy: qaPolicy,
        include_reference_relationships: false,
        include_containment_relationships: false,
        max_depth: maxDepth,
        max_assets: maxAssets,
        requested_by: isDemoMode ? "Demo Reviewer" : "Local Operator",
        request_notes: "",
        force_recalculate: force,
        preserve_review_decisions: true,
      });
      await openRun(run.trace_run_id);
      const refreshed = await provider.get<RunResponse>(`/api/network-trace/${config.canonicalValue}/runs?limit=50`);
      setRuns(refreshed.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Trace failed safely.");
    } finally {
      setRunning(false);
    }
  }

  async function downloadReceipt() {
    if (!result) return;
    const receipt = await provider.get<Record<string, unknown>>(`/api/network-trace/${config.canonicalValue}/runs/${encodeURIComponent(result.trace_run_id)}/calibrated-safe-summary`);
    const url = URL.createObjectURL(new Blob([JSON.stringify(receipt, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${result.trace_run_id}-calibrated-safe-trace-receipt.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (error && !types.length) return <OfflineState service="Network Trace service" />;
  if (!types.length) return <><LoadingSkeleton /><LoadingSkeleton /></>;

  const startAsset = assets.find((item) => item.asset_id === selectedStartAssetId);
  const estimatedConfidence = !readiness?.qa_evaluated ? "Indeterminate"
    : readiness.blockers.length ? "Low"
      : readiness.provisional_relationships || readiness.warnings.length ? "Medium" : "High";
  const verticalDisclaimer = config.id === "electric"
    ? "Electric traces are vendor-neutral analytical results based on synthetic canonical relationships. They are not operational switching instructions, engineering studies, outage predictions, or authoritative utility-network traces."
    : "Telecom traces are vendor-neutral analytical results based on synthetic canonical relationships. They are not authoritative inventory, provisioning, construction, or service-impact records.";

  return (
    <div className={styles.workspace}>
      <header className={styles.title}>
        <div><span>Read-only analytical traversal</span><h2>{config.shortTitle} Network Trace</h2></div>
        <StatusBadge value="Network Trace V1" tone="success" />
      </header>
      <p className={styles.disclaimer}>{isDemoMode ? verticalDisclaimer : result?.disclaimer ?? verticalDisclaimer}</p>
      {error ? <div className={styles.error} role="alert">{error}</div> : null}

      <div className={styles.setupGrid}>
        <Panel title="Trace setup" description="Only asset classes valid for the selected trace profile are available.">
          <div className={styles.form}>
            <label>Trace type<select value={traceType} onChange={(event) => {
              const selected = types.find((item) => item.trace_type === event.target.value);
              setTraceType(event.target.value);
              setDirection(selected?.default_direction ?? "downstream");
              setTargetAssetId("");
            }}>{types.map((item) => <option key={item.trace_type} value={item.trace_type}>{item.name}</option>)}</select></label>
            <label>Search start assets<input value={startSearch} onChange={(event) => setStartSearch(event.target.value)} placeholder="Name, ID, or class" /></label>
            <label>Start asset<select value={selectedStartAssetId} onChange={(event) => setStartAssetId(event.target.value)}>{eligibleAssets.map((item) => <option key={item.asset_id} value={item.asset_id}>{item.canonical_name} / {label(item.asset_class)}</option>)}</select></label>
            <label>Optional target<select value={targetAssetId} onChange={(event) => setTargetAssetId(event.target.value)}><option value="">Profile terminal condition</option>{targetAssets.map((item) => <option key={item.asset_id} value={item.asset_id}>{item.canonical_name}</option>)}</select></label>
            <label>Direction<select value={direction} onChange={(event) => setDirection(event.target.value)}>{["upstream", "downstream", "bidirectional", "toward_source", "toward_terminal"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            <label>Lifecycle mode<select value={lifecycle} onChange={(event) => setLifecycle(event.target.value)}>{["active_only", "active_and_installed", "include_proposed", "include_inactive", "historical"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            <label>Provisional relationships<select value={provisional} onChange={(event) => setProvisional(event.target.value)}>{["exclude", "include_with_warning", "require_when_only_path"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            <label>QA policy<select value={qaPolicy} onChange={(event) => setQaPolicy(event.target.value)}>{["strict", "conservative", "diagnostic"].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            <details className={styles.advanced}><summary>Advanced safe limits</summary><div><label>Maximum depth<input type="number" min="1" max="100" value={maxDepth} onChange={(event) => setMaxDepth(Number(event.target.value))} /></label><label>Maximum assets<input type="number" min="1" max="1000" value={maxAssets} onChange={(event) => setMaxAssets(Number(event.target.value))} /></label></div></details>
            <button className={ws.button} type="button" disabled={running || !selectedStartAssetId} onClick={() => runTrace(false)}><calcite-icon icon="play" scale="s" aria-hidden="true" />{running ? "Running trace..." : "Run Trace"}</button>
          </div>
        </Panel>

        <Panel title="Readiness preview" description="A preflight view of represented evidence, not the final trace result.">
          {readiness && startAsset ? <dl className={styles.readiness}>
            <div><dt>Start asset</dt><dd>{startAsset.canonical_name}</dd></div>
            <div><dt>Class</dt><dd>{label(startAsset.asset_class)}</dd></div>
            <div><dt>Lifecycle</dt><dd><StatusBadge value={readiness.lifecycle_status} /></dd></div>
            <div><dt>Operational</dt><dd>{label(readiness.operational_status)}</dd></div>
            <div><dt>Available relationships</dt><dd>{readiness.available_relationships ?? startAsset.relationship_count}</dd></div>
            <div><dt>Blocking QA groups</dt><dd>{readiness.blockers.length}</dd></div>
            <div><dt>Advisory QA groups</dt><dd>{readiness.warnings.length}</dd></div>
            <div><dt>Provisional relationships</dt><dd>{readiness.provisional_relationships}</dd></div>
            <div><dt>Estimated confidence</dt><dd>{estimatedConfidence}</dd></div>
            <div><dt>Trace eligible</dt><dd>{readiness.trace_ready && readiness.eligible_trace_types.some((item) => item.trace_type === traceType) ? "Yes" : "No"}</dd></div>
          </dl> : <EmptyState title="Select a start asset" message="Readiness evidence will appear before the trace runs." />}
        </Panel>
      </div>

      {running ? <Panel title="Trace progress" description="The synchronous trace request is executing; no artificial delay or percentage is shown."><p>Validating request and loading persisted canonical evidence...</p></Panel> : null}
      {result && calibrated ? <TraceResult
        config={config} result={result} calibrated={calibrated} calibratedEvents={calibratedEvents}
        steps={steps} runs={runs} types={types} view={view}
        setView={setView} onOpenRun={openRun} onRerun={() => runTrace(true)} onDownload={downloadReceipt}
      /> : <EmptyState title="No trace selected" message="Run a trace or open an immutable historical result." />}
    </div>
  );
}

function TraceResult({
  config, result, calibrated, calibratedEvents, steps, runs, types, view, setView, onOpenRun, onRerun, onDownload,
}: {
  config: UtilityVerticalConfig;
  result: TraceRun;
  calibrated: CalibratedTraceResult;
  calibratedEvents: CalibratedTraceEvent[];
  steps: TraceStep[];
  runs: TraceRun[];
  types: TraceType[];
  view: ResultView;
  setView: (view: ResultView) => void;
  onOpenRun: (id: string) => Promise<void>;
  onRerun: () => void;
  onDownload: () => Promise<void>;
}) {
  const tabs: Array<[ResultView, string]> = [
    ["summary", "Summary"], ["ordered", "Ordered Paths"], ["logical", "Logical Network"],
    ["primary", "Primary Issues"], ["background", "Background Conditions"],
    ["evidence", "All Trace Evidence"], ["history", "History"], ["types", "Trace Types"],
  ];
  return (
    <>
      <section className={ws.grid12} aria-label="Trace result metrics">
        <div className={ws.span3}><MetricTile labelText="Calibrated outcome" value={label(calibrated.calibrated_outcome)} detail={calibrated.objective_reached ? "Trace objective reached" : "Trace objective not reached"} /></div>
        <div className={ws.span3}><MetricTile labelText="Calibrated confidence" value={label(calibrated.calibrated_confidence)} detail="Selected-path evidence only" /></div>
        <div className={ws.span3}><MetricTile labelText="Path conditions" value={String(calibrated.path_specific_blocker_count + calibrated.path_specific_warning_count)} detail={`${calibrated.background_warning_count} background conditions separated`} /></div>
        <div className={ws.span3}><MetricTile labelText="Branches" value={String(calibrated.normal_branch_count)} detail={`${calibrated.ambiguous_branch_count} ambiguous alternative(s)`} /></div>
      </section>
      <Panel title="Calibrated interpretation" description={`${result.trace_type} / ${result.trace_run_id}`}>
        <div className={styles.resultSummary}>
          <span><strong>Start</strong>{result.start_asset_id}</span>
          <span><strong>Target / objective</strong>{result.target_asset_id || "Profile terminal condition"}</span>
          <span><strong>Objective reached</strong>{calibrated.objective_reached ? "Yes" : "No"}</span>
          <span><strong>Primary condition</strong>{label(calibrated.primary_stopping_category || "none")}</span>
          <span><strong>Provisional segments</strong>{calibrated.provisional_segment_count}</span>
        </div>
        <div className={ws.buttonRow}>
          <button className={ws.button} type="button" onClick={onRerun}><calcite-icon icon="refresh" scale="s" aria-hidden="true" />Rerun</button>
          <button className={ws.button} type="button" onClick={onDownload}><calcite-icon icon="download" scale="s" aria-hidden="true" />Download Calibrated Receipt</button>
        </div>
      </Panel>
      <Panel title="Original trace result" description="Immutable traversal evidence remains available and is never rewritten by calibration.">
        <div className={styles.resultSummary}>
          <span><strong>Original outcome</strong>{label(result.outcome)}</span>
          <span><strong>Original confidence</strong>{label(result.confidence)}</span>
          <span><strong>Raw warnings</strong>{result.warnings_count}</span>
          <span><strong>Raw blockers</strong>{result.blockers_count}</span>
          <span><strong>Raw events</strong>{calibrated.related_raw_event_count}</span>
        </div>
      </Panel>
      <nav className={styles.resultTabs} aria-label="Trace result views" role="tablist">
        {tabs.map(([id, name]) => <button
          aria-selected={view === id} className={view === id ? styles.activeTab : ""}
          key={id} onClick={() => setView(id)} role="tab" type="button"
        >{name}</button>)}
      </nav>
      {view === "summary" ? <CalibrationSummary result={calibrated} paths={result.paths} /> : null}
      {view === "ordered" ? <OrderedView config={config} paths={result.paths} steps={steps} /> : null}
      {view === "logical" ? <LogicalView config={config} paths={result.paths} steps={steps} /> : null}
      {view === "primary" ? <PrimaryIssues config={config} events={calibratedEvents} /> : null}
      {view === "background" ? <BackgroundConditions events={calibratedEvents} /> : null}
      {view === "evidence" ? <RawEvidence config={config} paths={result.paths} events={result.events} /> : null}
      {view === "history" ? <HistoryView runs={runs} selected={result.trace_run_id} onOpen={onOpenRun} /> : null}
      {view === "types" ? <TraceTypesView types={types} /> : null}
    </>
  );
}

function CalibrationSummary({ result, paths }: { result: CalibratedTraceResult; paths: TracePath[] }) {
  const normal = result.normal_branch_count ? paths.slice(1, result.normal_branch_count + 1) : [];
  return <>
    <Panel title="Why this result" description="Deterministic reasons based on selected paths, not the full network warning count.">
      <ul className={styles.reasonList}>{result.outcome_reason.map((reason) => <li key={reason}>{reason}</li>)}</ul>
      <h4>Confidence</h4>
      <ul className={styles.reasonList}>{result.confidence_reason.map((reason) => <li key={reason}>{reason}</li>)}</ul>
      <p><strong>Safest next action:</strong> {result.recommended_action}</p>
    </Panel>
    <Panel title="Branch interpretation" description="Expected fan-out is separate from competing authoritative alternatives.">
      <div className={styles.branchGrid}>
        <section><h4>Normal branches</h4><p>{result.normal_branch_count} expected branch alternative(s).</p>
          {normal.map((path) => <p key={path.trace_path_id}><strong>{path.trace_path_id}</strong><br />Ends at {path.end_asset_id}; {label(path.path_status)}{path.provisional ? "; provisional" : ""}.</p>)}
        </section>
        <section><h4>Ambiguous alternatives</h4><p>{result.ambiguous_branch_count ? `${result.ambiguous_branch_count} competing interpretation(s) require review.` : "No competing authoritative interpretation was identified."}</p></section>
      </div>
    </Panel>
    <Panel title="Future comparison fields" description="Stable read-only fields prepared for a later proposed-edit workspace.">
      <div className={styles.resultSummary}>
        <span><strong>Comparison key</strong>{result.comparison_key}</span>
        <span><strong>Path signature</strong>{result.path_signature}</span>
        <span><strong>Branch signature</strong>{result.branch_signature}</span>
        <span><strong>Reachable assets</strong>{result.reachable_asset_ids.length}</span>
        <span><strong>Suggested category</strong>{label(result.recommended_edit_category)}</span>
      </div>
    </Panel>
  </>;
}

function PrimaryIssues({ config, events }: { config: UtilityVerticalConfig; events: CalibratedTraceEvent[] }) {
  const items = events.filter((event) =>
    event.primary || ["stopping_condition", "path_specific", "branch_specific", "start_asset_context", "target_asset_context"].includes(event.scope),
  );
  return <Panel title="Primary issues and selected-path conditions" description="Grouped operational interpretation; all underlying events remain in All Trace Evidence.">
    {items.length ? <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Priority</th><th>Condition</th><th>Scope</th><th>Affected evidence</th><th>Effect</th><th>Safe action</th></tr></thead>
      <tbody>{items.map((event) => <tr key={event.calibrated_event_id}><td>{event.primary ? <StatusBadge value="Primary" tone="danger" /> : event.priority}</td><td><strong>{event.title}</strong><small className={styles.assetId}>{label(event.category)}</small></td><td>{label(event.scope)}</td><td>{event.path_ids.length} path(s), {event.repeated_count} reference(s){event.issue_group_ids[0] ? <><br /><Link href={`${config.routeBase}/connectivity-qa?issue_group_id=${encodeURIComponent(event.issue_group_ids[0])}`}>{event.issue_group_ids[0]}</Link></> : null}</td><td>{event.summary}<small className={styles.assetId}>{label(event.trace_effect)}</small></td><td>{event.recommended_action}</td></tr>)}</tbody>
    </table></div> : <EmptyState title="No selected-path issues" message="Only background or informational evidence was found." />}
  </Panel>;
}

function BackgroundConditions({ events }: { events: CalibratedTraceEvent[] }) {
  const background = events.filter((event) => ["network_background", "unrelated_to_selected_path"].includes(event.scope));
  const groups = [...new Set(background.map((event) => event.category))].map((category) => {
    const items = background.filter((event) => event.category === category);
    return {
      category, issueGroups: new Set(items.flatMap((event) => event.issue_group_ids)).size,
      assets: new Set(items.flatMap((event) => event.asset_ids)).size,
      references: items.reduce((sum, event) => sum + event.repeated_count, 0),
    };
  });
  return <Panel title="Background Network Conditions" description="These conditions were present in the evaluated network but did not directly determine the selected trace result.">
    {groups.length ? <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Category</th><th>Issue groups</th><th>Off-path assets</th><th>Evidence references</th></tr></thead><tbody>
      {groups.map((group) => <tr key={group.category}><td>{label(group.category)}</td><td>{group.issueGroups}</td><td>{group.assets}</td><td>{group.references}</td></tr>)}
    </tbody></table></div> : <EmptyState title="No background conditions" message="All calibrated evidence was related to a returned path." />}
  </Panel>;
}

function RawEvidence({ config, paths, events }: { config: UtilityVerticalConfig; paths: TracePath[]; events: TraceEvent[] }) {
  return <>
    <BlockingView config={config} paths={paths} events={events} />
    <Panel title="Immutable raw trace events" description="Complete event-level evidence retained exactly as produced by the trace run.">
      {events.length ? <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Event</th><th>Type</th><th>Asset / relationship</th><th>Issue group</th><th>Message</th></tr></thead><tbody>
        {events.map((event) => <tr key={event.trace_event_id}><td>{event.trace_event_id}</td><td>{label(event.event_type)}</td><td>{event.asset_id || event.relationship_id || "Trace context"}</td><td>{event.issue_group_id || "None"}</td><td>{event.message}</td></tr>)}
      </tbody></table></div> : <EmptyState title="No raw events" message="The immutable trace did not produce event records." />}
    </Panel>
  </>;
}

function TraceTypesView({ types }: { types: TraceType[] }) {
  return <Panel title="Allowlisted trace types" description="Profiles define vendor-neutral analytical objectives and safe terminal conditions.">
    <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Code</th><th>Name</th><th>Direction</th><th>Eligible starts</th><th>Terminal classes</th></tr></thead><tbody>
      {types.map((type) => <tr key={type.trace_type}><td>{type.trace_type}</td><td>{type.name}</td><td>{label(type.default_direction)}</td><td>{type.start_asset_classes.map(label).join(", ")}</td><td>{type.terminal_asset_classes.map(label).join(", ") || "Evidence boundary"}</td></tr>)}
    </tbody></table></div>
  </Panel>;
}

function LogicalView({ config, paths, steps }: { config: UtilityVerticalConfig; paths: TracePath[]; steps: TraceStep[] }) {
  const stepByAsset = new Map(steps.map((item) => [item.asset_id, item]));
  return <Panel title="Logical relationship view" description="Not an engineering diagram or operational switching model.">
    <div className={styles.logical} aria-label="Logical trace paths">{paths.map((path) => <div className={styles.logicalPath} key={path.trace_path_id}>
      {path.asset_ids.map((assetId, index) => {
        const step = stepByAsset.get(assetId);
        const stopped = index === path.asset_ids.length - 1 && path.path_status !== "complete";
        return <div className={styles.nodeGroup} key={`${path.trace_path_id}-${assetId}`}>
          {index ? <span className={styles.connector} aria-hidden="true" /> : null}
          <Link className={`${styles.node} ${index === 0 ? styles.startNode : ""} ${stopped ? styles.stoppedNode : ""}`} href={`${config.routeBase}/assets?asset_id=${encodeURIComponent(assetId)}`}>
            <strong>{step?.canonical_name ?? assetId}</strong><span>{label(step?.asset_class ?? "")}</span>
          </Link>
        </div>;
      })}
      <span className={styles.pathStop}>{label(path.stopping_reason)}{path.provisional ? " / provisional" : ""}</span>
    </div>)}</div>
    <ol className={styles.textEquivalent}>{paths.map((path) => <li key={path.trace_path_id}>Path {path.path_rank}: {path.asset_ids.join(" to ")}. Stopped: {label(path.stopping_reason)}.</li>)}</ol>
  </Panel>;
}

function OrderedView({ config, paths, steps }: { config: UtilityVerticalConfig; paths: TracePath[]; steps: TraceStep[] }) {
  if (!steps.length) return <EmptyState title="No ordered steps" message="The selected trace has no traversable path steps." />;
  const pathRank = new Map(paths.map((path) => [path.trace_path_id, path.path_rank]));
  return <Panel title="Ordered path" description="Safe canonical context and trace decisions in deterministic order.">
    <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Path / step</th><th>Asset</th><th>Class</th><th>Lifecycle</th><th>Operational</th><th>Relationship</th><th>Context</th><th>Decision</th></tr></thead>
      <tbody>{steps.map((step) => <tr key={`${step.trace_path_id}-${step.sequence}`}>
        <td>{pathRank.get(step.trace_path_id) ?? 1} / {step.sequence}</td>
        <td><Link href={`${config.routeBase}/assets?asset_id=${encodeURIComponent(step.asset_id)}`}>{step.canonical_name || step.asset_id}</Link><small className={styles.assetId}>{step.asset_id}</small></td>
        <td>{label(step.asset_class)}</td><td>{label(step.lifecycle_status)}</td><td>{label(step.operational_state)}</td>
        <td>{step.entered_by_relationship_id ? <Link href={`${config.routeBase}/relationships?relationship_id=${encodeURIComponent(step.entered_by_relationship_id)}`}>{step.entered_by_relationship_id}</Link> : "Start"}</td>
        <td>{step.feeder_or_route_context || Object.entries(step.asset_context ?? {}).map(([key, value]) => `${label(key)} ${value}`).join(" / ") || "Unavailable"}</td>
        <td>{label(step.decision)}<small className={styles.assetId}>{label(step.decision_reason)}</small></td>
      </tr>)}</tbody></table></div>
  </Panel>;
}

function BlockingView({ config, paths, events }: { config: UtilityVerticalConfig; paths: TracePath[]; events: TraceEvent[] }) {
  const conditions = paths.flatMap((path) => [...path.blockers, ...path.warnings]);
  return <Panel title="Blocking issues and warnings" description="Calibrated findings remain candidates for review; tracing never changes them.">
    {conditions.length ? <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Effect</th><th>Asset or relationship</th><th>Message</th><th>Issue group</th></tr></thead><tbody>{conditions.map((item, index) => <tr key={`${item.code}-${item.asset_id}-${index}`}><td><StatusBadge value={item.code} tone={paths.some((path) => path.blockers.includes(item)) ? "danger" : "warning"} /></td><td>{item.asset_id || item.relationship_id}</td><td>{item.message}</td><td>{item.issue_group_id ? <Link href={`${config.routeBase}/connectivity-qa?issue_group_id=${encodeURIComponent(item.issue_group_id)}`}>{item.issue_group_id}</Link> : "Profile decision"}</td></tr>)}</tbody></table></div> : <EmptyState title="No blockers or warnings" message="This trace used represented canonical evidence without a reported condition." />}
    <p className={styles.eventCount}>{events.length} immutable trace events recorded.</p>
  </Panel>;
}

function HistoryView({ runs, selected, onOpen }: { runs: TraceRun[]; selected: string; onOpen: (id: string) => Promise<void> }) {
  return <Panel title="Immutable trace history" description="Historical paths retain their original QA references and stopping conditions.">
    {runs.length ? <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Run</th><th>Type / profile</th><th>Start</th><th>Target</th><th>Outcome</th><th>Confidence</th><th>Paths</th><th>Input evidence</th><th>Completed</th></tr></thead><tbody>{runs.map((run) => <tr key={run.trace_run_id}><td><button className={styles.historyLink} type="button" aria-current={selected === run.trace_run_id ? "true" : undefined} onClick={() => onOpen(run.trace_run_id)}>{run.trace_run_id}</button></td><td>{run.trace_type}<small className={styles.assetId}>{run.trace_profile} / {run.trace_rule_version}</small></td><td>{run.start_asset_id}</td><td>{run.target_asset_id || "Profile terminal"}</td><td><StatusBadge value={run.outcome} /></td><td>{label(run.confidence)}</td><td>{run.paths_evaluated}</td><td><small className={styles.assetId}>{run.input_fingerprint}</small></td><td>{run.completed_at}</td></tr>)}</tbody></table></div> : <EmptyState title="No trace history" message="Run a trace to create an immutable local or session-only record." />}
  </Panel>;
}
