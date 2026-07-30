import { demoAllRelationships, demoAssets, type AssetRelationship, type UtilityAsset } from "./utility-assets";

export type ConnectivityRule = {
  rule_code: string;
  name: string;
  category: string;
  severity: "info" | "warning" | "error" | "critical";
  blocking: boolean;
  scope: "asset" | "relationship";
  description: string;
  recommended_action: string;
  limitation: string;
  enabled: true;
  rule_version: string;
};

export type ConnectivityFinding = {
  qa_run_id: string;
  finding_id: string;
  finding_fingerprint: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  rule_code: string;
  rule_version: string;
  severity: ConnectivityRule["severity"];
  blocking: boolean;
  asset_id: string;
  related_asset_id: string;
  relationship_id: string;
  asset_class: string;
  asset_name: string;
  related_asset_name: string;
  short_title: string;
  explanation: string;
  recommended_action: string;
  evidence: Record<string, unknown>;
  review_status: string;
  review_comment: string;
  reviewed_by: string;
  reviewed_at: string;
  created_at: string;
  updated_at: string;
};

export type ConnectivityRun = {
  qa_run_id: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  profile_name: string;
  model_version: string;
  rule_version: string;
  run_fingerprint: string;
  status: string;
  force_recalculate: boolean;
  asset_count: number;
  relationship_count: number;
  rules_executed: number;
  rules_skipped: number;
  findings_count: number;
  blocking_findings_count: number;
  error_count: number;
  started_at: string;
  completed_at: string;
  created_by: string;
  summary: ConnectivitySummary;
  rule_runs: Array<{ rule_code: string; status: string; finding_count: number; error_message: string }>;
  reused?: boolean;
};

export type ConnectivitySummary = {
  qa_run_id: string;
  status: string;
  findings_count: number;
  blocking_findings_count: number;
  by_severity: Record<string, number>;
  by_rule: Record<string, number>;
  by_review_status: Record<string, number>;
  rules_executed: number;
  rules_skipped: number;
  error_count: number;
  message: string;
  limitations: string[];
};

export type ConnectivityGroupMember = {
  finding_id: string;
  finding_role: "primary" | "contributing" | "consequence" | "corroborating" | "informational" | "independent";
  relationship_to_primary: string;
  grouping_reason: string;
  confidence: string;
};

export type ConnectivityIssueGroup = {
  calibration_run_id: string;
  issue_group_id: string;
  qa_run_id: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  issue_family: string;
  root_cause_key: string;
  primary_finding_id: string;
  member_finding_ids: string[];
  affected_asset_ids: string[];
  affected_relationship_ids: string[];
  primary_rule_code: string;
  related_rule_codes: string[];
  group_title: string;
  group_summary: string;
  highest_severity: ConnectivityRule["severity"];
  effective_blocking: boolean;
  technical_finding_count: number;
  recommended_action: string;
  action_category: string;
  display_priority: "immediate" | "high" | "normal" | "low" | "informational";
  confidence: string;
  root_cause_confidence: string;
  trace_impact: "stops_trace" | "limits_trace" | "introduces_ambiguity" | "advisory" | "no_trace_effect" | "not_evaluated";
  trace_impact_reason: string;
  calibration_rule_version: string;
  canonical_rule_category: string;
  external_rule_mapping_status: string;
  vendor_equivalent_hints: string[];
  adapter_notes: string;
  review_status: string;
  review_comment: string;
  reviewed_by: string;
  reviewed_at: string;
  superseded: boolean;
  created_at: string;
  members: ConnectivityGroupMember[];
};

export type CalibratedSummary = {
  calibration_rule_version: string;
  technical_findings: number;
  actionable_issue_groups: number;
  primary_blockers: number;
  consequence_findings: number;
  independent_findings: number;
  informational_conditions: number;
  affected_assets: number;
  affected_relationships: number;
  unresolved_primary_groups: number;
  acknowledged_primary_groups: number;
  accepted_risk_groups: number;
  false_positive_groups: number;
  findings_hidden_by_display_filters: number;
  trace_stopping_groups: number;
  trace_limiting_groups: number;
  by_severity: Record<string, number>;
  by_issue_family: Record<string, number>;
  by_trace_impact: Record<string, number>;
  by_display_priority: Record<string, number>;
  by_review_status: Record<string, number>;
  limitations: string[];
};

export type ConnectivityCalibrationRun = {
  calibration_run_id: string;
  qa_run_id: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  calibration_rule_version: string;
  status: string;
  started_at: string;
  completed_at: string;
  technical_findings_read: number;
  issue_groups_created: number;
  primary_findings: number;
  consequence_findings: number;
  independent_findings: number;
  summary: CalibratedSummary;
  reused?: boolean;
  message?: string;
};

export type ConnectivityIssueGroupDetail = Omit<ConnectivityIssueGroup, "members"> & {
  members: Array<ConnectivityGroupMember & ConnectivityFinding>;
  graph_context: {
    assets: Array<Pick<UtilityAsset, "asset_id" | "canonical_name" | "asset_class" | "lifecycle_status" | "operational_status">>;
    relationships: AssetRelationship[];
    geometry: string;
    disclaimer: string;
  };
  history: Array<Record<string, unknown>>;
};

