import type { Issue } from "../api-types";
import type { AutomationLayerState, AutomationRun, AutomationSummary, DataSourceItem, DuplicateGroup, IntakeSubmission, StagingPlanItem, SubmissionLayer } from "./types";

const key = "utilities-platform-demo-reviews";
const intakeKey = "utilities-platform-demo-intake";
const inspectionKey = "utilities-platform-demo-source-inspection";

type ReviewPatch = Partial<Issue>;
type ReviewMap = Record<string, ReviewPatch>;
type InspectionStore = {
  layerReviews: Record<string, Partial<SubmissionLayer>>;
  duplicateGroups: Record<string, Partial<DuplicateGroup>>;
  stagingPlan: Record<string, Partial<StagingPlanItem>>;
  stagedOutputs: DataSourceItem[];
  automation: Record<string, { latest: AutomationRun; runs: AutomationRun[]; summary: AutomationSummary }>;
};

function read(): ReviewMap {
  if (typeof sessionStorage === "undefined") return {};
  try {
    return JSON.parse(sessionStorage.getItem(key) ?? "{}") as ReviewMap;
  } catch {
    return {};
  }
}

function write(reviews: ReviewMap) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(key, JSON.stringify(reviews));
}

export function applyDemoReview(issue: Issue): Issue {
  const patch = read()[issue.issue_id];
  return patch ? { ...issue, ...patch, review_status: patch.workflow_status ?? patch.review_status ?? issue.review_status } : issue;
}

export function updateDemoIssue(issue: Issue, update: ReviewPatch): Issue {
  const reviews = read();
  reviews[issue.issue_id] = { ...reviews[issue.issue_id], ...update };
  write(reviews);
  return applyDemoReview(issue);
}

export function batchUpdateDemoIssues(issues: Issue[], issueIds: string[], update: ReviewPatch) {
  const byId = new Set(issueIds);
  const reviews = read();
  const updated = issues.filter((issue) => byId.has(issue.issue_id)).map((issue) => issue.issue_id);
  for (const issueId of updated) reviews[issueId] = { ...reviews[issueId], ...update };
  write(reviews);
  return { updated_count: updated.length, updated_issue_ids: updated, missing_issue_ids: issueIds.filter((issueId) => !updated.includes(issueId)) };
}

export function resetDemoSession() {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(key);
    sessionStorage.removeItem(intakeKey);
    sessionStorage.removeItem(inspectionKey);
  }
}

export function readDemoIntake(): IntakeSubmission[] {
  if (typeof sessionStorage === "undefined") return [];
  try {
    return JSON.parse(sessionStorage.getItem(intakeKey) ?? "[]") as IntakeSubmission[];
  } catch {
    return [];
  }
}

export function writeDemoIntake(items: IntakeSubmission[]) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(intakeKey, JSON.stringify(items));
}

export function resetDemoIntake() {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(intakeKey);
    sessionStorage.removeItem(inspectionKey);
  }
}

