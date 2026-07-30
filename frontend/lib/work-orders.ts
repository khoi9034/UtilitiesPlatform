import type { ProposedEdit } from "./proposed-edits";

export type UtilityVertical = "electric_distribution" | "telecom_fiber" | "water" | "wastewater";
export type WorkOrderRecord = Record<string, unknown>;
export type WorkOrder = {
  work_order_id: string;
  work_order_version: number;
  scenario_code: string;
  work_order_number: string;
  utility_vertical: UtilityVertical;
  work_order_type: string;
  title: string;
  summary: string;
  priority: string;
  overall_status: string;
  design_status: string;
  field_work_status: string;
  gis_implementation_status: string;
  inspection_status: string;
  qa_status: string;
  trace_status: string;
  review_status: string;
  closeout_status: string;
  readiness: string;
  closeout_readiness: string;
  linked_proposal_id: string;
  linked_proposal_version: number;
  proposal_fingerprint: string;
  baseline_fingerprint: string;
  proposal_approved: boolean;
  baseline_current: boolean;
  affected_asset_ids: string[];
  affected_relationship_ids: string[];
  requested_by: string;
  created_by: string;
  current_owner: string;
  final_approver: string;
  approved_by: string;
  approved_at: string;
  target_completion_date: string;
  external_mapping_status: string;
  implementation_confirmation_status: string;
  version_fingerprint: string;
  release_fingerprint: string;
  locked: boolean;
  is_synthetic: boolean;
  created_at: string;
  updated_at: string;
  assignments: WorkOrderRecord[];
  phases: WorkOrderRecord[];
  steps: WorkOrderRecord[];
  prerequisites: WorkOrderRecord[];
  inspections: WorkOrderRecord[];
  evidence: WorkOrderRecord[];
  implementation?: WorkOrderRecord;
  conformance?: WorkOrderRecord;
  post_work_qa?: WorkOrderRecord;
  post_work_traces: WorkOrderRecord[];
  history: WorkOrderRecord[];
  versions: WorkOrderRecord[];
  three_state_comparison: ThreeStateComparison;
  disclaimer: string;
};

export type ThreeStateComparison = {
  baseline: Record<string, unknown>;
  approved_plan: Record<string, unknown>;
  recorded_implementation: Record<string, unknown>;
  notice: string;
};

const storeKey = "utilities-platform-demo-work-orders-v1";
export const workOrderDisclaimer = "UtilitiesPlatform Work Order and Job Package V1 records synthetic vendor-neutral planning, review, evidence, validation, and closeout without modifying an operational utility GIS or executing work.";
export const implementationNotice = "Synthetic implementation record - no operational GIS was changed.";
const createdAt = "2026-07-28T12:00:00Z";

const sharedTypes = ["corrective_maintenance", "planned_maintenance", "asset_installation", "asset_replacement", "asset_retirement", "connectivity_correction", "data_correction", "inspection_follow_up", "network_extension", "route_adjustment", "construction_update", "emergency_record_correction", "manual_investigation", "multi_operation_job"];
const electricTypes = ["transformer_replacement", "pole_replacement", "conductor_connection", "feeder_assignment_correction", "phase_record_correction", "voltage_record_correction", "conduit_installation_or_association", "device_state_verification", "protective_device_record_update", "electric_asset_retirement", "electric_network_extension"];
const telecomTypes = ["fiber_route_extension", "cable_endpoint_correction", "splice_installation_or_confirmation", "strand_assignment_correction", "capacity_record_correction", "conduit_installation_or_association", "aerial_support_update", "terminal_connection", "cable_replacement", "telecom_asset_retirement", "proposed_construction_completion"];
const waterTypes = ["hydrant_and_valve_installation", "water_main_replacement", "water_main_abandonment", "service_and_meter_installation", "valve_isolation_repair", "water_main_relocation"];
const wastewaterTypes = ["gravity_main_replacement", "manhole_installation", "lateral_repair", "lift_station_and_force_main_installation", "invert_elevation_correction", "legacy_sewer_abandonment", "emergency_blockage_repair"];
const verticalTypes = { electric_distribution: electricTypes, telecom_fiber: telecomTypes, water: waterTypes, wastewater: wastewaterTypes };
const roles = ["requester", "planner", "designer", "utility_gis_technician", "field_technician", "construction_coordinator", "inspector", "qa_reviewer", "data_steward", "technical_reviewer", "final_approver", "closeout_reviewer", "system"];
const prerequisiteTypes = ["approved_proposal", "current_baseline", "required_asset_identifiers", "required_relationships", "design_review_complete", "field_access_confirmed", "source_evidence_available", "material_or_equipment_reference", "safety_review_external", "permit_or_authorization_external", "inspection_required", "qa_rules_available", "trace_scenarios_available", "reviewer_assigned", "final_approver_assigned", "external_adapter_required", "external_system_access_required", "manual_investigation_required"];
const inspectionTypes = ["identifier_verification", "installation_verification", "condition_verification", "location_reference_verification", "relationship_verification", "phase_verification", "voltage_verification", "device_state_verification", "conduit_verification", "structure_support_verification", "cable_endpoint_verification", "splice_verification", "strand_assignment_verification", "capacity_verification", "construction_status_verification", "retirement_verification", "replacement_verification", "diameter_verification", "material_verification", "pressure_zone_verification", "valve_state_verification", "hydrant_verification", "meter_verification", "invert_verification", "rim_elevation_verification", "slope_verification", "flow_direction_verification", "basin_verification"];
const evidenceTypes = ["field_note", "inspection_note", "checklist_result", "identifier_confirmation", "attribute_confirmation", "relationship_confirmation", "installation_record", "retirement_record", "replacement_record", "source_document_reference", "external_ticket_reference", "safe_attachment_metadata", "before_after_summary", "qa_receipt", "trace_receipt", "reviewer_signoff", "implementation_statement", "exception_record"];
const phaseNames = ["Intake", "Planning", "Design Review", "Pre-Work Validation", "Release", "Field or Construction Work", "GIS Record Update", "Post-Work Inspection", "Post-Work QA", "Post-Work Trace Verification", "Technical Review", "Closeout", "Archive"];

