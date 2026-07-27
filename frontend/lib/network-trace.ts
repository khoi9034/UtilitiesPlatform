import { demoConnectivityIssueGroups, ensureDemoConnectivityCalibration, type ConnectivityIssueGroup } from "./connectivity-qa";
import { demoAllRelationships, demoAssets, type AssetRelationship, type UtilityAsset } from "./utility-assets";

export type TraceOutcome = "complete" | "complete_with_warnings" | "partial" | "blocked" | "no_path" | "ambiguous" | "failed_safely";
export type TraceType = {
  trace_type: string;
  name: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  start_asset_classes: string[];
  terminal_asset_classes: string[];
  default_direction: string;
  description: string;
  trace_profile_version: string;
  trace_rule_version: string;
  read_only: true;
};
export type TraceCondition = { code: string; message: string; asset_id: string; relationship_id: string; issue_group_id: string };
export type TraceStep = {
  trace_step_id?: string;
  trace_path_id: string;
  sequence: number;
  asset_id: string;
  canonical_name: string;
  asset_class: string;
  entered_by_relationship_id: string;
  exited_by_relationship_id: string;
  step_role: string;
  operational_state: string;
  lifecycle_status: string;
  feeder_or_route_context: string;
  qa_issue_group_ids: string[];
  trace_effect: string;
  decision: string;
  decision_reason: string;
  asset_context: Record<string, unknown>;
};
export type TracePath = {
  trace_path_id: string;
  trace_run_id: string;
  path_rank: number;
  path_status: string;
  start_asset_id: string;
  end_asset_id: string;
  asset_ids: string[];
  relationship_ids: string[];
  hop_count: number;
  confidence: string;
  provisional: boolean;
  warnings: TraceCondition[];
  blockers: TraceCondition[];
  stopping_reason: string;
  qa_issue_group_ids: string[];
  steps?: TraceStep[];
  created_at: string;
};
export type TraceEvent = {
  trace_event_id: string;
  event_type: string;
  asset_id: string;
  relationship_id: string;
  issue_group_id: string;
  severity: string;
  message: string;
  created_at: string;
};
export type TraceRun = {
  trace_run_id: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  trace_type: string;
  trace_profile: string;
  trace_rule_version: string;
  input_fingerprint: string;
  status: string;
  outcome: TraceOutcome;
  start_asset_id: string;
  target_asset_id: string;
  direction: string;
  lifecycle_mode: string;
  operational_mode: string;
  provisional_policy: string;
  qa_policy: string;
  request_options: Record<string, unknown>;
  started_at: string;
  completed_at: string;
  assets_visited: number;
  relationships_traversed: number;
  paths_evaluated: number;
  warnings_count: number;
  blockers_count: number;
  provisional_segments: number;
  confidence: string;
  safe_error_code: string;
  safe_error_message: string;
  summary: Record<string, unknown>;
  paths: TracePath[];
  events: TraceEvent[];
  history: Array<Record<string, unknown>>;
  disclaimer: string;
  request_fingerprint: string;
  reused?: boolean;
  message?: string;
};

export const traceDisclaimer = "UtilitiesPlatform Network Trace V1 performs read-only analytical traversal of the platform's vendor-neutral canonical asset and relationship model. It is not an operational ArcFM, Smallworld, Esri Utility Network, outage-management, engineering, or telecom-provisioning trace.";

const profileVersion = "network-trace-profiles-v1";
const ruleVersion = "network-trace-rules-v1";
const storeKey = "utilities-platform-demo-network-trace-v1";
const electricFlow = ["substation", "feeder", "feeder_breaker", "switch", "fuse", "recloser", "transformer", "overhead_conductor", "underground_conductor", "secondary_conductor", "service_point", "junction"];
const telecomFlow = ["central_office", "network_hub", "fiber_cabinet", "fiber_route", "fiber_cable", "handhole", "manhole", "splice_closure", "splitter", "terminal", "proposed_construction_segment"];

