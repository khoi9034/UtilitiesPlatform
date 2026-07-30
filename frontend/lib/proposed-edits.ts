import { demoAssets, demoAllRelationships } from "./utility-assets";

export type ProposedOperation = {
  operation_id: string;
  operation_type: string;
  sequence: number;
  target_asset_id?: string;
  target_relationship_id?: string;
  new_asset_temporary_id?: string;
  field_name?: string;
  prior_value?: unknown;
  proposed_value?: unknown;
  prior_values?: Record<string, unknown>;
  proposed_values?: Record<string, unknown>;
  relationship_type?: string;
  from_asset_id?: string;
  to_asset_id?: string;
  reason: string;
  validation_status: string;
  validation_errors?: Array<{ code: string; message: string }>;
  validation_warnings?: Array<{ code: string; message: string }>;
};

export type QaComparison = {
  comparison_status: string;
  baseline_blocker_count: number;
  proposed_blocker_count: number;
  baseline_warning_count: number;
  proposed_warning_count: number;
  resolved_issue_group_ids: string[];
  unchanged_issue_group_ids: string[];
  new_issue_group_ids: string[];
  worsened_issue_group_ids: string[];
};

export type TraceComparison = {
  trace_scenario_code: string;
  baseline_outcome: string;
  proposed_outcome: string;
  baseline_confidence: string;
  proposed_confidence: string;
  baseline_objective_reached: boolean;
  proposed_objective_reached: boolean;
  reachable_asset_delta: number;
  baseline_path_signature: string;
  proposed_path_signature: string;
  baseline_branch_signature: string;
  proposed_branch_signature: string;
  result: string;
};

export type ProposedEdit = {
  proposal_id: string;
  proposal_version: number;
  scenario_code: string;
  utility_vertical: "electric_distribution" | "telecom_fiber" | "water" | "wastewater";
  proposal_type: string;
  title: string;
  summary: string;
  status: string;
  baseline_fingerprint: string;
  proposal_fingerprint: string;
  overlay_fingerprint: string;
  validation_status: string;
  analysis_status: string;
  review_status: string;
  approval_status: string;
  implementation_readiness: string;
  created_by: string;
  submitted_by?: string;
  reviewed_by?: string;
  approved_by?: string;
  approved_at?: string;
  locked: boolean;
  approved_not_implemented: boolean;
  implementation_status: "not_implemented";
  trace_type?: string;
  trace_start_asset_id?: string;
  operation_count?: number;
  operations: ProposedOperation[];
  qa_comparison?: QaComparison;
  trace_comparisons: TraceComparison[];
  impact_summary?: Record<string, unknown>;
  reviews: Array<Record<string, unknown>>;
  history: Array<Record<string, unknown>>;
  versions: Array<Record<string, unknown>>;
  disclaimer: string;
};

const storeKey = "utilities-platform-demo-proposed-edits-v1";
export const proposalDisclaimer = "UtilitiesPlatform Proposed Edit Workspace V1 creates isolated vendor-neutral change plans and evaluates them against temporary network overlays. Approval confirms the plan for future implementation review; it does not modify an operational utility GIS, execute switching, allocate telecom capacity, or apply changes to ArcFM, Smallworld, Esri Utility Network, or another proprietary system.";
const lifecycle = ["draft", "validation_failed", "ready_for_analysis", "analyzing", "analysis_complete", "needs_revision", "submitted_for_review", "under_review", "approved", "rejected", "deferred", "withdrawn", "superseded", "implementation_ready", "implementation_exported", "archived"];
const sharedTypes = ["connectivity_correction", "attribute_correction", "relationship_correction", "lifecycle_change", "operational_state_proposal", "containment_association", "structure_association", "asset_replacement", "asset_retirement", "proposed_asset_addition", "route_or_feeder_assignment", "data_quality_correction", "manual_investigation", "multi_operation_change_set"];
const electricTypes = ["connect_conductor_endpoint", "assign_transformer_feeder", "correct_phase", "correct_voltage", "associate_conductor_conduit", "confirm_or_change_device_state", "replace_transformer", "replace_pole", "correct_upstream_downstream", "add_protective_relationship", "retire_electric_asset", "add_proposed_electric_asset"];
const telecomTypes = ["assign_cable_endpoint", "add_splice_relationship", "correct_strand_assignment", "correct_capacity", "associate_cable_conduit", "associate_aerial_support", "connect_terminal", "correct_route_membership", "close_proposed_route_gap", "replace_cable", "retire_telecom_asset", "add_proposed_telecom_asset"];
const waterTypes = ["add_main", "replace_main", "retire_main", "add_valve", "replace_valve", "add_hydrant", "relocate_hydrant", "add_service", "replace_meter", "update_pressure_zone_relationship", "repair_water_connectivity", "update_water_asset_attributes"];
const wastewaterTypes = ["add_gravity_main", "replace_gravity_main", "add_force_main", "add_manhole", "relocate_manhole", "add_lateral", "replace_lift_station_relationship", "update_invert_or_rim", "update_flow_direction_relationship", "retire_abandoned_wastewater_asset", "repair_wastewater_connectivity"];
const verticalTypes = { electric_distribution: electricTypes, telecom_fiber: telecomTypes, water: waterTypes, wastewater: wastewaterTypes };
const operationTypes = ["add_asset", "update_asset_attribute", "update_asset_attributes", "change_lifecycle_status", "change_operational_status", "add_relationship", "remove_relationship", "replace_relationship", "update_relationship", "confirm_provisional_relationship", "mark_relationship_provisional", "assign_membership", "remove_membership", "retire_asset", "replace_asset", "associate_container", "remove_container_association", "associate_structure", "remove_structure_association", "add_note", "request_manual_investigation"];