type Seed = { code: string; proposal?: string; type: string; title: string; operationCount?: number; blocked?: boolean; invalid?: boolean; complete?: boolean };
const seeds: Record<UtilityVertical, Seed[]> = {
  electric_distribution: [
    { code: "E-WO-001", proposal: "E-EDIT-001", type: "conductor_connection", title: "Connect conductor endpoint", operationCount: 2 },
    { code: "E-WO-002", proposal: "E-EDIT-002", type: "feeder_assignment_correction", title: "Assign transformer feeder", operationCount: 2 },
    { code: "E-WO-003", proposal: "E-EDIT-004", type: "conduit_installation_or_association", title: "Record conduit association", operationCount: 2 },
    { code: "E-WO-004", proposal: "E-EDIT-005", type: "device_state_verification", title: "Confirm device-state record", operationCount: 2 },
    { code: "E-WO-005", proposal: "E-EDIT-006", type: "transformer_replacement", title: "Review transformer replacement", operationCount: 6, blocked: true },
    { code: "E-WO-006", type: "manual_investigation", title: "Incomplete electric investigation", invalid: true },
  ],
  telecom_fiber: [
    { code: "T-WO-001", proposal: "T-EDIT-001", type: "cable_endpoint_correction", title: "Assign cable endpoint", operationCount: 2, complete: true },
    { code: "T-WO-002", proposal: "T-EDIT-002", type: "splice_installation_or_confirmation", title: "Confirm splice relationship", operationCount: 1 },
    { code: "T-WO-003", proposal: "T-EDIT-003", type: "strand_assignment_correction", title: "Correct strand assignment", operationCount: 1 },
    { code: "T-WO-004", proposal: "T-EDIT-004", type: "capacity_record_correction", title: "Correct capacity record", operationCount: 1 },
    { code: "T-WO-005", proposal: "T-EDIT-007", type: "proposed_construction_completion", title: "Review proposed route completion", operationCount: 1 },
    { code: "T-WO-006", proposal: "T-EDIT-008", type: "cable_replacement", title: "Review retired cable replacement", operationCount: 3, blocked: true },
    { code: "T-WO-007", type: "manual_investigation", title: "Incomplete telecom investigation", invalid: true },
  ],
  water: [
    { code: "W-WO-001", proposal: "W-EDIT-001", type: "hydrant_and_valve_installation", title: "Install hydrant and valve", operationCount: 2 },
    { code: "W-WO-002", proposal: "W-EDIT-002", type: "water_main_replacement", title: "Replace water-main segment", operationCount: 2 },
    { code: "W-WO-003", type: "water_main_abandonment", title: "Abandon old main", operationCount: 1 },
    { code: "W-WO-004", type: "service_and_meter_installation", title: "Install service and meter", operationCount: 2 },
    { code: "W-WO-005", type: "valve_isolation_repair", title: "Repair valve-isolation record", operationCount: 1 },
    { code: "W-WO-006", type: "water_main_relocation", title: "Relocate main around road construction", operationCount: 2 },
  ],
  wastewater: [
    { code: "WW-WO-001", proposal: "WW-EDIT-001", type: "gravity_main_replacement", title: "Replace gravity-main segment", operationCount: 2 },
    { code: "WW-WO-002", proposal: "WW-EDIT-002", type: "manhole_installation", title: "Add manhole", operationCount: 1 },
    { code: "WW-WO-003", type: "lateral_repair", title: "Repair lateral", operationCount: 1 },
    { code: "WW-WO-004", type: "lift_station_and_force_main_installation", title: "Install lift station and force main", operationCount: 2 },
    { code: "WW-WO-005", type: "invert_elevation_correction", title: "Correct invert elevations", operationCount: 1 },
    { code: "WW-WO-006", type: "legacy_sewer_abandonment", title: "Abandon legacy sewer", operationCount: 1 },
    { code: "WW-WO-007", type: "emergency_blockage_repair", title: "Record emergency blockage repair", operationCount: 2 },
  ],
};

function seedStore(): WorkOrder[] {
  return (Object.entries(seeds) as Array<[UtilityVertical, Seed[]]>).flatMap(([vertical, items]) =>
    items.map((seed) => buildSeed(vertical, seed)),
  );
}