const shared = [
  ["SHARED-001", "Missing relationship endpoint", "error", true, "relationship"],
  ["SHARED-002", "Self-referential relationship", "error", true, "relationship"],
  ["SHARED-003", "Duplicate relationship", "warning", false, "relationship"],
  ["SHARED-004", "Provisional relationship", "warning", false, "relationship"],
  ["SHARED-005", "Retired asset linked to active asset", "error", true, "relationship"],
  ["SHARED-006", "Incompatible utility vertical relationship", "critical", true, "relationship"],
  ["SHARED-007", "Missing canonical identifier", "error", true, "asset"],
  ["SHARED-008", "Unknown lifecycle state", "warning", false, "asset"],
] as const;
const electric = [
  ["ELEC-001", "Disconnected conductor", "error", true, "asset"],
  ["ELEC-002", "Conductor endpoint missing", "error", true, "asset"],
  ["ELEC-003", "Transformer missing feeder ID", "error", true, "asset"],
  ["ELEC-004", "Transformer disconnected from primary", "error", true, "asset"],
  ["ELEC-005", "Invalid or incompatible phase", "error", true, "asset"],
  ["ELEC-006", "Voltage mismatch", "error", true, "asset"],
  ["ELEC-007", "Underground conductor missing conduit", "warning", false, "asset"],
  ["ELEC-008", "Equipment missing structure association", "warning", false, "asset"],
  ["ELEC-009", "Feeder inconsistency across relationship", "error", true, "relationship"],
  ["ELEC-010", "Circuit inconsistency across relationship", "warning", false, "relationship"],
  ["ELEC-011", "Invalid relationship direction", "warning", false, "relationship"],
  ["ELEC-012", "Normally open device", "info", false, "asset"],
  ["ELEC-013", "Protective device type missing", "warning", false, "asset"],
  ["ELEC-014", "Active-retired electric relationship", "error", true, "relationship"],
  ["ELEC-015", "Electric placement contradiction", "warning", false, "asset"],
] as const;
const telecom = [
  ["TEL-001", "Fiber cable endpoint missing", "error", true, "asset"],
  ["TEL-002", "Invalid fiber termination", "error", true, "relationship"],
  ["TEL-003", "Overlapping strand range", "error", true, "asset"],
  ["TEL-004", "Capacity exceeds total", "error", true, "asset"],
  ["TEL-005", "Available capacity mismatch", "warning", false, "asset"],
  ["TEL-006", "Fiber count and strand range mismatch", "error", true, "asset"],
  ["TEL-007", "Disconnected splice closure", "error", true, "asset"],
  ["TEL-008", "Disconnected terminal", "error", true, "asset"],
  ["TEL-009", "Cabinet missing route", "warning", false, "asset"],
  ["TEL-010", "Underground cable missing conduit", "warning", false, "asset"],
  ["TEL-011", "Aerial cable missing support", "warning", false, "asset"],
  ["TEL-012", "Proposed route gap", "warning", false, "asset"],
  ["TEL-013", "Retired cable linked to active terminal", "error", true, "relationship"],
  ["TEL-014", "Provisional splice relationship", "warning", false, "relationship"],
  ["TEL-015", "Splitter capacity inconsistency", "error", true, "asset"],
  ["TEL-016", "Telecom placement contradiction", "warning", false, "asset"],
] as const;
const water = [
  ["WATER-001", "Blank asset identifier", "error", true, "asset"],
  ["WATER-002", "Duplicate asset identifier", "error", true, "asset"],
  ["WATER-003", "Invalid or unsupported geometry", "error", true, "asset"],
  ["WATER-004", "Unknown spatial reference", "warning", true, "asset"],
  ["WATER-005", "Suspicious extent", "warning", false, "asset"],
  ["WATER-006", "Invalid diameter", "error", true, "asset"],
  ["WATER-007", "Invalid material", "warning", false, "asset"],
  ["WATER-008", "Invalid lifecycle status", "warning", false, "asset"],
  ["WATER-009", "Disconnected main endpoint", "error", true, "asset"],
  ["WATER-010", "Isolated service line", "error", true, "asset"],
  ["WATER-011", "Hydrant lacks plausible main relationship", "warning", false, "asset"],
  ["WATER-012", "Valve lacks main relationship", "warning", false, "asset"],
  ["WATER-013", "Invalid pressure-zone reference", "warning", false, "asset"],
  ["WATER-014", "Missing owner or jurisdiction", "warning", false, "asset"],
  ["WATER-015", "Invalid facility reference", "warning", false, "asset"],
  ["WATER-016", "Active asset connected only to retired assets", "error", true, "asset"],
  ["WATER-017", "Service line lacks endpoint", "warning", false, "asset"],
  ["WATER-018", "Conflicting water-system identity", "warning", false, "relationship"],
] as const;
const wastewater = [
  ["WW-001", "Blank asset identifier", "error", true, "asset"],
  ["WW-002", "Duplicate asset identifier", "error", true, "asset"],
  ["WW-003", "Invalid geometry", "error", true, "asset"],
  ["WW-004", "Unknown spatial reference", "warning", true, "asset"],
  ["WW-005", "Suspicious extent", "warning", false, "asset"],
  ["WW-006", "Gravity main lacks structures", "error", true, "asset"],
  ["WW-007", "Gravity segment has identical endpoints", "error", true, "asset"],
  ["WW-008", "Invalid or zero diameter", "error", true, "asset"],
  ["WW-009", "Invalid material", "warning", false, "asset"],
  ["WW-010", "Suspicious slope", "warning", false, "asset"],
  ["WW-011", "Missing expected invert elevation", "warning", false, "asset"],
  ["WW-012", "Upstream/downstream invert contradiction", "error", true, "asset"],
  ["WW-013", "Force main carries gravity-only attributes", "warning", false, "asset"],
  ["WW-014", "Gravity main attached to pressure equipment", "error", true, "relationship"],
  ["WW-015", "Lateral lacks receiving main", "error", true, "asset"],
  ["WW-016", "Disconnected manhole", "error", true, "asset"],
  ["WW-017", "Lift station lacks downstream force main", "error", true, "asset"],
  ["WW-018", "Active asset connected only to retired assets", "error", true, "asset"],
  ["WW-019", "Invalid basin or system reference", "warning", false, "asset"],
  ["WW-020", "Missing owner or jurisdiction", "warning", false, "asset"],
] as const;

export function connectivityRules(vertical: UtilityAsset["utility_vertical"]): ConnectivityRule[] {
  const profiles = { electric_distribution: electric, telecom_fiber: telecom, water, wastewater };
  return [...shared, ...profiles[vertical]].map(([rule_code, name, severity, blocking, scope]) => ({
    rule_code,
    name,
    category: rule_code.startsWith("SHARED") ? "shared" : vertical,
    severity,
    blocking,
    scope,
    description: `${name} is evaluated from safe canonical fields and explicit stored relationships.`,
    recommended_action: "Review the canonical evidence and record a human decision; do not repair source geometry automatically.",
    limitation: "V1 evaluates canonical registry evidence only and does not perform an authoritative network trace.",
    enabled: true,
    rule_version: "connectivity-qa-rules-v2",
  }));
}

