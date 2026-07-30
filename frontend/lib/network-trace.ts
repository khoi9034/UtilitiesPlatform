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
  hydraulic_simulation: false;
  disclaimer: string;
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
export type CalibratedTraceEvent = {
  calibrated_event_id: string;
  calibration_run_id: string;
  trace_run_id: string;
  category: string;
  scope: string;
  priority: number;
  title: string;
  summary: string;
  source_event_ids: string[];
  path_ids: string[];
  asset_ids: string[];
  relationship_ids: string[];
  issue_group_ids: string[];
  primary: boolean;
  repeated_count: number;
  trace_effect: string;
  recommended_action: string;
  created_at: string;
};
export type CalibratedTraceResult = {
  calibrated_result_id: string;
  calibration_run_id: string;
  trace_run_id: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  trace_calibration_version: string;
  original_outcome: TraceOutcome;
  calibrated_outcome: TraceOutcome;
  original_confidence: string;
  calibrated_confidence: string;
  objective_reached: boolean;
  primary_stopping_reason: string;
  primary_stopping_category: string;
  primary_stopping_asset_id: string;
  primary_stopping_relationship_id: string;
  primary_issue_group_id: string;
  path_specific_blocker_count: number;
  path_specific_warning_count: number;
  branch_specific_warning_count: number;
  background_warning_count: number;
  informational_event_count: number;
  normal_branch_count: number;
  ambiguous_branch_count: number;
  provisional_segment_count: number;
  excluded_asset_count: number;
  excluded_relationship_count: number;
  related_raw_event_count: number;
  confidence_reason: string[];
  outcome_reason: string[];
  recommended_action: string;
  recommended_edit_category: string;
  comparison_key: string;
  path_signature: string;
  branch_signature: string;
  reachable_asset_ids: string[];
  unreachable_asset_ids: string[];
  blocked_path_ids: string[];
  path_specific_issue_group_ids: string[];
  external_trace_mapping_status: string;
  adapter_required: boolean;
  vendor_concept_hints: string[];
  disclaimer: string;
  created_at: string;
};
export type TraceCalibrationRun = {
  calibration_run_id: string;
  trace_run_id: string;
  utility_vertical: UtilityAsset["utility_vertical"];
  trace_calibration_version: string;
  input_fingerprint: string;
  status: string;
  started_at: string;
  completed_at: string;
  raw_events_read: number;
  raw_warnings_read: number;
  raw_blockers_read: number;
  calibrated_events_created: number;
  path_specific_warning_count: number;
  background_warning_count: number;
  primary_blocker_count: number;
  normal_branch_count: number;
  ambiguous_branch_count: number;
  supersedes_calibration_run_id: string;
  result: CalibratedTraceResult;
  events: CalibratedTraceEvent[];
  history: Array<Record<string, unknown>>;
  reused?: boolean;
  message?: string;
};

export const traceDisclaimer = "UtilitiesPlatform Network Trace V1 performs read-only analytical traversal of the platform's vendor-neutral canonical asset and relationship model. This is a topology/connectivity trace and not a hydraulic simulation. It is not an operational ArcFM, Smallworld, Esri Utility Network, outage-management, engineering, or telecom-provisioning trace.";