function buildSeed(vertical: UtilityVertical, seed: Seed): WorkOrder {
  const id = `demo-${seed.code.toLowerCase()}`;
  const blocked = Boolean(seed.blocked || seed.invalid);
  const assignments = ["planner", "utility_gis_technician", "qa_reviewer", "technical_reviewer", "final_approver"]
    .filter((role) => !seed.invalid || ["planner", "utility_gis_technician"].includes(role))
    .map((role) => ({ assignment_id: `${id}-${role}`, role, assignee: `Synthetic ${title(role)}`, assignment_status: seed.complete ? "completed" : "assigned", notes: "Synthetic application role." }));
  const steps = Array.from({ length: seed.invalid ? Math.max(0, (seed.operationCount ?? 0) - 1) : seed.operationCount ?? 0 }, (_, index) => ({
    step_id: `${id}-step-${index + 1}`, source_operation_id: `${seed.proposal ?? seed.code}-OP-${index + 1}`,
    sequence: index + 1, phase_code: "gis_record_update",
    step_type: seed.type.includes("capacity") ? "verify_capacity" : seed.type.includes("strand") ? "verify_strand" : seed.type.includes("device") ? "confirm_device_state" : "verify_relationship",
    title: index ? "Record approved operation result" : title(seed.type),
    instructions: seed.type.includes("device") ? "Verify the proposed device-state record with approved evidence. Do not operate equipment through UtilitiesPlatform." : "Review and record the approved operation result in the synthetic job package.",
    affected_asset_ids: [`demo-${vertical}-asset-${index + 1}`], affected_relationship_ids: [],
    expected_result: "Recorded result matches the approved proposal.", assigned_role: "utility_gis_technician",
    completion_status: seed.complete ? "completed" : "not_started", exception_status: "none",
  }));
  const prerequisites = ["approved_proposal", "current_baseline", "required_asset_identifiers", "qa_rules_available", "trace_scenarios_available", "reviewer_assigned", "final_approver_assigned"].map((type) => ({
    prerequisite_id: `${id}-${type}`, prerequisite_type: type, title: title(type), required: true,
    status: blocked && ["approved_proposal", "current_baseline", "reviewer_assigned", "final_approver_assigned"].includes(type) ? "blocked" : "satisfied",
    description: type === "approved_proposal" ? "The linked Proposed Edit is approved and locked." : "Required synthetic planning evidence is available.",
  }));
  const domainInspection = {
    electric_distribution: "relationship_verification",
    telecom_fiber: "cable_endpoint_verification",
    water: "valve_state_verification",
    wastewater: "invert_verification",
  }[vertical];
  const inspections = ["identifier_verification", domainInspection].map((type) => ({
    inspection_id: `${id}-${type}`, inspection_type: type, title: title(type), required: true,
    status: seed.complete ? "passed" : "pending", result: seed.complete ? "pass" : "not_recorded",
    expected_condition: "Condition agrees with approved evidence.",
  }));
  const implementation = seed.complete ? implementationFor(id, steps) : undefined;
  const conformance = seed.complete ? conformanceFor(steps) : undefined;
  const postQa = seed.complete ? qaFor() : undefined;
  const postTraces = seed.complete ? [traceFor(seed.code)] : [];
  const closed = Boolean(seed.complete);
  return {
    work_order_id: id, work_order_version: 1, scenario_code: seed.code, work_order_number: seed.code,
    utility_vertical: vertical, work_order_type: seed.type, title: seed.title,
    summary: "Deterministic synthetic work-order scenario.", priority: "normal",
    overall_status: closed ? "closed" : "planning", design_status: closed ? "approved" : "draft",
    field_work_status: closed ? "completed" : "not_released",
    gis_implementation_status: closed ? "recorded_in_overlay" : "not_started",
    inspection_status: closed ? "passed" : "pending", qa_status: closed ? "passed_with_warnings" : "not_run",
    trace_status: closed ? "passed" : "not_run", review_status: closed ? "approved" : "not_submitted",
    closeout_status: closed ? "closed" : "not_ready",
    readiness: closed ? "released" : blocked ? "blocked" : "ready_for_review",
    closeout_readiness: closed ? "approved" : "blocked",
    linked_proposal_id: seed.proposal ? `demo-${seed.proposal.toLowerCase()}` : "",
    linked_proposal_version: seed.proposal ? 1 : 0,
    proposal_fingerprint: seed.proposal ? `synthetic-proposal-demo-${seed.proposal.toLowerCase()}-v1-${seed.operationCount}` : "",
    baseline_fingerprint: seed.proposal ? `synthetic-${vertical}-baseline-v1` : "",
    proposal_approved: Boolean(seed.proposal && !seed.blocked), baseline_current: !seed.blocked,
    affected_asset_ids: steps.flatMap((step) => step.affected_asset_ids as string[]),
    affected_relationship_ids: [], requested_by: "Synthetic Requester", created_by: "synthetic_demo",
    current_owner: "Synthetic Planner", final_approver: closed ? "Synthetic Final Reviewer" : "",
    approved_by: closed ? "Synthetic Final Reviewer" : "", approved_at: closed ? createdAt : "",
    target_completion_date: "2026-08-15", external_mapping_status: "adapter_required",
    implementation_confirmation_status: closed ? "simulated_overlay_only" : "not_started",
    version_fingerprint: `synthetic-work-order-${seed.code}-v1`, release_fingerprint: closed ? `synthetic-release-${seed.code}` : "",
    locked: closed, is_synthetic: true, created_at: createdAt, updated_at: createdAt,
    assignments, phases: phaseNames.map((name, index) => ({ phase_id: `${id}-phase-${index + 1}`, phase_code: name.toLowerCase().replaceAll(" ", "_"), phase_name: name, sequence: index + 1, required: index < 12, status: closed ? "completed" : index === 0 ? "ready" : "not_started", assigned_role: "planner" })),
    steps, prerequisites, inspections, evidence: closed ? [{ evidence_id: `${id}-evidence-1`, evidence_type: "implementation_statement", title: "Synthetic implementation statement", summary: implementationNotice, recorded_by: "Synthetic GIS Technician", review_status: "approved" }] : [],
    implementation, conformance, post_work_qa: postQa, post_work_traces: postTraces,
    history: [{ action: "synthetic_scenario_seeded", actor: "system", created_at: createdAt }, ...(closed ? [{ action: "approve_closeout", actor: "Synthetic Final Reviewer", created_at: createdAt }] : [])],
    versions: [{ work_order_version: 1, overall_status: closed ? "closed" : "planning", created_at: createdAt }],
    three_state_comparison: comparisonFor(postQa, postTraces), disclaimer: workOrderDisclaimer,
  };
}