type DemoStore = {
  runs: ConnectivityRun[];
  findings: ConnectivityFinding[];
  history: Array<Record<string, unknown>>;
  calibrationRuns: ConnectivityCalibrationRun[];
  issueGroups: ConnectivityIssueGroup[];
  calibrationHistory: Array<Record<string, unknown>>;
};
const storeKey = "utilities-platform-demo-connectivity-qa-v1";
const calibrationVersion = "connectivity-calibration-v1";
const severityRank: Record<string, number> = { info: 0, warning: 1, error: 2, critical: 3 };
const traceRank: Record<string, number> = { not_evaluated: 0, no_trace_effect: 1, advisory: 2, introduces_ambiguity: 3, limits_trace: 4, stops_trace: 5 };
const calibrationMeta: Record<string, { family: string; action: string; precedence: number; trace: ConnectivityIssueGroup["trace_impact"]; category: string; hint: string }> = {
  "SHARED-004": { family: "provisional_evidence", action: "confirm_relationship", precedence: 9, trace: "introduces_ambiguity", category: "evidence_quality", hint: "network connectivity validation" },
  "SHARED-005": { family: "lifecycle_conflict", action: "confirm_lifecycle", precedence: 5, trace: "stops_trace", category: "lifecycle_integrity", hint: "lifecycle conflict review" },
  "ELEC-001": { family: "conductor_connectivity", action: "repair_connectivity", precedence: 2, trace: "stops_trace", category: "electric_connectivity", hint: "network connectivity validation" },
  "ELEC-002": { family: "conductor_connectivity", action: "repair_connectivity", precedence: 2, trace: "stops_trace", category: "electric_connectivity", hint: "network connectivity validation" },
  "ELEC-003": { family: "feeder_assignment", action: "confirm_feeder", precedence: 6, trace: "limits_trace", category: "electric_membership", hint: "feeder membership validation" },
  "ELEC-005": { family: "phase_compatibility", action: "confirm_phase", precedence: 7, trace: "stops_trace", category: "electric_phase", hint: "phase consistency review" },
  "ELEC-007": { family: "containment_gap", action: "confirm_conduit", precedence: 4, trace: "limits_trace", category: "electric_containment", hint: "network connectivity validation" },
  "ELEC-012": { family: "operational_state", action: "retain_operational_context", precedence: 8, trace: "no_trace_effect", category: "electric_device_state", hint: "device-state-aware continuity" },
  "ELEC-014": { family: "lifecycle_conflict", action: "confirm_lifecycle", precedence: 5, trace: "stops_trace", category: "lifecycle_integrity", hint: "lifecycle conflict review" },
  "TEL-001": { family: "cable_endpoint", action: "repair_connectivity", precedence: 2, trace: "stops_trace", category: "telecom_connectivity", hint: "cable endpoint validation" },
  "TEL-002": { family: "cable_termination", action: "repair_connectivity", precedence: 3, trace: "stops_trace", category: "telecom_connectivity", hint: "cable endpoint validation" },
  "TEL-003": { family: "strand_allocation", action: "review_strand_allocation", precedence: 7, trace: "stops_trace", category: "fiber_allocation", hint: "fiber allocation validation" },
  "TEL-005": { family: "capacity_consistency", action: "reconcile_capacity", precedence: 7, trace: "introduces_ambiguity", category: "telecom_capacity", hint: "capacity consistency" },
  "TEL-012": { family: "proposed_construction", action: "complete_design", precedence: 2, trace: "limits_trace", category: "proposed_connectivity", hint: "cable endpoint validation" },
  "TEL-013": { family: "lifecycle_conflict", action: "confirm_lifecycle", precedence: 5, trace: "stops_trace", category: "lifecycle_integrity", hint: "lifecycle conflict review" },
  "TEL-014": { family: "provisional_evidence", action: "confirm_relationship", precedence: 9, trace: "introduces_ambiguity", category: "evidence_quality", hint: "network connectivity validation" },
  "WATER-002": { family: "asset_identity", action: "confirm_identifier", precedence: 6, trace: "advisory", category: "water_identity", hint: "asset identity validation" },
  "WATER-010": { family: "service_connectivity", action: "repair_connectivity", precedence: 2, trace: "stops_trace", category: "water_connectivity", hint: "water topology validation" },
  "WATER-017": { family: "service_endpoint", action: "confirm_endpoint", precedence: 4, trace: "limits_trace", category: "water_connectivity", hint: "water topology validation" },
  "WW-010": { family: "gravity_slope", action: "confirm_slope", precedence: 7, trace: "advisory", category: "wastewater_attributes", hint: "gravity-flow evidence review" },
  "WW-012": { family: "invert_direction", action: "confirm_inverts", precedence: 4, trace: "limits_trace", category: "wastewater_flow_evidence", hint: "gravity-flow evidence review" },
  "WW-016": { family: "structure_connectivity", action: "repair_connectivity", precedence: 2, trace: "stops_trace", category: "wastewater_connectivity", hint: "wastewater topology validation" },
};
const dependencyParents: Record<string, string[]> = {
  "ELEC-002": ["ELEC-001"],
  "ELEC-014": ["SHARED-005"],
  "TEL-002": ["TEL-001"],
  "TEL-013": ["SHARED-005"],
  "TEL-014": ["SHARED-004"],
};

export function runDemoConnectivityQa(vertical: UtilityAsset["utility_vertical"], force = false): ConnectivityRun {
  const store = readStore();
  const assets = demoAssets().filter((asset) => asset.utility_vertical === vertical);
  const relationships = demoAllRelationships().filter((item) => assets.some((asset) => asset.asset_id === item.from_asset_id || asset.asset_id === item.to_asset_id));
  const fingerprint = hash(JSON.stringify({
    vertical,
    assets: assets.map((asset) => [asset.asset_id, asset.lifecycle_status, asset.operational_status, asset.canonical_attributes_json]),
    relationships: relationships.map((item) => [item.relationship_id, item.from_asset_id, item.to_asset_id, item.relationship_type, item.provisional]),
    version: "connectivity-qa-rules-v2",
  }));
  const existing = store.runs.find((run) => run.utility_vertical === vertical && run.run_fingerprint === fingerprint);
  if (existing && !force) return { ...existing, reused: true };

  const qaRunId = `demo-qa-${vertical}-${force ? store.runs.filter((run) => run.utility_vertical === vertical).length + 1 : 1}`;
  const now = new Date().toISOString();
  const findings = deriveFindings(vertical, qaRunId, assets, relationships).map((finding) => {
    const prior = store.findings.find((item) => item.finding_fingerprint === finding.finding_fingerprint);
    return prior ? { ...finding, review_status: prior.review_status, review_comment: prior.review_comment, reviewed_by: prior.reviewed_by, reviewed_at: prior.reviewed_at } : finding;
  });
  const rules = connectivityRules(vertical);
  const summary = summarize(qaRunId, findings, rules.length);
  const run: ConnectivityRun = {
    qa_run_id: qaRunId,
    utility_vertical: vertical,
    profile_name: `${vertical}_v1`,
    model_version: "canonical-connectivity-graph-v1",
    rule_version: "connectivity-qa-rules-v2",
    run_fingerprint: fingerprint,
    status: "succeeded",
    force_recalculate: force,
    asset_count: assets.length,
    relationship_count: relationships.length,
    rules_executed: rules.length,
    rules_skipped: 0,
    findings_count: findings.length,
    blocking_findings_count: findings.filter((item) => item.blocking).length,
    error_count: 0,
    started_at: now,
    completed_at: now,
    created_by: "Demo Reviewer",
    summary,
    rule_runs: rules.map((rule) => {
      const count = findings.filter((item) => item.rule_code === rule.rule_code).length;
      return { rule_code: rule.rule_code, status: count ? rule.blocking ? "failed" : "warning" : "passed", finding_count: count, error_message: "" };
    }),
  };
  store.runs.unshift(run);
  store.findings = [...findings, ...store.findings.filter((item) => item.utility_vertical !== vertical)];
  store.history.push({ qa_run_id: qaRunId, action: "run_completed", created_at: now, actor: "demo" });
  writeStore(store);
  return run;
}