const profileRows: Record<UtilityAsset["utility_vertical"], Array<[string, string, string[], string[], string]>> = {
  electric_distribution: [
    ["ELEC-TRACE-001", "Feeder downstream trace", ["feeder", "feeder_breaker", "substation"], ["service_point"], "downstream"],
    ["ELEC-TRACE-002", "Asset upstream trace", electricFlow.filter((item) => !["substation", "feeder", "feeder_breaker"].includes(item)), ["feeder_breaker", "feeder", "substation"], "upstream"],
    ["ELEC-TRACE-003", "Protective device trace", ["transformer", "overhead_conductor", "underground_conductor", "secondary_conductor", "service_point", "junction"], ["fuse", "recloser", "switch", "feeder_breaker"], "upstream"],
    ["ELEC-TRACE-004", "Isolation trace", ["switch", "fuse", "recloser", "feeder_breaker", "overhead_conductor", "underground_conductor", "secondary_conductor"], ["service_point"], "downstream"],
    ["ELEC-TRACE-005", "Transformer service trace", ["transformer"], ["service_point"], "downstream"],
    ["ELEC-TRACE-006", "Feeder membership trace", electricFlow, [], "bidirectional"],
    ["ELEC-TRACE-007", "Trace to source", electricFlow, ["feeder_breaker", "substation"], "toward_source"],
  ],
  telecom_fiber: [
    ["TEL-TRACE-001", "Hub-to-terminal trace", ["network_hub", "central_office", "fiber_cabinet"], ["terminal"], "toward_terminal"],
    ["TEL-TRACE-002", "Terminal upstream trace", ["terminal", "splitter", "fiber_cabinet"], ["fiber_cabinet", "network_hub", "central_office"], "upstream"],
    ["TEL-TRACE-003", "Cable route trace", ["fiber_cable", "fiber_route", "proposed_construction_segment"], [], "bidirectional"],
    ["TEL-TRACE-004", "Splice sequence trace", ["fiber_cable", "splice_closure", "terminal"], ["terminal", "fiber_cabinet", "network_hub"], "bidirectional"],
    ["TEL-TRACE-005", "Cabinet downstream trace", ["fiber_cabinet"], ["terminal"], "downstream"],
    ["TEL-TRACE-006", "Affected-network trace", ["fiber_cable", "splice_closure", "fiber_cabinet"], ["terminal"], "downstream"],
    ["TEL-TRACE-007", "Capacity-path trace", ["network_hub", "fiber_cabinet", "fiber_cable", "splitter"], ["terminal"], "toward_terminal"],
    ["TEL-TRACE-008", "Proposed construction continuity trace", ["proposed_construction_segment", "fiber_route"], [], "bidirectional"],
  ],
};

type TraceCatalog = {
  utility_vertical: UtilityAsset["utility_vertical"];
  profile_name: string;
  trace_profile_version: string;
  trace_rule_version: string;
  items: TraceType[];
};
type TraceCatalogRoot = {
  trace_profile_version: string;
  trace_rule_version: string;
  profiles: Record<UtilityAsset["utility_vertical"], TraceCatalog>;
};

export function demoTraceTypes(): TraceCatalogRoot;
export function demoTraceTypes(vertical: UtilityAsset["utility_vertical"]): TraceCatalog;
export function demoTraceTypes(vertical?: UtilityAsset["utility_vertical"]): TraceCatalog | TraceCatalogRoot {
  if (!vertical) return {
    trace_profile_version: profileVersion,
    trace_rule_version: ruleVersion,
    profiles: {
      electric_distribution: traceCatalog("electric_distribution"),
      telecom_fiber: traceCatalog("telecom_fiber"),
    },
  };
  return traceCatalog(vertical);
}

function traceCatalog(vertical: UtilityAsset["utility_vertical"]): TraceCatalog {
  return {
    utility_vertical: vertical,
    profile_name: `${vertical}_trace_v1`,
    trace_profile_version: profileVersion,
    trace_rule_version: ruleVersion,
    items: profileRows[vertical].map(([trace_type, name, start_asset_classes, terminal_asset_classes, default_direction]): TraceType => ({
      trace_type, name, utility_vertical: vertical, start_asset_classes, terminal_asset_classes, default_direction,
      description: `${name} uses explicit synthetic canonical relationships and calibrated QA evidence.`,
      trace_profile_version: profileVersion, trace_rule_version: ruleVersion, read_only: true,
    })),
  };
}

export function demoTraceRuns(vertical: UtilityAsset["utility_vertical"]) {
  return readRuns().filter((item) => item.utility_vertical === vertical).sort((a, b) => b.started_at.localeCompare(a.started_at));
}

export function demoTraceRun(traceRunId: string) {
  const run = readRuns().find((item) => item.trace_run_id === traceRunId);
  if (!run) throw new Error("Synthetic trace run not found.");
  return run;
}