function read(): WorkOrder[] {
  if (typeof sessionStorage === "undefined") return seedStore();
  try {
    const stored = JSON.parse(sessionStorage.getItem(storeKey) ?? "") as WorkOrder[];
    return stored.length ? stored : seedStore();
  } catch { return seedStore(); }
}

function write(items: WorkOrder[]) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(storeKey, JSON.stringify(items));
}

function update(workOrder: WorkOrder) {
  const items = read();
  const index = items.findIndex((item) => item.work_order_id === workOrder.work_order_id);
  if (index >= 0) items[index] = workOrder; else items.push(workOrder);
  workOrder.updated_at = new Date().toISOString();
  write(items);
  return structuredClone(workOrder);
}

export function demoWorkOrderGet(path: string, params: URLSearchParams): unknown {
  const parts = path.split("/");
  if (path === "/api/work-orders/types") return catalog();
  if (path === "/api/work-orders/roles") return { roles, synthetic_identities_only: true };
  if (path === "/api/work-orders/prerequisite-types") return { prerequisite_types: prerequisiteTypes };
  if (path === "/api/work-orders/inspection-types") return { inspection_types: inspectionTypes };
  if (path === "/api/work-orders/evidence-types") return { evidence_types: evidenceTypes, attachment_storage: "metadata_only" };
  if (parts[3] === "types") return catalog(parts[4] as UtilityVertical);
  const vertical = parts[3] as UtilityVertical;
  const items = read().filter((item) => item.utility_vertical === vertical);
  if (!parts[4]) {
    const filtered = items.filter((item) =>
      (!params.get("status") || item.overall_status === params.get("status"))
      && (!params.get("work_order_type") || item.work_order_type === params.get("work_order_type"))
      && (!params.get("priority") || item.priority === params.get("priority"))
      && (!params.get("readiness") || item.readiness === params.get("readiness"))
      && (!params.get("search") || `${item.title} ${item.scenario_code} ${item.work_order_number}`.toLowerCase().includes(params.get("search")!.toLowerCase())),
    );
    return { items: filtered, pagination: { total: filtered.length, limit: 100, offset: 0, has_more: false }, disclaimer: workOrderDisclaimer };
  }
  const item = items.find((row) => row.work_order_id === decodeURIComponent(parts[4]));
  if (!item) throw new Error("Synthetic work order not found.");
  const suffix = parts[5];
  if (!suffix) return item;
  if (["assignments", "phases", "steps", "prerequisites", "inspections", "evidence"].includes(suffix) && !parts[6]) return { items: item[suffix as keyof WorkOrder] };
  if (suffix === "evidence" && parts[6]) return item.evidence.find((row) => row.evidence_id === decodeURIComponent(parts[6])) ?? {};
  if (suffix === "readiness") return readinessFor(item);
  if (suffix === "closeout-readiness") return closeoutFor(item);
  if (suffix === "implementation") return item.implementation ?? {};
  if (suffix === "conformance") return item.conformance ?? {};
  if (suffix === "post-work-qa") return item.post_work_qa ?? {};
  if (suffix === "post-work-traces") return { items: item.post_work_traces };
  if (suffix === "validation-summary") return validationFor(item);
  if (suffix === "safe-summary") return { work_order: item, three_state_comparison: item.three_state_comparison, executable: false, disclaimer: workOrderDisclaimer };
  if (suffix === "job-package") return packageFor(item);
  if (suffix === "completion-receipt") return receiptFor(item);
  return item;
}