export function ensureDemoConnectivityRun(vertical: UtilityAsset["utility_vertical"]) {
  return readStore().runs.find((run) => run.utility_vertical === vertical) ?? runDemoConnectivityQa(vertical);
}

export function demoConnectivityRuns(vertical: UtilityAsset["utility_vertical"]) {
  ensureDemoConnectivityRun(vertical);
  return readStore().runs.filter((run) => run.utility_vertical === vertical);
}

export function demoConnectivityFindings(vertical: UtilityAsset["utility_vertical"], params = new URLSearchParams()) {
  const run = ensureDemoConnectivityRun(vertical);
  let items = readStore().findings.filter((item) => item.utility_vertical === vertical && item.qa_run_id === run.qa_run_id);
  for (const field of ["severity", "review_status", "rule_code", "asset_class", "asset_id"] as const) {
    const value = params.get(field);
    if (value) items = items.filter((item) => item[field] === value);
  }
  if (params.has("blocking")) items = items.filter((item) => item.blocking === (params.get("blocking") === "true"));
  const total = items.length;
  const limit = Number(params.get("limit") || 100);
  const offset = Number(params.get("offset") || 0);
  return { items: items.slice(offset, offset + limit), qa_run_id: run.qa_run_id, pagination: { total, limit, offset, has_more: offset + limit < total } };
}

export function demoConnectivityFinding(vertical: UtilityAsset["utility_vertical"], findingId: string) {
  const finding = readStore().findings.find((item) => item.utility_vertical === vertical && item.finding_id === findingId);
  if (!finding) throw new Error("Synthetic connectivity finding not found.");
  const rule = connectivityRules(vertical).find((item) => item.rule_code === finding.rule_code)!;
  const assets = demoAssets().filter((asset) => [finding.asset_id, finding.related_asset_id].includes(asset.asset_id)).map((asset) => ({
    asset_id: asset.asset_id,
    canonical_name: asset.canonical_name,
    asset_class: asset.asset_class,
    lifecycle_status: asset.lifecycle_status,
    operational_status: asset.operational_status,
  }));
  const relationship = demoAllRelationships().find((item) => item.relationship_id === finding.relationship_id) ?? null;
  const history = readStore().history.filter((item) => item.finding_id === findingId);
  return { ...finding, rule, graph_context: { assets, relationship, geometry: "logical_graph_only" }, history };
}

export function reviewDemoConnectivityFinding(
  vertical: UtilityAsset["utility_vertical"],
  findingId: string,
  action: string,
  body: Record<string, unknown>,
) {
  const status: Record<string, string> = { acknowledge: "acknowledged", defer: "deferred", "accept-risk": "accepted_risk", "mark-false-positive": "false_positive", reopen: "open" };
  const reviewer = String(body.reviewer || "").trim();
  const comment = String(body.comment || body.rationale || "").trim();
  if (!reviewer) throw new Error("Reviewer is required.");
  if (["defer", "accept-risk", "mark-false-positive"].includes(action) && !comment) throw new Error("A review rationale is required for this action.");
  const store = readStore();
  const index = store.findings.findIndex((item) => item.utility_vertical === vertical && item.finding_id === findingId);
  if (index < 0 || !status[action]) throw new Error("Synthetic review action is unavailable.");
  const prior = store.findings[index];
  const now = new Date().toISOString();
  store.findings[index] = { ...prior, review_status: status[action], review_comment: comment, reviewed_by: reviewer, reviewed_at: now, updated_at: now };
  store.history.push({ qa_run_id: prior.qa_run_id, finding_id: findingId, action, prior_value: prior.review_status, new_value: status[action], actor: reviewer, comment, created_at: now });
  const run = store.runs.find((item) => item.qa_run_id === prior.qa_run_id);
  if (run) run.summary = summarize(run.qa_run_id, store.findings.filter((item) => item.qa_run_id === run.qa_run_id), run.rules_executed);
  writeStore(store);
  return demoConnectivityFinding(vertical, findingId);
}

export function runDemoConnectivityCalibration(
  vertical: UtilityAsset["utility_vertical"],
  qaRunId = "",
  force = false,
  preserveReviewDecisions = true,
): ConnectivityCalibrationRun {
  const store = readStore();
  const qaRun = qaRunId
    ? store.runs.find((item) => item.qa_run_id === qaRunId)
    : store.runs.find((item) => item.utility_vertical === vertical) ?? runDemoConnectivityQa(vertical);
  if (!qaRun || qaRun.utility_vertical !== vertical) throw new Error("Synthetic Connectivity QA run not found.");
  const findings = store.findings.filter((item) => item.qa_run_id === qaRun.qa_run_id);
  const fingerprint = hash([
    qaRun.qa_run_id,
    ...findings.map((item) => item.finding_fingerprint).sort(),
    "connectivity-dependencies-v1",
    "connectivity-priority-v1",
    "connectivity-grouping-v1",
    "connectivity-trace-impact-v1",
  ].join("|"));
  const existing = store.calibrationRuns.find((item) => item.utility_vertical === vertical && (item as ConnectivityCalibrationRun & { input_fingerprint?: string }).input_fingerprint === fingerprint);
  if (existing && !force) return { ...existing, reused: true, message: "No QA findings or calibration rules changed" };

  const now = new Date().toISOString();
  const calibrationRunId = `demo-calibration-${vertical}-${store.calibrationRuns.filter((item) => item.utility_vertical === vertical).length + 1}`;
  const groups = buildDemoIssueGroups(vertical, qaRun.qa_run_id, findings, calibrationRunId, now);
  if (preserveReviewDecisions) {
    groups.forEach((group) => {
      const prior = store.issueGroups.find((item) => item.issue_group_id === group.issue_group_id);
      if (prior) {
        group.review_status = prior.review_status;
        group.review_comment = prior.review_comment;
        group.reviewed_by = prior.reviewed_by;
        group.reviewed_at = prior.reviewed_at;
      }
    });
  }
  const summary = summarizeCalibration(findings, groups);
  const roles = groups.flatMap((group) => group.members.map((member) => member.finding_role));
  const run = {
    calibration_run_id: calibrationRunId,
    qa_run_id: qaRun.qa_run_id,
    utility_vertical: vertical,
    calibration_rule_version: calibrationVersion,
    input_fingerprint: fingerprint,
    status: "succeeded",
    started_at: now,
    completed_at: now,
    technical_findings_read: findings.length,
    issue_groups_created: groups.length,
    primary_findings: roles.filter((role) => role === "primary").length,
    consequence_findings: roles.filter((role) => role === "consequence").length,
    independent_findings: roles.filter((role) => role === "independent").length,
    summary,
  };
  store.calibrationRuns.unshift(run);
  store.issueGroups.unshift(...groups);
  store.calibrationHistory.push({ calibration_run_id: calibrationRunId, action: "calibration_completed", created_at: now });
  writeStore(store);
  return run;
}

