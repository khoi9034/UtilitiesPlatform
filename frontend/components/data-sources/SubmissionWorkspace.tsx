"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import type { ClassificationCandidate, DuplicateGroup, IntakeEvent, IntakeSubmission, SourceInspectionStatus, StagingPlanItem, SubmissionLayer } from "../../lib/data-provider/types";
import { compactNumber, label, safeText, shortDate } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, MetricTile, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./data-sources.module.css";

const tabs = ["Overview", "Layers", "Needs Review", "Duplicate Candidates", "Coordinate Review", "Staging Plan", "Events"] as const;
type Tab = typeof tabs[number];
type FilterState = { utility_system: string; owner: string; confidence: string; routing_state: string; duplicate_status: string; coordinate_status: string; operational_role: string; lifecycle_representation: string; search: string };

export function SubmissionWorkspace() {
  const provider = getDataProvider();
  const [submissionId, setSubmissionId] = useState("");
  const [submission, setSubmission] = useState<IntakeSubmission | null>(null);
  const [events, setEvents] = useState<IntakeEvent[]>([]);
  const [inspection, setInspection] = useState<SourceInspectionStatus | null>(null);
  const [layers, setLayers] = useState<SubmissionLayer[]>([]);
  const [duplicateGroups, setDuplicateGroups] = useState<DuplicateGroup[]>([]);
  const [stagingPlan, setStagingPlan] = useState<StagingPlanItem[]>([]);
  const [selectedLayerId, setSelectedLayerId] = useState("");
  const [selectedLayer, setSelectedLayer] = useState<SubmissionLayer | null>(null);
  const [candidates, setCandidates] = useState<ClassificationCandidate[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>(() => initialTab());
  const [filters, setFilters] = useState<FilterState>({ utility_system: "", owner: "", confidence: "", routing_state: "", duplicate_status: "", coordinate_status: "", operational_role: "", lifecycle_representation: "", search: "" });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void Promise.resolve().then(() => setSubmissionId(initialSubmissionId()));
  }, []);

  async function load() {
    setLoading(true);
    const results = await Promise.allSettled([
      provider.getIntakeSubmission(submissionId),
      provider.getIntakeEvents(submissionId),
      provider.getSourceInspectionStatus(submissionId),
      provider.getSubmissionLayers(submissionId, layerQuery()),
      provider.getDuplicateGroups(submissionId),
      provider.getStagingPlan(submissionId),
    ]);
    if (results[0].status === "fulfilled") setSubmission(results[0].value); else setMessage("Submission is unavailable.");
    if (results[1].status === "fulfilled") setEvents(results[1].value.events);
    if (results[2].status === "fulfilled") setInspection(results[2].value);
    if (results[3].status === "fulfilled") {
      const loadedLayers = results[3].value.items;
      setLayers(loadedLayers);
      setSelectedLayerId((current) => loadedLayers.some((layer) => layer.layer_id === current) ? current : loadedLayers[0]?.layer_id ?? "");
      if (!loadedLayers.length) {
        setSelectedLayer(null);
        setCandidates([]);
      }
    }
    if (results[4].status === "fulfilled") setDuplicateGroups(results[4].value.items);
    if (results[5].status === "fulfilled") setStagingPlan(results[5].value.items);
    setLoading(false);
  }

  async function runInspection() {
    const result = await provider.startSourceInspection(submissionId);
    await load();
    setMessage(String(result.message ?? "Source inspection finished. Human approval is still required before staging."));
  }

  async function approveLayer(layer: SubmissionLayer) {
    await provider.reviewSubmissionLayer(submissionId, layer.layer_id, {
      workflow_status: "classification_approved",
      classification_decision: "approve_top_candidate",
      sensitivity_decision: "complete",
      reviewer: isDemoMode ? "demo_reviewer" : "local_reviewer",
      review_notes: "Approved top candidate for staging-plan consideration.",
    });
    await load();
    setSelectedLayerId(layer.layer_id);
    setMessage("Layer review saved. Staging approval is still a separate gate.");
  }

  async function deferLayer(layer: SubmissionLayer) {
    await provider.reviewSubmissionLayer(submissionId, layer.layer_id, {
      workflow_status: "deferred",
      classification_decision: "deferred",
      reviewer: isDemoMode ? "demo_reviewer" : "local_reviewer",
      review_notes: "Deferred pending source-owner confirmation.",
      data_owner_confirmation_required: true,
    });
    await load();
    setSelectedLayerId(layer.layer_id);
    setMessage("Layer deferred for source-owner confirmation.");
  }

  async function resolveDuplicate(group: DuplicateGroup, status: string) {
    await provider.reviewDuplicateGroup(submissionId, group.duplicate_group_id, { status, reviewer: isDemoMode ? "demo_reviewer" : "local_reviewer" });
    await load();
    setMessage("Duplicate review decision recorded.");
  }

  async function approvePlanItem(item: StagingPlanItem) {
    if (item.blocker && !isDemoMode) {
      setMessage(`Staging approval blocked: ${item.blocker}`);
      return;
    }
    await provider.reviewStagingPlanItem(submissionId, item.staging_plan_item_id, {
      approved_for_staging: true,
      approval_status: "approved",
      reviewer: isDemoMode ? "demo_reviewer" : "local_reviewer",
    });
    await load();
    setMessage(isDemoMode ? "Demo staging approval recorded in sessionStorage." : "Staging approval recorded.");
  }

  async function stageApproved() {
    const result = await provider.stageApprovedLayers(submissionId);
    await load();
    setMessage(String(result.message ?? "Stage-approved action completed."));
  }

  function layerQuery() {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (!value) continue;
      params.set(key === "owner" ? "search" : key, value);
    }
    params.set("limit", "250");
    return `/api/intake/submissions/${encodeURIComponent(submissionId)}/layers?${params.toString()}`;
  }

  useEffect(() => {
    if (!submissionId) return;
    void Promise.resolve().then(load);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submissionId]);

  useEffect(() => {
    if (!selectedLayerId) return;
    Promise.allSettled([
      provider.getSubmissionLayer(submissionId, selectedLayerId),
      provider.getLayerClassificationCandidates(submissionId, selectedLayerId),
    ]).then(([layerResult, candidateResult]) => {
      if (layerResult.status === "fulfilled") setSelectedLayer(layerResult.value);
      if (candidateResult.status === "fulfilled") setCandidates(candidateResult.value.items);
    });
  }, [provider, selectedLayerId, submissionId]);

  const filteredLayers = useMemo(() => layers.filter((layer) => matchesLayer(layer, filters)), [layers, filters]);
  const needsReview = filteredLayers.filter((layer) => layer.routing_state !== "ready_for_classification_review" || layer.duplicate_status === "potential_duplicate" || layer.coordinate_status !== "coordinate_ready");
  const coordinateReview = filteredLayers.filter((layer) => !["coordinate_ready", "mixed_source_spatial_references"].includes(layer.coordinate_status));
  const approvedPlanItems = stagingPlan.filter((item) => item.approved_for_staging);

  if (loading) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <LoadingSkeleton />
      </div>
    );
  }

  if (!submission) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <EmptyState title="Submission not found" message={message || "Open a submission from the Raw stage or upload receipt."} />
      </div>
    );
  }

  return (
    <div className={ws.workspace}>
      <PageIntro />
      {message ? <p className={styles.muted}>{message}</p> : null}

      <section className={ws.grid12}>
        <div className={ws.span3}><MetricTile labelText="Inspection" value={label(inspection?.inspection_status ?? submission.inventory_status)} detail="Inspection copy only." /></div>
        <div className={ws.span3}><MetricTile labelText="Child layers" value={compactNumber(inspection?.child_layer_count ?? layers.length)} detail="Independently classified." /></div>
        <div className={ws.span3}><MetricTile labelText="Needs review" value={compactNumber(needsReview.length)} detail="Taxonomy, duplicate, owner, or coordinate review." /></div>
        <div className={ws.span3}><MetricTile labelText="Approved staging" value={compactNumber(approvedPlanItems.length)} detail="Explicit plan approvals only." /></div>
      </section>

      <div className={styles.tabBar} role="tablist" aria-label="Submission workspace">
        {tabs.map((tab) => (
          <button className={styles.tabButton} role="tab" aria-selected={activeTab === tab} key={tab} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Overview" ? <Overview submission={submission} inspection={inspection} layers={layers} duplicateGroups={duplicateGroups} stagingPlan={stagingPlan} onInspect={runInspection} /> : null}
      {activeTab === "Layers" ? <LayerReviewWorkspace layers={filteredLayers} selectedLayerId={selectedLayerId} selectedLayer={selectedLayer} candidates={candidates} filters={filters} onFilter={setFilters} onSelect={setSelectedLayerId} onApprove={approveLayer} onDefer={deferLayer} /> : null}
      {activeTab === "Needs Review" ? <LayerTable title="Needs Review" description="Layers routed to taxonomy, duplicate, coordinate, owner, sensitivity, or data-owner confirmation review." layers={needsReview} selectedLayerId={selectedLayerId} onSelect={setSelectedLayerId} /> : null}
      {activeTab === "Duplicate Candidates" ? <DuplicateGroups groups={duplicateGroups} onResolve={resolveDuplicate} /> : null}
      {activeTab === "Coordinate Review" ? <CoordinateReview layers={coordinateReview} /> : null}
      {activeTab === "Staging Plan" ? <StagingPlan items={stagingPlan} hasApproved={approvedPlanItems.length > 0} onApprove={approvePlanItem} onStageApproved={stageApproved} /> : null}
      {activeTab === "Events" ? <EventsPanel events={events} /> : null}
    </div>
  );
}

function Overview({ submission, inspection, layers, duplicateGroups, stagingPlan, onInspect }: { submission: IntakeSubmission; inspection: SourceInspectionStatus | null; layers: SubmissionLayer[]; duplicateGroups: DuplicateGroup[]; stagingPlan: StagingPlanItem[]; onInspect: () => void }) {
  const byRouting = countBy(layers, "routing_state");
  return (
    <section className={styles.layout}>
      <Panel title="Submission Identity" description="Safe metadata; no full local paths.">
        <dl className={styles.metadataList}>
          <div><dt>Submission ID</dt><dd className="technical">{submission.submission_id}</dd></div>
          <div><dt>Name</dt><dd>{submission.submission_name}</dd></div>
          <div><dt>Original filename</dt><dd>{submission.original_filename}</dd></div>
          <div><dt>Package utility context</dt><dd>{label(submission.utility_system)}</dd></div>
          <div><dt>Source format</dt><dd>{label(submission.source_format)}</dd></div>
          <div><dt>Source owner</dt><dd>{safeText(submission.source_owner)}</dd></div>
          <div><dt>Sensitivity</dt><dd><StatusBadge value={submission.sensitivity_level} /></dd></div>
          <div><dt>Next action</dt><dd>{submission.next_required_action}</dd></div>
        </dl>
      </Panel>

      <Panel title="Inspection Summary" description="Generated from the inspection copy, not the immutable original.">
        <dl className={styles.metadataList}>
          <div><dt>Status</dt><dd><StageBadge value={inspection?.inspection_status ?? "not_started"} /></dd></div>
          <div><dt>Child layers</dt><dd>{compactNumber(inspection?.child_layer_count ?? layers.length)}</dd></div>
          <div><dt>Tables</dt><dd>{compactNumber(inspection?.table_count ?? 0)}</dd></div>
          <div><dt>Spatial references</dt><dd>{compactNumber(inspection?.spatial_reference_count ?? 0)}</dd></div>
          <div><dt>Duplicate groups</dt><dd>{compactNumber(duplicateGroups.length)}</dd></div>
          <div><dt>Staging plan items</dt><dd>{compactNumber(stagingPlan.length)}</dd></div>
          <div><dt>Routing summary</dt><dd>{Object.entries(byRouting).map(([key, value]) => `${label(key)}: ${value}`).join(" | ") || "Not inspected"}</dd></div>
          <div><dt>Warnings</dt><dd>{listText(inspection?.warnings)}</dd></div>
          <div><dt>Blockers</dt><dd>{listText(inspection?.blockers)}</dd></div>
        </dl>
        <div className={ws.buttonRow}>
          <button className={`${ws.button} ${ws.buttonPrimary}`} onClick={onInspect}>{submission.current_status === "inspection_blocked" ? "Retry Inspection" : "Run Source Inspection"}</button>
          <Link className={ws.button} href="/data-sources?stage=raw">View Raw Stage</Link>
          <Link className={ws.button} href="/data-sources/upload">Upload Another Package</Link>
        </div>
      </Panel>

      <Panel title="Methodology" description="Layer Classification Rules">
        <dl className={styles.metadataList}>
          <div><dt>Rule version</dt><dd>utility_layer_rules_v1</dd></div>
          <div><dt>Evidence</dt><dd>Layer names, aliases, feature datasets, fields, geometry, spatial reference, owner signals, and package metadata.</dd></div>
          <div><dt>Confidence</dt><dd>High, medium, low, and unavailable candidates still require human approval before staging.</dd></div>
          <div><dt>Limitations</dt><dd>Duplicate detection does not select an authoritative source. Coordinate naming such as WGS84 is not proof of spatial reference.</dd></div>
        </dl>
      </Panel>
    </section>
  );
}

function LayerReviewWorkspace(props: { layers: SubmissionLayer[]; selectedLayerId: string; selectedLayer: SubmissionLayer | null; candidates: ClassificationCandidate[]; filters: FilterState; onFilter: (filters: FilterState) => void; onSelect: (layerId: string) => void; onApprove: (layer: SubmissionLayer) => void; onDefer: (layer: SubmissionLayer) => void }) {
  return (
    <section className={styles.layout}>
      <LayerFilters layers={props.layers} filters={props.filters} onFilter={props.onFilter} />
      <LayerTable title="Child Layers" description="Package layers may be independently classified, reviewed, excluded, deferred, or approved for staging." layers={props.layers} selectedLayerId={props.selectedLayerId} onSelect={props.onSelect} />
      <LayerInspector layer={props.selectedLayer} candidates={props.candidates} onApprove={props.onApprove} onDefer={props.onDefer} />
    </section>
  );
}

function LayerFilters({ layers, filters, onFilter }: { layers: SubmissionLayer[]; filters: FilterState; onFilter: (filters: FilterState) => void }) {
  return (
    <Panel title="Filters" description={`${compactNumber(layers.length)} visible layer(s).`}>
      <div className={styles.formGrid}>
        <SelectFilter labelText="Utility" value={filters.utility_system} options={unique(layers, "utility_system")} onChange={(value) => onFilter({ ...filters, utility_system: value })} />
        <SelectFilter labelText="Confidence" value={filters.confidence} options={unique(layers, "confidence")} onChange={(value) => onFilter({ ...filters, confidence: value })} />
        <SelectFilter labelText="Routing" value={filters.routing_state} options={unique(layers, "routing_state")} onChange={(value) => onFilter({ ...filters, routing_state: value })} />
        <SelectFilter labelText="Duplicate" value={filters.duplicate_status} options={unique(layers, "duplicate_status")} onChange={(value) => onFilter({ ...filters, duplicate_status: value })} />
        <SelectFilter labelText="Coordinate" value={filters.coordinate_status} options={unique(layers, "coordinate_status")} onChange={(value) => onFilter({ ...filters, coordinate_status: value })} />
        <SelectFilter labelText="Role" value={filters.operational_role} options={unique(layers, "operational_role")} onChange={(value) => onFilter({ ...filters, operational_role: value })} />
        <SelectFilter labelText="Lifecycle" value={filters.lifecycle_representation} options={unique(layers, "lifecycle_representation")} onChange={(value) => onFilter({ ...filters, lifecycle_representation: value })} />
        <label>Search<input className={ws.input} value={filters.search} onChange={(event) => onFilter({ ...filters, search: event.target.value })} /></label>
      </div>
    </Panel>
  );
}

function SelectFilter({ labelText, value, options, onChange }: { labelText: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label>{labelText}
      <select className={ws.select} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All</option>
        {options.map((option) => <option key={option} value={option}>{label(option)}</option>)}
      </select>
    </label>
  );
}

function LayerTable({ title, description, layers, selectedLayerId, onSelect }: { title: string; description: string; layers: SubmissionLayer[]; selectedLayerId: string; onSelect: (layerId: string) => void }) {
  return (
    <Panel title={title} description={description}>
      {layers.length ? (
        <div className={ws.tableWrap}>
          <table className={ws.table}>
            <thead><tr><th>Source Layer</th><th>Alias</th><th>Owner/Jurisdiction</th><th>Utility</th><th>Network Group</th><th>Category</th><th>Subcategory</th><th>Role</th><th>Lifecycle</th><th>Geometry</th><th>Records</th><th>Spatial Reference</th><th>Confidence</th><th>Routing State</th><th>Staging Status</th></tr></thead>
            <tbody>
              {layers.map((layer) => (
                <tr key={layer.layer_id} className={selectedLayerId === layer.layer_id ? styles.selectedRow : ""}>
                  <td><button className={styles.rowButton} onClick={() => onSelect(layer.layer_id)}>{layer.source_layer_name}</button></td>
                  <td>{safeText(layer.source_layer_alias)}</td>
                  <td>{safeText(layer.owner_or_jurisdiction)}</td>
                  <td>{label(layer.utility_system)}</td>
                  <td>{label(layer.network_group)}</td>
                  <td>{label(layer.asset_category)}</td>
                  <td>{label(layer.asset_subcategory)}</td>
                  <td>{label(layer.operational_role)}</td>
                  <td>{label(layer.lifecycle_representation)}</td>
                  <td>{label(layer.geometry_type)}</td>
                  <td>{compactNumber(layer.record_count)}</td>
                  <td>{safeText(layer.spatial_reference_name)}</td>
                  <td><StatusBadge value={layer.confidence} /></td>
                  <td><StageBadge value={layer.routing_state} /></td>
                  <td><StatusBadge value={layer.staging_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <EmptyState title="No child layers" message="Run source inspection or adjust filters." />}
    </Panel>
  );
}

function LayerInspector({ layer, candidates, onApprove, onDefer }: { layer: SubmissionLayer | null; candidates: ClassificationCandidate[]; onApprove: (layer: SubmissionLayer) => void; onDefer: (layer: SubmissionLayer) => void }) {
  if (!layer) {
    return (
      <Panel title="Layer Inspector" description="Select a layer to review.">
        <EmptyState title="No layer selected" message="Layer source profile and classification candidates will appear here." />
      </Panel>
    );
  }
  const fields = Array.isArray(layer.field_profile) ? layer.field_profile as Record<string, unknown>[] : [];
  return (
    <Panel title="Layer Inspector" description="Safe metadata and aggregate field profiles only.">
      <dl className={styles.metadataList}>
        <div><dt>Source profile</dt><dd>{layer.source_layer_name} - {label(layer.object_type as string)} - {label(layer.geometry_type)}</dd></div>
        <div><dt>Records</dt><dd>{compactNumber(layer.record_count)}</dd></div>
        <div><dt>Fields</dt><dd>{compactNumber(layer.field_count as number | string | undefined)} total; likely IDs: {listText(layer.likely_id_fields as string[] | undefined)}</dd></div>
        <div><dt>Domains</dt><dd>{listText(layer.domain_names as string[] | undefined)}</dd></div>
        <div><dt>Relationships</dt><dd>{safeText(layer.relationship_summary)}</dd></div>
        <div><dt>Attachments</dt><dd>{label(String(layer.attachment_status ?? ""))}</dd></div>
        <div><dt>Editor tracking</dt><dd>{label(String(layer.editor_tracking_status ?? ""))}</dd></div>
      </dl>
      <h3 className={styles.sectionTitle}>Classification Recommendation</h3>
      <div className={styles.candidateList}>
        {(candidates.length ? candidates : []).map((candidate) => (
          <div className={styles.fileItem} key={candidate.candidate_id}>
            <strong>#{candidate.rank} {label(candidate.utility_system)} / {label(candidate.network_group)} / {label(candidate.asset_subcategory)}</strong>
            <span className={styles.muted}>{label(candidate.confidence)} confidence - score {candidate.score}</span>
            <span className={styles.muted}>{candidate.evidence?.join(" | ")}</span>
            {candidate.warnings?.length ? <span className={styles.muted}>{candidate.warnings.join(" | ")}</span> : null}
          </div>
        ))}
        {!candidates.length ? <EmptyState title="No candidates" message="No classification candidates are available for this layer." /> : null}
      </div>
      {fields.length ? <p className={styles.muted}>Field profiles are aggregate metadata only; full source records are not shown.</p> : null}
      <div className={ws.buttonRow}>
        <button className={`${ws.button} ${ws.buttonPrimary}`} onClick={() => onApprove(layer)}>Approve Top Candidate</button>
        <button className={ws.button} onClick={() => onDefer(layer)}>Defer</button>
      </div>
    </Panel>
  );
}

function DuplicateGroups({ groups, onResolve }: { groups: DuplicateGroup[]; onResolve: (group: DuplicateGroup, status: string) => void }) {
  return (
    <Panel title="Duplicate Candidates" description="Potential duplicates are review groups; no authoritative layer is selected automatically.">
      {groups.length ? groups.map((group) => (
        <div className={styles.fileItem} key={group.duplicate_group_id}>
          <strong>{label(group.status)} - {label(group.confidence)} confidence</strong>
          <span className={styles.muted}>{group.recommended_action}</span>
          <div className={ws.tableWrap}>
            <table className={ws.table}>
              <thead><tr><th>Layer</th><th>Geometry</th><th>Records</th><th>Similarity</th><th>Notes</th></tr></thead>
              <tbody>{group.members.map((member) => <tr key={String(member.layer_id)}><td>{String(member.source_layer_name)}</td><td>{label(String(member.geometry_type ?? ""))}</td><td>{compactNumber(String(member.record_count ?? ""))}</td><td>{compactNumber(String(member.similarity_score ?? ""))}</td><td>{String(member.notes ?? "")}</td></tr>)}</tbody>
            </table>
          </div>
          <div className={ws.buttonRow}>
            <button className={ws.button} onClick={() => onResolve(group, "retain_both")}>Retain Both</button>
            <button className={ws.button} onClick={() => onResolve(group, "deferred")}>Defer</button>
          </div>
        </div>
      )) : <EmptyState title="No duplicate candidates" message="No duplicate-looking layers were detected for this submission." />}
    </Panel>
  );
}

function CoordinateReview({ layers }: { layers: SubmissionLayer[] }) {
  return (
    <LayerTable title="Coordinate Review" description="Coordinate review is descriptive only; projection and define-projection tools are not available in this phase." layers={layers} selectedLayerId="" onSelect={() => undefined} />
  );
}

function StagingPlan({ items, hasApproved, onApprove, onStageApproved }: { items: StagingPlanItem[]; hasApproved: boolean; onApprove: (item: StagingPlanItem) => void; onStageApproved: () => void }) {
  return (
    <Panel title="Staging Plan" description="Reviewed layers may be copied later into submission-specific staging. Raw layer names are never changed.">
      {items.length ? (
        <>
          <div className={ws.tableWrap}>
            <table className={ws.table}>
              <thead><tr><th>Source Layer</th><th>Approved Taxonomy</th><th>Proposed Target</th><th>Source Coordinate System</th><th>Projection Required Later</th><th>Blockers</th><th>Approval</th><th>Reviewer</th><th></th></tr></thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.staging_plan_item_id}>
                    <td>{safeText(item.source_layer_name)}</td>
                    <td>{label(String(item.target_utility_system))} / {label(String(item.target_network_group))} / {label(String(item.target_asset_subcategory))}</td>
                    <td className="technical">{item.proposed_target_name}</td>
                    <td>{safeText(item.source_spatial_reference)}</td>
                    <td>{item.projection_required ? "Yes" : "No"}</td>
                    <td>{safeText(item.blocker, "None recorded")}</td>
                    <td><StatusBadge value={item.approval_status} /></td>
                    <td>{safeText(item.reviewer)}</td>
                    <td><button className={ws.button} onClick={() => onApprove(item)} disabled={Boolean(item.blocker) && !isDemoMode}>Approve</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasApproved ? <button className={`${ws.button} ${ws.buttonPrimary}`} onClick={onStageApproved}>{isDemoMode ? "Simulate Approved Staging" : "Stage Approved Layers"}</button> : null}
        </>
      ) : <EmptyState title="No staging plan" message="Run source inspection to create a candidate staging plan. Nothing is staged automatically." />}
    </Panel>
  );
}

function EventsPanel({ events }: { events: IntakeEvent[] }) {
  return (
    <Panel title="Events" description="Immutable intake and review timeline.">
      <div className={styles.timeline}>
        {events.length ? events.map((event) => (
          <div className={styles.timelineItem} key={event.event_id}>
            <strong>{label(event.event_type)}</strong>
            <span className={styles.muted}>{event.message}</span>
            <span className={styles.muted}>{shortDate(event.created_at)}</span>
          </div>
        )) : <EmptyState title="No events" message="No event history is available for this submission." />}
      </div>
    </Panel>
  );
}

function PageIntro() {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>{isDemoMode ? "PORTFOLIO DEMO" : "LOCAL INTAKE"}</span>
      <h1>Submission Layer Review</h1>
      <p>Inspect child layers, review classification evidence, resolve ambiguity, and prepare an explicit staging plan without exposing local paths.</p>
    </header>
  );
}

function initialSubmissionId() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("id") ?? (isDemoMode ? "DEMO-UPL-20260720-A1B2C3D4" : "");
}

function initialTab(): Tab {
  if (typeof window === "undefined") return "Overview";
  const requested = new URLSearchParams(window.location.search).get("tab");
  return tabs.includes(requested as Tab) ? requested as Tab : "Overview";
}

function matchesLayer(layer: SubmissionLayer, filters: FilterState) {
  const search = filters.search.toLowerCase();
  return (!filters.utility_system || layer.utility_system === filters.utility_system)
    && (!filters.confidence || layer.confidence === filters.confidence)
    && (!filters.routing_state || layer.routing_state === filters.routing_state)
    && (!filters.duplicate_status || layer.duplicate_status === filters.duplicate_status)
    && (!filters.coordinate_status || layer.coordinate_status === filters.coordinate_status)
    && (!filters.operational_role || layer.operational_role === filters.operational_role)
    && (!filters.lifecycle_representation || layer.lifecycle_representation === filters.lifecycle_representation)
    && (!filters.owner || String(layer.owner_or_jurisdiction ?? "").toLowerCase().includes(filters.owner.toLowerCase()))
    && (!search || [layer.source_layer_name, layer.source_layer_alias, layer.owner_or_jurisdiction].some((value) => String(value ?? "").toLowerCase().includes(search)));
}

function unique(layers: SubmissionLayer[], field: keyof SubmissionLayer) {
  return Array.from(new Set(layers.map((layer) => String(layer[field] ?? "")).filter(Boolean))).sort();
}

function countBy(layers: SubmissionLayer[], field: keyof SubmissionLayer) {
  return layers.reduce<Record<string, number>>((counts, layer) => {
    const key = String(layer[field] ?? "");
    if (key) counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
}

function listText(values: string[] | undefined) {
  return Array.isArray(values) && values.length ? values.join(", ") : "None recorded";
}