export function demoWorkOrderPost(path: string, body: Record<string, unknown> = {}): unknown {
  rejectUnsafe(body);
  const parts = path.split("/");
  const vertical = parts[3] as UtilityVertical;
  if (!parts[4]) return createWorkOrder(vertical, body);
  const item = read().find((row) => row.work_order_id === decodeURIComponent(parts[4]));
  if (!item) throw new Error("Synthetic work order not found.");
  const action = parts[5];
  if (action === "clone") {
    const clone = structuredClone(item);
    clone.work_order_id = `${item.work_order_id}-copy-${Date.now()}`;
    clone.work_order_number = `SYN-COPY-${read().length + 1}`;
    clone.title = String(body.title || `Copy of ${item.title}`);
    clone.overall_status = "draft"; clone.locked = false; clone.history = [{ action: "work_order_cloned", actor: String(body.created_by || "Demo Planner"), created_at: new Date().toISOString() }];
    return update(clone);
  }
  if (action === "new-version") {
    item.work_order_version += 1; item.overall_status = "planning"; item.locked = false;
    item.history.push({ action: "work_order_version_created", actor: body.actor || "Demo Planner", reason: body.reason, created_at: new Date().toISOString() });
    return update(item);
  }
  if (action === "steps" && parts[6] && parts[7]) {
    const step = item.steps.find((row) => row.step_id === decodeURIComponent(parts[6]));
    if (!step) throw new Error("Synthetic job step not found.");
    step.completion_status = parts[7] === "exception" ? "completed_with_exception" : "completed";
    step.completed_by = body.actor || "Synthetic GIS Technician"; step.completion_notes = body.notes || "";
    update(item);
    return step;
  }
  if (action === "prerequisites" && parts[6] && parts[7]) {
    const prerequisite = item.prerequisites.find((row) => row.prerequisite_id === decodeURIComponent(parts[6]));
    if (!prerequisite) throw new Error("Synthetic prerequisite not found.");
    prerequisite.status = parts[7] === "waive" ? "waived" : String(body.status || "satisfied");
    prerequisite.confirmed_by = body.actor || "Synthetic Reviewer"; prerequisite.notes = body.reason || body.notes || "";
    item.readiness = readinessFor(item).state;
    update(item);
    return prerequisite;
  }
  if (action === "inspections" && parts[6] && parts[7] === "record") {
    const inspection = item.inspections.find((row) => row.inspection_id === decodeURIComponent(parts[6]));
    if (!inspection) throw new Error("Synthetic inspection not found.");
    inspection.result = body.result || "pass"; inspection.status = body.result === "pass" ? "passed" : "failed";
    inspection.inspector = body.inspector || "Synthetic Inspector"; inspection.observed_condition = body.observed_condition || "";
    update(item);
    return inspection;
  }
  if (action === "assignments" && !parts[6]) {
    const assignment = { assignment_id: `${item.work_order_id}-${String(body.role)}-${Date.now()}`, role: body.role, assignee: body.assignee, assignment_status: body.assignment_status || "assigned", notes: body.notes || "" };
    item.assignments.push(assignment);
    update(item);
    return assignment;
  }
  if (action === "evidence") {
    const evidence = { evidence_id: `${item.work_order_id}-evidence-${Date.now()}`, ...body, recorded_at: new Date().toISOString(), review_status: body.review_status || "unreviewed" };
    item.evidence.push(evidence);
    update(item);
    return evidence;
  }
  if (action === "record-implementation") {
    const completed = (body.completed_operation_ids as string[] | undefined) ?? item.steps.map((step) => String(step.source_operation_id));
    item.implementation = implementationFor(item.work_order_id, item.steps, completed, (body.skipped_operation_ids as string[] | undefined) ?? [], (body.exception_operation_ids as string[] | undefined) ?? []);
    item.overall_status = "gis_update_recorded"; item.field_work_status = "completed";
    item.gis_implementation_status = "recorded_in_overlay"; item.implementation_confirmation_status = "simulated_overlay_only";
    item.three_state_comparison.recorded_implementation.status = "simulated_overlay_only";
    return update(item).implementation;
  }
  if (action === "run-conformance") {
    if (!item.implementation) throw new Error("Record implementation before conformance.");
    item.conformance = conformanceFor(item.steps, item.implementation.completed_operation_ids as string[], item.implementation.skipped_operation_ids as string[], item.implementation.exception_operation_ids as string[]);
    return update(item).conformance;
  }
  if (action === "run-post-work-qa") {
    if (!item.implementation) throw new Error("Record implementation before post-work QA.");
    item.post_work_qa = qaFor(); item.qa_status = "passed_with_warnings"; item.overall_status = "post_work_validation";
    item.three_state_comparison = comparisonFor(item.post_work_qa, item.post_work_traces);
    return update(item).post_work_qa;
  }
  if (action === "run-post-work-traces") {
    if (!item.implementation) throw new Error("Record implementation before post-work traces.");
    item.post_work_traces = [traceFor(item.scenario_code || item.work_order_id)]; item.trace_status = "passed"; item.overall_status = "post_work_validation";
    item.three_state_comparison = comparisonFor(item.post_work_qa, item.post_work_traces);
    update(item);
    return { items: item.post_work_traces, status: "passed" };
  }
  if (action === "job-package") return packageFor(item);
  if (action === "submit") return transition(item, body, "ready_for_review", "submitted");
  if (action === "start-review") return transition(item, body, "under_review", "under_review");
  if (action === "approve-release") {
    const ready = readinessFor({ ...item, review_status: "approved" });
    if (ready.blockers.length) throw new Error(`Release approval is blocked: ${ready.blockers.join(" ")}`);
    item.approved_by = String(body.actor || "Synthetic Final Reviewer"); item.approved_at = new Date().toISOString();
    return transition(item, body, "approved_for_release", "approved");
  }
  if (action === "release") {
    if (item.review_status !== "approved") throw new Error("Approve for release first.");
    item.field_work_status = "released"; item.locked = true; item.readiness = "released";
    return transition(item, body, "released", "approved");
  }
  if (action === "start-work") { item.field_work_status = "in_progress"; return transition(item, body, "in_progress", item.review_status); }
  if (action === "record-field-complete") { item.field_work_status = "completed"; return transition(item, body, "field_complete", item.review_status); }
  if (action === "record-gis-update") { item.gis_implementation_status = "pending"; return transition(item, body, "gis_update_pending", item.review_status); }
  if (action === "submit-closeout") {
    const ready = closeoutFor(item);
    if (ready.blockers.length) throw new Error(`Closeout is blocked: ${ready.blockers.join(" ")}`);
    item.closeout_status = "under_review"; return transition(item, body, "closeout_review", item.review_status);
  }
  if (action === "approve-closeout") {
    if (item.overall_status !== "closeout_review") throw new Error("Submit closeout first.");
    item.closeout_status = "closed"; item.final_approver = String(body.actor || "Synthetic Final Reviewer"); item.locked = true;
    return transition(item, body, "closed", "approved");
  }
  if (["request-revision", "reject", "defer", "reopen", "suspend", "cancel", "supersede"].includes(action)) {
    const states: Record<string, string> = { "request-revision": "planning", reject: "rejected", defer: "deferred", reopen: "planning", suspend: "suspended", cancel: "cancelled", supersede: "superseded" };
    return transition(item, body, states[action], action === "request-revision" ? "revision_requested" : item.review_status);
  }
  return update(item);
}