export function createDemoIntakeSubmission(formData: FormData): IntakeSubmission {
  const file = formData.getAll("files").find((value): value is File => typeof File !== "undefined" && value instanceof File);
  const now = new Date().toISOString();
  const sample = formData.get("demo_sample") === "true";
  const directory = formData.get("package_mode") === "directory";
  const filename = sample ? "Sample_Mixed_Utility_Source.gdb" : String(formData.get("directory_root") || file?.name || "Selected_Metadata_Only_Source.dat");
  const size = sample ? 1843200 : Number(formData.get("directory_size") || file?.size || 0);
  const fileCount = Number(formData.get("directory_file_count") || (file ? 1 : 0));
  const submission: IntakeSubmission = {
    submission_id: `DEMO-UPL-${Date.now().toString(36).toUpperCase()}`,
    submission_name: String(formData.get("submission_name") || (sample ? "Synthetic Mixed Utility Source" : "Metadata-Only Demo Source")),
    original_filename: filename,
    utility_system: sample ? "mixed" : String(formData.get("utility_system") || "wastewater"),
    source_type: String(formData.get("source_type") || "demo_source"),
    source_format: sample || directory ? "file_geodatabase" : detectDemoFormat(filename),
    source_owner: String(formData.get("source_owner") || "Synthetic Data Owner"),
    source_description: String(formData.get("source_description") || "Session-only portfolio demo intake simulation."),
    sensitivity_level: String(formData.get("sensitivity_level") || "restricted"),
    project_id: String(formData.get("project_id") || "DEMO"),
    authorization_confirmed: true,
    file_size_bytes: size,
    sha256_prefix: sample || directory ? "syntheticgdb" : "metadataonly",
    mime_type: sample || directory ? "application/vnd.esri.filegdb" : file?.type ?? "metadata-only",
    extension: sample || directory ? ".gdb" : filename.includes(".") ? `.${filename.split(".").pop()}` : "",
    current_status: "inventory_complete",
    current_stage: "raw",
    inventory_status: "complete",
    classification_status: "review_required",
    staging_status: "not_approved",
    duplicate_of_submission_id: "",
    created_at: now,
    updated_at: now,
    raw_registered_at: now,
    inventory_started_at: now,
    inventory_completed_at: now,
    files: [{ safe_filename: filename, relative_role: sample || directory ? "synthetic_directory_package" : "metadata_only", extension: sample || directory ? ".gdb" : filename.includes(".") ? `.${filename.split(".").pop()}` : "", size_bytes: size, validation_status: "simulated", notes: directory ? `${fileCount} selected files; demo mode did not upload or read file contents.` : "Demo mode did not upload or read file contents." }],
    lineage: ["Selected package", "Demo validation", "Synthetic Raw registration", "Synthetic source inspection", "Human staging approval required"],
    blockers: ["Demo mode is non-persistent", "Human staging approval required"],
    next_required_action: "Review synthetic child-layer classifications before simulated staging.",
  };
  const items = [submission, ...readDemoIntake()];
  writeDemoIntake(items);
  return submission;
}

export function updateDemoIntakeInventory(submissionId: string): Record<string, unknown> {
  const items = readDemoIntake();
  const updated = items.map((item) => item.submission_id === submissionId ? { ...item, current_status: "inventory_complete", inventory_status: "complete", classification_status: "review_required" } : item);
  writeDemoIntake(updated);
  return { submission_id: submissionId, inventory_status: "complete", classification_status: "review_required", run_id: "DEMO-INVENTORY" };
}

export function demoIntakeEvents(submissionId: string) {
  const item = readDemoIntake().find((submission) => submission.submission_id === submissionId);
  if (!item) return [];
  const automation = readInspection().automation[submissionId];
  return [
    { event_id: `${submissionId}-1`, submission_id: submissionId, event_type: "upload_started", message: "Demo upload simulation started; no backend request was made.", created_at: String(item.created_at), previous_status: "", new_status: "uploading", actor: "demo" },
    { event_id: `${submissionId}-2`, submission_id: submissionId, event_type: "raw_registered", message: "Synthetic Raw registration created in sessionStorage.", created_at: String(item.created_at), previous_status: "validating", new_status: "registered_raw", actor: "demo" },
    { event_id: `${submissionId}-3`, submission_id: submissionId, event_type: "source_inspection_completed", message: "Synthetic child-layer inspection results loaded for portfolio review.", created_at: String(item.created_at), previous_status: "inspection_running", new_status: "inspection_complete", actor: "demo" },
    ...(automation ? [{ event_id: `${submissionId}-4`, submission_id: submissionId, event_type: "automated_review_completed", message: "Synthetic conservative review completed in sessionStorage.", created_at: String(automation.latest.completed_at), previous_status: "inspection_complete", new_status: "automated_review_complete", actor: "demo_automation" }] : []),
  ];
}

