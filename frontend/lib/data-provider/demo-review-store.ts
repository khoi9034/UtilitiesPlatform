import type { Issue } from "../api-types";
import type { DataSourceItem, DuplicateGroup, IntakeSubmission, StagingPlanItem, SubmissionLayer } from "./types";

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
  return [
    { event_id: `${submissionId}-1`, submission_id: submissionId, event_type: "upload_started", message: "Demo upload simulation started; no backend request was made.", created_at: String(item.created_at), previous_status: "", new_status: "uploading", actor: "demo" },
    { event_id: `${submissionId}-2`, submission_id: submissionId, event_type: "raw_registered", message: "Synthetic Raw registration created in sessionStorage.", created_at: String(item.created_at), previous_status: "validating", new_status: "registered_raw", actor: "demo" },
    { event_id: `${submissionId}-3`, submission_id: submissionId, event_type: "source_inspection_completed", message: "Synthetic child-layer inspection results loaded for portfolio review.", created_at: String(item.created_at), previous_status: "inspection_running", new_status: "inspection_complete", actor: "demo" },
  ];
}

export function applyDemoLayerReview(layer: SubmissionLayer): SubmissionLayer {
  return { ...layer, ...readInspection().layerReviews[layer.layer_id] };
}

export function updateDemoLayerReview(layer: SubmissionLayer, update: Record<string, unknown>): SubmissionLayer {
  const store = readInspection();
  const review = {
    latest_review_status: String(update.workflow_status || "classification_approved"),
    latest_reviewer: String(update.reviewer || "demo_reviewer"),
    classification_status: "classification_approved",
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
  return { layerReviews: {}, duplicateGroups: {}, stagingPlan: {}, stagedOutputs: [] };
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