export function demoWorkOrderPut(path: string, body: Record<string, unknown>): unknown {
  rejectUnsafe(body);
  const parts = path.split("/");
  const item = read().find((row) => row.work_order_id === decodeURIComponent(parts[4]));
  if (!item || item.locked) throw new Error("Released work-order definitions are immutable.");
  if (parts[5] === "assignments") {
    const assignment = item.assignments.find((row) => row.assignment_id === decodeURIComponent(parts[6]));
    if (!assignment) throw new Error("Synthetic assignment not found.");
    Object.assign(assignment, body);
    update(item);
    return assignment;
  }
  const step = item.steps.find((row) => row.step_id === decodeURIComponent(parts[6]));
  if (!step) throw new Error("Synthetic job step not found.");
  Object.assign(step, body);
  update(item);
  return step;
}

export function demoWorkOrderDelete(path: string): unknown {
  const parts = path.split("/");
  const item = read().find((row) => row.work_order_id === decodeURIComponent(parts[4]));
  if (!item || item.locked) throw new Error("Assignments cannot be removed after release.");
  item.assignments = item.assignments.filter((row) => row.assignment_id !== decodeURIComponent(parts[6]));
  update(item);
  return { removed: true, history_preserved: true };
}

function createWorkOrder(vertical: UtilityVertical, body: Record<string, unknown>): WorkOrder {
  const workOrderType = String(body.work_order_type || "manual_investigation");
  const proposal = body.proposal as ProposedEdit | undefined;
  if (workOrderType !== "manual_investigation" && (!body.proposal_id || body.proposal_approved === false)) throw new Error("Operational work orders require an approved Proposed Edit.");
  if (workOrderType === "manual_investigation" && body.proposal_id) throw new Error("Manual investigations do not carry network-changing operations.");
  const seed: Seed = {
    code: `DEMO-WO-${read().length + 1}`, proposal: proposal?.scenario_code || String(body.proposal_code || ""),
    type: workOrderType, title: String(body.title || "Synthetic work order"),
    operationCount: Number(body.operation_count || proposal?.operations?.length || 0),
  };
  const item = buildSeed(vertical, seed);
  item.work_order_id = `demo-work-order-${Date.now()}`;
  item.scenario_code = ""; item.work_order_number = `SYN-WO-${read().length + 1}`;
  item.linked_proposal_id = String(body.proposal_id || ""); item.linked_proposal_version = Number(body.proposal_version || 0);
  item.proposal_approved = workOrderType === "manual_investigation" || body.proposal_approved !== false;
  item.created_by = String(body.created_by || "Demo Planner"); item.current_owner = item.created_by;
  return update(item);
}

function transition(item: WorkOrder, body: Record<string, unknown>, overall: string, review: string) {
  item.overall_status = overall; item.review_status = review;
  item.history.push({ action: overall, actor: body.actor || body.reviewer || "Synthetic Reviewer", notes: body.notes || "", created_at: new Date().toISOString() });
  item.readiness = readinessFor(item).state; item.closeout_readiness = closeoutFor(item).state;
  return update(item);
}