export function runDemoTrace(vertical: UtilityAsset["utility_vertical"], body: Record<string, unknown>): TraceRun {
  const definition = (demoTraceTypes(vertical).items as TraceType[]).find((item) => item.trace_type === body.trace_type);
  if (!definition) throw new Error("Select an allowlisted trace type.");
  const assets = demoAssets().filter((item) => item.utility_vertical === vertical);
  const byId = new Map(assets.map((item) => [item.asset_id, item]));
  const startId = String(body.start_asset_id ?? "");
  const start = byId.get(startId);
  if (!start || !definition.start_asset_classes.includes(start.asset_class)) throw new Error("Select an eligible synthetic start asset.");
  const request = {
    trace_type: definition.trace_type,
    start_asset_id: startId,
    optional_target_asset_id: String(body.optional_target_asset_id ?? ""),
    direction: String(body.direction ?? definition.default_direction),
    lifecycle_mode: String(body.lifecycle_mode ?? "active_only"),
    operational_mode: String(body.operational_mode ?? "respect_state"),
    provisional_relationship_policy: String(body.provisional_relationship_policy ?? "include_with_warning"),
    qa_policy: String(body.qa_policy ?? "conservative"),
    include_reference_relationships: Boolean(body.include_reference_relationships),
    include_containment_relationships: Boolean(body.include_containment_relationships),
    max_depth: bounded(body.max_depth, 40, 1, 100),
    max_assets: bounded(body.max_assets, 250, 1, 1000),
  };
  const requestFingerprint = JSON.stringify(request);
  const runs = readRuns();
  const reusable = runs.find((item) => item.utility_vertical === vertical && item.request_fingerprint === requestFingerprint && item.status === "succeeded");
  if (reusable && !body.force_recalculate) return { ...reusable, reused: true, message: "No asset, relationship, QA, calibration, or trace-policy changes detected" };

  ensureDemoConnectivityCalibration(vertical);
  const groups = demoConnectivityIssueGroups(vertical, new URLSearchParams("limit=500")).items;
  const relationships = demoAllRelationships().filter((item) => byId.has(item.from_asset_id) || byId.has(item.to_asset_id));
  const paths = walkSyntheticGraph(start, definition, request, byId, relationships, groups);
  const complete = paths.filter((item) => ["target_reached", "source_reached", "terminal_reached"].includes(item.stopping_reason));
  const warnings = paths.reduce((total, item) => total + item.warnings.length, 0);
  const blockers = paths.reduce((total, item) => total + item.blockers.length, 0);
  const outcome: TraceOutcome = complete.length
    ? warnings || blockers || complete.length !== paths.length ? "complete_with_warnings" : "complete"
    : blockers ? "blocked" : paths.some((item) => item.hop_count) ? "partial" : "no_path";
  const now = new Date().toISOString();
  const traceRunId = `demo-trace-${vertical}-${runs.length + 1}`;
  const persistedPaths = paths.map((path, index) => ({
    ...path,
    trace_run_id: traceRunId,
    trace_path_id: `${traceRunId}-path-${index + 1}`,
    path_rank: index + 1,
    created_at: now,
    steps: path.steps.map((step) => ({ ...step, trace_path_id: `${traceRunId}-path-${index + 1}` })),
  }));
  const run: TraceRun = {
    trace_run_id: traceRunId, utility_vertical: vertical, trace_type: definition.trace_type,
    trace_profile: `${vertical}_trace_v1`, trace_rule_version: ruleVersion,
    input_fingerprint: "synthetic-canonical-graph-v1", status: "succeeded", outcome,
    start_asset_id: startId, target_asset_id: request.optional_target_asset_id, direction: request.direction,
    lifecycle_mode: request.lifecycle_mode, operational_mode: request.operational_mode,
    provisional_policy: request.provisional_relationship_policy, qa_policy: request.qa_policy,
    request_options: request, started_at: now, completed_at: now,
    assets_visited: new Set(persistedPaths.flatMap((item) => item.asset_ids)).size,
    relationships_traversed: new Set(persistedPaths.flatMap((item) => item.relationship_ids)).size,
    paths_evaluated: persistedPaths.length, warnings_count: warnings, blockers_count: blockers,
    provisional_segments: new Set(persistedPaths.filter((item) => item.provisional).flatMap((item) => item.relationship_ids)).size,
    confidence: outcome === "complete" ? "high" : outcome === "complete_with_warnings" ? "medium" : blockers ? "low" : "indeterminate",
    safe_error_code: "", safe_error_message: "",
    summary: {
      outcome,
      message: outcome.replaceAll("_", " "),
      confidence_notice: "Vendor-neutral analytical confidence based on canonical relationship evidence.",
      limitations: [traceDisclaimer, "Synthetic demo trace; no operational data or services are connected."],
    },
    paths: persistedPaths,
    events: persistedPaths.flatMap((path) => [...path.warnings, ...path.blockers]).map((item, index) => ({
      trace_event_id: `${traceRunId}-event-${index + 1}`, event_type: item.code, asset_id: item.asset_id,
      relationship_id: item.relationship_id, issue_group_id: item.issue_group_id,
      severity: pathSeverity(item, persistedPaths), message: item.message, created_at: now,
    })),
    history: [
      { action: "run_started", actor_type: "human", actor: "Demo Reviewer", reason: "Synthetic trace requested.", created_at: now },
      { action: "run_completed", actor_type: "system", actor: "demo_engine", reason: "Synthetic trace completed.", created_at: now },
    ],
    disclaimer: traceDisclaimer,
    request_fingerprint: requestFingerprint,
  };
  writeRuns([run, ...runs]);
  return run;
}