type Vertical = ProposedEdit["utility_vertical"];
type Seed = [string, string, string, string, Partial<ProposedOperation>[]];

const seeds: Record<Vertical, Seed[]> = {
  electric_distribution: [
    ["E-EDIT-001", "Connect missing conductor endpoint", "connect_conductor_endpoint", "demo-electric_distribution-overhead_conductor-8", [{ operation_type: "add_relationship", from_asset_id: "demo-electric_distribution-overhead_conductor-6", to_asset_id: "demo-electric_distribution-overhead_conductor-8", relationship_type: "feeds" }, { operation_type: "add_relationship", from_asset_id: "demo-electric_distribution-overhead_conductor-8", to_asset_id: "demo-electric_distribution-overhead_conductor-4", relationship_type: "feeds" }]],
    ["E-EDIT-002", "Assign transformer feeder", "assign_transformer_feeder", "demo-electric_distribution-transformer-8", [{ operation_type: "update_asset_attribute", target_asset_id: "demo-electric_distribution-transformer-8", field_name: "feeder_id", proposed_value: "FEEDER-1" }, { operation_type: "add_relationship", from_asset_id: "demo-electric_distribution-feeder-2", to_asset_id: "demo-electric_distribution-transformer-8", relationship_type: "belongs_to_feeder" }]],
    ["E-EDIT-003", "Correct phase assignment", "correct_phase", "demo-electric_distribution-transformer-7", [{ operation_type: "update_asset_attribute", target_asset_id: "demo-electric_distribution-transformer-7", field_name: "phase", proposed_value: "A" }]],
    ["E-EDIT-004", "Associate underground conductor with conduit", "associate_conductor_conduit", "demo-electric_distribution-underground_conductor-3", [{ operation_type: "update_asset_attribute", target_asset_id: "demo-electric_distribution-underground_conductor-3", field_name: "conduit_id", proposed_value: "CONDUIT-1" }, { operation_type: "add_relationship", from_asset_id: "demo-electric_distribution-underground_conductor-3", to_asset_id: "demo-electric_distribution-conduit-1", relationship_type: "routed_through" }]],
    ["E-EDIT-005", "Confirm proposed switch state", "confirm_or_change_device_state", "demo-electric_distribution-switch-3", [{ operation_type: "change_operational_status", target_asset_id: "demo-electric_distribution-switch-3", proposed_value: "closed" }]],
    ["E-EDIT-006", "Replace transformer", "replace_transformer", "demo-electric_distribution-transformer-7", [{ operation_type: "add_asset", new_asset_temporary_id: "PROP-E-EDIT-006-1", proposed_values: { asset_class: "transformer", lifecycle_status: "proposed" } }, { operation_type: "retire_asset", target_asset_id: "demo-electric_distribution-transformer-7" }]],
    ["E-EDIT-007", "Correct upstream downstream relationship", "correct_upstream_downstream", "demo-electric_distribution-transformer-8", [{ operation_type: "replace_relationship", target_relationship_id: "synthetic-directional-relation", from_asset_id: "demo-electric_distribution-junction-2", to_asset_id: "demo-electric_distribution-transformer-8", relationship_type: "feeds" }]],
    ["E-EDIT-008", "Unsafe voltage proposal", "correct_voltage", "demo-electric_distribution-transformer-7", [{ operation_type: "update_asset_attribute", target_asset_id: "demo-electric_distribution-transformer-7", field_name: "operating_voltage", proposed_value: 4.16 }]],
  ],
  telecom_fiber: [
    ["T-EDIT-001", "Assign cable endpoint", "assign_cable_endpoint", "demo-telecom_fiber-fiber_cable-4", [{ operation_type: "update_asset_attribute", target_asset_id: "demo-telecom_fiber-fiber_cable-4", field_name: "to_structure_id", proposed_value: "STRUCT-05" }, { operation_type: "add_relationship", from_asset_id: "demo-telecom_fiber-fiber_cable-4", to_asset_id: "demo-telecom_fiber-handhole-4", relationship_type: "terminates_at" }]],
    ["T-EDIT-002", "Confirm splice relationship", "add_splice_relationship", "demo-telecom_fiber-splice_closure-1", [{ operation_type: "confirm_provisional_relationship", target_relationship_id: "synthetic-provisional-splice" }]],
    ["T-EDIT-003", "Correct strand overlap", "correct_strand_assignment", "demo-telecom_fiber-fiber_cable-4", [{ operation_type: "update_asset_attributes", target_asset_id: "demo-telecom_fiber-fiber_cable-4", proposed_values: { strand_start: 145, strand_end: 288 } }]],
    ["T-EDIT-004", "Correct capacity values", "correct_capacity", "demo-telecom_fiber-terminal-6", [{ operation_type: "update_asset_attribute", target_asset_id: "demo-telecom_fiber-terminal-6", field_name: "available_capacity", proposed_value: 4 }]],
    ["T-EDIT-005", "Associate cable with conduit", "associate_cable_conduit", "demo-telecom_fiber-fiber_cable-1", [{ operation_type: "add_relationship", from_asset_id: "demo-telecom_fiber-fiber_cable-1", to_asset_id: "demo-telecom_fiber-conduit-1", relationship_type: "routed_through" }]],
    ["T-EDIT-006", "Connect terminal upstream", "connect_terminal", "demo-telecom_fiber-terminal-6", [{ operation_type: "add_relationship", from_asset_id: "demo-telecom_fiber-fiber_cable-4", to_asset_id: "demo-telecom_fiber-terminal-6", relationship_type: "terminates_at" }]],
    ["T-EDIT-007", "Close proposed route gap", "close_proposed_route_gap", "demo-telecom_fiber-proposed_construction_segment-1", [{ operation_type: "update_asset_attribute", target_asset_id: "demo-telecom_fiber-proposed_construction_segment-1", field_name: "to_structure_id", proposed_value: "STRUCT-08" }]],
    ["T-EDIT-008", "Replace retired cable relationship", "replace_cable", "demo-telecom_fiber-fiber_cable-3", [{ operation_type: "add_asset", new_asset_temporary_id: "PROP-T-EDIT-008-1", proposed_values: { asset_class: "fiber_cable", lifecycle_status: "proposed" } }, { operation_type: "remove_relationship", target_relationship_id: "synthetic-retired-cable-relation" }, { operation_type: "add_relationship", from_asset_id: "PROP-T-EDIT-008-1", to_asset_id: "demo-telecom_fiber-terminal-1", relationship_type: "terminates_at" }]],
    ["T-EDIT-009", "Unsafe strand proposal", "correct_strand_assignment", "demo-telecom_fiber-fiber_cable-2", [{ operation_type: "update_asset_attributes", target_asset_id: "demo-telecom_fiber-fiber_cable-2", proposed_values: { strand_start: 300, strand_end: 400 } }]],
  ],
  water: [
    ["W-EDIT-001", "Repair disconnected service relationship", "repair_water_connectivity", "demo-water-service_line-2", [{ operation_type: "add_relationship", from_asset_id: "demo-water-distribution_main-1", to_asset_id: "demo-water-service_line-2", relationship_type: "feeds" }]],
    ["W-EDIT-002", "Propose distribution main replacement", "replace_main", "demo-water-distribution_main-1", [{ operation_type: "add_asset", new_asset_temporary_id: "PROP-W-EDIT-002-1", proposed_values: { asset_class: "distribution_main", lifecycle_status: "proposed" } }]],
  ],
  wastewater: [
    ["WW-EDIT-001", "Correct gravity-main invert evidence", "update_invert_or_rim", "demo-wastewater-gravity_main-2", [{ operation_type: "update_asset_attributes", target_asset_id: "demo-wastewater-gravity_main-2", proposed_values: { upstream_invert: 97, downstream_invert: 96, slope: 0.02 } }]],
    ["WW-EDIT-002", "Repair disconnected manhole relationship", "repair_wastewater_connectivity", "demo-wastewater-manhole-3", [{ operation_type: "add_relationship", from_asset_id: "demo-wastewater-manhole-3", to_asset_id: "demo-wastewater-gravity_main-2", relationship_type: "flows_to" }]],
  ],
};