export function runDemoAutomatedReview(
  submissionId: string,
  layers: SubmissionLayer[],
  duplicateGroups: DuplicateGroup[],
  forceRecalculate = false,
): AutomationRun {
  const store = readInspection();
  const previous = store.automation[submissionId];
  if (previous && !forceRecalculate) {
    const unchanged = { ...previous.latest, automation_run_id: `DEMO-AUT-${Date.now().toString(36).toUpperCase()}`, status: "unchanged", reused_run_id: previous.latest.automation_run_id };
    previous.runs = [unchanged, ...previous.runs];
    previous.latest = unchanged;
    writeInspection(store);
    return unchanged;
  }
  const now = new Date().toISOString();
  const states = layers.map((layer): AutomationLayerState => {
    const decision = String(layer.classification_decision ?? "");
    const excluded = decision === "excluded";
    const deferred = decision === "deferred";
    const manuallyApproved = decision === "manual_override";
    const approved = !excluded && !deferred && (manuallyApproved || (layer.confidence === "high" && layer.utility_system !== "review_required"));
    const duplicate = layer.duplicate_status === "potential_duplicate";
    const coordinateBlocked = layer.coordinate_status !== "coordinate_ready";
    const ownerConfirmed = layer.owner_decision === "acknowledge_provisional";
    const blockers = [
      ...(!approved ? ["Taxonomy requires human review."] : []),
      ...(coordinateBlocked ? ["Coordinate metadata requires human review."] : []),
      ...(duplicate ? ["Potential duplicate requires individual review."] : []),
      ...(approved && !ownerConfirmed ? ["Final staging reviewer must acknowledge provisional ownership."] : []),
    ];
    return {
      layer_id: layer.layer_id,
      source_layer_name: layer.source_layer_name,
      canonical_layer_name: layer.source_layer_name,
      taxonomy_status: excluded ? "excluded" : approved ? "approved" : "deferred",
      taxonomy_decision: excluded ? "excluded" : manuallyApproved ? "manual_override_preserved" : deferred ? "deferred" : approved ? "approved" : "needs_taxonomy_review",
      coordinate_status: coordinateBlocked ? "coordinate_name_conflict" : "coordinate_ready",
      sensitivity_status: "inherited_from_package",
      duplicate_status: layer.duplicate_status,
      owner_status: ownerConfirmed ? "confirmed" : "provisional",
      staging_readiness: excluded ? "excluded" : coordinateBlocked || duplicate ? "staging_blocked" : approved ? ownerConfirmed ? "fully_ready_for_staging_review" : "human_review_required" : "deferred",
      staging_blockers: blockers,
      approved_utility_system: layer.approved_utility_system ?? layer.utility_system,
      approved_network_group: layer.approved_network_group ?? layer.network_group,
      approved_asset_category: layer.approved_asset_category ?? layer.asset_category,
      approved_asset_subcategory: layer.approved_asset_subcategory ?? layer.asset_subcategory,
      approved_operational_role: layer.approved_operational_role ?? layer.operational_role,
      approved_lifecycle_representation: layer.approved_lifecycle_representation ?? layer.lifecycle_representation,
      owner_candidate: layer.approved_owner_or_jurisdiction ?? layer.owner_or_jurisdiction,
      owner_confidence: ownerConfirmed ? "human_confirmed" : "high",
      coordinate_blocker: coordinateBlocked ? "Synthetic coordinate naming conflict." : "",
      sensitivity_blocker: "",
      approved_for_staging: false,
    };
  });
  for (const state of states) {
    store.layerReviews[state.layer_id] = {
      ...store.layerReviews[state.layer_id],
      classification_status: state.taxonomy_status,
      sensitivity_status: "inherited_from_package",
      duplicate_status: state.duplicate_status,
    };
  }
  const stageNames = ["validate_inspection", "apply_sensitivity", "normalize_names", "classify_layers", "evaluate_coordinates", "detect_duplicates", "evaluate_ownership", "calculate_staging_readiness", "generate_staging_preview", "write_summary"];
  const latest: AutomationRun = {
    automation_run_id: `DEMO-AUT-${Date.now().toString(36).toUpperCase()}`,
    status: "complete",
    rule_version: "source_review_automation_v1",
    policy_mode: "conservative",
    layers_processed: states.length,
    taxonomy_approved: states.filter((state) => state.taxonomy_status === "approved").length,
    taxonomy_deferred: states.filter((state) => state.taxonomy_status === "deferred").length,
    coordinate_blocked: states.filter((state) => state.coordinate_status !== "coordinate_ready").length,
    duplicate_groups: duplicateGroups.length,
    sensitivity_inherited: states.length,
    owner_confirmation_required: states.filter((state) => state.owner_status !== "confirmed").length,
    staging_ready: states.filter((state) => state.staging_readiness === "fully_ready_for_staging_review").length,
    staging_blocked: states.filter((state) => state.staging_readiness !== "fully_ready_for_staging_review").length,
    started_at: now,
    completed_at: now,
    stages: stageNames.map((stage_name) => ({ stage_name, status: "complete", records_read: states.length, records_updated: states.length })),
  };
  const exceptions = {
    taxonomy_ambiguity: states.filter((state) => state.taxonomy_status === "deferred"),
    coordinate_conflict: states.filter((state) => state.coordinate_status !== "coordinate_ready"),
    duplicate_candidate: states.filter((state) => state.duplicate_status === "potential_duplicate"),
    owner_uncertainty: states.filter((state) => state.owner_status !== "confirmed"),
    sensitivity_escalation: [],
    unsupported_source: [],
    out_of_scope_recommendation: [],
  };
  const summary: AutomationSummary = {
    latest_run: latest,
    rule_version: latest.rule_version,
    policy_mode: latest.policy_mode,
    layers: states,
    exceptions,
    exception_count: new Set(Object.values(exceptions).flat().map((state) => state.layer_id)).size,
    taxonomy_approved_operational: states.filter((state) => state.taxonomy_status === "approved").map((state) => state.source_layer_name),
    taxonomy_approved_reference: [],
    staging_ready_layers: states.filter((state) => state.staging_readiness === "fully_ready_for_staging_review").map((state) => state.source_layer_name),
    message: "Synthetic automated review results loaded.",
  };
  store.automation[submissionId] = { latest, runs: [latest, ...(previous?.runs ?? [])], summary };
  writeInspection(store);
  return latest;
}