export function demoTraceReadiness(assetId: string) {
  const asset = demoAssets().find((item) => item.asset_id === assetId);
  if (!asset) throw new Error("Synthetic asset not found.");
  ensureDemoConnectivityCalibration(asset.utility_vertical);
  const relationships = demoAllRelationships().filter((item) => item.from_asset_id === assetId || item.to_asset_id === assetId);
  const relationIds = new Set(relationships.map((item) => item.relationship_id));
  const groups = demoConnectivityIssueGroups(asset.utility_vertical, new URLSearchParams("limit=500")).items.filter((item) =>
    item.affected_asset_ids.includes(assetId) || item.affected_relationship_ids.some((id) => relationIds.has(id)),
  );
  const recent = demoTraceRuns(asset.utility_vertical).filter((run) => run.paths.some((path) => path.asset_ids.includes(assetId))).slice(0, 10);
  const usage = Object.fromEntries(relationships.map((relationship) => {
    const paths = recent.flatMap((run) => run.paths).filter((path) => path.relationship_ids.includes(relationship.relationship_id));
    return [relationship.relationship_id, {
      traces_used: paths.length,
      traces_stopped: paths.filter((path) => !["target_reached", "source_reached", "terminal_reached"].includes(path.stopping_reason)).length,
    }];
  }));
  return {
    asset_id: asset.asset_id, utility_vertical: asset.utility_vertical, asset_class: asset.asset_class,
    canonical_name: asset.canonical_name, lifecycle_status: asset.lifecycle_status,
    operational_status: asset.operational_status,
    eligible_trace_types: (demoTraceTypes(asset.utility_vertical).items as TraceType[])
      .filter((item) => item.start_asset_classes.includes(asset.asset_class))
      .map((item) => ({ trace_type: item.trace_type, name: item.name, default_direction: item.default_direction })),
    trace_ready: true, qa_evaluated: true, calibration_available: true,
    blockers: groups.filter((item) => item.trace_impact === "stops_trace").map(safeGroup),
    warnings: groups.filter((item) => item.trace_impact !== "stops_trace").map(safeGroup),
    provisional_relationships: relationships.filter((item) => item.provisional).length,
    available_relationships: relationships.length,
    latest_trace: recent[0] ?? null, trace_count: recent.length,
    recent_traces: recent.map((item) => ({ trace_run_id: item.trace_run_id, trace_type: item.trace_type, outcome: item.outcome, confidence: item.confidence, completed_at: item.completed_at })),
    relationship_trace_usage: usage,
    confidence_notice: "Vendor-neutral analytical confidence based on canonical relationship evidence.",
    disclaimer: traceDisclaimer,
  };
}

type DemoPath = Omit<TracePath, "trace_path_id" | "trace_run_id" | "path_rank" | "created_at"> & { steps: TraceStep[] };
type DemoRequest = {
  trace_type: string;
  start_asset_id: string;
  optional_target_asset_id: string;
  direction: string;
  lifecycle_mode: string;
  operational_mode: string;
  provisional_relationship_policy: string;
  qa_policy: string;
  include_reference_relationships: boolean;
  include_containment_relationships: boolean;
  max_depth: number;
  max_assets: number;
};

