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

export function connectivityRules(vertical: UtilityAsset["utility_vertical"]): ConnectivityRule[] {
  return [...shared, ...(vertical === "electric_distribution" ? electric : telecom)].map(([rule_code, name, severity, blocking, scope]) => ({
    rule_code,
    name,
    category: rule_code.startsWith("SHARED") ? "shared" : vertical === "electric_distribution" ? "electric" : "telecom",
    severity,
    blocking,
    scope,
    description: `${name} is evaluated from safe canonical fields and explicit stored relationships.`,
    recommended_action: "Review the canonical evidence and record a human decision; do not repair source geometry automatically.",
    limitation: "V1 evaluates canonical registry evidence only and does not perform an authoritative network trace.",
    enabled: true,
    rule_version: "connectivity-qa-rules-v1",
  }));
}

type DemoStore = {
  runs: ConnectivityRun[];
  findings: ConnectivityFinding[];
  history: Array<Record<string, unknown>>;
};
const storeKey = "utilities-platform-demo-connectivity-qa-v1";

export function runDemoConnectivityQa(vertical: UtilityAsset["utility_vertical"], force = false): ConnectivityRun {
  const store = readStore();
  const assets = demoAssets().filter((asset) => asset.utility_vertical === vertical);
  const relationships = demoAllRelationships().filter((item) => assets.some((asset) => asset.asset_id === item.from_asset_id || asset.asset_id === item.to_asset_id));
  const fingerprint = hash(JSON.stringify({
    vertical,
    assets: assets.map((asset) => [asset.asset_id, asset.lifecycle_status, asset.operational_status, asset.canonical_attributes_json]),
    relationships: relationships.map((item) => [item.relationship_id, item.from_asset_id, item.to_asset_id, item.relationship_type, item.provisional]),
    version: "connectivity-qa-rules-v1",
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
    profile_name: vertical === "electric_distribution" ? "electric_distribution_v1" : "telecom_fiber_v1",
    model_version: "canonical-connectivity-graph-v1",
    rule_version: "connectivity-qa-rules-v1",
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
    assets.filter((asset) => asset.asset_class === "transformer" && !asset.canonical_attributes_json?.feeder_id).forEach((asset) => add("ELEC-003", asset, "The transformer feeder identifier is missing."));
    assets.filter((asset) => !["", "A", "B", "C", "AB", "AC", "BC", "ABC", "N"].includes(String(asset.canonical_attributes_json?.phase || "").toUpperCase())).forEach((asset) => add("ELEC-005", asset, "The phase code is outside the V1 allowlist.", undefined, undefined, { phase: asset.canonical_attributes_json?.phase }));
    assets.filter((asset) => asset.asset_class === "underground_conductor" && !asset.canonical_attributes_json?.conduit_id).forEach((asset) => add("ELEC-007", asset, "The underground conductor has no conduit evidence."));
    assets.filter((asset) => asset.operational_status === "normally_open" || asset.canonical_attributes_json?.normally_open === true).forEach((asset) => add("ELEC-012", asset, "The switch is normally open and future traces must honor that state."));
  } else {
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
  if (typeof sessionStorage === "undefined") return { runs: [], findings: [], history: [] };
  try {
    return JSON.parse(sessionStorage.getItem(storeKey) || "") as DemoStore;
  } catch {
    return { runs: [], findings: [], history: [] };
  }
}

function writeStore(store: DemoStore) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(storeKey, JSON.stringify(store));
}