export function demoAutomatedReviewStatus(submissionId: string): AutomationRun {
  return readInspection().automation[submissionId]?.latest ?? {
    automation_run_id: "",
    status: "not_started",
    rule_version: "source_review_automation_v1",
    policy_mode: "conservative",
    layers_processed: 0,
    taxonomy_approved: 0,
    taxonomy_deferred: 0,
    coordinate_blocked: 0,
    duplicate_groups: 0,
    sensitivity_inherited: 0,
    owner_confirmation_required: 0,
    staging_ready: 0,
    staging_blocked: 0,
  };
}

export function demoAutomatedReviewSummary(submissionId: string): AutomationSummary {
  return readInspection().automation[submissionId]?.summary ?? {
    latest_run: demoAutomatedReviewStatus(submissionId),
    rule_version: "source_review_automation_v1",
    policy_mode: "conservative",
    layers: [],
    exceptions: {},
    exception_count: 0,
    taxonomy_approved_operational: [],
    taxonomy_approved_reference: [],
    staging_ready_layers: [],
    message: "Synthetic automated review has not run.",
  };
}

export function demoAutomatedReviewRuns(submissionId: string) {
  const runs = readInspection().automation[submissionId]?.runs ?? [];
  return { items: runs, message: runs.length ? "Synthetic automation history loaded." : "Synthetic automated review has not run." };
}

export function applyDemoLayerReview(layer: SubmissionLayer): SubmissionLayer {
  return { ...layer, ...readInspection().layerReviews[layer.layer_id] };
}

export function updateDemoLayerReview(layer: SubmissionLayer, update: Record<string, unknown>): SubmissionLayer {
  const store = readInspection();
  const decision = String(update.classification_decision ?? "");
  const review = {
    ...update,
    latest_review_status: String(update.workflow_status || "classification_approved"),
    latest_reviewer: String(update.reviewer || "demo_reviewer"),
    classification_status: decision === "excluded" ? "excluded" : decision === "deferred" ? "deferred" : "classification_approved",
    sensitivity_status: update.sensitivity_decision === "complete" ? "sensitivity_review_complete" : layer.sensitivity_status,
  };
  store.layerReviews[layer.layer_id] = { ...store.layerReviews[layer.layer_id], ...review };
  writeInspection(store);
  return applyDemoLayerReview(layer);
}

export function batchUpdateDemoLayers(layers: SubmissionLayer[], layerIds: string[], update: Record<string, unknown>) {
  const byId = new Set(layerIds);
  const store = readInspection();
  const updated = layers.filter((layer) => byId.has(layer.layer_id)).map((layer) => layer.layer_id);
  for (const layerId of updated) {
    store.layerReviews[layerId] = {
      ...store.layerReviews[layerId],
      latest_review_status: String(update.workflow_status || "classification_approved"),
      latest_reviewer: String(update.reviewer || "demo_reviewer"),
      classification_status: "classification_approved",
    };
  }
  writeInspection(store);
  return { updated_count: updated.length, updated_layer_ids: updated, missing_layer_ids: layerIds.filter((layerId) => !updated.includes(layerId)) };
}