function walkSyntheticGraph(
  start: UtilityAsset,
  definition: TraceType,
  request: DemoRequest,
  byId: Map<string, UtilityAsset>,
  relationships: AssetRelationship[],
  groups: ConnectivityIssueGroup[],
): DemoPath[] {
  const flowClasses = new Set(start.utility_vertical === "electric_distribution" ? electricFlow : telecomFlow);
  const queue: Array<{ ids: string[]; rels: string[]; warnings: TraceCondition[]; provisional: boolean }> = [{ ids: [start.asset_id], rels: [], warnings: [], provisional: false }];
  const finished: DemoPath[] = [];
  while (queue.length && finished.length < 20) {
    const state = queue.shift()!;
    const current = byId.get(state.ids.at(-1)!)!;
    const targetReached = state.rels.length && request.optional_target_asset_id === current.asset_id;
    const terminalReached = state.rels.length && definition.terminal_asset_classes.includes(current.asset_class);
    if (targetReached || terminalReached) {
      finished.push(demoPath(state, byId, [], targetReached ? "target_reached" : ["substation", "feeder", "feeder_breaker", "network_hub", "central_office", "fiber_cabinet"].includes(current.asset_class) ? "source_reached" : "terminal_reached"));
      continue;
    }
    if (state.rels.length >= request.max_depth || new Set(state.ids).size >= request.max_assets) {
      finished.push(demoPath(state, byId, [condition("maximum_depth", "A configured trace guardrail was reached.", current.asset_id)], "maximum_depth"));
      continue;
    }
    const candidates = relationships.flatMap((relationship) => {
      const forward = ["downstream", "toward_terminal"].includes(request.direction);
      const upstream = ["upstream", "toward_source"].includes(request.direction);
      if ((forward || request.direction === "bidirectional") && relationship.from_asset_id === current.asset_id) return [[relationship, relationship.to_asset_id] as const];
      if ((upstream || request.direction === "bidirectional") && relationship.to_asset_id === current.asset_id) return [[relationship, relationship.from_asset_id] as const];
      return [];
    }).filter(([relationship, nextId]) =>
      ["feeds", "connects_to", "spliced_to", "terminates_at"].includes(relationship.relationship_type)
      && flowClasses.has(byId.get(nextId)?.asset_class ?? "")
      && !state.ids.includes(nextId)
      && !(relationship.provisional && request.provisional_relationship_policy === "exclude"),
    ).sort(([left], [right]) => left.relationship_id.localeCompare(right.relationship_id));
    if (!candidates.length) {
      finished.push(demoPath(state, byId, [], state.rels.length && ["ELEC-TRACE-004", "ELEC-TRACE-006", "TEL-TRACE-003", "TEL-TRACE-004", "TEL-TRACE-006", "TEL-TRACE-008"].includes(definition.trace_type) ? "terminal_reached" : "no_traversable_edge"));
      continue;
    }
    for (const [relationship, nextId] of candidates) {
      const next = byId.get(nextId)!;
      const nextState = {
        ids: [...state.ids, nextId],
        rels: [...state.rels, relationship.relationship_id],
        warnings: [...state.warnings],
        provisional: state.provisional || relationship.provisional,
      };
      if (relationship.provisional) nextState.warnings.push(condition("provisional_relationship", "The path uses provisional relationship evidence.", nextId, relationship.relationship_id));
      const blockers: TraceCondition[] = [];
      if (request.lifecycle_mode === "active_only" && next.lifecycle_status !== "active") blockers.push(condition("retired_asset", "Lifecycle policy excludes this asset.", nextId, relationship.relationship_id));
      if (request.operational_mode === "respect_state" && ["open", "normally_open"].includes(next.operational_status)) blockers.push(condition("open_device", "The open device stops downstream traversal.", nextId, relationship.relationship_id));
      const affected = groups.filter((group) => group.affected_asset_ids.includes(nextId) || group.affected_relationship_ids.includes(relationship.relationship_id));
      for (const group of affected) {
        const item = condition(group.trace_impact, group.trace_impact_reason, nextId, relationship.relationship_id, group.issue_group_id);
        if (group.trace_impact === "stops_trace" && request.qa_policy !== "diagnostic") blockers.push(item);
        else if (group.trace_impact !== "no_trace_effect") nextState.warnings.push(item);
      }
      if (blockers.length) finished.push(demoPath(nextState, byId, blockers, blockers[0].code === "stops_trace" ? "trace_stopping_issue" : blockers[0].code));
      else queue.push(nextState);
    }
  }
  return finished.length ? finished : [demoPath(queue[0] ?? { ids: [start.asset_id], rels: [], warnings: [], provisional: false }, byId, [], "no_traversable_edge")];
}