function operation(code: string, index: number, value: Partial<ProposedOperation>): ProposedOperation {
  return {
    operation_id: `${code}-OP-${index + 1}`,
    operation_type: value.operation_type ?? "request_manual_investigation",
    sequence: index + 1,
    reason: value.reason ?? "Synthetic proposal operation for portfolio review.",
    validation_status: "not_evaluated",
    ...value,
  };
}

function seedStore(): ProposedEdit[] {
  return (Object.entries(seeds) as Array<[Vertical, Seed[]]>).flatMap(([vertical, rows]) =>
    rows.map(([code, title, type, start, values]) => analyze({
      proposal_id: `demo-${code.toLowerCase()}`,
      proposal_version: 1,
      scenario_code: code,
      utility_vertical: vertical,
      proposal_type: type,
      title,
      summary: "Deterministic synthetic proposed-change scenario.",
      status: "draft",
      baseline_fingerprint: `synthetic-${vertical}-baseline-v1`,
      proposal_fingerprint: "",
      overlay_fingerprint: "",
      validation_status: "not_evaluated",
      analysis_status: "not_started",
      review_status: "not_submitted",
      approval_status: "not_requested",
      implementation_readiness: "not_evaluated",
      created_by: "synthetic_demo",
      locked: false,
      approved_not_implemented: false,
      implementation_status: "not_implemented",
      trace_type: {
        electric_distribution: "ELEC-TRACE-002",
        telecom_fiber: "TEL-TRACE-002",
        water: "WATER-TRACE-005",
        wastewater: "WW-TRACE-001",
      }[vertical],
      trace_start_asset_id: start,
      operations: values.map((item, index) => operation(code, index, item)),
      trace_comparisons: [],
      reviews: [],
      history: [{ action: "synthetic_scenario_seeded", actor: "system", created_at: "2026-07-27T12:00:00Z" }],
      versions: [{ proposal_version: 1, status: "draft" }],
      disclaimer: proposalDisclaimer,
    })),
  );
}