function readinessFor(item: WorkOrder) {
  const blockers: string[] = [];
  if (item.work_order_type !== "manual_investigation" && !item.proposal_approved) blockers.push("An approved Proposed Edit is required.");
  if (!item.baseline_current) blockers.push("The proposal baseline is stale.");
  for (const role of ["technical_reviewer", "final_approver"]) if (!item.assignments.some((row) => row.role === role)) blockers.push(`Required ${title(role)} assignment is missing.`);
  item.prerequisites.filter((row) => row.required && !["satisfied", "satisfied_with_conditions", "waived", "not_applicable"].includes(String(row.status))).forEach((row) => blockers.push(`Prerequisite blocked: ${String(row.title)}.`));
  const released = ["released", "in_progress", "field_complete", "gis_update_pending", "gis_update_recorded", "post_work_validation", "closeout_review", "closed"].includes(item.overall_status);
  return { state: blockers.length ? "blocked" : released ? "released" : item.review_status === "approved" ? "ready_for_release" : "ready_for_review", blockers };
}

function closeoutFor(item: WorkOrder) {
  const blockers: string[] = [];
  if (item.steps.some((row) => !["completed", "completed_with_exception", "skipped"].includes(String(row.completion_status)))) blockers.push("Required job steps are incomplete.");
  if (item.inspections.some((row) => row.required && !["pass", "pass_with_conditions", "not_applicable"].includes(String(row.result)))) blockers.push("Required inspections are incomplete or failed.");
  if (!item.conformance || !["conformant", "conformant_with_conditions"].includes(String(item.conformance.status))) blockers.push("Implementation conformance is incomplete.");
  if (!item.post_work_qa || !["passed", "passed_with_warnings"].includes(String(item.post_work_qa.status))) blockers.push("Post-work QA has not passed.");
  if (!item.post_work_traces.length || item.post_work_traces.some((row) => !["passed", "passed_with_warnings"].includes(String(row.status)))) blockers.push("Required traces have not passed.");
  return { state: blockers.length ? "blocked" : item.closeout_status === "closed" ? "approved" : "ready", blockers };
}

function implementationFor(id: string, steps: WorkOrderRecord[], completed = steps.map((step) => String(step.source_operation_id)), skipped: string[] = [], exceptions: string[] = []) {
  return { implementation_record_id: `${id}-implementation-1`, implementation_type: "synthetic_overlay", status: "simulated_overlay_only", completed_operation_ids: completed, skipped_operation_ids: skipped, exception_operation_ids: exceptions, overlay_fingerprint: `${id}-implementation-overlay-v1`, recorded_by: "Synthetic GIS Technician", recorded_at: createdAt, notice: implementationNotice };
}

function conformanceFor(steps: WorkOrderRecord[], completed = steps.map((step) => String(step.source_operation_id)), skipped: string[] = [], exceptions: string[] = []) {
  const expected = steps.map((step) => String(step.source_operation_id));
  const missing = expected.filter((id) => !completed.includes(id) && !skipped.includes(id) && !exceptions.includes(id));
  const mismatched = [...skipped, ...exceptions].filter((id) => expected.includes(id));
  return { conformance_run_id: `demo-conformance-${expected.length}`, status: missing.length ? "nonconformant" : mismatched.length ? "conformant_with_conditions" : "conformant", approved_operation_count: expected.length, completed_operation_count: completed.filter((id) => expected.includes(id)).length, missing_operation_ids: missing, unexpected_operation_ids: completed.filter((id) => !expected.includes(id)), mismatched_operation_ids: mismatched, compliant_operation_ids: completed.filter((id) => expected.includes(id)), exceptions: exceptions.map((id) => ({ operation_id: id, reason: "Recorded exception requires review." })) };
}

function qaFor() {
  return { work_order_post_qa_run_id: "demo-post-qa-1", status: "passed_with_warnings", comparison: { comparison_status: "improved", baseline_blocker_count: 4, proposed_blocker_count: 2, baseline_warning_count: 8, proposed_warning_count: 7, resolved_issue_group_ids: ["SYN-QA-RESOLVED-1", "SYN-QA-RESOLVED-2"], unchanged_issue_group_ids: ["SYN-QA-BACKGROUND"], new_issue_group_ids: [], worsened_issue_group_ids: [] }, warnings: ["Synthetic background warning remains."] };
}

function traceFor(code: string) {
  const traceType = code.startsWith("WW-") ? "WW-TRACE-001" : code.startsWith("W-") ? "WATER-TRACE-005" : code.startsWith("E") ? "ELEC-TRACE-002" : "TEL-TRACE-003";
  return { work_order_post_trace_run_id: `demo-post-trace-${code}`, status: "passed", trace_type: traceType, comparison_result: { result: "unchanged", approved: { outcome: "complete_with_warnings", confidence: "medium", objective_reached: true, path_signature: `${code}-approved`, branch_signature: `${code}-branch` }, implemented: { outcome: "complete_with_warnings", confidence: "medium", objective_reached: true, path_signature: `${code}-approved`, branch_signature: `${code}-branch` }, baseline: { outcome: "blocked", confidence: "low", objective_reached: false, path_signature: `${code}-baseline`, branch_signature: `${code}-branch` } } };
}