export function ensureDemoConnectivityCalibration(vertical: UtilityAsset["utility_vertical"]): ConnectivityCalibrationRun {
  const qaRun = ensureDemoConnectivityRun(vertical);
  return readStore().calibrationRuns.find((item) => item.utility_vertical === vertical && item.qa_run_id === qaRun.qa_run_id)
    ?? runDemoConnectivityCalibration(vertical, qaRun.qa_run_id);
}

export function demoConnectivityCalibrationRuns(vertical: UtilityAsset["utility_vertical"]) {
  ensureDemoConnectivityCalibration(vertical);
  return readStore().calibrationRuns.filter((item) => item.utility_vertical === vertical);
}

export function demoConnectivityIssueGroups(vertical: UtilityAsset["utility_vertical"], params = new URLSearchParams()) {
  const run = ensureDemoConnectivityCalibration(vertical);
  let items = readStore().issueGroups.filter((item) => item.calibration_run_id === run.calibration_run_id && !item.superseded);
  const fieldMap: Record<string, keyof ConnectivityIssueGroup> = {
    issue_family: "issue_family",
    severity: "highest_severity",
    display_priority: "display_priority",
    trace_impact: "trace_impact",
    review_status: "review_status",
    primary_rule_code: "primary_rule_code",
  };
  Object.entries(fieldMap).forEach(([parameter, field]) => {
    const value = params.get(parameter);
    if (value) items = items.filter((item) => item[field] === value);
  });
  if (params.has("effective_blocking")) items = items.filter((item) => item.effective_blocking === (params.get("effective_blocking") === "true"));
  if (params.get("asset_id")) items = items.filter((item) => item.affected_asset_ids.includes(params.get("asset_id")!));
  if (params.get("relationship_id")) items = items.filter((item) => item.affected_relationship_ids.includes(params.get("relationship_id")!));
  const total = items.length;
  const limit = Number(params.get("limit") || 100);
  const offset = Number(params.get("offset") || 0);
  return { items: items.slice(offset, offset + limit), calibration_run_id: run.calibration_run_id, pagination: { total, limit, offset, has_more: offset + limit < total } };
}

export function demoConnectivityIssueGroup(vertical: UtilityAsset["utility_vertical"], issueGroupId: string): ConnectivityIssueGroupDetail {
  const store = readStore();
  const group = store.issueGroups.find((item) => item.utility_vertical === vertical && item.issue_group_id === issueGroupId);
  if (!group) throw new Error("Synthetic connectivity issue group not found.");
  const members = group.members.map((member) => ({
    ...store.findings.find((item) => item.qa_run_id === group.qa_run_id && item.finding_id === member.finding_id)!,
    ...member,
  }));
  const assets = demoAssets().filter((asset) => group.affected_asset_ids.includes(asset.asset_id)).map((asset) => ({
    asset_id: asset.asset_id,
    canonical_name: asset.canonical_name,
    asset_class: asset.asset_class,
    lifecycle_status: asset.lifecycle_status,
    operational_status: asset.operational_status,
  }));
  const relationships = demoAllRelationships().filter((item) => group.affected_relationship_ids.includes(item.relationship_id));
  return {
    ...group,
    members,
    graph_context: {
      assets,
      relationships,
      geometry: "logical_relationship_view_only",
      disclaimer: "Logical relationship view - not an engineering diagram.",
    },
    history: store.calibrationHistory.filter((item) => item.issue_group_id === issueGroupId),
  };
}

export function reviewDemoConnectivityIssueGroup(
  vertical: UtilityAsset["utility_vertical"],
  issueGroupId: string,
  action: string,
  body: Record<string, unknown>,
) {
  const statuses: Record<string, string> = { acknowledge: "acknowledged", defer: "deferred", "accept-risk": "accepted_risk", "mark-false-positive": "false_positive", reopen: "open" };
  const reviewer = String(body.reviewer || "").trim();
  const comment = String(body.comment || body.rationale || "").trim();
  if (!reviewer) throw new Error("Reviewer is required.");
  if (["defer", "accept-risk", "mark-false-positive"].includes(action) && !comment) throw new Error("A review rationale is required for this action.");
  if (!statuses[action]) throw new Error("Synthetic issue-group review action is unavailable.");
  const store = readStore();
  const group = store.issueGroups.find((item) => item.utility_vertical === vertical && item.issue_group_id === issueGroupId);
  if (!group) throw new Error("Synthetic connectivity issue group not found.");
  const now = new Date().toISOString();
  group.review_status = statuses[action];
  group.review_comment = comment;
  group.reviewed_by = reviewer;
  group.reviewed_at = now;
  group.member_finding_ids.forEach((findingId) => {
    const finding = store.findings.find((item) => item.qa_run_id === group.qa_run_id && item.finding_id === findingId);
    if (finding) {
      finding.review_status = statuses[action];
      finding.review_comment = comment;
      finding.reviewed_by = reviewer;
      finding.reviewed_at = now;
      finding.updated_at = now;
    }
    store.calibrationHistory.push({ calibration_run_id: group.calibration_run_id, issue_group_id: issueGroupId, finding_id: findingId, action, actor: reviewer, reason: comment, created_at: now });
  });
  const run = store.calibrationRuns.find((item) => item.calibration_run_id === group.calibration_run_id);
  if (run) {
    run.summary = summarizeCalibration(
      store.findings.filter((item) => item.qa_run_id === group.qa_run_id),
      store.issueGroups.filter((item) => item.calibration_run_id === group.calibration_run_id),
    );
  }
  writeStore(store);
  return demoConnectivityIssueGroup(vertical, issueGroupId);
}

