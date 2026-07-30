"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import { label } from "../../lib/formatters";
import type {
  MappingCandidate,
  MappingField,
  MappingPreview,
  MappingReviewPlan,
  ValueMapping,
} from "../../lib/mapping-review";
import { EmptyState, LoadingSkeleton, OfflineState, Panel, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./mapping-review.module.css";

const steps = [
  "Source Evidence", "Domain and Role", "Canonical Class", "Field Mapping",
  "Value Mapping", "Geometry and Coordinates", "Owner and Jurisdiction",
  "Preview", "Eligibility", "Review", "History",
] as const;

type Filters = {
  domain: string;
  role: string;
  status: string;
  assetClass: string;
  owner: string;
  jurisdiction: string;
  blocker: string;
};

const emptyFilters: Filters = {
  domain: "", role: "", status: "", assetClass: "", owner: "",
  jurisdiction: "", blocker: "",
};

export function MappingReviewWorkspace() {
  const provider = getDataProvider();
  const searchParams = useSearchParams();
  const [candidates, setCandidates] = useState<MappingCandidate[]>([]);
  const [plans, setPlans] = useState<MappingReviewPlan[]>([]);
  const [selected, setSelected] = useState<MappingReviewPlan | null>(null);
  const [activeStep, setActiveStep] = useState<(typeof steps)[number]>("Source Evidence");
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [preview, setPreview] = useState<MappingPreview | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const selectedPlanId = searchParams.get("plan_id") ?? "";

  async function load() {
    try {
      const [candidateData, planData] = await Promise.all([
        provider.get<{ items: MappingCandidate[] }>("/api/utility-assets/water-wastewater/mapping-candidates"),
        provider.get<{ items: MappingReviewPlan[] }>("/api/utility-assets/mapping-plans"),
      ]);
      setCandidates(candidateData.items);
      setPlans(planData.items);
      const plan = planData.items.find((item) => item.plan_id === selectedPlanId);
      if (plan) await openPlan(plan);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mapping review service unavailable.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void Promise.resolve().then(load); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => candidates.filter((item) =>
    (!filters.domain || item.recommended_domain === filters.domain)
    && (!filters.role || item.source_role === filters.role)
    && (!filters.status || item.plan_status === filters.status)
    && (!filters.assetClass || item.recommended_asset_class === filters.assetClass)
    && (!filters.owner || item.owner_status === filters.owner)
    && (!filters.jurisdiction || item.jurisdiction_status === filters.jurisdiction)
    && (!filters.blocker
      || filters.blocker === "review_ready" && item.eligibility_state === "review_ready"
      || filters.blocker === "coordinate" && item.coordinate_status !== "confirmed"
      || filters.blocker === "staging" && item.staging_status !== "approved"),
  ), [candidates, filters]);

  async function openPlan(summary: MappingReviewPlan) {
    const path = planPath(summary);
    const plan = await provider.get<MappingReviewPlan>(path);
    setSelected(plan);
    setPreview(null);
    setMessage("");
    window.history.replaceState({}, "", `?plan_id=${encodeURIComponent(plan.plan_id)}`);
  }

  async function createPlan(candidate: MappingCandidate) {
    try {
      const path = layerPath(candidate.submission_id, candidate.source_layer_id);
      const plan = await provider.post<MappingReviewPlan>(`${path}/mapping-plan`, {});
      await load();
      await openPlan(plan);
      setMessage("Draft mapping plan created. No staging approval or canonical asset was created.");
    } catch (reason) {
      setMessage(safeError(reason));
    }
  }

  async function updatePlan(pathSuffix: string, body: Record<string, unknown>) {
    if (!selected) return;
    try {
      const updated = await provider.post<MappingReviewPlan>(`${planPath(selected)}/${pathSuffix}`, body);
      setSelected(updated);
      setPlans((items) => items.map((item) => item.plan_id === updated.plan_id ? updated : item));
      setMessage(`Mapping plan ${label(pathSuffix)} recorded. Canonical asset creation remains disabled.`);
    } catch (reason) {
      setMessage(safeError(reason));
    }
  }

  async function saveFields(mappings: MappingField[]) {
    if (!selected) return;
    try {
      const updated = await provider.put<MappingReviewPlan>(`${planPath(selected)}/fields`, {
        mappings, actor: "Mapping Reviewer", reason: "Field mapping review.",
      });
      setSelected(updated);
      setMessage("Field mappings saved. Source values remain unchanged.");
    } catch (reason) {
      setMessage(safeError(reason));
    }
  }

  async function saveValues(mappings: ValueMapping[]) {
    if (!selected) return;
    try {
      const updated = await provider.put<MappingReviewPlan>(`${planPath(selected)}/values`, {
        mappings, actor: "Mapping Reviewer", reason: "Value mapping review.",
      });
      setSelected(updated);
      setMessage("Value mappings saved. Original source text is preserved.");
    } catch (reason) {
      setMessage(safeError(reason));
    }
  }

  async function generatePreview() {
    if (!selected) return;
    try {
      const result = await provider.post<MappingPreview>(`${planPath(selected)}/preview`, {});
      setPreview(result);
      setMessage(result.message);
    } catch (reason) {
      setMessage(safeError(reason));
    }
  }

  if (loading) return <div className={ws.workspace}><LoadingSkeleton /><LoadingSkeleton /></div>;
  if (error && !candidates.length) return <div className={ws.workspace}><OfflineState service="Water and wastewater mapping review" /></div>;
  if (selected) {
    return (
      <PlanDetail
        activeStep={activeStep}
        onBack={() => {
          setSelected(null);
          setPreview(null);
          window.history.replaceState({}, "", window.location.pathname);
        }}
        onPreview={generatePreview}
        onSaveFields={saveFields}
        onSaveValues={saveValues}
        onSelectStep={setActiveStep}
        onUpdatePlan={updatePlan}
        plan={selected}
        preview={preview}
        message={message}
      />
    );
  }

  const planById = new Map(plans.map((plan) => [plan.plan_id, plan]));
  return (
    <div className={ws.workspace}>
      {isDemoMode ? (
        <div className={styles.demoNotice} role="status">
          <strong>PORTFOLIO DEMO</strong>
          <span>All source layers, field mappings, preview records, and review decisions in this demo are synthetic and reset with the demo session.</span>
        </div>
      ) : null}
      <section className={styles.summary} aria-label="Mapping plan summary">
        <div><span>Source candidates</span><strong>{candidates.length}</strong></div>
        <div><span>Draft or review</span><strong>{plans.filter((plan) => !["approved_plan", "deferred", "rejected"].includes(plan.status)).length}</strong></div>
        <div><span>Approved plans</span><strong>{plans.filter((plan) => plan.approved_plan).length}</strong></div>
        <div><span>Creation enabled</span><strong>0</strong></div>
      </section>
      <Panel title="Mapping plans" description="Review source evidence before any future staging approval or canonical creation.">
        <div className={styles.filters}>
          <Filter labelText="Domain" value={filters.domain} options={unique(candidates.map((item) => item.recommended_domain))} onChange={(domain) => setFilters({ ...filters, domain })} />
          <Filter labelText="Source role" value={filters.role} options={unique(candidates.map((item) => item.source_role))} onChange={(role) => setFilters({ ...filters, role })} />
          <Filter labelText="Plan status" value={filters.status} options={unique(candidates.map((item) => item.plan_status).filter(Boolean))} onChange={(status) => setFilters({ ...filters, status })} />
          <Filter labelText="Canonical class" value={filters.assetClass} options={unique(candidates.map((item) => item.recommended_asset_class).filter(Boolean))} onChange={(assetClass) => setFilters({ ...filters, assetClass })} />
          <Filter labelText="Owner status" value={filters.owner} options={unique(candidates.map((item) => item.owner_status))} onChange={(owner) => setFilters({ ...filters, owner })} />
          <Filter labelText="Jurisdiction" value={filters.jurisdiction} options={unique(candidates.map((item) => item.jurisdiction_status))} onChange={(jurisdiction) => setFilters({ ...filters, jurisdiction })} />
          <Filter labelText="Gate" value={filters.blocker} options={["review_ready", "coordinate", "staging"]} onChange={(blocker) => setFilters({ ...filters, blocker })} />
        </div>
        {!filtered.length ? <EmptyState title="No matching mapping candidates" message="Adjust the filters or generate recommendations from reviewed source evidence." /> : (
          <div className={styles.tableWrap}>
            <table>
              <thead><tr><th>Plan / source</th><th>Domain</th><th>Role</th><th>Canonical class</th><th>Mappings</th><th>Gates</th><th>Status</th><th><span className={styles.srOnly}>Action</span></th></tr></thead>
              <tbody>{filtered.map((candidate) => {
                const plan = planById.get(candidate.plan_id);
                return (
                  <tr key={`${candidate.submission_id}-${candidate.source_layer_id}`}>
                    <td><strong>{candidate.plan_id || candidate.source_layer}</strong><span>{candidate.source_layer}</span></td>
                    <td><StatusBadge value={candidate.recommended_domain} /><small>{label(candidate.domain_confidence)} confidence</small></td>
                    <td>{label(candidate.source_role)}</td>
                    <td>{label(candidate.recommended_asset_class || "review_required")}<small>{label(candidate.taxonomy_confidence)} confidence</small></td>
                    <td>{plan ? `${plan.mapped_field_count} mapped / ${plan.unmapped_field_count} unmapped` : "Not started"}</td>
                    <td>{candidate.blocker_count} blockers<small>Staging: {label(candidate.staging_status)}</small></td>
                    <td><StatusBadge value={candidate.plan_status || candidate.eligibility_state} /></td>
                    <td>{plan
                      ? <button type="button" onClick={() => void openPlan(plan)}>Review</button>
                      : <button type="button" onClick={() => void createPlan(candidate)}>Create plan</button>}
                    </td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

function PlanDetail({
  activeStep, message, onBack, onPreview, onSaveFields, onSaveValues,
  onSelectStep, onUpdatePlan, plan, preview,
}: {
  activeStep: (typeof steps)[number];
  message: string;
  onBack: () => void;
  onPreview: () => Promise<void>;
  onSaveFields: (mappings: MappingField[]) => Promise<void>;
  onSaveValues: (mappings: ValueMapping[]) => Promise<void>;
  onSelectStep: (step: (typeof steps)[number]) => void;
  onUpdatePlan: (suffix: string, body: Record<string, unknown>) => Promise<void>;
  plan: MappingReviewPlan;
  preview: MappingPreview | null;
}) {
  return (
    <div className={ws.workspace}>
      <div className={styles.detailHeader}>
        <button type="button" onClick={onBack}><calcite-icon icon="arrowLeft" scale="s" aria-hidden="true" /> Mapping plans</button>
        <div><span>{plan.plan_id} - Version {plan.plan_version}</span><h2>{label(plan.target_asset_class || "Mapping review")}</h2><p>{String(plan.source_evidence.source_layer || plan.source_layer_id)}</p></div>
        <StatusBadge value={plan.status} />
      </div>
      {isDemoMode ? <div className={styles.demoNotice} role="status"><strong>PORTFOLIO DEMO</strong><span>All source layers, field mappings, preview records, and review decisions in this demo are synthetic and reset with the demo session.</span></div> : null}
      {message ? <div className={styles.notice} role="status">{message}</div> : null}
      <nav className={styles.steps} aria-label="Mapping review steps">
        {steps.map((step, index) => <button type="button" aria-current={step === activeStep ? "step" : undefined} key={step} onClick={() => onSelectStep(step)}><span>{index + 1}</span>{step}</button>)}
      </nav>
      {activeStep === "Source Evidence" ? <SourceEvidence plan={plan} /> : null}
      {activeStep === "Domain and Role" ? <DomainRole plan={plan} onSave={(body) => onUpdatePlan("recalculate", body)} /> : null}
      {activeStep === "Canonical Class" ? <CanonicalClass plan={plan} onSave={(body) => onUpdatePlan("recalculate", body)} /> : null}
      {activeStep === "Field Mapping" ? <FieldMappings plan={plan} onSave={onSaveFields} /> : null}
      {activeStep === "Value Mapping" ? <ValueMappings plan={plan} onSave={onSaveValues} /> : null}
      {activeStep === "Geometry and Coordinates" ? <GeometryReview plan={plan} /> : null}
      {activeStep === "Owner and Jurisdiction" ? <OwnerReview plan={plan} onSave={(body) => onUpdatePlan("recalculate", body)} /> : null}
      {activeStep === "Preview" ? <Preview plan={plan} preview={preview} onPreview={onPreview} /> : null}
      {activeStep === "Eligibility" ? <EligibilityReview plan={plan} /> : null}
      {activeStep === "Review" ? <ReviewActions plan={plan} onAction={onUpdatePlan} /> : null}
      {activeStep === "History" ? <History plan={plan} /> : null}
    </div>
  );
}

function SourceEvidence({ plan }: { plan: MappingReviewPlan }) {
  const fields = Object.entries(plan.source_evidence).filter(([key]) => !["local_paths_included", "raw_coordinates_included"].includes(key));
  return <Panel title="Stored source evidence" description="Safe metadata only; no local paths, coordinates, or unrestricted values."><dl className={styles.definitionGrid}>{fields.map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{typeof value === "boolean" ? label(String(value)) : String(value)}</dd></div>)}</dl></Panel>;
}

function DomainRole({ plan, onSave }: { plan: MappingReviewPlan; onSave: (body: Record<string, unknown>) => Promise<void> }) {
  const [domain, setDomain] = useState(plan.utility_domain);
  const [role, setRole] = useState(plan.source_role);
  const [notes, setNotes] = useState(String(plan.decisions.reviewer_notes || ""));
  return <Panel title="Domain and source role" description="Recommendations remain provisional until a reviewer confirms them."><div className={styles.formGrid}><LabeledSelect labelText="Selected domain" value={domain} options={["water", "wastewater", "water_wastewater", "multi_utility", "unknown"]} onChange={setDomain} /><LabeledSelect labelText="Source role" value={role} options={["operational_inventory", "reference_inventory", "facility_inventory", "network_context", "service_area", "boundary", "planning_context", "historical", "deprecated", "unknown"]} onChange={setRole} /><label>Reviewer notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label></div><Evidence plan={plan} /><button type="button" onClick={() => void onSave({ utility_domain: domain, source_role: role, reviewer_notes: notes, domain_confirmed: ["water", "wastewater"].includes(domain), actor: "Mapping Reviewer" })}>Save domain and role</button></Panel>;
}

function CanonicalClass({ plan, onSave }: { plan: MappingReviewPlan; onSave: (body: Record<string, unknown>) => Promise<void> }) {
  const [target, setTarget] = useState(plan.target_asset_class);
  return <Panel title="Canonical class recommendation" description="Line geometry alone never determines gravity or pressure behavior."><div className={styles.candidates}>{plan.recommendation.class_candidates.map((item) => <label key={item.asset_class}><input type="radio" name="asset-class" checked={target === item.asset_class} onChange={() => setTarget(item.asset_class)} /><span><strong>{label(item.asset_class)}</strong><small>Evidence score {item.score.toFixed(2)}</small></span></label>)}</div><Evidence plan={plan} /><button type="button" onClick={() => void onSave({ target_asset_class: target, taxonomy_confirmed: true, actor: "Mapping Reviewer" })}>Save class decision</button></Panel>;
}

function FieldMappings({ plan, onSave }: { plan: MappingReviewPlan; onSave: (mappings: MappingField[]) => Promise<void> }) {
  const [items, setItems] = useState(plan.field_mappings);
  function update(index: number, change: Partial<MappingField>) {
    setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...change, human_override: true } : item));
  }
  return <Panel title="Field mappings" description="Allowlisted deterministic transformations only. Source values are never overwritten."><div className={styles.tableWrap}><table><thead><tr><th>Source field</th><th>Canonical field</th><th>Transformation</th><th>Confidence</th><th>Status</th><th>Action</th></tr></thead><tbody>{items.map((item, index) => <tr key={item.mapping_id}><td><strong>{item.source_field}</strong><span>{item.source_alias}</span><small>{item.sample_safe_type_summary}</small></td><td><input aria-label={`Canonical field for ${item.source_field}`} value={item.target_field} onChange={(event) => update(index, { target_field: event.target.value })} /></td><td>{label(item.transformation_type)}</td><td>{label(item.confidence)}</td><td><StatusBadge value={item.mapping_status} /></td><td><button type="button" onClick={() => update(index, item.transformation_type === "unmapped" ? { transformation_type: "renamed", mapping_status: "accepted" } : { target_field: "", transformation_type: "unmapped", mapping_status: "unmapped" })}>{item.transformation_type === "unmapped" ? "Accept recommendation" : "Mark unmapped"}</button></td></tr>)}</tbody></table></div><button type="button" onClick={() => void onSave(items)}>Save field mappings</button></Panel>;
}

function ValueMappings({ plan, onSave }: { plan: MappingReviewPlan; onSave: (mappings: ValueMapping[]) => Promise<void> }) {
  const [items, setItems] = useState(plan.value_mappings);
  return <Panel title="Value mappings" description="Original safe coded text is preserved beside the normalized value."><div className={styles.tableWrap}><table><thead><tr><th>Source field</th><th>Source value</th><th>Target value</th><th>Transformation</th><th>Status</th></tr></thead><tbody>{items.map((item, index) => <tr key={item.value_mapping_id}><td>{item.source_field}</td><td>{item.source_value}</td><td><input aria-label={`Target value for ${item.source_field} ${item.source_value}`} value={item.target_value} onChange={(event) => setItems((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, target_value: event.target.value, human_override: true } : row))} /></td><td>{label(item.transformation_type)}</td><td><StatusBadge value={item.review_status} /></td></tr>)}</tbody></table></div><button type="button" onClick={() => void onSave(items)}>Save value mappings</button></Panel>;
}

function GeometryReview({ plan }: { plan: MappingReviewPlan }) {
  const geometry = plan.recommendation.geometry_compatibility;
  return <Panel title="Geometry and coordinates" description="Review only. Projection, geometry repair, and endpoint snapping are unavailable."><dl className={styles.definitionGrid}>{Object.entries(geometry).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{label(value)}</dd></div>)}<div><dt>Coordinate status</dt><dd><StatusBadge value={plan.coordinate_status} /></dd></div><div><dt>Source freshness</dt><dd><StatusBadge value={plan.source_fingerprint_status} /></dd></div></dl><div className={styles.warning}>No geometry modification controls are available in Mapping Review V1.</div></Panel>;
}

function OwnerReview({ plan, onSave }: { plan: MappingReviewPlan; onSave: (body: Record<string, unknown>) => Promise<void> }) {
  const [owner, setOwner] = useState(String(plan.decisions.owner_candidate || ""));
  const [jurisdiction, setJurisdiction] = useState(String(plan.decisions.jurisdiction_candidate || ""));
  return <Panel title="Owner and jurisdiction review" description="Candidates are provisional until human confirmation."><div className={styles.formGrid}><label>Provisional owner candidate<input value={owner} onChange={(event) => setOwner(event.target.value)} /></label><label>Provisional jurisdiction candidate<input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} /></label></div><button type="button" onClick={() => void onSave({ owner_candidate: owner, jurisdiction_candidate: jurisdiction, owner_status: "confirmed", jurisdiction_status: "confirmed", actor: "Mapping Reviewer" })}>Confirm reviewed values</button></Panel>;
}

function Preview({ plan, preview, onPreview }: { plan: MappingReviewPlan; preview: MappingPreview | null; onPreview: () => Promise<void> }) {
  return <Panel title="Canonical preview" description="Preview only - no canonical asset has been created." action={<button type="button" onClick={() => void onPreview()}>Generate safe preview</button>}>{preview ? <><div className={styles.previewNotice}>{preview.message}</div>{preview.items.length ? <div className={styles.tableWrap}><table><thead><tr><th>Proposed ID</th><th>Class</th><th>Mapped identifier</th><th>Confidence</th><th>Status</th></tr></thead><tbody>{preview.items.map((item) => <tr key={String(item.preview_id)}><td>{String(item.proposed_canonical_identifier)}</td><td>{label(String(item.canonical_class))}</td><td>{String(item.mapped_asset_identifier)}</td><td>{label(String(item.mapping_confidence))}</td><td>Preview only</td></tr>)}</tbody></table></div> : <pre>{JSON.stringify(preview.aggregate, null, 2)}</pre>}</> : <EmptyState title="No preview generated" message={`${plan.preview_record_count} prior preview records are recorded; generate a current safe preview to inspect this version.`} />}</Panel>;
}

function EligibilityReview({ plan }: { plan: MappingReviewPlan }) {
  return <Panel title="Eligibility and blockers" description="Each gate is independent; mapping approval never replaces final staging approval."><div className={styles.gates}>{Object.entries(plan.eligibility.gates).map(([key, gate]) => <div key={key}><StatusBadge value={gate.status} /><strong>{label(key)}</strong><span>{gate.reason}</span></div>)}</div><div className={styles.warning}><strong>{plan.approved_plan ? "Approved mapping plan" : "Canonical creation blocked"}</strong><span>{plan.eligibility.creation_disabled_reason}</span></div></Panel>;
}

function ReviewActions({ plan, onAction }: { plan: MappingReviewPlan; onAction: (suffix: string, body: Record<string, unknown>) => Promise<void> }) {
  const actions = [
    ["submit", "Submit for Review"], ["start-review", "Start Review"],
    ["request-revision", "Request Revision"], ["approve", "Approve Mapping Plan"],
    ["defer", "Defer"], ["reject", "Reject"], ["new-version", "Create New Version"],
  ];
  return <Panel title="Human review" description="Approval confirms only the reviewed mapping plan."><div className={styles.actionBar}>{actions.map(([action, text]) => <button type="button" key={action} onClick={() => void onAction(action, { actor: "Mapping Reviewer", approved_by: "Mapping Reviewer", reason: `${text} from mapping review.` })}>{text}</button>)}</div><div className={styles.disabledAction}><button type="button" disabled>Create Canonical Assets</button><span>{plan.eligibility.creation_disabled_reason}</span></div></Panel>;
}

function History({ plan }: { plan: MappingReviewPlan }) {
  return <Panel title="Immutable mapping history" description="Every review decision and version change is append-only."><ol className={styles.history}>{plan.history.map((item, index) => <li key={String(item.history_id || index)}><strong>{label(String(item.action))}</strong><span>{String(item.actor)} - {String(item.created_at)}</span><p>{String(item.reason || "")}</p></li>)}</ol></Panel>;
}

function Evidence({ plan }: { plan: MappingReviewPlan }) {
  return <div className={styles.evidence}><div><strong>Evidence</strong><span>{plan.recommendation.evidence_categories.map(label).join(", ") || "No supporting evidence recorded."}</span></div><div><strong>Contradictions</strong><span>{plan.recommendation.contradictory_evidence.join("; ") || "None recorded."}</span></div></div>;
}

function Filter({ labelText, value, options, onChange }: { labelText: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <LabeledSelect labelText={labelText} value={value} options={options} onChange={onChange} allowAll />;
}

function LabeledSelect({ labelText, value, options, onChange, allowAll = false }: { labelText: string; value: string; options: string[]; onChange: (value: string) => void; allowAll?: boolean }) {
  return <label>{labelText}<select value={value} onChange={(event) => onChange(event.target.value)}>{allowAll ? <option value="">All</option> : null}{options.map((option) => <option value={option} key={option}>{label(option)}</option>)}</select></label>;
}

function planPath(plan: Pick<MappingReviewPlan, "submission_id" | "source_layer_id">) {
  return `${layerPath(plan.submission_id, plan.source_layer_id)}/mapping-plan`;
}

function layerPath(submissionId: string, layerId: string) {
  return `/api/intake/submissions/${encodeURIComponent(submissionId)}/layers/${encodeURIComponent(layerId)}`;
}

function safeError(reason: unknown) {
  return reason instanceof Error ? reason.message : "Mapping review action failed safely.";
}

function unique(items: string[]) {
  return [...new Set(items)].sort();
}