function comparisonFor(qa?: WorkOrderRecord, traces: WorkOrderRecord[] = []): ThreeStateComparison {
  const comparison = qa?.comparison as Record<string, unknown> | undefined;
  const trace = traces[0]?.comparison_result as Record<string, Record<string, unknown>> | undefined;
  return {
    baseline: { label: "Baseline", qa_blockers: comparison?.baseline_blocker_count ?? 4, qa_warnings: comparison?.baseline_warning_count ?? 8, trace: trace?.baseline?.outcome ?? "blocked" },
    approved_plan: { label: "Approved Plan", qa_blockers: comparison?.proposed_blocker_count ?? 2, qa_warnings: comparison?.proposed_warning_count ?? 7, trace: trace?.approved?.outcome ?? "complete_with_warnings" },
    recorded_implementation: { label: "Recorded Implementation", qa_blockers: qa ? comparison?.proposed_blocker_count : null, qa_warnings: qa ? comparison?.proposed_warning_count : null, trace: trace?.implemented?.outcome ?? "not_run", status: qa ? "simulated_overlay_only" : "not_started" },
    notice: implementationNotice,
  };
}

function validationFor(item: WorkOrder) {
  return { work_order_id: item.work_order_id, conformance: item.conformance ?? {}, post_work_qa: item.post_work_qa ?? {}, post_work_traces: item.post_work_traces, closeout_readiness: closeoutFor(item), three_state_comparison: item.three_state_comparison, notice: implementationNotice };
}

function packageFor(item: WorkOrder) {
  if (item.review_status !== "approved" && !["released", "in_progress", "gis_update_recorded", "post_work_validation", "closeout_review", "closed"].includes(item.overall_status)) throw new Error("Release approval is required before package generation.");
  return { package_id: `demo-job-package-${item.work_order_id}-v${item.work_order_version}`, package_version: "work-order-job-package-v1", work_order_id: item.work_order_id, work_order_version: item.work_order_version, utility_vertical: item.utility_vertical, work_order_type: item.work_order_type, linked_proposal_id: item.linked_proposal_id, linked_proposal_version: item.linked_proposal_version, approved_proposal_fingerprint: item.proposal_fingerprint, work_order_fingerprint: item.version_fingerprint, priority: item.priority, assignments: item.assignments, prerequisites: item.prerequisites, work_phases: item.phases, ordered_job_steps: item.steps, inspection_requirements: item.inspections, qa_requirements: ["Connectivity QA against recorded implementation overlay"], trace_requirements: ["Selected proposal and affected-asset trace scenarios"], affected_canonical_asset_ids: item.affected_asset_ids, affected_relationship_ids: item.affected_relationship_ids, release_approval: { approved_by: item.approved_by, approved_at: item.approved_at }, external_mapping_status: "adapter_required", required_adapter_capabilities: ["create_work_order", "attach_job_step", "attach_evidence", "run_network_validation", "external_approval_required"], executable: false, descriptive_only: true, disclaimer: workOrderDisclaimer };
}

function receiptFor(item: WorkOrder) {
  if (item.overall_status !== "closed") throw new Error("Completion receipt is available only after approved closeout.");
  return { receipt_id: `demo-completion-receipt-${item.work_order_id}`, receipt_version: "work-order-completion-receipt-v1", work_order_id: item.work_order_id, work_order_version: item.work_order_version, linked_approved_proposal: { proposal_id: item.linked_proposal_id, version: item.linked_proposal_version, fingerprint: item.proposal_fingerprint }, implementation_record_id: item.implementation?.implementation_record_id, implementation_result: item.implementation?.status, conformance: item.conformance, completed_steps: item.steps.map((row) => row.step_id), inspections: item.inspections, evidence_ids: item.evidence.map((row) => row.evidence_id), post_work_qa: item.post_work_qa, post_work_traces: item.post_work_traces, closeout_approval: { approved_by: item.final_approver, approved_at: item.updated_at }, external_implementation_status: item.implementation_confirmation_status, closeout_fingerprint: `synthetic-closeout-${item.work_order_id}`, disclaimer: "Completion receipt records the UtilitiesPlatform job-review workflow. It does not prove that a real operational utility system was updated unless separately verified through an authorized external process." };
}

function catalog(vertical?: UtilityVertical) {
  return vertical ? { utility_vertical: vertical, work_order_types: [...sharedTypes, ...verticalTypes[vertical]], priorities: ["low", "normal", "high", "urgent", "emergency_record_review"], disclaimer: workOrderDisclaimer } : { version: "work-order-v1", utility_verticals: Object.keys(verticalTypes), shared_work_order_types: sharedTypes, vertical_work_order_types: verticalTypes, disclaimer: workOrderDisclaimer };
}

function rejectUnsafe(value: unknown) {
  const serialized = JSON.stringify(value);
  if (/[A-Za-z]:[\\/]|https?:\/\/|\\\\|\"(?:sql|python|shell|command|script|credentials|connection_string)\"|(?:\.exe|\.bat|\.cmd|\.ps1|\.py|\.sh)\"/i.test(serialized)) throw new Error("Executable, filesystem, external URL, and credential inputs are not accepted.");
}

function title(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function resetDemoWorkOrders() {
  if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(storeKey);
}