function buildDemoIssueGroups(
  vertical: UtilityAsset["utility_vertical"],
  qaRunId: string,
  findings: ConnectivityFinding[],
  calibrationRunId: string,
  createdAt: string,
): ConnectivityIssueGroup[] {
  const assets = new Map(demoAssets().map((asset) => [asset.asset_id, asset]));
  const grouped = new Map<string, ConnectivityFinding[]>();
  findings.forEach((finding) => {
    const key = demoRootKey(finding, assets);
    grouped.set(key, [...(grouped.get(key) ?? []), finding]);
  });
  return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([rootKey, rawMembers]) => {
    const members = [...rawMembers].sort((left, right) => {
      const leftMeta = calibrationMeta[left.rule_code] ?? { precedence: 10 };
      const rightMeta = calibrationMeta[right.rule_code] ?? { precedence: 10 };
      return leftMeta.precedence - rightMeta.precedence
        || Number(Boolean(dependencyParents[left.rule_code])) - Number(Boolean(dependencyParents[right.rule_code]))
        || severityRank[right.severity] - severityRank[left.severity]
        || left.rule_code.localeCompare(right.rule_code);
    });
    const primary = members[0];
    const meta = calibrationMeta[primary.rule_code] ?? { family: "unsupported_condition", action: "manual_review", precedence: 10, trace: "not_evaluated" as const, category: "unsupported", hint: "network connectivity validation" };
    const memberships: ConnectivityGroupMember[] = members.map((finding) => {
      if (members.length === 1) return { finding_id: finding.finding_id, finding_role: finding.severity === "info" ? "informational" : "independent", relationship_to_primary: "independent", grouping_reason: "Separate corrective action or evidence scope.", confidence: "high" };
      if (finding.finding_id === primary.finding_id) return { finding_id: finding.finding_id, finding_role: "primary", relationship_to_primary: "root_cause_candidate", grouping_reason: "Highest deterministic root-cause precedence in this evidence group.", confidence: "high" };
      if ((dependencyParents[finding.rule_code] ?? []).includes(primary.rule_code)) return { finding_id: finding.finding_id, finding_role: "consequence", relationship_to_primary: "confirmed_deterministic_dependency", grouping_reason: `${finding.rule_code} is an allowlisted consequence of ${primary.rule_code} on the same canonical evidence.`, confidence: "high" };
      return { finding_id: finding.finding_id, finding_role: "contributing", relationship_to_primary: "possible_dependency", grouping_reason: "The finding shares explicit canonical evidence and a corrective-action family.", confidence: "medium" };
    });
    const traces = members.map((finding) => calibrationMeta[finding.rule_code]?.trace ?? "not_evaluated");
    const traceImpact = traces.sort((left, right) => traceRank[right] - traceRank[left])[0];
    const highestSeverity = members.map((finding) => finding.severity).sort((left, right) => severityRank[right] - severityRank[left])[0];
    const effectiveBlocking = members.some((finding) => finding.blocking);
    const displayPriority: ConnectivityIssueGroup["display_priority"] = traceImpact === "stops_trace" && effectiveBlocking ? "high"
      : effectiveBlocking || traceImpact === "limits_trace" ? "high"
        : memberships.every((member) => member.finding_role === "informational") ? "informational"
          : ["advisory", "no_trace_effect"].includes(traceImpact) ? "low" : "normal";
    const affectedAssetIds = [...new Set(members.flatMap((finding) => [finding.asset_id, finding.related_asset_id]).filter(Boolean))].sort();
    const affectedRelationshipIds = [...new Set(members.map((finding) => finding.relationship_id).filter(Boolean))].sort();
    const reviewStatuses = [...new Set(members.map((finding) => finding.review_status))];
    return {
      calibration_run_id: calibrationRunId,
      issue_group_id: `demo-group-${hash([vertical, rootKey, ...members.map((finding) => finding.finding_fingerprint).sort(), calibrationVersion].join("|"))}`,
      qa_run_id: qaRunId,
      utility_vertical: vertical,
      issue_family: meta.family,
      root_cause_key: rootKey,
      primary_finding_id: primary.finding_id,
      member_finding_ids: members.map((finding) => finding.finding_id),
      affected_asset_ids: affectedAssetIds,
      affected_relationship_ids: affectedRelationshipIds,
      primary_rule_code: primary.rule_code,
      related_rule_codes: [...new Set(members.slice(1).map((finding) => finding.rule_code))].sort(),
      group_title: groupTitle(meta.family, primary.short_title),
      group_summary: members.length > 1 ? `${primary.explanation} ${members.length - 1} related technical finding(s) remain available as evidence.` : primary.explanation,
      highest_severity: highestSeverity,
      effective_blocking: effectiveBlocking,
      technical_finding_count: members.length,
      recommended_action: primary.recommended_action,
      action_category: meta.action,
      display_priority: displayPriority,
      confidence: memberships.some((member) => member.finding_role === "consequence") ? "high" : "medium",
      root_cause_confidence: memberships.some((member) => member.finding_role === "consequence") ? "high" : members.length === 1 ? "high" : "medium",
      trace_impact: traceImpact,
      trace_impact_reason: demoTraceReason(traceImpact),
      calibration_rule_version: calibrationVersion,
      canonical_rule_category: meta.category,
      external_rule_mapping_status: "conceptually_mappable",
      vendor_equivalent_hints: [...new Set(members.map((finding) => calibrationMeta[finding.rule_code]?.hint ?? "network connectivity validation"))].sort(),
      adapter_notes: "Conceptual vendor-neutral mapping only; an organization-specific adapter is required.",
      review_status: reviewStatuses.length === 1 ? reviewStatuses[0] : "mixed",
      review_comment: "",
      reviewed_by: "",
      reviewed_at: "",
      superseded: false,
      created_at: createdAt,
      members: memberships,
    };
  });
}

function demoRootKey(finding: ConnectivityFinding, assets: Map<string, UtilityAsset>) {
  if (["ELEC-001", "ELEC-002"].includes(finding.rule_code)) return `conductor_connectivity:${finding.asset_id}`;
  if (["SHARED-005", "ELEC-014", "TEL-013"].includes(finding.rule_code)) return `lifecycle_conflict:${finding.relationship_id || finding.asset_id}`;
  if (["SHARED-004", "TEL-014"].includes(finding.rule_code)) return `provisional_evidence:${finding.relationship_id || finding.asset_id}`;
  if (["TEL-001", "TEL-002"].includes(finding.rule_code)) {
    const cable = [finding.asset_id, finding.related_asset_id].find((id) => assets.get(id)?.asset_class === "fiber_cable");
    return `cable_endpoint:${cable || finding.asset_id || finding.relationship_id}`;
  }
  const meta = calibrationMeta[finding.rule_code] ?? { family: "unsupported_condition" };
  return `${meta.family}:${finding.rule_code}:${finding.asset_id || finding.relationship_id || finding.finding_id}`;
}

function groupTitle(family: string, fallback: string) {
  const titles: Record<string, string> = {
    conductor_connectivity: "Conductor connectivity and endpoints",
    lifecycle_conflict: "Active and retired network conflict",
    provisional_evidence: "Provisional relationship evidence",
    cable_endpoint: "Cable endpoint and termination",
    capacity_consistency: "Capacity values do not reconcile",
    strand_allocation: "Fiber strand allocation conflict",
  };
  return titles[family] ?? fallback;
}

function demoTraceReason(trace: ConnectivityIssueGroup["trace_impact"]) {
  return {
    stops_trace: "The condition prevents a defensible future path through the affected evidence.",
    limits_trace: "A future trace can only proceed to the confirmed evidence boundary.",
    introduces_ambiguity: "A future trace may continue provisionally but must report the ambiguity.",
    advisory: "The condition remains visible but does not independently block continuity.",
    no_trace_effect: "The condition is operational context that a future trace should honor.",
    not_evaluated: "Trace impact has not been evaluated.",
  }[trace];
}