function read(): ProposedEdit[] {
  if (typeof sessionStorage === "undefined") return seedStore();
  try {
    const stored = JSON.parse(sessionStorage.getItem(storeKey) ?? "") as ProposedEdit[];
    return stored.length ? stored : seedStore();
  } catch { return seedStore(); }
}

function write(items: ProposedEdit[]) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(storeKey, JSON.stringify(items));
}

function validationErrors(proposal: ProposedEdit) {
  const serialized = JSON.stringify(proposal.operations);
  const errors: Array<{ code: string; message: string }> = [];
  if (!proposal.operations.length) errors.push({ code: "empty_operation_list", message: "At least one proposed operation is required." });
  if (/[A-Za-z]:[\\/]|https?:\/\/|\"(?:sql|python|shell|command|script|expression)\"/i.test(serialized)) errors.push({ code: "unsafe_payload", message: "Executable, external, and filesystem inputs are not accepted." });
  if (proposal.operations.some((item) => item.field_name === "operating_voltage" && item.proposed_value === 4.16)) errors.push({ code: "voltage_conflict", message: "The proposal creates a nominal and operating voltage conflict." });
  if (proposal.operations.some((item) => Number(item.proposed_values?.strand_end) > 288 || Number(item.proposed_values?.strand_start) < 1)) errors.push({ code: "invalid_strand_range", message: "The strand range exceeds the synthetic cable capacity." });
  return errors;
}

function analyze(proposal: ProposedEdit): ProposedEdit {
  const errors = validationErrors(proposal);
  proposal.operations = proposal.operations.map((item) => ({ ...item, validation_status: errors.length ? "failed" : "passed", validation_errors: errors }));
  proposal.validation_status = errors.length ? "failed" : "passed";
  proposal.proposal_fingerprint = `synthetic-proposal-${proposal.proposal_id}-v${proposal.proposal_version}-${proposal.operations.length}`;
  if (errors.length) {
    proposal.status = "validation_failed";
    proposal.analysis_status = "not_started";
    proposal.implementation_readiness = "blocked";
    return proposal;
  }
  const corrective = proposal.operations.filter((item) =>
    ["add_relationship", "replace_relationship", "confirm_provisional_relationship", "update_asset_attribute", "update_asset_attributes"].includes(item.operation_type),
  ).length;
  const flowChange = proposal.operations.some((item) =>
    ["add_relationship", "replace_relationship", "change_operational_status"].includes(item.operation_type)
      && item.relationship_type !== "routed_through",
  );
  const resolved = Array.from({ length: Math.min(corrective, 2) }, (_, index) => `${proposal.scenario_code}-RESOLVED-${index + 1}`);
  proposal.status = "analysis_complete";
  proposal.analysis_status = "complete";
  proposal.overlay_fingerprint = `synthetic-overlay-${proposal.proposal_id}-v${proposal.proposal_version}-${proposal.operations.length}`;
  proposal.qa_comparison = {
    comparison_status: resolved.length ? "improved" : "unchanged",
    baseline_blocker_count: 4,
    proposed_blocker_count: Math.max(0, 4 - resolved.length),
    baseline_warning_count: 8,
    proposed_warning_count: Math.max(0, 8 - corrective),
    resolved_issue_group_ids: resolved,
    unchanged_issue_group_ids: [`${proposal.scenario_code}-BACKGROUND`],
    new_issue_group_ids: [],
    worsened_issue_group_ids: [],
  };
  proposal.trace_comparisons = [{
    trace_scenario_code: proposal.scenario_code,
    baseline_outcome: "blocked",
    proposed_outcome: flowChange ? "complete_with_warnings" : "blocked",
    baseline_confidence: "low",
    proposed_confidence: flowChange ? "medium" : "low",
    baseline_objective_reached: false,
    proposed_objective_reached: flowChange,
    reachable_asset_delta: flowChange ? 3 : 0,
    baseline_path_signature: `${proposal.scenario_code}-before`,
    proposed_path_signature: flowChange ? `${proposal.scenario_code}-after` : `${proposal.scenario_code}-before`,
    baseline_branch_signature: `${proposal.scenario_code}-branch`,
    proposed_branch_signature: `${proposal.scenario_code}-branch`,
    result: flowChange ? "improved" : "unchanged",
  }];
  proposal.impact_summary = {
    operation_count: proposal.operations.length,
    qa_blockers_before: 4,
    qa_blockers_after: proposal.qa_comparison.proposed_blocker_count,
    qa_groups_resolved: resolved.length,
    traces_improved: flowChange ? 1 : 0,
    implementation_readiness: "review_ready",
  };
  proposal.implementation_readiness = "review_ready";
  return proposal;
}

function update(proposal: ProposedEdit) {
  const items = read();
  const index = items.findIndex((item) => item.proposal_id === proposal.proposal_id);
  if (index >= 0) items[index] = proposal; else items.push(proposal);
  write(items);
  return structuredClone(proposal);
}

export function demoProposalTypes(vertical?: Vertical) {
  return vertical
    ? { utility_vertical: vertical, proposal_types: [...sharedTypes, ...verticalTypes[vertical]], operation_types: operationTypes, lifecycle_states: lifecycle, disclaimer: proposalDisclaimer }
    : { utility_verticals: Object.keys(verticalTypes), shared_proposal_types: sharedTypes, vertical_proposal_types: verticalTypes, lifecycle_states: lifecycle, disclaimer: proposalDisclaimer };
}

export function demoOperationTypes() {
  return { operation_types: operationTypes, external_mapping_statuses: ["not_mapped", "conceptually_mappable", "adapter_required", "unsupported", "unknown"], executable_operations_supported: false, disclaimer: proposalDisclaimer };
}

export function demoProposedGet(path: string, params: URLSearchParams): unknown {
  const parts = path.split("/");
  if (path === "/api/proposed-edits/types") return demoProposalTypes();
  if (path === "/api/proposed-edits/operation-types") return demoOperationTypes();
  if (parts[3] === "types") return demoProposalTypes(parts[4] as Vertical);
  const vertical = parts[3] as Vertical;
  const items = read().filter((item) => item.utility_vertical === vertical);
  if (!parts[4]) {
    const filtered = items.filter((item) =>
      (!params.get("status") || item.status === params.get("status"))
      && (!params.get("proposal_type") || item.proposal_type === params.get("proposal_type"))
      && (!params.get("search") || `${item.title} ${item.scenario_code}`.toLowerCase().includes(params.get("search")!.toLowerCase())),
    );
    return { items: filtered, pagination: { total: filtered.length, limit: 100, offset: 0, has_more: false }, disclaimer: proposalDisclaimer };
  }
  const proposal = items.find((item) => item.proposal_id === decodeURIComponent(parts[4]));
  if (!proposal) throw new Error("Synthetic proposed edit not found.");
  const suffix = parts[5];
  if (!suffix) return proposal;
  if (suffix === "operations") return { items: proposal.operations, proposal_id: proposal.proposal_id, proposal_version: proposal.proposal_version };
  if (suffix === "validation") return { status: proposal.validation_status, errors: proposal.operations.flatMap((item) => item.validation_errors ?? []), warnings: [] };
  if (suffix === "overlay") return { ...(proposal.impact_summary ?? {}), overlay_fingerprint: proposal.overlay_fingerprint, changed_asset_ids: proposal.operations.map((item) => item.target_asset_id).filter(Boolean), notice: "Proposed overlay - no canonical or source records have been changed." };
  if (suffix === "qa-comparison") return proposal.qa_comparison ?? {};
  if (suffix === "trace-comparisons") return { items: proposal.trace_comparisons, disclaimer: proposalDisclaimer };
  if (suffix === "impact-summary") return proposal.impact_summary ?? {};
  if (suffix === "safe-summary") return { proposal, operations: proposal.operations, impact_summary: proposal.impact_summary, external_mapping_status: "adapter_required", executable: false, disclaimer: proposalDisclaimer };
  if (suffix === "implementation-package") return packageFor(proposal);
  return proposal;
}

export function demoProposedPost(path: string, body: Record<string, unknown> = {}): unknown {
  const parts = path.split("/");
  const vertical = parts[3] as Vertical;
  if (!parts[4]) {
    const proposal: ProposedEdit = {
      ...seedStore()[0],
      proposal_id: `demo-proposal-${Date.now()}`,
      scenario_code: "",
      utility_vertical: vertical,
      proposal_type: String(body.proposal_type || "manual_investigation"),
      title: String(body.title || "Untitled synthetic proposal"),
      summary: String(body.summary || ""),
      status: "draft",
      baseline_fingerprint: `synthetic-${vertical}-baseline-v1`,
      proposal_fingerprint: "",
      overlay_fingerprint: "",
      validation_status: "not_evaluated",
      analysis_status: "not_started",
      review_status: "not_submitted",
      approval_status: "not_requested",
      implementation_readiness: "not_evaluated",
      created_by: String(body.created_by || "Demo Author"),
      locked: false,
      approved_not_implemented: false,
      operations: [],
      qa_comparison: undefined,
      trace_comparisons: [],
      impact_summary: {},
      reviews: [],
      history: [{ action: "proposal_created", actor: "Demo Author", created_at: new Date().toISOString() }],
      versions: [{ proposal_version: 1, status: "draft" }],
    };
    return update(proposal);
  }
  const proposal = read().find((item) => item.proposal_id === decodeURIComponent(parts[4]));
  if (!proposal) throw new Error("Synthetic proposed edit not found.");
  const action = parts[5];
  if (action === "operations") {
    if (proposal.locked) throw new Error("This proposal version is locked.");
    proposal.operations.push(operation(proposal.proposal_id, proposal.operations.length, body as Partial<ProposedOperation>));
    proposal.status = "draft"; proposal.validation_status = "not_evaluated"; proposal.analysis_status = "not_started";
    return update(proposal).operations.at(-1);
  }
  if (action === "validate") return update(analyze(proposal)).validation_status === "passed"
    ? { status: "passed", errors: [], warnings: [] }
    : { status: "failed", errors: validationErrors(proposal), warnings: [] };
  if (action === "analyze") return update(analyze(proposal));
  if (action === "submit") {
    if (proposal.analysis_status !== "complete") throw new Error("Analysis must be complete before review.");
    proposal.status = "submitted_for_review"; proposal.review_status = "submitted"; proposal.approval_status = "pending"; proposal.locked = true;
  } else if (action === "start-review") {
    proposal.status = "under_review"; proposal.review_status = "under_review";
  } else if (action === "approve") {
    proposal.status = "approved"; proposal.review_status = "decision_recorded"; proposal.approval_status = "approved"; proposal.implementation_readiness = "approved_plan_only"; proposal.approved_by = String(body.reviewer || "Synthetic Reviewer"); proposal.approved_at = new Date().toISOString(); proposal.approved_not_implemented = true;
  } else if (action === "request-revision") {
    proposal.status = "needs_revision"; proposal.locked = false;
  } else if (["reject", "defer", "withdraw"].includes(action)) {
    proposal.status = action === "reject" ? "rejected" : action === "defer" ? "deferred" : "withdrawn";
  } else if (action === "reopen") {
    proposal.status = "needs_revision"; proposal.locked = false; proposal.approval_status = "not_requested";
  } else if (action === "implementation-package") {
    if (proposal.approval_status !== "approved") throw new Error("Only an approved plan can produce a package.");
    proposal.status = "implementation_ready"; proposal.implementation_readiness = "implementation_package_ready";
    update(proposal);
    return packageFor(proposal);
  }
  proposal.reviews.push({ action, reviewer: body.reviewer || body.actor || "Synthetic Reviewer", notes: body.notes || "", created_at: new Date().toISOString() });
  proposal.history.push({ action, actor: body.reviewer || body.actor || "Synthetic Reviewer", created_at: new Date().toISOString() });
  return update(proposal);
}

export function demoProposedPut(path: string, body: Record<string, unknown>): unknown {
  const parts = path.split("/");
  const proposal = read().find((item) => item.proposal_id === decodeURIComponent(parts[4]));
  if (!proposal || proposal.locked) throw new Error("Synthetic proposal operation cannot be changed.");
  const index = proposal.operations.findIndex((item) => item.operation_id === decodeURIComponent(parts[6]));
  if (index < 0) throw new Error("Synthetic operation not found.");
  proposal.operations[index] = { ...proposal.operations[index], ...body, sequence: proposal.operations[index].sequence };
  return update(proposal).operations[index];
}

export function demoProposedDelete(path: string): unknown {
  const parts = path.split("/");
  const proposal = read().find((item) => item.proposal_id === decodeURIComponent(parts[4]));
  if (!proposal || proposal.locked) throw new Error("Synthetic proposal operation cannot be removed.");
  const operationId = decodeURIComponent(parts[6]);
  proposal.operations = proposal.operations.filter((item) => item.operation_id !== operationId);
  update(proposal);
  return { deleted: true, operation_id: operationId, history_preserved: true };
}

function packageFor(proposal: ProposedEdit) {
  return {
    package_id: `demo-package-${proposal.proposal_id}-v${proposal.proposal_version}`,
    package_version: "proposed-edit-package-v1",
    proposal_id: proposal.proposal_id,
    proposal_version: proposal.proposal_version,
    utility_vertical: proposal.utility_vertical,
    baseline_fingerprint: proposal.baseline_fingerprint,
    proposal_fingerprint: proposal.proposal_fingerprint,
    overlay_fingerprint: proposal.overlay_fingerprint,
    operations: proposal.operations,
    qa_comparison: proposal.qa_comparison,
    trace_comparisons: proposal.trace_comparisons,
    external_mapping_status: "adapter_required",
    required_adapter_capabilities: ["external_approval_required", "topology_validation_required"],
    implementation_status: "not_implemented",
    descriptive_only: true,
    executable: false,
    disclaimer: proposalDisclaimer,
  };
}

export function resetDemoProposedEdits() {
  if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(storeKey);
}

export function proposedAssetOptions(vertical: Vertical) {
  return demoAssets().filter((item) => item.utility_vertical === vertical).map((item) => ({ id: item.asset_id, name: item.canonical_name, assetClass: item.asset_class }));
}

export function proposedRelationshipOptions(vertical: Vertical) {
  const assetIds = new Set(demoAssets().filter((item) => item.utility_vertical === vertical).map((item) => item.asset_id));
  return demoAllRelationships().filter((item) => assetIds.has(item.from_asset_id) || assetIds.has(item.to_asset_id));
}
