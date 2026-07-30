"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import { label } from "../../lib/formatters";
import type { ProposedEdit } from "../../lib/proposed-edits";
import type { UtilityVerticalConfig } from "../../lib/utility-verticals";
import type { WorkOrder, WorkOrderRecord } from "../../lib/work-orders";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, PageHeader, Panel, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "../proposed-edits/proposed-edits.module.css";

type ListResponse = { items: WorkOrder[]; pagination: { total: number } };
type ProposalResponse = { items: ProposedEdit[] };
type TypeCatalog = { work_order_types: string[]; priorities: string[]; disclaimer: string };
const views = ["Overview", "Plan", "Assignments", "Prerequisites", "Job Steps", "Inspections", "Release", "Implementation", "Validate", "Review", "Closeout", "History"] as const;
type View = (typeof views)[number];

export function WorkOrderWorkspace({ config }: { config: UtilityVerticalConfig }) {
  const provider = getDataProvider();
  const vertical = config.canonicalValue;
  const [items, setItems] = useState<WorkOrder[]>([]);
  const [proposals, setProposals] = useState<ProposedEdit[]>([]);
  const [catalog, setCatalog] = useState<TypeCatalog | null>(null);
  const [selected, setSelected] = useState<WorkOrder | null>(null);
  const [view, setView] = useState<View>("Overview");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [packageData, setPackageData] = useState<Record<string, unknown> | null>(null);
  const [receiptData, setReceiptData] = useState<Record<string, unknown> | null>(null);

  const load = async (preferredId = "") => {
    setError("");
    try {
      const list = await provider.get<ListResponse>(`/api/work-orders/${vertical}`);
      const [types, proposalList] = await Promise.all([
        provider.get<TypeCatalog>(`/api/work-orders/types/${vertical}`),
        provider.get<ProposalResponse>(`/api/proposed-edits/${vertical}`),
      ]);
      setItems(list.items); setCatalog(types); setProposals(proposalList.items);
      const id = preferredId || selected?.work_order_id || list.items[0]?.work_order_id;
      if (id) setSelected(await provider.get<WorkOrder>(`/api/work-orders/${vertical}/${encodeURIComponent(id)}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Work Order workspace is unavailable.");
    }
  };

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [vertical]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => items.filter((item) =>
    (!status || item.overall_status === status)
    && (!type || item.work_order_type === type)
    && (!search || `${item.title} ${item.scenario_code} ${item.work_order_number}`.toLowerCase().includes(search.toLowerCase())),
  ), [items, search, status, type]);

  const run = async (action: string, body: Record<string, unknown> = {}) => {
    if (!selected) return;
    if (["approve-release", "release", "record-implementation", "approve-closeout"].includes(action)
      && !window.confirm(`Confirm ${label(action)} for this synthetic, vendor-neutral job workflow?`)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await provider.post<Record<string, unknown>>(
        `/api/work-orders/${vertical}/${encodeURIComponent(selected.work_order_id)}/${action}`,
        body,
      );
      if (action === "job-package") setPackageData(result);
      setMessage(`${label(action)} recorded. No canonical, source, staged, or operational network was changed.`);
      await load(selected.work_order_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Work-order action failed safely.");
    } finally { setBusy(false); }
  };

  const loadReceipt = async () => {
    if (!selected) return;
    try {
      setReceiptData(await provider.get(`/api/work-orders/${vertical}/${encodeURIComponent(selected.work_order_id)}/completion-receipt`));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Completion receipt is not available."); }
  };

  if (error && !catalog) return <OfflineState service={`Work Order workspace: ${error}`} />;
  if (!catalog) return <LoadingSkeleton />;
  return (
    <div className={styles.workspace}>
      <PageHeader
        eyebrow={isDemoMode ? "PORTFOLIO DEMO" : "Vendor-neutral job management"}
        title={`${config.shortTitle} Work Orders`}
        subtitle="Convert approved Proposed Edits into controlled planning, evidence, validation, and closeout workflows."
      />
      <div className={styles.safety} role="note">
        <calcite-icon icon="briefcase" scale="s" aria-hidden="true" />
        <span><strong>Synthetic job package.</strong> No operational utility GIS, field system, work-management system, ArcFM, Smallworld, Esri Utility Network, or telecom inventory system is connected.</span>
      </div>
      {config.id === "electric" ? <div className={styles.operationalWarning}>Device-state review is data verification, not a switching instruction or outage response.</div> : null}
      {["water", "wastewater"].includes(config.canonicalValue) ? <div className={styles.operationalWarning}>Work packages are synthetic review records. They do not operate valves or pumps, perform field work, or change a hydraulic model.</div> : null}
      {message ? <div className={styles.message} role="status">{message}</div> : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      <section className={styles.metrics} aria-label="Work-order metrics">
        <MetricTile labelText="Work orders" value={String(items.length)} detail={`${config.shortTitle} synthetic and local jobs`} />
        <MetricTile labelText="Ready for review" value={String(items.filter((item) => item.readiness === "ready_for_review").length)} detail="Planning gates satisfied" />
        <MetricTile labelText="Release blocked" value={String(items.filter((item) => item.readiness === "blocked").length)} detail="Prerequisite or proposal blocker" />
        <MetricTile labelText="Closed" value={String(items.filter((item) => item.overall_status === "closed").length)} detail="Synthetic closeout receipt available" />
      </section>
      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <div className={styles.sidebarHeader}>
            <div><span>Job registry</span><strong>{filtered.length} visible</strong></div>
            <button className={ws.button} type="button" onClick={() => setShowCreate((value) => !value)}>
              <calcite-icon icon="plus" scale="s" aria-hidden="true" /> New
            </button>
          </div>
          {showCreate ? <CreateWorkOrder catalog={catalog} proposals={proposals} onCancel={() => setShowCreate(false)} onCreate={async (body) => {
            setBusy(true);
            try {
              const created = await provider.post<WorkOrder>(`/api/work-orders/${vertical}`, body);
              setShowCreate(false); await load(created.work_order_id); setMessage("Synthetic work-order draft created.");
            } catch (reason) { setError(reason instanceof Error ? reason.message : "Work-order creation failed safely."); }
            finally { setBusy(false); }
          }} /> : null}
          <div className={styles.filters}>
            <label>Search<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title or job number" /></label>
            <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All states</option>{[...new Set(items.map((item) => item.overall_status))].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
            <label>Work type<select value={type} onChange={(event) => setType(event.target.value)}><option value="">All types</option>{catalog.work_order_types.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
          </div>
          <div className={styles.proposalList} aria-label={`${config.title} work orders`}>
            {filtered.map((item) => (
              <button
                type="button"
                className={item.work_order_id === selected?.work_order_id ? styles.selectedProposal : styles.proposal}
                key={item.work_order_id}
                onClick={async () => {
                  setSelected(await provider.get<WorkOrder>(`/api/work-orders/${vertical}/${encodeURIComponent(item.work_order_id)}`));
                  setView("Overview"); setPackageData(null); setReceiptData(null);
                }}
              >
                <span>{item.scenario_code || item.work_order_number}</span>
                <strong>{item.title}</strong>
                <small>{label(item.overall_status)} / {label(item.readiness)}</small>
              </button>
            ))}
          </div>
        </aside>
        <main className={styles.detail}>
          {!selected ? <EmptyState title="Select a work order" message="Choose a synthetic scenario or create a controlled draft." /> : (
            <>
              <WorkOrderHeader item={selected} />
              <nav className={styles.steps} aria-label="Work-order workflow">
                {views.map((item, index) => <button key={item} type="button" className={view === item ? styles.activeStep : ""} onClick={() => setView(item)}><span>{index + 1}</span>{item}</button>)}
              </nav>
              {view === "Overview" ? <Overview item={selected} config={config} /> : null}
              {view === "Plan" ? <Plan item={selected} config={config} /> : null}
              {view === "Assignments" ? <Assignments item={selected} /> : null}
              {view === "Prerequisites" ? <Prerequisites item={selected} busy={busy} provider={provider} onChanged={() => load(selected.work_order_id)} onError={setError} /> : null}
              {view === "Job Steps" ? <JobSteps item={selected} busy={busy} provider={provider} onChanged={() => load(selected.work_order_id)} onError={setError} /> : null}
              {view === "Inspections" ? <Inspections item={selected} busy={busy} provider={provider} onChanged={() => load(selected.work_order_id)} onError={setError} /> : null}
              {view === "Release" ? <Release item={selected} busy={busy} run={run} /> : null}
              {view === "Implementation" ? <Implementation item={selected} busy={busy} run={run} /> : null}
              {view === "Validate" ? <Validation item={selected} busy={busy} run={run} /> : null}
              {view === "Review" ? <Review item={selected} packageData={packageData} busy={busy} run={run} /> : null}
              {view === "Closeout" ? <Closeout item={selected} receiptData={receiptData} busy={busy} run={run} loadReceipt={loadReceipt} /> : null}
              {view === "History" ? <History item={selected} /> : null}
            </>
          )}
        </main>
      </div>
      <p className={styles.disclaimer}>{catalog.disclaimer}</p>
    </div>
  );
}

function CreateWorkOrder({ catalog, proposals, onCancel, onCreate }: { catalog: TypeCatalog; proposals: ProposedEdit[]; onCancel: () => void; onCreate: (body: Record<string, unknown>) => void }) {
  const approved = proposals.filter((item) => item.approval_status === "approved");
  const [proposalId, setProposalId] = useState(approved[0]?.proposal_id ?? "");
  const [workType, setWorkType] = useState(approved.length ? catalog.work_order_types.find((item) => item !== "manual_investigation") ?? catalog.work_order_types[0] : "manual_investigation");
  const [titleValue, setTitleValue] = useState("");
  const selectedProposal = approved.find((item) => item.proposal_id === proposalId);
  const manual = workType === "manual_investigation";
  return <form className={styles.createForm} onSubmit={(event) => {
    event.preventDefault();
    onCreate({
      proposal_id: manual ? "" : proposalId,
      proposal_version: manual ? 0 : selectedProposal?.proposal_version,
      proposal_approved: manual ? undefined : selectedProposal?.approval_status === "approved",
      proposal_code: selectedProposal?.scenario_code,
      operation_count: selectedProposal?.operations?.length ?? selectedProposal?.operation_count ?? 0,
      work_order_type: workType, title: titleValue,
      created_by: isDemoMode ? "Demo Planner" : "Local Planner",
      summary: "Vendor-neutral synthetic job workflow.",
    });
  }}>
    <label>Approved proposal<select disabled={manual} value={proposalId} onChange={(event) => setProposalId(event.target.value)}><option value="">{approved.length ? "Select approved proposal" : "No approved proposals"}</option>{approved.map((item) => <option key={item.proposal_id} value={item.proposal_id}>{item.scenario_code || item.title}</option>)}</select></label>
    <label>Work type<select value={workType} onChange={(event) => setWorkType(event.target.value)}>{catalog.work_order_types.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
    <label>Title<input required maxLength={180} value={titleValue} onChange={(event) => setTitleValue(event.target.value)} /></label>
    <div className={styles.formActions}><button type="button" onClick={onCancel}>Cancel</button><button className={ws.button} disabled={!manual && !proposalId} type="submit">Create draft</button></div>
  </form>;
}

function WorkOrderHeader({ item }: { item: WorkOrder }) {
  return <header className={styles.proposalHeader}>
    <div><span>{item.scenario_code || item.work_order_number}</span><h2>{item.title}</h2><p>{label(item.work_order_type)} / Version {item.work_order_version}</p></div>
    <div className={styles.headerStatuses}><StatusBadge value={item.overall_status} tone={item.readiness === "blocked" ? "danger" : item.overall_status === "closed" ? "success" : "neutral"} /><StatusBadge value={item.priority} /></div>
  </header>;
}

function Overview({ item, config }: { item: WorkOrder; config: UtilityVerticalConfig }) {
  const dimensions = [
    ["Overall", item.overall_status], ["Design", item.design_status], ["Field work", item.field_work_status],
    ["GIS implementation", item.gis_implementation_status], ["Inspection", item.inspection_status],
    ["QA", item.qa_status], ["Trace", item.trace_status], ["Review", item.review_status], ["Closeout", item.closeout_status],
  ];
  return <div className={styles.stack}>
    <section className={styles.metrics} aria-label="Work-order status dimensions">
      {dimensions.map(([name, value]) => <MetricTile key={name} labelText={name} value={label(value)} detail="Independent workflow state" />)}
    </section>
    <div className={styles.viewGrid}>
      <Panel title="Job identity" description={item.summary}>
        <dl className={styles.definition}>
          <div><dt>Vertical</dt><dd>{config.title}</dd></div><div><dt>Number</dt><dd>{item.work_order_number}</dd></div>
          <div><dt>Current owner</dt><dd>{item.current_owner}</dd></div><div><dt>Target date</dt><dd>{item.target_completion_date || "Not set"}</dd></div>
          <div><dt>Release readiness</dt><dd><StatusBadge value={item.readiness} tone={item.readiness === "blocked" ? "danger" : "neutral"} /></dd></div>
          <div><dt>Closeout readiness</dt><dd><StatusBadge value={item.closeout_readiness} tone={item.closeout_readiness === "blocked" ? "danger" : "neutral"} /></dd></div>
        </dl>
      </Panel>
      <Panel title="External-system boundary" description="A future organization-specific adapter is required.">
        <div className={styles.stack}><StatusBadge value={item.external_mapping_status} /><span>No vendor SDK, command, credential, or transaction is present.</span><span>{item.implementation_confirmation_status === "simulated_overlay_only" ? "Recorded in implementation overlay" : "No implementation recorded"}</span></div>
      </Panel>
    </div>
  </div>;
}

function Plan({ item, config }: { item: WorkOrder; config: UtilityVerticalConfig }) {
  return <div className={styles.stack}>
    <Panel title="Approved proposal" description="The linked Proposed Edit remains immutable and is not edited from this workspace.">
      {item.linked_proposal_id ? <dl className={styles.definition}><div><dt>Proposal</dt><dd><Link href={`${config.routeBase}/proposed-edits`}>{item.linked_proposal_id}</Link></dd></div><div><dt>Version</dt><dd>{item.linked_proposal_version}</dd></div><div><dt>Approved</dt><dd>{item.proposal_approved ? "Yes" : "No"}</dd></div><div><dt>Baseline current</dt><dd>{item.baseline_current ? "Yes" : "No"}</dd></div></dl> : <p>Manual investigation only. No network-changing operation is attached.</p>}
    </Panel>
    <Panel title="Job phases" description="Required phases retain independent state and assigned role.">
      <ol className={styles.history}>{item.phases.map((phase) => <li key={String(phase.phase_id)}><strong>{String(phase.sequence)}. {String(phase.phase_name)}</strong><span>{label(String(phase.assigned_role || ""))}</span><StatusBadge value={String(phase.status)} /></li>)}</ol>
    </Panel>
  </div>;
}

function Assignments({ item }: { item: WorkOrder }) {
  return <Panel title="Role assignments" description="Synthetic application roles are separate from current ownership and final approval.">
    <ul className={styles.findings}>{item.assignments.map((assignment) => <li key={String(assignment.assignment_id)}><strong>{label(String(assignment.role))}</strong><span>{String(assignment.assignee)}</span><StatusBadge value={String(assignment.assignment_status)} /></li>)}</ul>
  </Panel>;
}

function Prerequisites({ item, busy, provider, onChanged, onError }: RecordEditorProps) {
  const act = async (id: string, action: "confirm" | "waive") => {
    try {
      await provider.post(`/api/work-orders/${item.utility_vertical}/${encodeURIComponent(item.work_order_id)}/prerequisites/${encodeURIComponent(id)}/${action}`, { actor: "Synthetic Reviewer", reason: action === "waive" ? "Reviewed synthetic exception." : "", status: "satisfied" });
      onChanged();
    } catch (reason) { onError(reason instanceof Error ? reason.message : "Prerequisite update failed safely."); }
  };
  return <Panel title="Release prerequisites" description="Critical blockers explain what is missing, why it matters, and who can resolve it.">
    <ul className={styles.findings}>{item.prerequisites.map((prerequisite) => <li key={String(prerequisite.prerequisite_id)}>
      <strong>{String(prerequisite.title)}</strong><span>{String(prerequisite.description || "")}</span><StatusBadge value={String(prerequisite.status)} tone={prerequisite.status === "blocked" ? "danger" : "neutral"} />
      {!item.locked && !["satisfied", "waived"].includes(String(prerequisite.status)) ? <div className={styles.reviewActions}><button className={ws.button} disabled={busy} onClick={() => act(String(prerequisite.prerequisite_id), "confirm")}>Confirm</button><button disabled={busy} onClick={() => act(String(prerequisite.prerequisite_id), "waive")}>Waive with reason</button></div> : null}
    </li>)}</ul>
  </Panel>;
}

function JobSteps({ item, busy, provider, onChanged, onError }: RecordEditorProps) {
  const complete = async (step: WorkOrderRecord, exception = false) => {
    try {
      await provider.post(`/api/work-orders/${item.utility_vertical}/${encodeURIComponent(item.work_order_id)}/steps/${encodeURIComponent(String(step.step_id))}/${exception ? "exception" : "complete"}`, { actor: "Synthetic GIS Technician", notes: exception ? "Synthetic exception requires review." : "Synthetic result recorded." });
      onChanged();
    } catch (reason) { onError(reason instanceof Error ? reason.message : "Job step update failed safely."); }
  };
  return <div className={styles.stack}>
    {item.steps.length ? item.steps.map((step) => <article className={styles.operationCard} key={String(step.step_id)}>
      <span className={styles.sequence}>{String(step.sequence)}</span>
      <div><strong>{String(step.title)}</strong><p>{String(step.instructions)}</p><small>{label(String(step.step_type))} / {String((step.affected_asset_ids as string[] | undefined)?.join(", ") || "No asset reference")}</small></div>
      <StatusBadge value={String(step.completion_status)} />
      {!["completed", "completed_with_exception"].includes(String(step.completion_status)) ? <div className={styles.reviewActions}><button className={ws.button} disabled={busy} onClick={() => complete(step)}>Complete</button><button disabled={busy} onClick={() => complete(step, true)}>Record exception</button></div> : null}
    </article>) : <EmptyState title="No network-changing steps" message="Manual investigations record review evidence only." />}
  </div>;
}

function Inspections({ item, busy, provider, onChanged, onError }: RecordEditorProps) {
  const record = async (inspection: WorkOrderRecord, result: string) => {
    try {
      await provider.post(`/api/work-orders/${item.utility_vertical}/${encodeURIComponent(item.work_order_id)}/inspections/${encodeURIComponent(String(inspection.inspection_id))}/record`, { result, inspector: "Synthetic Inspector", observed_condition: result === "pass" ? "Synthetic condition agrees with approved evidence." : "Unable to verify from synthetic evidence." });
      onChanged();
    } catch (reason) { onError(reason instanceof Error ? reason.message : "Inspection update failed safely."); }
  };
  return <Panel title={`${label(item.utility_vertical)} inspection requirements`} description="V1 stores safe synthetic evidence metadata; no real field photos or EXIF locations are accepted.">
    <ul className={styles.findings}>{item.inspections.map((inspection) => <li key={String(inspection.inspection_id)}><strong>{String(inspection.title)}</strong><span>{String(inspection.expected_condition)}</span><StatusBadge value={String(inspection.result)} />
      {inspection.result === "not_recorded" ? <div className={styles.reviewActions}><button className={ws.button} disabled={busy} onClick={() => record(inspection, "pass")}>Record pass</button><button disabled={busy} onClick={() => record(inspection, "unable_to_verify")}>Unable to verify</button></div> : null}
    </li>)}</ul>
  </Panel>;
}

function Release({ item, busy, run }: ActionProps) {
  const blockers = item.prerequisites.filter((row) => row.required && !["satisfied", "satisfied_with_conditions", "waived", "not_applicable"].includes(String(row.status)));
  return <div className={styles.stack}>
    <Panel title="Release readiness" description="Approval and release are separate explicit decisions.">
      <div className={styles.approvalBox}><StatusBadge value={item.readiness} tone={item.readiness === "blocked" ? "danger" : "neutral"} />
        {blockers.length ? <ul>{blockers.map((row) => <li key={String(row.prerequisite_id)}>{String(row.title)}</li>)}</ul> : <p>Required assignments, prerequisites, proposal evidence, and checklist definition are present.</p>}
        <div className={styles.reviewActions}>
          {["draft", "planning", "ready_for_review"].includes(item.overall_status) ? <button className={ws.button} disabled={busy || item.readiness === "blocked"} onClick={() => run("submit", actor("Synthetic Planner"))}>Submit for Review</button> : null}
          {item.overall_status === "ready_for_review" ? <button className={ws.button} disabled={busy} onClick={() => run("start-review", actor("Synthetic Technical Reviewer"))}>Start Review</button> : null}
          {item.overall_status === "under_review" ? <button className={ws.button} disabled={busy} onClick={() => run("approve-release", actor("Synthetic Final Reviewer", "Reviewed synthetic release package."))}>Approve for Release</button> : null}
          {item.overall_status === "approved_for_release" ? <button className={ws.button} disabled={busy} onClick={() => run("release", actor("Synthetic Final Reviewer"))}>Release Work</button> : null}
        </div>
      </div>
    </Panel>
    <p className={styles.disclaimer}>Release authorizes only this synthetic workflow. It does not dispatch a crew, operate equipment, provision fiber, or update an external system.</p>
  </div>;
}

function Implementation({ item, busy, run }: ActionProps) {
  return <div className={styles.stack}>
    <Panel title="Recorded implementation" description="Approved operations are recorded in a temporary implementation overlay.">
      {item.implementation ? <dl className={styles.definition}><div><dt>Status</dt><dd><StatusBadge value={String(item.implementation.status)} /></dd></div><div><dt>Completed operations</dt><dd>{String((item.implementation.completed_operation_ids as string[])?.length ?? 0)}</dd></div><div><dt>Skipped</dt><dd>{String((item.implementation.skipped_operation_ids as string[])?.length ?? 0)}</dd></div><div><dt>Overlay</dt><dd className={styles.fingerprint}>{String(item.implementation.overlay_fingerprint)}</dd></div></dl> : <p>No implementation result has been recorded.</p>}
      <div className={styles.reviewActions}>
        {item.overall_status === "released" ? <button className={ws.button} disabled={busy} onClick={() => run("start-work", actor("Synthetic GIS Technician"))}>Start Work</button> : null}
        {["in_progress", "field_complete", "gis_update_pending", "released"].includes(item.overall_status) && !item.implementation ? <button className={ws.button} disabled={busy} onClick={() => run("record-implementation", { recorded_by: "Synthetic GIS Technician", notes: "Record the approved operations in the synthetic implementation overlay." })}>Record Implementation</button> : null}
      </div>
      <p className={styles.emptyEvidence}>Recorded implementation is synthetic and has not changed the canonical or source network.</p>
    </Panel>
    <ThreeState item={item} />
  </div>;
}

function Validation({ item, busy, run }: ActionProps) {
  const qa = item.post_work_qa;
  const trace = item.post_work_traces[0];
  return <div className={styles.stack}>
    <section className={styles.metrics} aria-label="Post-work validation">
      <MetricTile labelText="Conformance" value={label(String(item.conformance?.status || "not_run"))} detail="Approved versus recorded operations" />
      <MetricTile labelText="Post-work QA" value={label(String(qa?.status || item.qa_status))} detail="Existing Connectivity QA engine" />
      <MetricTile labelText="Post-work trace" value={label(String(trace?.status || item.trace_status))} detail="Existing Network Trace engine" />
      <MetricTile labelText="Closeout" value={label(item.closeout_readiness)} detail="All gates must pass" />
    </section>
    <div className={styles.reviewActions}>
      <button className={ws.button} disabled={busy || !item.implementation} onClick={() => run("run-conformance")}>Run Conformance</button>
      <button className={ws.button} disabled={busy || !item.implementation} onClick={() => run("run-post-work-qa")}>Run Post-Work QA</button>
      <button className={ws.button} disabled={busy || !item.implementation} onClick={() => run("run-post-work-traces")}>Run Post-Work Traces</button>
    </div>
    <ThreeState item={item} />
  </div>;
}

function ThreeState({ item }: { item: WorkOrder }) {
  const states = [item.three_state_comparison.baseline, item.three_state_comparison.approved_plan, item.three_state_comparison.recorded_implementation];
  return <Panel title="Baseline / approved plan / recorded implementation" description="QA and trace evidence remains state-specific and comparable.">
    <div className={styles.compareGrid}>{states.map((state) => <article className={styles.compareValue} key={String(state.label)}><span>{String(state.label)}</span><div><strong>{state.qa_blockers == null ? "Not run" : `${String(state.qa_blockers)} blockers`}</strong></div><small>Trace: {label(String(state.trace || "not_run"))}</small></article>)}</div>
    <p className={styles.emptyEvidence}>{item.three_state_comparison.notice}</p>
  </Panel>;
}

function Review({ item, packageData, busy, run }: ActionProps & { packageData: Record<string, unknown> | null }) {
  return <div className={styles.stack}>
    <Panel title="Technical review" description="Review proposal linkage, implementation evidence, conformance, QA, traces, inspections, and exceptions.">
      <ul className={styles.findings}><li><strong>Proposal</strong><span>{item.linked_proposal_id || "Manual investigation"}</span><StatusBadge value={item.proposal_approved ? "approved" : "not approved"} /></li><li><strong>Implementation</strong><span>{item.implementation ? "Recorded in implementation overlay" : "Not recorded"}</span><StatusBadge value={item.implementation_confirmation_status} /></li><li><strong>Conformance</strong><span>Approved sequence versus recorded results</span><StatusBadge value={String(item.conformance?.status || "not_run")} /></li></ul>
    </Panel>
    <Panel title="Vendor-neutral job package" description="Structured, descriptive, nonexecutable JSON for future adapter mapping.">
      <div className={styles.packageHeader}><span>External mapping: adapter required</span><button className={ws.button} disabled={busy || item.review_status !== "approved"} onClick={() => run("job-package", actor("Synthetic Reviewer"))}>Generate Job Package</button></div>
      {packageData ? <pre className={styles.package}>{JSON.stringify(packageData, null, 2)}</pre> : <p className={styles.emptyEvidence}>Release approval is required. The generated package contains no scripts, commands, geometry, credentials, or local paths.</p>}
    </Panel>
  </div>;
}

function Closeout({ item, receiptData, busy, run, loadReceipt }: ActionProps & { receiptData: Record<string, unknown> | null; loadReceipt: () => void }) {
  return <div className={styles.stack}>
    <Panel title="Closeout gates" description="Required steps, inspections, conformance, QA, traces, evidence, and review must be complete.">
      <div className={styles.approvalBox}><StatusBadge value={item.closeout_readiness} tone={item.closeout_readiness === "blocked" ? "danger" : "success"} /><div className={styles.reviewActions}>
        {item.closeout_readiness === "ready" && item.overall_status !== "closeout_review" ? <button className={ws.button} disabled={busy} onClick={() => run("submit-closeout", actor("Synthetic Closeout Reviewer"))}>Submit Closeout</button> : null}
        {item.overall_status === "closeout_review" ? <button className={ws.button} disabled={busy} onClick={() => run("approve-closeout", actor("Synthetic Final Reviewer", "Approved synthetic closeout evidence."))}>Approve Closeout</button> : null}
        {item.overall_status === "closed" ? <button className={ws.button} disabled={busy} onClick={loadReceipt}>View Completion Receipt</button> : null}
      </div></div>
    </Panel>
    {receiptData ? <Panel title="Immutable completion receipt" description="UtilitiesPlatform workflow evidence only; external implementation requires separate authorized verification."><pre className={styles.package}>{JSON.stringify(receiptData, null, 2)}</pre></Panel> : null}
  </div>;
}

function History({ item }: { item: WorkOrder }) {
  return <Panel title="Immutable work-order history" description="Definition changes, release decisions, implementation evidence, validation, and closeout remain append-only.">
    <ol className={styles.history}>{item.history.map((event, index) => <li key={`${String(event.action)}-${index}`}><strong>{label(String(event.action))}</strong><span>{String(event.actor || "system")}</span><small>{String(event.created_at || "")}</small></li>)}</ol>
  </Panel>;
}

type RecordEditorProps = {
  item: WorkOrder;
  busy: boolean;
  provider: ReturnType<typeof getDataProvider>;
  onChanged: () => void;
  onError: (value: string) => void;
};
type ActionProps = { item: WorkOrder; busy: boolean; run: (action: string, body?: Record<string, unknown>) => void };

function actor(name: string, notes = "") {
  return { actor: name, reviewer: name, notes };
}
