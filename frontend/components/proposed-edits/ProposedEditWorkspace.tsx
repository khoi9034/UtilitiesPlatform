"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import { label } from "../../lib/formatters";
import type { ProposedEdit, ProposedOperation } from "../../lib/proposed-edits";
import type { UtilityAsset } from "../../lib/utility-assets";
import { getUtilityVerticalByCanonical, utilityViewPath, type UtilityVerticalConfig } from "../../lib/utility-verticals";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, PageHeader, Panel, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./proposed-edits.module.css";

type ListResponse = { items: ProposedEdit[]; pagination: { total: number } };
type TypeCatalog = { proposal_types: string[]; operation_types: string[]; disclaimer: string };
type AssetResponse = { items: UtilityAsset[] };
const steps = ["Define", "Operations", "Validate", "Analyze", "Compare", "Review", "Approval", "Package"] as const;
type Step = (typeof steps)[number];

export function ProposedEditWorkspace({ config }: { config: UtilityVerticalConfig }) {
  const provider = getDataProvider();
  const vertical = config.canonicalValue;
  const [proposals, setProposals] = useState<ProposedEdit[]>([]);
  const [selected, setSelected] = useState<ProposedEdit | null>(null);
  const [catalog, setCatalog] = useState<TypeCatalog | null>(null);
  const [assets, setAssets] = useState<UtilityAsset[]>([]);
  const [step, setStep] = useState<Step>("Define");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [packageData, setPackageData] = useState<Record<string, unknown> | null>(null);

  const load = async (preferredId = "") => {
    setError("");
    try {
      const [list, types, assetData] = await Promise.all([
        provider.get<ListResponse>(`/api/proposed-edits/${vertical}`),
        provider.get<TypeCatalog>(`/api/proposed-edits/types/${vertical}`),
        provider.get<AssetResponse>(`/api/utility-assets?utility_vertical=${vertical}&limit=500`),
      ]);
      setProposals(list.items);
      setCatalog(types);
      setAssets(assetData.items);
      const id = preferredId || selected?.proposal_id || list.items[0]?.proposal_id;
      if (id) setSelected(await provider.get<ProposedEdit>(`/api/proposed-edits/${vertical}/${encodeURIComponent(id)}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Proposed Edit workspace is unavailable.");
    }
  };

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [vertical]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => proposals.filter((proposal) =>
    (!status || proposal.status === status)
    && (!type || proposal.proposal_type === type)
    && (!search || `${proposal.title} ${proposal.scenario_code} ${proposal.proposal_id}`.toLowerCase().includes(search.toLowerCase())),
  ), [proposals, search, status, type]);

  const run = async (action: string, body: Record<string, unknown> = {}) => {
    if (!selected) return;
    if (["approve", "reject", "withdraw", "implementation-package"].includes(action)
      && !window.confirm(`Confirm ${label(action)} for this vendor-neutral change plan?`)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await provider.post<Record<string, unknown>>(
        `/api/proposed-edits/${vertical}/${encodeURIComponent(selected.proposal_id)}/${action}`,
        body,
      );
      if (action === "implementation-package") setPackageData(result);
      setMessage(`${label(action)} completed. No canonical or source records were changed.`);
      await load(selected.proposal_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Proposal action failed safely.");
    } finally { setBusy(false); }
  };

  if (error && !catalog) return <OfflineState service={`Proposed Edit workspace: ${error}`} />;
  if (!catalog) return <LoadingSkeleton />;
  return (
    <div className={styles.workspace}>
      <PageHeader
        eyebrow={isDemoMode ? "PORTFOLIO DEMO" : "Vendor-neutral controlled change"}
        title={`${config.shortTitle} Proposed Edits`}
        subtitle="Create isolated change plans, evaluate temporary overlays, and preserve human approval without applying operational edits."
      />
      <div className={styles.safety} role="note">
        <calcite-icon icon="lock" scale="s" aria-hidden="true" />
        <span><strong>Proposal workspace only.</strong> Canonical assets, source records, staged geometry, operational states, and vendor systems remain unchanged.</span>
      </div>
      {config.id === "electric" ? <div className={styles.operationalWarning}>This is a proposed data change, not a switching instruction.</div> : null}
      {["water", "wastewater"].includes(config.canonicalValue) ? <div className={styles.operationalWarning}>This proposal changes review evidence only. It does not operate equipment, edit source geometry, or run a hydraulic simulation.</div> : null}
      {message ? <div className={styles.message} role="status">{message}</div> : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}
      <section className={styles.metrics} aria-label="Proposal metrics">
        <MetricTile labelText="Proposals" value={String(proposals.length)} detail={`${config.shortTitle} synthetic and local plans`} />
        <MetricTile labelText="Analysis complete" value={String(proposals.filter((item) => item.analysis_status === "complete").length)} detail="Temporary evidence available" />
        <MetricTile labelText="Validation blocked" value={String(proposals.filter((item) => item.validation_status === "failed").length)} detail="Requires revision" />
        <MetricTile labelText="Approved plans" value={String(proposals.filter((item) => item.approval_status === "approved").length)} detail="Not implemented" />
      </section>
      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <div className={styles.sidebarHeader}>
            <div><span>Proposal registry</span><strong>{filtered.length} visible</strong></div>
            <button className={ws.button} type="button" onClick={() => setShowCreate((value) => !value)}>
              <calcite-icon icon="plus" scale="s" aria-hidden="true" /> New
            </button>
          </div>
          {showCreate ? <CreateProposal catalog={catalog} onCancel={() => setShowCreate(false)} onCreate={async (body) => {
            setBusy(true);
            try {
              const created = await provider.post<ProposedEdit>(`/api/proposed-edits/${vertical}`, body);
              setShowCreate(false); await load(created.proposal_id); setMessage("Draft proposal created.");
            } catch (reason) { setError(reason instanceof Error ? reason.message : "Proposal creation failed safely."); }
            finally { setBusy(false); }
          }} /> : null}
          <div className={styles.filters}>
            <label>Search<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title or scenario" /></label>
            <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All states</option>{[...new Set(proposals.map((item) => item.status))].map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Proposal type<select value={type} onChange={(event) => setType(event.target.value)}><option value="">All types</option>{catalog.proposal_types.map((item) => <option key={item}>{item}</option>)}</select></label>
          </div>
          <div className={styles.proposalList} aria-label={`${config.title} proposals`}>
            {filtered.map((proposal) => (
              <button
                type="button"
                className={proposal.proposal_id === selected?.proposal_id ? styles.selectedProposal : styles.proposal}
                key={proposal.proposal_id}
                onClick={async () => {
                  setSelected(await provider.get<ProposedEdit>(`/api/proposed-edits/${vertical}/${encodeURIComponent(proposal.proposal_id)}`));
                  setStep("Define"); setPackageData(null);
                }}
              >
                <span>{proposal.scenario_code || `Version ${proposal.proposal_version}`}</span>
                <strong>{proposal.title}</strong>
                <small>{label(proposal.status)} / {proposal.operation_count ?? proposal.operations?.length ?? 0} operations</small>
              </button>
            ))}
          </div>
        </aside>
        <main className={styles.detail}>
          {!selected ? <EmptyState title="Select a proposal" message="Choose an existing scenario or create a draft change plan." /> : (
            <>
              <ProposalHeader proposal={selected} />
              <nav className={styles.steps} aria-label="Proposal workflow">
                {steps.map((item, index) => <button key={item} type="button" className={step === item ? styles.activeStep : ""} onClick={() => setStep(item)}><span>{index + 1}</span>{item}</button>)}
              </nav>
              {step === "Define" ? <DefineView proposal={selected} config={config} /> : null}
              {step === "Operations" ? <OperationsView proposal={selected} catalog={catalog} assets={assets} busy={busy} provider={provider} onChanged={() => load(selected.proposal_id)} onError={setError} /> : null}
              {step === "Validate" ? <ValidationView proposal={selected} busy={busy} onValidate={() => run("validate", { actor: "Local Proposal Author" })} /> : null}
              {step === "Analyze" ? <AnalysisView proposal={selected} busy={busy} onAnalyze={() => run("analyze", { actor: "Local Proposal Author" })} /> : null}
              {step === "Compare" ? <ComparisonView proposal={selected} config={config} /> : null}
              {step === "Review" ? <ReviewView proposal={selected} busy={busy} run={run} /> : null}
              {step === "Approval" ? <ApprovalView proposal={selected} busy={busy} run={run} /> : null}
              {step === "Package" ? <PackageView proposal={selected} packageData={packageData} busy={busy} onCreate={() => run("implementation-package", { actor: "Synthetic Reviewer", notes: "Create descriptive package." })} /> : null}
            </>
          )}
        </main>
      </div>
      <p className={styles.disclaimer}>{catalog.disclaimer}</p>
    </div>
  );
}

function CreateProposal({ catalog, onCancel, onCreate }: { catalog: TypeCatalog; onCancel: () => void; onCreate: (body: Record<string, unknown>) => void }) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState(catalog.proposal_types[0] ?? "");
  return <form className={styles.createForm} onSubmit={(event) => { event.preventDefault(); onCreate({ title, proposal_type: type, created_by: isDemoMode ? "Demo Author" : "Local Proposal Author", summary: "Vendor-neutral proposed change plan." }); }}>
    <label>Title<input required maxLength={180} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
    <label>Proposal type<select value={type} onChange={(event) => setType(event.target.value)}>{catalog.proposal_types.map((item) => <option key={item}>{item}</option>)}</select></label>
    <div className={styles.formActions}><button type="button" onClick={onCancel}>Cancel</button><button className={ws.button} type="submit">Create draft</button></div>
  </form>;
}

function ProposalHeader({ proposal }: { proposal: ProposedEdit }) {
  return <header className={styles.proposalHeader}>
    <div><span>{proposal.scenario_code || `Proposal version ${proposal.proposal_version}`}</span><h2>{proposal.title}</h2><p>{label(proposal.proposal_type)}</p></div>
    <div className={styles.headerStatuses}><StatusBadge value={proposal.status} tone={proposal.validation_status === "failed" ? "danger" : proposal.approval_status === "approved" ? "success" : "neutral"} /><span>v{proposal.proposal_version}</span></div>
  </header>;
}

function DefineView({ proposal, config }: { proposal: ProposedEdit; config: UtilityVerticalConfig }) {
  return <div className={styles.viewGrid}>
    <Panel title="Change definition" description={proposal.summary || "No additional summary supplied."}>
      <dl className={styles.definition}>
        <div><dt>Utility vertical</dt><dd>{config.title}</dd></div><div><dt>Proposal type</dt><dd>{label(proposal.proposal_type)}</dd></div>
        <div><dt>Author</dt><dd>{proposal.created_by}</dd></div><div><dt>Version</dt><dd>{proposal.proposal_version}</dd></div>
        <div><dt>Baseline</dt><dd className={styles.fingerprint}>{proposal.baseline_fingerprint}</dd></div><div><dt>Implementation</dt><dd>Not implemented</dd></div>
      </dl>
    </Panel>
    <Panel title="Fixed baseline" description="Analysis fails closed if canonical assets, relationships, QA rules, or trace rules change.">
      <div className={styles.stack}><StatusBadge value="baseline captured" tone="success" /><span>Operations are evaluated against an isolated sparse overlay.</span><span>No GIS feature class or operational transaction is created.</span></div>
    </Panel>
  </div>;
}

function OperationsView({ proposal, catalog, assets, busy, provider, onChanged, onError }: { proposal: ProposedEdit; catalog: TypeCatalog; assets: UtilityAsset[]; busy: boolean; provider: ReturnType<typeof getDataProvider>; onChanged: () => void; onError: (value: string) => void }) {
  const [showEditor, setShowEditor] = useState(false);
  const [operationType, setOperationType] = useState("update_asset_attribute");
  const [target, setTarget] = useState(assets[0]?.asset_id ?? "");
  const [field, setField] = useState("");
  const [value, setValue] = useState("");
  const [related, setRelated] = useState(assets[1]?.asset_id ?? "");
  const [relationshipType, setRelationshipType] = useState("connects_to");
  const [reason, setReason] = useState("");
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const body: Record<string, unknown> = { operation_type: operationType, reason };
    if (operationType.includes("relationship") || operationType.startsWith("associate_")) Object.assign(body, { from_asset_id: target, to_asset_id: related, relationship_type: relationshipType });
    else if (operationType === "add_asset") Object.assign(body, { new_asset_temporary_id: `PROP-${proposal.proposal_id}-${proposal.operations.length + 1}`, proposed_values: { asset_class: value || "junction", lifecycle_status: "proposed" } });
    else Object.assign(body, { target_asset_id: target, field_name: field, proposed_value: parseValue(value) });
    try { await provider.post(`/api/proposed-edits/${proposal.utility_vertical}/${encodeURIComponent(proposal.proposal_id)}/operations`, body); setShowEditor(false); onChanged(); }
    catch (error) { onError(error instanceof Error ? error.message : "Operation was rejected safely."); }
  };
  return <div className={styles.stack}>
    <div className={styles.viewToolbar}><div><strong>Ordered operations</strong><span>{proposal.locked ? "Submitted version is immutable." : "Each change is allowlisted and proposal-only."}</span></div>{!proposal.locked ? <button className={ws.button} type="button" onClick={() => setShowEditor((open) => !open)}><calcite-icon icon="plus" scale="s" aria-hidden="true" /> Add operation</button> : null}</div>
    {showEditor ? <form className={styles.operationForm} onSubmit={submit}>
      <label>Operation type<select value={operationType} onChange={(event) => setOperationType(event.target.value)}>{catalog.operation_types.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label>Target asset<select value={target} onChange={(event) => setTarget(event.target.value)}>{assets.map((item) => <option key={item.asset_id} value={item.asset_id}>{item.canonical_name} / {label(item.asset_class)}</option>)}</select></label>
      {operationType.includes("relationship") || operationType.startsWith("associate_") ? <>
        <label>Related asset<select value={related} onChange={(event) => setRelated(event.target.value)}>{assets.map((item) => <option key={item.asset_id} value={item.asset_id}>{item.canonical_name}</option>)}</select></label>
        <label>Relationship type<select value={relationshipType} onChange={(event) => setRelationshipType(event.target.value)}>{["connects_to", "feeds", "terminates_at", "routed_through", "mounted_on", "belongs_to_feeder", "belongs_to_route"].map((item) => <option key={item}>{item}</option>)}</select></label>
      </> : <>
        <label>Canonical field<input value={field} onChange={(event) => setField(event.target.value)} placeholder="phase, feeder_id, available_capacity" /></label>
        <label>Proposed value<input value={value} onChange={(event) => setValue(event.target.value)} /></label>
      </>}
      <label className={styles.wide}>Reason<textarea required value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <div className={styles.formActions}><button type="button" onClick={() => setShowEditor(false)}>Cancel</button><button className={ws.button} disabled={busy} type="submit">Add proposal operation</button></div>
    </form> : null}
    {proposal.operations.length ? <div className={styles.operationList}>{proposal.operations.map((item) => <OperationCard key={item.operation_id} operation={item} />)}</div> : <EmptyState title="No operations yet" message="Add one allowlisted proposed operation before validation." />}
  </div>;
}

function OperationCard({ operation }: { operation: ProposedOperation }) {
  return <article className={styles.operationCard}>
    <span className={styles.sequence}>{operation.sequence}</span>
    <div><strong>{label(operation.operation_type)}</strong><p>{operation.reason}</p><small>{operation.target_asset_id || operation.from_asset_id || operation.new_asset_temporary_id || "Proposal annotation"}{operation.field_name ? ` / ${label(operation.field_name)}: ${String(operation.proposed_value)}` : ""}</small></div>
    <StatusBadge value={operation.validation_status} tone={operation.validation_status === "failed" ? "danger" : operation.validation_status === "passed" ? "success" : "neutral"} />
  </article>;
}

function ValidationView({ proposal, busy, onValidate }: { proposal: ProposedEdit; busy: boolean; onValidate: () => void }) {
  const errors = proposal.operations.flatMap((item) => item.validation_errors ?? []);
  return <Panel title="Deterministic validation" description="Checks baseline freshness, operation allowlists, target compatibility, lifecycle transitions, contradictions, and vertical-specific constraints.">
    <div className={styles.actionRow}><StatusBadge value={proposal.validation_status} tone={proposal.validation_status === "failed" ? "danger" : proposal.validation_status === "passed" ? "success" : "neutral"} />{!proposal.locked ? <button className={ws.button} disabled={busy} onClick={onValidate}>Validate operations</button> : null}</div>
    {errors.length ? <ul className={styles.findings}>{errors.map((item, index) => <li key={`${item.code}-${index}`}><strong>{label(item.code)}</strong><span>{item.message}</span></li>)}</ul> : <p className={styles.emptyEvidence}>{proposal.validation_status === "passed" ? "All proposal operations passed the V1 validation profile." : "Validation has not run."}</p>}
  </Panel>;
}

function AnalysisView({ proposal, busy, onAnalyze }: { proposal: ProposedEdit; busy: boolean; onAnalyze: () => void }) {
  return <div className={styles.viewGrid}>
    <Panel title="Temporary overlay analysis" description="Runs Connectivity QA, calibration, selected traces, and trace calibration against effective proposal state.">
      <div className={styles.actionRow}><StatusBadge value={proposal.analysis_status} tone={proposal.analysis_status === "complete" ? "success" : "neutral"} />{!proposal.locked ? <button className={ws.button} disabled={busy || proposal.validation_status === "failed"} onClick={onAnalyze}>Analyze temporary state</button> : null}</div>
      <p className={styles.emptyEvidence}>Proposed overlay - no canonical or source records have been changed.</p>
    </Panel>
    <Panel title="Overlay fingerprint" description="Deterministic evidence supports reuse and stale-baseline detection."><code className={styles.code}>{proposal.overlay_fingerprint || "Not generated"}</code></Panel>
  </div>;
}

function ComparisonView({ proposal, config }: { proposal: ProposedEdit; config: UtilityVerticalConfig }) {
  const qa = proposal.qa_comparison;
  const trace = proposal.trace_comparisons[0];
  if (!qa) return <EmptyState title="No comparison available" message="Validate and analyze the proposal first." />;
  return <div className={styles.stack}>
    <section className={styles.compareGrid} aria-label="QA before and after">
      <CompareValue labelText="QA blockers" before={qa.baseline_blocker_count} after={qa.proposed_blocker_count} />
      <CompareValue labelText="QA warnings" before={qa.baseline_warning_count} after={qa.proposed_warning_count} />
      <MetricTile labelText="Resolved groups" value={String(qa.resolved_issue_group_ids.length)} detail="Primary candidates no longer present" />
      <MetricTile labelText="New groups" value={String(qa.new_issue_group_ids.length)} detail="Must be reviewed before approval" />
    </section>
    <Panel title="Connectivity QA comparison" description="Candidate findings are compared by calibrated root-cause identity; raw QA evidence remains immutable.">
      <div className={styles.deltaLists}><div><strong>Resolved</strong><ul>{qa.resolved_issue_group_ids.map((item) => <li key={item}>{item}</li>) || null}</ul></div><div><strong>New or worsened</strong><ul>{[...qa.new_issue_group_ids, ...qa.worsened_issue_group_ids].map((item) => <li key={item}>{item}</li>)}</ul></div></div>
    </Panel>
    <Panel title="Network Trace comparison" description={`${config.shortTitle} path evidence before and after the proposal overlay.`}>
      {trace ? <div className={styles.traceCompare}>
        <div><span>Before</span><strong>{label(trace.baseline_outcome)}</strong><small>{label(trace.baseline_confidence)} confidence / objective {trace.baseline_objective_reached ? "reached" : "not reached"}</small></div>
        <calcite-icon icon="arrowRight" scale="m" aria-hidden="true" />
        <div><span>After</span><strong>{label(trace.proposed_outcome)}</strong><small>{label(trace.proposed_confidence)} confidence / objective {trace.proposed_objective_reached ? "reached" : "not reached"}</small></div>
        <StatusBadge value={trace.result} tone={trace.result === "improved" ? "success" : trace.result === "worsened" ? "danger" : "neutral"} />
      </div> : <p>No relevant trace was selected.</p>}
    </Panel>
  </div>;
}

function CompareValue({ labelText, before, after }: { labelText: string; before: number; after: number }) {
  return <article className={styles.compareValue}><span>{labelText}</span><div><strong>{before}</strong><calcite-icon icon="arrowRight" scale="s" aria-hidden="true" /><strong>{after}</strong></div><small>{after < before ? "Improved" : after > before ? "Worsened" : "Unchanged"}</small></article>;
}

function ReviewView({ proposal, busy, run }: { proposal: ProposedEdit; busy: boolean; run: (action: string, body?: Record<string, unknown>) => void }) {
  const notes = "Synthetic technical review confirms the plan and its proposal-only limitations.";
  return <div className={styles.stack}>
    <Panel title="Human review workflow" description="Submission locks this version. Review decisions and notes are preserved as immutable events.">
      <div className={styles.reviewActions}>
        {proposal.status === "analysis_complete" || proposal.status === "needs_revision" ? <button className={ws.button} disabled={busy} onClick={() => run("submit", { actor: isDemoMode ? "Demo Author" : "Local Proposal Author" })}>Submit for Review</button> : null}
        {proposal.status === "submitted_for_review" ? <button className={ws.button} disabled={busy} onClick={() => run("start-review", { reviewer: "Synthetic Reviewer", reviewer_role: "technical_reviewer" })}>Start Review</button> : null}
        {proposal.status === "under_review" ? <button disabled={busy} onClick={() => run("request-revision", { reviewer: "Synthetic Reviewer", reviewer_role: "technical_reviewer", notes })}>Request Revision</button> : null}
        {["analysis_complete", "submitted_for_review", "under_review", "needs_revision"].includes(proposal.status) ? <button disabled={busy} onClick={() => run("defer", { reviewer: "Synthetic Reviewer", reviewer_role: "data_steward", notes })}>Defer</button> : null}
        {["draft", "analysis_complete", "needs_revision", "submitted_for_review"].includes(proposal.status) ? <button disabled={busy} onClick={() => run("withdraw", { actor: proposal.created_by })}>Withdraw</button> : null}
      </div>
    </Panel>
    <History events={proposal.history} />
  </div>;
}

function ApprovalView({ proposal, busy, run }: { proposal: ProposedEdit; busy: boolean; run: (action: string, body?: Record<string, unknown>) => void }) {
  const ready = proposal.status === "under_review" && proposal.validation_status === "passed" && proposal.analysis_status === "complete";
  return <div className={styles.stack}>
    <Panel title="Change-plan approval" description="Approval confirms the vendor-neutral plan only. It does not apply, switch, provision, publish, or implement anything.">
      <div className={styles.approvalBox}>
        <StatusBadge value={proposal.approval_status} tone={proposal.approval_status === "approved" ? "success" : "neutral"} />
        <ul><li>Validation passed: {proposal.validation_status === "passed" ? "Yes" : "No"}</li><li>Analysis complete: {proposal.analysis_status === "complete" ? "Yes" : "No"}</li><li>Baseline preserved: Yes</li><li>Implementation status: Not implemented</li></ul>
        {ready ? <button className={ws.button} disabled={busy} onClick={() => run("approve", { reviewer: "Synthetic Reviewer", reviewer_role: "final_approver", notes: "Reviewed synthetic plan and accepted proposal-only limitations.", acknowledge_new_blockers: false })}><calcite-icon icon="checkCircle" scale="s" aria-hidden="true" /> Approve Change Plan</button> : null}
        {proposal.approval_status === "approved" ? <>
          <strong className={styles.approved}>Approved plan - not implemented in any operational utility system.</strong>
          <Link className={ws.button} href={utilityViewPath(
            { ...getUtilityVerticalByCanonical(proposal.utility_vertical)!, canonicalValue: proposal.utility_vertical },
            "work-orders",
            { proposal_id: proposal.proposal_id },
          )}>Create Work Order</Link>
        </> : null}
      </div>
    </Panel>
    <History events={proposal.reviews} />
  </div>;
}

function PackageView({ proposal, packageData, busy, onCreate }: { proposal: ProposedEdit; packageData: Record<string, unknown> | null; busy: boolean; onCreate: () => void }) {
  return <Panel title="Safe implementation package" description="A descriptive, nonexecutable JSON change plan for a future licensed-system adapter and organization-specific review.">
    <div className={styles.packageHeader}><div><StatusBadge value={proposal.implementation_readiness} /><span>External mapping: adapter required</span></div><button className={ws.button} disabled={busy || proposal.approval_status !== "approved"} onClick={onCreate}>Generate safe package</button></div>
    {packageData ? <pre className={styles.package}>{JSON.stringify(packageData, null, 2)}</pre> : <p className={styles.emptyEvidence}>{proposal.approval_status === "approved" ? "The approved plan is eligible for a descriptive package." : "Approve the change plan before package generation."}</p>}
  </Panel>;
}

function History({ events }: { events: Array<Record<string, unknown>> }) {
  return <Panel title="Immutable history" description="Proposal actions remain version-specific and append-only.">
    {events.length ? <ol className={styles.history}>{events.map((event, index) => <li key={`${String(event.action)}-${index}`}><strong>{label(String(event.action || "event"))}</strong><span>{String(event.actor || event.reviewer || "system")}</span><small>{String(event.created_at || "")}</small></li>)}</ol> : <p className={styles.emptyEvidence}>No review events yet.</p>}
  </Panel>;
}

function parseValue(value: string) {
  if (value === "true") return true;
  if (value === "false") return false;
  const numeric = Number(value);
  return value.trim() && Number.isFinite(numeric) ? numeric : value;
}