export function updateDemoDuplicateGroup(group: DuplicateGroup, update: Record<string, unknown>): DuplicateGroup {
  const store = readInspection();
  store.duplicateGroups[group.duplicate_group_id] = { ...store.duplicateGroups[group.duplicate_group_id], ...update, updated_at: new Date().toISOString() };
  writeInspection(store);
  return applyDemoDuplicateGroup(group);
}

export function applyDemoDuplicateGroup(group: DuplicateGroup): DuplicateGroup {
  return { ...group, ...readInspection().duplicateGroups[group.duplicate_group_id] };
}

export function updateDemoStagingPlanItem(item: StagingPlanItem, update: Record<string, unknown>): StagingPlanItem {
  const store = readInspection();
  const approved = Boolean(update.approved_for_staging);
  store.stagingPlan[item.staging_plan_item_id] = {
    ...store.stagingPlan[item.staging_plan_item_id],
    ...update,
    approved_for_staging: approved,
    approval_status: approved ? "approved" : String(update.approval_status || item.approval_status),
    blocker: approved ? "" : String(update.blocker || item.blocker || ""),
    reviewed_at: approved ? new Date().toISOString() : String(update.reviewed_at || item.reviewed_at || ""),
  };
  writeInspection(store);
  return { ...item, ...store.stagingPlan[item.staging_plan_item_id] };
}

export function applyDemoStagingPlanItem(item: StagingPlanItem): StagingPlanItem {
  return { ...item, ...readInspection().stagingPlan[item.staging_plan_item_id] };
}

export function stageDemoApprovedLayers(items: StagingPlanItem[]) {
  const store = readInspection();
  const approved = items.map(applyDemoStagingPlanItem).filter((item) => item.approved_for_staging);
  const existing = new Set(store.stagedOutputs.map((item) => item.item_id));
  const outputs = approved
    .filter((item) => !existing.has(`demo-staged:${item.staging_plan_item_id}`))
    .map((item) => ({
      item_id: `demo-staged:${item.staging_plan_item_id}`,
      name: item.proposed_target_name,
      stage: "staging" as const,
      utility_system: String(item.target_utility_system),
      network_group: String(item.target_network_group),
      asset_category: String(item.target_asset_category),
      asset_subcategory: String(item.target_asset_subcategory),
      source_format: "file_geodatabase",
      sensitivity_level: "public_demo",
      status: "simulated_staged",
      inventory_status: "complete",
      classification_status: "classification_approved",
      staging_status: "approved",
      next_required_action: "Run utility-specific QA in local mode; demo staging is temporary.",
      lineage: ["Synthetic Raw source", "Child-layer review", "Simulated submission-specific staging"],
      blockers: [],
    }));
  store.stagedOutputs = [...store.stagedOutputs, ...outputs];
  writeInspection(store);
  return { status: "simulated", staged_count: outputs.length, message: "Demo staging was simulated in sessionStorage." };
}

export function readDemoStagedOutputs(): DataSourceItem[] {
  return readInspection().stagedOutputs;
}

function readInspection(): InspectionStore {
  if (typeof sessionStorage === "undefined") return emptyInspectionStore();
  try {
    return { ...emptyInspectionStore(), ...JSON.parse(sessionStorage.getItem(inspectionKey) ?? "{}") as Partial<InspectionStore> };
  } catch {
    return emptyInspectionStore();
  }
}

function writeInspection(store: InspectionStore) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(inspectionKey, JSON.stringify(store));
}

function emptyInspectionStore(): InspectionStore {
  return { layerReviews: {}, duplicateGroups: {}, stagingPlan: {}, stagedOutputs: [], automation: {} };
}

function detectDemoFormat(filename: string) {
  const extension = filename.toLowerCase().split(".").pop();
  if (extension === "zip") return "shapefile";
  if (extension === "gpkg") return "geopackage";
  if (extension === "dwg" || extension === "dxf") return "cad";
  if (extension === "pdf") return "pdf";
  if (extension === "csv" || extension === "xlsx") return "spreadsheet";
  return "metadata_only";
}