function demoPath(
  state: { ids: string[]; rels: string[]; warnings: TraceCondition[]; provisional: boolean },
  byId: Map<string, UtilityAsset>,
  blockers: TraceCondition[],
  stoppingReason: string,
): DemoPath {
  const complete = ["target_reached", "source_reached", "terminal_reached"].includes(stoppingReason);
  return {
    path_status: complete ? "complete" : blockers.length ? "blocked" : "partial",
    start_asset_id: state.ids[0], end_asset_id: state.ids.at(-1)!, asset_ids: state.ids,
    relationship_ids: state.rels, hop_count: state.rels.length,
    confidence: complete && !state.warnings.length ? "high" : blockers.length ? "low" : "medium",
    provisional: state.provisional, warnings: uniqueConditions(state.warnings), blockers,
    stopping_reason: stoppingReason,
    qa_issue_group_ids: [...new Set([...state.warnings, ...blockers].map((item) => item.issue_group_id).filter(Boolean))],
    steps: state.ids.map((assetId, sequence) => {
      const asset = byId.get(assetId)!;
      const context = asset.canonical_attributes_json ?? {};
      return {
        trace_path_id: "", sequence, asset_id: assetId, canonical_name: asset.canonical_name,
        asset_class: asset.asset_class,
        entered_by_relationship_id: sequence ? state.rels[sequence - 1] : "",
        exited_by_relationship_id: sequence < state.rels.length ? state.rels[sequence] : "",
        step_role: sequence === 0 ? "start" : sequence === state.ids.length - 1 ? "stop" : "traversed",
        operational_state: asset.operational_status, lifecycle_status: asset.lifecycle_status,
        feeder_or_route_context: String(context.feeder_id ?? context.route_id ?? ""),
        qa_issue_group_ids: sequence === state.ids.length - 1 ? [...new Set([...state.warnings, ...blockers].map((item) => item.issue_group_id).filter(Boolean))] : [],
        trace_effect: sequence === state.ids.length - 1 && !complete ? "stopped" : "continued",
        decision: sequence === state.ids.length - 1 ? "stop" : "traverse",
        decision_reason: sequence === state.ids.length - 1 ? stoppingReason : "allowlisted synthetic relationship",
        asset_context: Object.fromEntries(Object.entries(context).filter(([key]) => ["feeder_id", "circuit_id", "phase", "nominal_voltage", "operating_voltage", "route_id", "cable_id", "fiber_count", "strand_start", "strand_end", "total_capacity", "used_capacity", "reserved_capacity", "available_capacity"].includes(key))),
      };
    }),
  };
}

function condition(code: string, message: string, assetId: string, relationshipId = "", issueGroupId = ""): TraceCondition {
  return { code, message, asset_id: assetId, relationship_id: relationshipId, issue_group_id: issueGroupId };
}

function safeGroup(group: ConnectivityIssueGroup) {
  return {
    issue_group_id: group.issue_group_id, primary_rule_code: group.primary_rule_code,
    group_title: group.group_title, trace_impact: group.trace_impact,
    trace_impact_reason: group.trace_impact_reason, recommended_action: group.recommended_action,
    review_status: group.review_status,
  };
}

function uniqueConditions(items: TraceCondition[]) {
  return [...new Map(items.map((item) => [`${item.code}:${item.asset_id}:${item.relationship_id}:${item.issue_group_id}`, item])).values()];
}

function bounded(value: unknown, fallback: number, minimum: number, maximum: number) {
  const parsed = Number(value ?? fallback);
  return Number.isInteger(parsed) ? Math.min(maximum, Math.max(minimum, parsed)) : fallback;
}

function pathSeverity(item: TraceCondition, paths: TracePath[]) {
  return paths.some((path) => path.blockers.includes(item)) ? "error" : "warning";
}

function readRuns(): TraceRun[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(sessionStorage.getItem(storeKey) ?? "[]") as TraceRun[]; } catch { return []; }
}

function writeRuns(runs: TraceRun[]) {
  if (typeof window !== "undefined") sessionStorage.setItem(storeKey, JSON.stringify(runs));
}