function summarizeCalibration(findings: ConnectivityFinding[], groups: ConnectivityIssueGroup[]): CalibratedSummary {
  const roles = groups.flatMap((group) => group.members.map((member) => member.finding_role));
  const count = (values: string[]) => values.reduce<Record<string, number>>((result, value) => ({ ...result, [value]: (result[value] || 0) + 1 }), {});
  return {
    calibration_rule_version: calibrationVersion,
    technical_findings: findings.length,
    actionable_issue_groups: groups.length,
    primary_blockers: groups.filter((group) => group.effective_blocking).length,
    consequence_findings: roles.filter((role) => role === "consequence").length,
    independent_findings: roles.filter((role) => role === "independent").length,
    informational_conditions: roles.filter((role) => role === "informational").length,
    affected_assets: new Set(groups.flatMap((group) => group.affected_asset_ids)).size,
    affected_relationships: new Set(groups.flatMap((group) => group.affected_relationship_ids)).size,
    unresolved_primary_groups: groups.filter((group) => ["open", "mixed"].includes(group.review_status)).length,
    acknowledged_primary_groups: groups.filter((group) => group.review_status === "acknowledged").length,
    accepted_risk_groups: groups.filter((group) => group.review_status === "accepted_risk").length,
    false_positive_groups: groups.filter((group) => group.review_status === "false_positive").length,
    findings_hidden_by_display_filters: 0,
    trace_stopping_groups: groups.filter((group) => group.trace_impact === "stops_trace").length,
    trace_limiting_groups: groups.filter((group) => group.trace_impact === "limits_trace").length,
    by_severity: count(findings.map((finding) => finding.severity)),
    by_issue_family: count(groups.map((group) => group.issue_family)),
    by_trace_impact: count(groups.map((group) => group.trace_impact)),
    by_display_priority: count(groups.map((group) => group.display_priority)),
    by_review_status: count(groups.map((group) => group.review_status)),
    limitations: [
      "Calibration groups immutable technical findings; it does not suppress, repair, or trace the network.",
      "All demo evidence is synthetic and session-scoped.",
      "Vendor-equivalent hints are conceptual and require organization-specific adapters.",
    ],
  };
}