const profileVersion = "network-trace-profiles-v1";
const ruleVersion = "network-trace-rules-v1";
const storeKey = "utilities-platform-demo-network-trace-v1";
const calibrationStoreKey = "utilities-platform-demo-network-trace-calibration-v1";
const traceCalibrationVersion = "network-trace-calibration-v1";
const electricFlow = ["substation", "feeder", "feeder_breaker", "switch", "fuse", "recloser", "transformer", "overhead_conductor", "underground_conductor", "secondary_conductor", "service_point", "junction"];
const telecomFlow = ["central_office", "network_hub", "fiber_cabinet", "fiber_route", "fiber_cable", "handhole", "manhole", "splice_closure", "splitter", "terminal", "proposed_construction_segment"];
const waterFlow = ["treatment_facility", "transmission_main", "distribution_main", "water_main", "isolation_valve", "valve", "hydrant", "service_line", "meter"];
const wastewaterFlow = ["service_lateral", "manhole", "gravity_main", "lift_station", "force_main", "treatment_facility", "outfall"];
const flowClasses: Record<UtilityAsset["utility_vertical"], string[]> = {
  electric_distribution: electricFlow,
  telecom_fiber: telecomFlow,
  water: waterFlow,
  wastewater: wastewaterFlow,
};

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
  water: [
    ["WATER-TRACE-001", "Connected assets from main", ["water_main", "transmission_main", "distribution_main"], [], "bidirectional"],
    ["WATER-TRACE-002", "Upstream source or facility path", waterFlow, ["treatment_facility"], "toward_source"],
    ["WATER-TRACE-003", "Service and hydrant reachability", ["water_main", "transmission_main", "distribution_main", "isolation_valve"], ["service_line", "meter", "hydrant"], "downstream"],
    ["WATER-TRACE-004", "Valve-isolation impact", ["valve", "isolation_valve"], ["service_line", "meter", "hydrant"], "downstream"],
    ["WATER-TRACE-005", "Affected services after valve closure", ["valve", "isolation_valve"], ["service_line", "meter"], "downstream"],
    ["WATER-TRACE-006", "Disconnected water assets", waterFlow, [], "bidirectional"],
  ],
  wastewater: [
    ["WW-TRACE-001", "Downstream gravity path", ["gravity_main", "manhole"], ["lift_station", "treatment_facility", "outfall"], "downstream"],
    ["WW-TRACE-002", "Upstream contributing assets", ["gravity_main", "manhole", "lift_station"], ["service_lateral", "manhole"], "upstream"],
    ["WW-TRACE-003", "Path to lift station", ["gravity_main", "manhole", "service_lateral"], ["lift_station"], "downstream"],
    ["WW-TRACE-004", "Force-main path", ["lift_station", "force_main"], ["treatment_facility", "outfall"], "downstream"],
    ["WW-TRACE-005", "Path to treatment or outfall", wastewaterFlow, ["treatment_facility", "outfall"], "downstream"],
    ["WW-TRACE-006", "Affected upstream assets after blockage", ["gravity_main", "manhole"], ["service_lateral", "manhole"], "upstream"],
    ["WW-TRACE-007", "Disconnected wastewater structures", wastewaterFlow, [], "bidirectional"],
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
      water: traceCatalog("water"),
      wastewater: traceCatalog("wastewater"),
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
      hydraulic_simulation: false, disclaimer: traceDisclaimer,
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

export function runDemoTraceCalibration(
  vertical: UtilityAsset["utility_vertical"],
  traceRunId: string,
  force = false,
): TraceCalibrationRun {
  const run = demoTraceRun(traceRunId);
  if (run.utility_vertical !== vertical) throw new Error("Synthetic trace run was not found in this utility vertical.");
  const fingerprint = demoHash(JSON.stringify({
    traceRunId, input: run.input_fingerprint, request: run.request_fingerprint,
    paths: run.paths.map((path) => [path.asset_ids, path.relationship_ids, path.stopping_reason]),
    events: run.events.map((event) => [event.trace_event_id, event.event_type, event.issue_group_id]),
    version: traceCalibrationVersion,
  }));
  const calibrations = readCalibrations();
  const reusable = calibrations.find((item) =>
    item.trace_run_id === traceRunId && item.input_fingerprint === fingerprint && item.status === "succeeded",
  );
  if (reusable && !force) return {
    ...reusable, reused: true, message: "No trace evidence or calibration-rule changes detected",
  };

  const now = new Date().toISOString();
  const calibrationRunId = `demo-trace-calibration-${vertical}-${calibrations.length + 1}`;
  const complete = run.paths.filter((path) =>
    path.path_status === "complete" && ["target_reached", "source_reached", "terminal_reached"].includes(path.stopping_reason),
  );
  const objectivePaths = run.target_asset_id
    ? complete.filter((path) => path.end_asset_id === run.target_asset_id)
    : complete;
  const objectiveReached = objectivePaths.length > 0;
  const objectivePathIds = new Set(objectivePaths.map((path) => path.trace_path_id));
  const normalTypes = new Set(["ELEC-TRACE-001", "ELEC-TRACE-004", "ELEC-TRACE-005", "ELEC-TRACE-006", "TEL-TRACE-001", "TEL-TRACE-004", "TEL-TRACE-005", "TEL-TRACE-006", "TEL-TRACE-008"]);
  const authoritativeTypes = new Set(["ELEC-TRACE-002", "ELEC-TRACE-003", "ELEC-TRACE-007", "TEL-TRACE-002", "TEL-TRACE-003", "TEL-TRACE-007"]);
  const branchCount = Math.max(0, run.paths.length - 1);
  const ambiguousBranchCount = authoritativeTypes.has(run.trace_type) && new Set(complete.map((path) => path.end_asset_id)).size > 1 ? 1 : 0;
  const normalBranchCount = normalTypes.has(run.trace_type) ? Math.max(0, branchCount - ambiguousBranchCount) : 0;
  const conditionRows = run.paths.flatMap((path) => [
    ...path.blockers.map((condition) => ({ condition, path, blocking: true })),
    ...path.warnings.map((condition) => ({ condition, path, blocking: false })),
  ]);
  const grouped = new Map<string, typeof conditionRows>();
  for (const row of conditionRows) {
    const key = row.condition.issue_group_id || [
      demoTraceCategory(row.condition.code, row.condition.message),
      row.condition.asset_id, row.condition.relationship_id, row.condition.message,
    ].join("|");
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  }
  const calibratedEvents: CalibratedTraceEvent[] = [...grouped.entries()].map(([key, rows]) => {
    const first = rows[0];
    const category = demoTraceCategory(first.condition.code, first.condition.message);
    const pathIds = [...new Set(rows.map((row) => row.path.trace_path_id))].sort();
    const assetIds = [...new Set(rows.map((row) => row.condition.asset_id).filter(Boolean))].sort();
    const relationshipIds = [...new Set(rows.map((row) => row.condition.relationship_id).filter(Boolean))].sort();
    const issueGroupIds = [...new Set(rows.map((row) => row.condition.issue_group_id).filter(Boolean))].sort();
    const stopping = rows.some((row) => row.blocking);
    const selected = pathIds.some((id) => objectivePathIds.has(id));
    const scope = stopping ? "stopping_condition"
      : assetIds.includes(run.start_asset_id) ? "start_asset_context"
        : run.target_asset_id && assetIds.includes(run.target_asset_id) ? "target_asset_context"
          : selected ? pathIds.length < objectivePathIds.size ? "branch_specific" : "path_specific"
            : pathIds.length ? "branch_specific" : "network_background";
    const rawIds = run.events.filter((event) =>
      issueGroupIds.includes(event.issue_group_id)
      || (!event.issue_group_id && event.asset_id === first.condition.asset_id && event.message === first.condition.message),
    ).map((event) => event.trace_event_id);
    return {
      calibrated_event_id: `demo-calibrated-event-${demoHash(`${traceRunId}|${key}|${scope}`)}`,
      calibration_run_id: calibrationRunId, trace_run_id: traceRunId, category, scope,
      priority: stopping ? 0 : selected ? 1 : 3,
      title: category.replaceAll("_", " "), summary: first.condition.message,
      source_event_ids: rawIds, path_ids: pathIds, asset_ids: assetIds,
      relationship_ids: relationshipIds, issue_group_ids: issueGroupIds,
      primary: false, repeated_count: rows.length + rawIds.length,
      trace_effect: stopping ? "stops_trace" : selected ? "advisory" : "background",
      recommended_action: demoRecommendedAction(category), created_at: now,
    };
  });
  const referencedGroups = new Set(calibratedEvents.flatMap((event) => event.issue_group_ids));
  for (const group of demoConnectivityIssueGroups(vertical, new URLSearchParams("limit=500")).items) {
    if (referencedGroups.has(group.issue_group_id)) continue;
    calibratedEvents.push({
      calibrated_event_id: `demo-calibrated-event-${demoHash(`${traceRunId}|${group.issue_group_id}|background`)}`,
      calibration_run_id: calibrationRunId, trace_run_id: traceRunId,
      category: demoTraceCategory(group.primary_rule_code, group.group_title), scope: "network_background",
      priority: 3, title: group.group_title, summary: group.group_summary,
      source_event_ids: [], path_ids: [], asset_ids: group.affected_asset_ids,
      relationship_ids: group.affected_relationship_ids, issue_group_ids: [group.issue_group_id],
      primary: false, repeated_count: group.technical_finding_count,
      trace_effect: "background", recommended_action: group.recommended_action, created_at: now,
    });
  }
  const primary = calibratedEvents
    .filter((event) => event.scope === "stopping_condition")
    .sort((left, right) => demoTracePriority(left.category) - demoTracePriority(right.category) || left.calibrated_event_id.localeCompare(right.calibrated_event_id))[0];
  if (primary) primary.primary = true;
  calibratedEvents.sort((left, right) => Number(right.primary) - Number(left.primary) || left.priority - right.priority || left.calibrated_event_id.localeCompare(right.calibrated_event_id));
  const pathWarnings = calibratedEvents.filter((event) =>
    ["path_specific", "start_asset_context", "target_asset_context"].includes(event.scope),
  ).length;
  const backgroundWarnings = calibratedEvents.filter((event) =>
    ["network_background", "unrelated_to_selected_path"].includes(event.scope),
  ).length;
  const materialWarning = calibratedEvents.some((event) =>
    ["stopping_condition", "path_specific", "branch_specific", "start_asset_context", "target_asset_context"].includes(event.scope)
    && !["normal_branch", "target_reached", "source_reached", "terminal_reached"].includes(event.category),
  );
  const calibratedOutcome: TraceOutcome = run.status === "failed" ? "failed_safely"
    : objectiveReached ? ambiguousBranchCount ? "ambiguous" : materialWarning ? "complete_with_warnings" : "complete"
      : ambiguousBranchCount ? "ambiguous"
        : run.paths.every((path) => path.path_status === "blocked") && primary ? "blocked"
          : run.paths.some((path) => path.hop_count > 0) ? "partial" : "no_path";
  const calibratedConfidence = ["failed_safely", "no_path"].includes(calibratedOutcome) ? "indeterminate"
    : ["blocked", "partial", "ambiguous"].includes(calibratedOutcome) ? "low"
      : materialWarning || normalBranchCount ? "medium" : "high";
  const selectedPaths = objectivePaths.length ? objectivePaths : run.paths.filter((path) => path.hop_count);
  const reachable = [...new Set(selectedPaths.flatMap((path) => path.asset_ids))].sort();
  const visited = new Set(run.paths.flatMap((path) => path.asset_ids));
  const result: CalibratedTraceResult = {
    calibrated_result_id: `demo-calibrated-result-${demoHash(`${fingerprint}|${traceCalibrationVersion}`)}`,
    calibration_run_id: calibrationRunId, trace_run_id: traceRunId, utility_vertical: vertical,
    trace_calibration_version: traceCalibrationVersion,
    original_outcome: run.outcome, calibrated_outcome: calibratedOutcome,
    original_confidence: run.confidence, calibrated_confidence: calibratedConfidence,
    objective_reached: objectiveReached,
    primary_stopping_reason: primary?.category ?? complete[0]?.stopping_reason ?? "",
    primary_stopping_category: primary?.category ?? complete[0]?.stopping_reason ?? "",
    primary_stopping_asset_id: primary?.asset_ids[0] ?? "",
    primary_stopping_relationship_id: primary?.relationship_ids[0] ?? "",
    primary_issue_group_id: primary?.issue_group_ids[0] ?? "",
    path_specific_blocker_count: primary && !objectiveReached ? 1 : 0,
    path_specific_warning_count: pathWarnings,
    branch_specific_warning_count: calibratedEvents.filter((event) => event.scope === "branch_specific").length,
    background_warning_count: backgroundWarnings,
    informational_event_count: calibratedEvents.filter((event) => event.scope === "informational").length,
    normal_branch_count: normalBranchCount, ambiguous_branch_count: ambiguousBranchCount,
    provisional_segment_count: selectedPaths.filter((path) => path.provisional).length,
    excluded_asset_count: run.events.filter((event) => event.event_type === "asset_excluded").length,
    excluded_relationship_count: run.events.filter((event) => event.event_type === "relationship_excluded").length,
    related_raw_event_count: run.events.length,
    confidence_reason: [
      objectiveReached ? "The objective was reached." : "The objective was not reached.",
      calibratedConfidence === "medium" ? "Selected evidence includes an advisory, provisional, or normal branch condition." : "Confidence uses selected-path evidence only.",
      "Background network conditions do not reduce confidence.",
    ],
    outcome_reason: [
      `Objective reached: ${objectiveReached ? "yes" : "no"}.`,
      primary ? `Primary represented condition: ${primary.category}.` : "No path-stopping condition was selected.",
      `${normalBranchCount} normal and ${ambiguousBranchCount} ambiguous branch alternative(s).`,
    ],
    recommended_action: primary?.recommended_action ?? "Review the selected path evidence before operational use.",
    recommended_edit_category: demoRecommendedEdit(primary?.category ?? ""),
    comparison_key: demoHash(`${vertical}|${run.trace_type}|${run.start_asset_id}|${run.target_asset_id}|${run.request_fingerprint}`),
    path_signature: demoHash(JSON.stringify(selectedPaths.map((path) => [path.asset_ids, path.relationship_ids]))),
    branch_signature: demoHash(JSON.stringify(run.paths.map((path) => path.end_asset_id))),
    reachable_asset_ids: reachable,
    unreachable_asset_ids: [...visited].filter((assetId) => !reachable.includes(assetId)).sort(),
    blocked_path_ids: run.paths.filter((path) => path.path_status === "blocked").map((path) => path.trace_path_id),
    path_specific_issue_group_ids: [...new Set(calibratedEvents.filter((event) => !["network_background", "unrelated_to_selected_path"].includes(event.scope)).flatMap((event) => event.issue_group_ids))].sort(),
    external_trace_mapping_status: "conceptually_mappable", adapter_required: true,
    vendor_concept_hints: {
      electric_distribution: ["downstream connectivity trace", "upstream source trace", "isolation analysis"],
      telecom_fiber: ["route continuity", "splice-sequence analysis", "affected-network analysis"],
      water: ["connected-main trace", "source-path trace", "valve-isolation analysis"],
      wastewater: ["downstream gravity path", "lift-station path", "blockage-impact analysis"],
    }[vertical],
    disclaimer: `${traceDisclaimer} Calibration does not alter assets, repair connectivity, operate devices, or reproduce proprietary traces.`,
    created_at: now,
  };
  const calibration: TraceCalibrationRun = {
    calibration_run_id: calibrationRunId, trace_run_id: traceRunId, utility_vertical: vertical,
    trace_calibration_version: traceCalibrationVersion, input_fingerprint: fingerprint,
    status: "succeeded", started_at: now, completed_at: now,
    raw_events_read: run.events.length, raw_warnings_read: run.warnings_count,
    raw_blockers_read: run.blockers_count, calibrated_events_created: calibratedEvents.length,
    path_specific_warning_count: pathWarnings, background_warning_count: backgroundWarnings,
    primary_blocker_count: primary && !objectiveReached ? 1 : 0,
    normal_branch_count: normalBranchCount, ambiguous_branch_count: ambiguousBranchCount,
    supersedes_calibration_run_id: calibrations.find((item) => item.trace_run_id === traceRunId)?.calibration_run_id ?? "",
    result, events: calibratedEvents,
    history: [
      { action: "calibration_started", actor_type: "system", actor: "demo_trace_calibration_v1", created_at: now },
      { action: "calibration_completed", actor_type: "system", actor: "demo_trace_calibration_v1", created_at: now },
    ],
  };
  writeCalibrations([calibration, ...calibrations]);
  return calibration;
}

export function demoTraceCalibrationRuns(vertical: UtilityAsset["utility_vertical"]) {
  return readCalibrations().filter((item) => item.utility_vertical === vertical);
}

export function demoTraceCalibrationRun(calibrationRunId: string) {
  const run = readCalibrations().find((item) => item.calibration_run_id === calibrationRunId);
  if (!run) throw new Error("Synthetic trace calibration run not found.");
  return run;
}

export function demoTraceCalibrationStatus(vertical: UtilityAsset["utility_vertical"]) {
  return demoTraceCalibrationRuns(vertical)[0] ?? {
    utility_vertical: vertical, status: "not_started", trace_calibration_version: traceCalibrationVersion,
    message: "Network Trace calibration has not been run for this utility vertical.",
  };
}

export function demoCalibratedTraceResult(vertical: UtilityAsset["utility_vertical"], traceRunId: string) {
  const run = demoTraceCalibrationRuns(vertical).find((item) => item.trace_run_id === traceRunId);
  if (!run) throw new Error("Calibrated synthetic trace result not found. Run calibration first.");
  return run.result;
}

export function demoCalibratedTraceEvents(
  vertical: UtilityAsset["utility_vertical"],
  traceRunId: string,
  params: URLSearchParams,
) {
  const run = demoTraceCalibrationRuns(vertical).find((item) => item.trace_run_id === traceRunId);
  if (!run) throw new Error("Calibrated synthetic trace result not found. Run calibration first.");
  let items = [...run.events];
  for (const [parameter, field] of [["scope", "scope"], ["category", "category"], ["priority", "priority"]] as const) {
    if (params.has(parameter)) items = items.filter((item) => String(item[field]) === params.get(parameter));
  }
  if (params.has("primary")) items = items.filter((item) => item.primary === (params.get("primary") === "true"));
  for (const [parameter, field] of [["path_id", "path_ids"], ["asset_id", "asset_ids"], ["relationship_id", "relationship_ids"], ["issue_group_id", "issue_group_ids"]] as const) {
    if (params.has(parameter)) items = items.filter((item) => item[field].includes(params.get(parameter)!));
  }
  const limit = bounded(params.get("limit"), 100, 1, 500);
  const offset = bounded(params.get("offset"), 0, 0, Number.MAX_SAFE_INTEGER);
  return {
    items: items.slice(offset, offset + limit), calibration_run_id: run.calibration_run_id,
    pagination: { total: items.length, limit, offset, has_more: offset + limit < items.length },
  };
}

export function demoCalibratedTraceSummary(vertical: UtilityAsset["utility_vertical"], traceRunId: string) {
  const run = demoTraceRun(traceRunId);
  const result = demoCalibratedTraceResult(vertical, traceRunId);
  return {
    trace_run_id: traceRunId, calibration_run_id: result.calibration_run_id,
    utility_vertical: vertical, trace_type: run.trace_type, trace_profile: run.trace_profile,
    trace_profile_version: profileVersion, trace_calibration_version: traceCalibrationVersion,
    start_asset_id: run.start_asset_id, target_asset_id: run.target_asset_id,
    original_outcome: result.original_outcome, calibrated_outcome: result.calibrated_outcome,
    original_confidence: result.original_confidence, calibrated_confidence: result.calibrated_confidence,
    objective_reached: result.objective_reached, primary_stopping_condition: result.primary_stopping_reason,
    primary_issue_group_ids: result.primary_issue_group_id ? [result.primary_issue_group_id] : [],
    normal_branches: result.normal_branch_count, ambiguous_branches: result.ambiguous_branch_count,
    path_specific_blockers: result.path_specific_blocker_count,
    path_specific_warnings: result.path_specific_warning_count,
    background_warning_count: result.background_warning_count,
    provisional_segments: result.provisional_segment_count,
    assets_visited: run.assets_visited, relationships_traversed: run.relationships_traversed,
    path_count: run.paths_evaluated,
    excluded_context: { assets: result.excluded_asset_count, relationships: result.excluded_relationship_count },
    recommended_next_safe_action: result.recommended_action,
    comparison_key: result.comparison_key, path_signature: result.path_signature,
    branch_signature: result.branch_signature, input_fingerprint: run.input_fingerprint,
    trace_started_at: run.started_at, trace_completed_at: run.completed_at,
    calibration_created_at: result.created_at, disclaimer: result.disclaimer,
  };
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
  const allowedClasses = new Set(flowClasses[start.utility_vertical]);
  const queue: Array<{ ids: string[]; rels: string[]; warnings: TraceCondition[]; provisional: boolean }> = [{ ids: [start.asset_id], rels: [], warnings: [], provisional: false }];
  const finished: DemoPath[] = [];
  while (queue.length && finished.length < 20) {
    const state = queue.shift()!;
    const current = byId.get(state.ids.at(-1)!)!;
    const targetReached = state.rels.length && request.optional_target_asset_id === current.asset_id;
    const terminalReached = state.rels.length && definition.terminal_asset_classes.includes(current.asset_class);
    if (targetReached || terminalReached) {
      const sources: Record<UtilityAsset["utility_vertical"], string[]> = {
        electric_distribution: ["substation", "feeder", "feeder_breaker"],
        telecom_fiber: ["network_hub", "central_office", "fiber_cabinet"],
        water: ["treatment_facility"],
        wastewater: [],
      };
      finished.push(demoPath(state, byId, [], targetReached ? "target_reached" : sources[start.utility_vertical].includes(current.asset_class) ? "source_reached" : "terminal_reached"));
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
      ["feeds", "connects_to", "spliced_to", "terminates_at", "served_by", "flows_to", "draws_from"].includes(relationship.relationship_type)
      && allowedClasses.has(byId.get(nextId)?.asset_class ?? "")
      && !state.ids.includes(nextId)
      && !(relationship.provisional && request.provisional_relationship_policy === "exclude"),
    ).sort(([left], [right]) => left.relationship_id.localeCompare(right.relationship_id));
    if (!candidates.length) {
      finished.push(demoPath(state, byId, [], state.rels.length && ["ELEC-TRACE-004", "ELEC-TRACE-006", "TEL-TRACE-003", "TEL-TRACE-004", "TEL-TRACE-006", "TEL-TRACE-008", "WATER-TRACE-001", "WATER-TRACE-004", "WATER-TRACE-005", "WATER-TRACE-006", "WW-TRACE-002", "WW-TRACE-006", "WW-TRACE-007"].includes(definition.trace_type) ? "terminal_reached" : "no_traversable_edge"));
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
        feeder_or_route_context: String(context.feeder_id ?? context.route_id ?? context.water_system_id ?? context.wastewater_system_id ?? context.basin_id ?? ""),
        qa_issue_group_ids: sequence === state.ids.length - 1 ? [...new Set([...state.warnings, ...blockers].map((item) => item.issue_group_id).filter(Boolean))] : [],
        trace_effect: sequence === state.ids.length - 1 && !complete ? "stopped" : "continued",
        decision: sequence === state.ids.length - 1 ? "stop" : "traverse",
        decision_reason: sequence === state.ids.length - 1 ? stoppingReason : "allowlisted synthetic relationship",
        asset_context: Object.fromEntries(Object.entries(context).filter(([key]) => ["feeder_id", "circuit_id", "phase", "nominal_voltage", "operating_voltage", "route_id", "cable_id", "fiber_count", "strand_start", "strand_end", "total_capacity", "used_capacity", "reserved_capacity", "available_capacity", "water_system_id", "pressure_zone_id", "wastewater_system_id", "basin_id", "diameter", "slope"].includes(key))),
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

function demoTraceCategory(...values: string[]) {
  const text = values.join(" ").toLowerCase().replaceAll("-", "_");
  const categories: Array<[string, string]> = [
    ["endpoint", "endpoint_failure"], ["termination", "endpoint_failure"],
    ["open_device", "open_device"], ["normally open", "open_device"],
    ["retired", "lifecycle_exclusion"], ["inactive", "lifecycle_exclusion"],
    ["provisional", "provisional_relationship"], ["missing relationship", "missing_relationship"],
    ["feeder", "feeder_conflict"], ["circuit", "circuit_conflict"], ["route", "route_conflict"],
    ["phase", "phase_conflict"], ["voltage", "voltage_conflict"], ["strand", "strand_conflict"],
    ["capacity", "capacity_conflict"], ["conduit", "containment_warning"],
    ["target_reached", "target_reached"], ["source_reached", "source_reached"],
    ["terminal_reached", "terminal_reached"], ["cycle", "cycle_detected"], ["maximum", "traversal_limit"],
  ];
  return categories.find(([needle]) => text.includes(needle))?.[1] ?? "background_qa";
}

function demoTracePriority(category: string) {
  const categories = [
    "endpoint_failure", "open_device", "phase_conflict", "voltage_conflict", "strand_conflict",
    "capacity_conflict", "lifecycle_exclusion", "feeder_conflict", "circuit_conflict",
    "route_conflict", "missing_relationship", "background_qa",
  ];
  const index = categories.indexOf(category);
  return index < 0 ? categories.length : index;
}

function demoRecommendedAction(category: string) {
  return ({
    endpoint_failure: "Confirm the missing endpoint in an approved source-system workflow.",
    open_device: "Confirm device state and trace policy with an authorized operator.",
    lifecycle_exclusion: "Confirm lifecycle status with the data owner.",
    provisional_relationship: "Confirm the provisional relationship with the data owner.",
    strand_conflict: "Review strand assignment evidence; do not allocate capacity from this result.",
    capacity_conflict: "Review safe aggregate capacity values with an authorized inventory owner.",
  } as Record<string, string>)[category] ?? "Review the grouped evidence before proposing any source-system change.";
}

function demoRecommendedEdit(category: string) {
  return ({
    endpoint_failure: "connect_endpoint", open_device: "confirm_device_state",
    lifecycle_exclusion: "confirm_lifecycle", provisional_relationship: "confirm_provisional_relationship",
    missing_relationship: "add_relationship", feeder_conflict: "correct_membership",
    circuit_conflict: "correct_membership", route_conflict: "resolve_route",
    phase_conflict: "correct_phase", voltage_conflict: "correct_voltage",
    strand_conflict: "correct_strand_assignment", capacity_conflict: "correct_capacity",
    containment_warning: "associate_conduit",
  } as Record<string, string>)[category] ?? "manual_investigation";
}

function readRuns(): TraceRun[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(sessionStorage.getItem(storeKey) ?? "[]") as TraceRun[]; } catch { return []; }
}

function writeRuns(runs: TraceRun[]) {
  if (typeof window !== "undefined") sessionStorage.setItem(storeKey, JSON.stringify(runs));
}

function readCalibrations(): TraceCalibrationRun[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(sessionStorage.getItem(calibrationStoreKey) ?? "[]") as TraceCalibrationRun[]; } catch { return []; }
}

function writeCalibrations(runs: TraceCalibrationRun[]) {
  if (typeof window !== "undefined") sessionStorage.setItem(calibrationStoreKey, JSON.stringify(runs));
}

function demoHash(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}