function deriveFindings(
  vertical: UtilityAsset["utility_vertical"],
  qaRunId: string,
  assets: UtilityAsset[],
  relationships: AssetRelationship[],
): ConnectivityFinding[] {
  const rules = new Map(connectivityRules(vertical).map((rule) => [rule.rule_code, rule]));
  const byId = new Map(assets.map((asset) => [asset.asset_id, asset]));
  const degree = new Map(assets.map((asset) => [asset.asset_id, relationships.filter((item) => item.from_asset_id === asset.asset_id || item.to_asset_id === asset.asset_id).length]));
  const candidates: Array<{ code: string; asset: UtilityAsset; related?: UtilityAsset; relationship?: AssetRelationship; explanation: string; evidence?: Record<string, unknown> }> = [];
  const add = (code: string, asset: UtilityAsset, explanation: string, related?: UtilityAsset, relationship?: AssetRelationship, evidence?: Record<string, unknown>) => candidates.push({ code, asset, related, relationship, explanation, evidence });

  relationships.filter((item) => item.provisional).forEach((relationship) => {
    const asset = byId.get(relationship.from_asset_id)!;
    add("SHARED-004", asset, "This explicit synthetic relationship remains provisional.", byId.get(relationship.to_asset_id), relationship);
    if (vertical === "telecom_fiber" && [asset, byId.get(relationship.to_asset_id)].some((item) => item?.asset_class === "splice_closure")) {
      add("TEL-014", asset, "A splice closure relationship remains provisional.", byId.get(relationship.to_asset_id), relationship);
    }
  });
  relationships.forEach((relationship) => {
    const left = byId.get(relationship.from_asset_id);
    const right = byId.get(relationship.to_asset_id);
    if (!left || !right) return;
    if ([left.lifecycle_status, right.lifecycle_status].includes("retired") && [left.lifecycle_status, right.lifecycle_status].includes("active")) {
      add("SHARED-005", left, "The relationship joins active and retired lifecycle contexts.", right, relationship);
      if (vertical === "electric_distribution") add("ELEC-014", left, "An active electric asset remains related to a retired asset.", right, relationship);
    }
    if (vertical === "telecom_fiber" && new Set([left.asset_class, right.asset_class]).has("fiber_cable") && new Set([left.asset_class, right.asset_class]).has("terminal")) {
      const cable = left.asset_class === "fiber_cable" ? left : right;
      if (cable.lifecycle_status === "retired") add("TEL-013", cable, "A retired cable remains related to an active terminal.", cable === left ? right : left, relationship);
    }
  });
  if (vertical === "electric_distribution") {
    assets.filter((asset) => ["overhead_conductor", "underground_conductor", "secondary_conductor"].includes(asset.asset_class) && degree.get(asset.asset_id) === 0).forEach((asset) => add("ELEC-001", asset, "The conductor has no explicit canonical relationship."));
    assets.filter((asset) => ["overhead_conductor", "underground_conductor", "secondary_conductor"].includes(asset.asset_class) && Number(degree.get(asset.asset_id) || 0) < 2).forEach((asset) => add("ELEC-002", asset, `The conductor has ${degree.get(asset.asset_id) || 0} explicit connected asset(s); two endpoints are expected.`));
    assets.filter((asset) => asset.asset_class === "transformer" && !asset.canonical_attributes_json?.feeder_id).forEach((asset) => add("ELEC-003", asset, "The transformer feeder identifier is missing."));
    assets.filter((asset) => !["", "A", "B", "C", "AB", "AC", "BC", "ABC", "N"].includes(String(asset.canonical_attributes_json?.phase || "").toUpperCase())).forEach((asset) => add("ELEC-005", asset, "The phase code is outside the V1 allowlist.", undefined, undefined, { phase: asset.canonical_attributes_json?.phase }));
    assets.filter((asset) => asset.asset_class === "underground_conductor" && !asset.canonical_attributes_json?.conduit_id).forEach((asset) => add("ELEC-007", asset, "The underground conductor has no conduit evidence."));
    assets.filter((asset) => asset.operational_status === "normally_open" || asset.canonical_attributes_json?.normally_open === true).forEach((asset) => add("ELEC-012", asset, "The switch is normally open and future traces must honor that state."));
  } else if (vertical === "telecom_fiber") {
    assets.filter((asset) => asset.asset_class === "fiber_cable" && (!asset.canonical_attributes_json?.from_structure_id || !asset.canonical_attributes_json?.to_structure_id)).forEach((asset) => add("TEL-001", asset, "The fiber cable is missing endpoint structure evidence."));
    const cables = assets.filter((asset) => asset.asset_class === "fiber_cable");
    cables.forEach((left, index) => cables.slice(index + 1).forEach((right) => {
      const la = left.canonical_attributes_json ?? {};
      const ra = right.canonical_attributes_json ?? {};
      if (la.route_id === ra.route_id && Number(la.strand_start) <= Number(ra.strand_end) && Number(ra.strand_start) <= Number(la.strand_end)) add("TEL-003", left, "Assigned strand ranges overlap on the same route.", right, undefined, { route_id: la.route_id });
    }));
    assets.filter((asset) => {
      const value = asset.canonical_attributes_json ?? {};
      return [value.total_capacity, value.used_capacity, value.reserved_capacity, value.available_capacity].every((item) => typeof item === "number")
        && Number(value.available_capacity) !== Number(value.total_capacity) - Number(value.used_capacity) - Number(value.reserved_capacity);
    }).forEach((asset) => add("TEL-005", asset, "Available capacity does not reconcile with total, used, and reserved capacity."));
    assets.filter((asset) => asset.asset_class === "proposed_construction_segment" && !asset.canonical_attributes_json?.to_structure_id).forEach((asset) => add("TEL-012", asset, "The proposed segment lacks complete endpoint evidence."));
  } else if (vertical === "water") {
    const identifiers = new Map<string, UtilityAsset>();
    assets.forEach((asset) => {
      const identifier = asset.source_asset_identifier.trim().toLowerCase();
      const previous = identifiers.get(identifier);
      if (identifier && previous) add("WATER-002", asset, "The normalized source identifier is shared by another synthetic asset.", previous);
      else if (identifier) identifiers.set(identifier, asset);
    });
    assets.filter((asset) => asset.asset_class === "service_line" && degree.get(asset.asset_id) === 0)
      .forEach((asset) => add("WATER-010", asset, "The service line has no explicit canonical relationship."));
    assets.filter((asset) => asset.asset_class === "service_line" && !relationships.some((item) => {
      const otherId = item.from_asset_id === asset.asset_id ? item.to_asset_id : item.to_asset_id === asset.asset_id ? item.from_asset_id : "";
      return otherId && ["meter", "service_point"].includes(byId.get(otherId)?.asset_class ?? "");
    })).forEach((asset) => add("WATER-017", asset, "The service line has no represented meter or safe service endpoint."));
  } else {
    assets.filter((asset) => asset.asset_class === "gravity_main" && Number(asset.canonical_attributes_json?.slope) <= 0)
      .forEach((asset) => add("WW-010", asset, "The mapped slope is zero or negative; source convention requires review.", undefined, undefined, { slope: asset.canonical_attributes_json?.slope }));
    assets.filter((asset) => asset.asset_class === "gravity_main"
      && Number(asset.canonical_attributes_json?.upstream_invert) <= Number(asset.canonical_attributes_json?.downstream_invert))
      .forEach((asset) => add("WW-012", asset, "Mapped upstream and downstream invert values conflict with the represented direction.", undefined, undefined, {
        upstream_invert: asset.canonical_attributes_json?.upstream_invert,
        downstream_invert: asset.canonical_attributes_json?.downstream_invert,
      }));
    assets.filter((asset) => asset.asset_class === "manhole" && degree.get(asset.asset_id) === 0)
      .forEach((asset) => add("WW-016", asset, "The manhole has no explicit relationship to a wastewater main."));
  }

  const now = new Date().toISOString();
  return [...new Map(candidates.map((candidate) => {
    const rule = rules.get(candidate.code)!;
    const fingerprint = hash([vertical, candidate.code, candidate.asset.asset_id, candidate.related?.asset_id || "", candidate.relationship?.relationship_id || "", JSON.stringify(candidate.evidence || {})].join("|"));
    const finding: ConnectivityFinding = {
      qa_run_id: qaRunId,
      finding_id: `demo-finding-${fingerprint}`,
      finding_fingerprint: fingerprint,
      utility_vertical: vertical,
      rule_code: rule.rule_code,
      rule_version: rule.rule_version,
      severity: rule.severity,
      blocking: rule.blocking,
      asset_id: candidate.asset.asset_id,
      related_asset_id: candidate.related?.asset_id || "",
      relationship_id: candidate.relationship?.relationship_id || "",
      asset_class: candidate.asset.asset_class,
      asset_name: candidate.asset.canonical_name,
      related_asset_name: candidate.related?.canonical_name || "",
      short_title: rule.name,
      explanation: candidate.explanation,
      recommended_action: rule.recommended_action,
      evidence: candidate.evidence || {},
      review_status: "open",
      review_comment: "",
      reviewed_by: "",
      reviewed_at: "",
      created_at: now,
      updated_at: now,
    };
    return [finding.finding_fingerprint, finding];
  })).values()];
}

function summarize(qaRunId: string, findings: ConnectivityFinding[], rulesExecuted: number): ConnectivitySummary {
  const count = (field: keyof ConnectivityFinding) => findings.reduce<Record<string, number>>((result, item) => {
    const key = String(item[field]);
    result[key] = (result[key] || 0) + 1;
    return result;
  }, {});
  return {
    qa_run_id: qaRunId,
    status: "succeeded",
    findings_count: findings.length,
    blocking_findings_count: findings.filter((item) => item.blocking).length,
    by_severity: count("severity"),
    by_rule: count("rule_code"),
    by_review_status: count("review_status"),
    rules_executed: rulesExecuted,
    rules_skipped: 0,
    error_count: 0,
    message: "Synthetic connectivity QA completed from explicit canonical relationships only.",
    limitations: [
      "This is not an ArcFM, GE Smallworld, or telecom network-inventory trace.",
      "Water and wastewater findings use represented topology only; they are not hydraulic-model results.",
      "No topology repair, snapping, service publishing, or source editing occurs.",
      "All demo evidence is synthetic and session-scoped.",
    ],
  };
}

function hash(value: string) {
  let result = 2166136261;
  for (let index = 0; index < value.length; index += 1) result = Math.imul(result ^ value.charCodeAt(index), 16777619);
  return (result >>> 0).toString(16).padStart(8, "0");
}

function readStore(): DemoStore {
  const empty = (): DemoStore => ({ runs: [], findings: [], history: [], calibrationRuns: [], issueGroups: [], calibrationHistory: [] });
  if (typeof sessionStorage === "undefined") return empty();
  try {
    const stored = JSON.parse(sessionStorage.getItem(storeKey) || "") as Partial<DemoStore>;
    return {
      runs: stored.runs ?? [],
      findings: stored.findings ?? [],
      history: stored.history ?? [],
      calibrationRuns: stored.calibrationRuns ?? [],
      issueGroups: stored.issueGroups ?? [],
      calibrationHistory: stored.calibrationHistory ?? [],
    };
  } catch {
    return empty();
  }
}

function writeStore(store: DemoStore) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(storeKey, JSON.stringify(store));
}
