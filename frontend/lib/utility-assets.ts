export type UtilityAsset = {
  asset_id: string;
  utility_vertical: "electric_distribution" | "telecom_fiber";
  asset_class: string;
  asset_subtype: string;
  canonical_name: string;
  display_name: string;
  geometry_type: string;
  lifecycle_status: string;
  operational_status: string;
  owner_status: string;
  source_system: string;
  source_submission_id: string;
  source_layer_id: string;
  source_record_id: string;
  source_asset_identifier: string;
  source_fingerprint: string;
  qa_status: string;
  review_status: string;
  sensitivity: string;
  confidence: string;
  notes?: string;
  canonical_attributes_json?: Record<string, unknown>;
  source_attributes_json?: Record<string, unknown>;
  evidence_json?: Record<string, unknown>;
  geometry_summary_json?: Record<string, unknown>;
  relationship_count: number;
  has_provisional_relationships: boolean;
  is_synthetic: boolean;
  canonicalization_plan_id?: string;
  mapping_rule_version?: string;
};

export type AssetRelationship = {
  relationship_id: string;
  from_asset_id: string;
  to_asset_id: string;
  relationship_type: string;
  direction: string;
  confidence: string;
  source: string;
  provisional: boolean;
  connected_asset_name: string;
  connected_asset_class: string;
  evidence_json: Record<string, unknown>;
};

export type CanonicalMapping = {
  mapping_id: string;
  source_field: string;
  source_alias: string;
  canonical_field: string;
  transformation_type: string;
  confidence: string;
  mapping_status: string;
  reviewer_type: string;
  human_override: boolean;
  notes: string;
};

export type CanonicalizationPlan = {
  plan_id: string;
  submission_id: string;
  layer_id: string;
  utility_vertical: string;
  target_asset_class: string;
  status: string;
  rule_version: string;
  source_record_count: number;
  preview_record_count: number;
  mapped_field_count: number;
  unmapped_field_count: number;
  warnings: string[];
  blockers: string[];
  approved_for_canonicalization: boolean;
  approved_by: string;
  mappings: CanonicalMapping[];
  history: Array<Record<string, unknown>>;
  preview_records: Array<Record<string, string>>;
};

export const electricCounts: Record<string, number> = {
  substation: 1, feeder: 2, feeder_breaker: 2, switch: 3, fuse: 2, recloser: 1,
  transformer: 8, pole: 20, overhead_conductor: 8, underground_conductor: 3,
  secondary_conductor: 4, conduit: 2, service_point: 8, junction: 2, attachment: 2, electric_structure: 2,
  reference_boundary: 1,
};

export const telecomCounts: Record<string, number> = {
  network_hub: 1, fiber_cabinet: 2, fiber_route: 3, fiber_cable: 4, pole: 8,
  conduit: 3, handhole: 4, manhole: 1, splice_closure: 3, splitter: 3, terminal: 6,
  proposed_construction_segment: 1, service_area: 1, telecom_structure: 2,
  reference_boundary: 1,
};

const assetSessionKey = "utilities-platform-demo-canonical-assets-v1";
const planSessionKey = "utilities-platform-demo-canonical-plans-v1";

export function demoAssets(): UtilityAsset[] {
  const base = [
    ...makeVertical("electric_distribution", electricCounts),
    ...makeVertical("telecom_fiber", telecomCounts),
    ...readSession<UtilityAsset[]>(assetSessionKey, []),
  ];
  const relationships = makeDemoRelationships(base);
  return base.map((asset) => {
    const related = relationships.filter((item) => item.from_asset_id === asset.asset_id || item.to_asset_id === asset.asset_id);
    return {
      ...asset,
      relationship_count: related.length,
      has_provisional_relationships: related.some((item) => item.provisional),
    };
  });
}

function makeVertical(vertical: UtilityAsset["utility_vertical"], counts: Record<string, number>): UtilityAsset[] {
  const prefix = vertical === "electric_distribution" ? "ELEC" : "FIBER";
  return Object.entries(counts).flatMap(([assetClass, count]) =>
    Array.from({ length: count }, (_, offset) => {
      const index = offset + 1;
      const name = `${prefix}-${assetClass.replaceAll("_", "-").toUpperCase()}-${String(index).padStart(3, "0")}`;
      const electricWarning = vertical === "electric_distribution"
        && ((assetClass === "transformer" && index >= 7) || (assetClass === "underground_conductor" && index === 3) || (assetClass === "overhead_conductor" && index === 8));
      const telecomWarning = vertical === "telecom_fiber"
        && ((assetClass === "fiber_cable" && index >= 3) || (assetClass === "terminal" && index === 6) || assetClass === "proposed_construction_segment");
      const warning = electricWarning || telecomWarning;
      const retired = (vertical === "electric_distribution" && assetClass === "attachment" && index === 2)
        || (vertical === "telecom_fiber" && assetClass === "fiber_cable" && index === 3);
      const normallyOpen = vertical === "electric_distribution" && assetClass === "switch" && index === 3;
      const proposed = assetClass === "proposed_construction_segment";
      return {
        asset_id: `demo-${vertical}-${assetClass}-${index}`,
        utility_vertical: vertical,
        asset_class: assetClass,
        asset_subtype: "synthetic_v1",
        canonical_name: name,
        display_name: name,
        geometry_type: ["feeder", "overhead_conductor", "underground_conductor", "secondary_conductor", "conduit", "fiber_route", "fiber_cable", "proposed_construction_segment"].includes(assetClass) ? "polyline" : ["reference_boundary", "service_area"].includes(assetClass) ? "polygon" : "point",
        lifecycle_status: retired ? "retired" : proposed ? "proposed" : "active",
        operational_status: retired ? "retired" : proposed ? "proposed" : normallyOpen ? "normally_open" : vertical === "electric_distribution" ? "energized" : "active",
        owner_status: "confirmed",
        source_system: "synthetic_generator",
        source_submission_id: vertical === "electric_distribution" ? "DEMO-ELECTRIC-001" : "DEMO-TELECOM-001",
        source_layer_id: `demo-${vertical}-${assetClass}`,
        source_record_id: String(index),
        source_asset_identifier: name,
        source_fingerprint: `synthetic-${vertical}-${assetClass}-v1`,
        qa_status: warning || retired ? "warning" : "passed",
        review_status: warning ? "needs_review" : "approved",
        sensitivity: "public_demo",
        confidence: "high",
        notes: "Synthetic training asset with no customer, address, subscriber, or production data.",
        source_attributes_json: { synthetic_source_id: name },
        canonical_attributes_json: vertical === "electric_distribution"
          ? { feeder_id: assetClass === "transformer" && index === 8 ? "" : `FEEDER-${1 + index % 2}`, phase: assetClass === "transformer" && index === 7 ? "AX" : "ABC", normally_open: normallyOpen, conduit_id: assetClass === "underground_conductor" && index === 3 ? "" : "CONDUIT-1" }
          : { route_id: `ROUTE-${1 + index % 3}`, fiber_count: index % 2 ? 144 : 288, strand_start: 1, strand_end: index % 2 ? 144 : 288, placement_type: "underground", from_structure_id: `STRUCT-${index}`, to_structure_id: (assetClass === "fiber_cable" && index === 4) || assetClass === "proposed_construction_segment" ? "" : `STRUCT-${index + 1}`, total_capacity: 32, used_capacity: 24, reserved_capacity: 4, available_capacity: assetClass === "terminal" && index === 6 ? 9 : 4 },
        evidence_json: { value_provenance: "synthetic", rule_version: "synthetic-assets-v1" },
        geometry_summary_json: { geometry_type: "safe_summary_only" },
        relationship_count: vertical === "electric_distribution" && assetClass === "overhead_conductor" && index === 8 ? 0 : index === count ? 1 : 2,
        has_provisional_relationships: (vertical === "electric_distribution" && assetClass === "recloser") || (vertical === "telecom_fiber" && assetClass === "splice_closure" && index === 1),
        is_synthetic: true,
      };
    }),
  );
}

export function demoRelationships(assetId: string): AssetRelationship[] {
  const assets = demoAssets();
  const byId = new Map(assets.map((asset) => [asset.asset_id, asset]));
  return demoAllRelationships().filter((item) => item.from_asset_id === assetId || item.to_asset_id === assetId).map((item) => {
    const neighbor = byId.get(item.from_asset_id === assetId ? item.to_asset_id : item.from_asset_id)!;
    return { ...item, connected_asset_name: neighbor.canonical_name, connected_asset_class: neighbor.asset_class };
  });
}

export function demoAllRelationships(): AssetRelationship[] {
  const assets = [
    ...makeVertical("electric_distribution", electricCounts),
    ...makeVertical("telecom_fiber", telecomCounts),
    ...readSession<UtilityAsset[]>(assetSessionKey, []),
  ];
  return makeDemoRelationships(assets);
}

function makeDemoRelationships(assets: UtilityAsset[]): AssetRelationship[] {
  const relationships: AssetRelationship[] = [];
  for (const vertical of ["electric_distribution", "telecom_fiber"] as const) {
    const items = assets.filter((asset) => asset.utility_vertical === vertical);
    items.slice(0, -1).forEach((left, index) => {
      const right = items[index + 1];
      if ([left, right].some((asset) => asset.canonical_name === "ELEC-OVERHEAD-CONDUCTOR-008")) return;
      const provisional = vertical === "electric_distribution"
        ? index + 1 === 11
        : left.asset_class === "splice_closure" && left.source_record_id === "1";
      relationships.push({
        relationship_id: `demo-rel-${vertical}-${index + 1}`,
        from_asset_id: left.asset_id,
        to_asset_id: right.asset_id,
        relationship_type: vertical === "electric_distribution" ? "feeds" : "connects_to",
        direction: "forward",
        confidence: provisional ? "medium" : "high",
        source: provisional ? "rule_inferred" : "source",
        provisional,
        connected_asset_name: right.canonical_name,
        connected_asset_class: right.asset_class,
        evidence_json: { synthetic: true },
      });
    });
  }
  const pairs = [
    ["ELEC-ATTACHMENT-002", "ELEC-OVERHEAD-CONDUCTOR-001", "reference_for"],
    ["FIBER-FIBER-CABLE-003", "FIBER-TERMINAL-001", "terminates_at"],
  ];
  pairs.forEach(([fromName, toName, relationshipType], index) => {
    const left = assets.find((asset) => asset.canonical_name === fromName);
    const right = assets.find((asset) => asset.canonical_name === toName);
    if (!left || !right) return;
    relationships.push({
      relationship_id: `demo-rel-retired-${index + 1}`,
      from_asset_id: left.asset_id,
      to_asset_id: right.asset_id,
      relationship_type: relationshipType,
      direction: "forward",
      confidence: "high",
      source: "source",
      provisional: false,
      connected_asset_name: right.canonical_name,
      connected_asset_class: right.asset_class,
      evidence_json: { synthetic: true, intentional_review_candidate: "retired_to_active" },
    });
  });
  [
    ["ELEC-SWITCH-002", "ELEC-OVERHEAD-CONDUCTOR-002"],
    ["ELEC-OVERHEAD-CONDUCTOR-004", "ELEC-UNDERGROUND-CONDUCTOR-002"],
    ["ELEC-SWITCH-002", "ELEC-FUSE-002"],
    ["ELEC-TRANSFORMER-008", "ELEC-JUNCTION-002"],
    ["ELEC-JUNCTION-002", "ELEC-SECONDARY-CONDUCTOR-002"],
    ["ELEC-SECONDARY-CONDUCTOR-004", "ELEC-SERVICE-POINT-002"],
    ["FIBER-FIBER-CABLE-002", "FIBER-SPLICE-CLOSURE-001"],
    ["FIBER-FIBER-CABLE-002", "FIBER-SPLICE-CLOSURE-002"],
  ].forEach(([fromName, toName], index) => {
    const left = assets.find((asset) => asset.canonical_name === fromName);
    const right = assets.find((asset) => asset.canonical_name === toName);
    if (!left || !right) return;
    relationships.push({
      relationship_id: `demo-rel-trace-${index + 1}`,
      from_asset_id: left.asset_id,
      to_asset_id: right.asset_id,
      relationship_type: left.utility_vertical === "electric_distribution" ? "feeds" : "connects_to",
      direction: "forward",
      confidence: "high",
      source: "synthetic_trace_fixture",
      provisional: false,
      connected_asset_name: right.canonical_name,
      connected_asset_class: right.asset_class,
      evidence_json: { synthetic: true, purpose: "deterministic_network_trace_scenario" },
    });
  });
  return relationships;
}

export function demoPlans(): CanonicalizationPlan[] {
  const base: CanonicalizationPlan[] = [
    makePlan("DEMO-ELECTRIC-PLAN", "electric_distribution", "transformer", "approved", true),
    makePlan("DEMO-TELECOM-PLAN", "telecom_fiber", "fiber_cable", "mapping_review", false),
  ];
  const updates = readSession<Record<string, Partial<CanonicalizationPlan>>>(planSessionKey, {});
  return base.map((plan) => ({ ...plan, ...updates[plan.plan_id] }));
}

function makePlan(planId: string, vertical: string, assetClass: string, status: string, approved: boolean): CanonicalizationPlan {
  return {
    plan_id: planId, submission_id: `DEMO-${vertical.toUpperCase()}`, layer_id: `demo-plan-${assetClass}`,
    utility_vertical: vertical, target_asset_class: assetClass, status, rule_version: "canonical-assets-v1",
    source_record_count: assetClass === "transformer" ? 8 : 4, preview_record_count: 3,
    mapped_field_count: 3, unmapped_field_count: 1, warnings: ["Synthetic preview only."], blockers: [],
    approved_for_canonicalization: approved, approved_by: approved ? "Demo Reviewer" : "",
    mappings: [
      { mapping_id: `${planId}-1`, source_field: "SOURCE_ID", source_alias: "Source ID", canonical_field: "source_asset_identifier", transformation_type: "renamed", confidence: "high", mapping_status: "accepted", reviewer_type: "human", human_override: false, notes: "Synthetic mapping." },
      { mapping_id: `${planId}-2`, source_field: "STATUS", source_alias: "Status", canonical_field: "lifecycle_status", transformation_type: "lifecycle_mapping", confidence: "medium", mapping_status: "proposed", reviewer_type: "human", human_override: false, notes: "Code confirmation required." },
      { mapping_id: `${planId}-3`, source_field: "TYPE", source_alias: "Type", canonical_field: "asset_subtype", transformation_type: "renamed", confidence: "high", mapping_status: "accepted", reviewer_type: "human", human_override: false, notes: "Synthetic mapping." },
      { mapping_id: `${planId}-4`, source_field: "LEGACY_NOTE", source_alias: "Legacy Note", canonical_field: "", transformation_type: "unmapped", confidence: "unavailable", mapping_status: "unmapped", reviewer_type: "human", human_override: false, notes: "Not needed in V1." },
    ],
    history: [{ action: "plan_created", actor: "demo", created_at: "2026-07-26T12:00:00Z" }],
    preview_records: [{ source_record_id: "1", source_asset_identifier: "SYNTH-001" }, { source_record_id: "2", source_asset_identifier: "SYNTH-002" }, { source_record_id: "3", source_asset_identifier: "SYNTH-003" }],
  };
}

export function updateDemoPlan(planId: string, update: Partial<CanonicalizationPlan>): CanonicalizationPlan {
  const current = demoPlans().find((plan) => plan.plan_id === planId);
  if (!current) throw new Error("Synthetic canonicalization plan not found.");
  const updates = readSession<Record<string, Partial<CanonicalizationPlan>>>(planSessionKey, {});
  updates[planId] = { ...updates[planId], ...update };
  writeSession(planSessionKey, updates);
  return { ...current, ...update };
}

export function createDemoCanonicalAssets(planId: string): { created_count: number; existing_count: number; published: false } {
  const plan = demoPlans().find((item) => item.plan_id === planId);
  if (!plan?.approved_for_canonicalization) throw new Error("Human plan approval is required.");
  const existing = readSession<UtilityAsset[]>(assetSessionKey, []);
  const created = plan.preview_records
    .filter((record) => !existing.some((asset) => asset.asset_id === `${planId}-${record.source_record_id}`))
    .map((record) => ({
      ...demoAssets().find((asset) => asset.utility_vertical === plan.utility_vertical && asset.asset_class === plan.target_asset_class)!,
      asset_id: `${planId}-${record.source_record_id}`,
      canonical_name: record.source_asset_identifier,
      display_name: record.source_asset_identifier,
      source_record_id: record.source_record_id,
      review_status: "imported",
      qa_status: "not_evaluated",
      canonicalization_plan_id: planId,
    }));
  writeSession(assetSessionKey, [...existing, ...created]);
  updateDemoPlan(planId, { status: "created" });
  return { created_count: created.length, existing_count: plan.preview_records.length - created.length, published: false };
}

function readSession<T>(key: string, fallback: T): T {
  if (typeof sessionStorage === "undefined") return fallback;
  try { return JSON.parse(sessionStorage.getItem(key) ?? "") as T; } catch { return fallback; }
}

function writeSession(key: string, value: unknown) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(key, JSON.stringify(value));
}

export function resetDemoUtilityAssets() {
  if (typeof sessionStorage !== "undefined") {
    sessionStorage.removeItem(assetSessionKey);
    sessionStorage.removeItem(planSessionKey);
    sessionStorage.removeItem("utilities-platform-demo-connectivity-qa-v1");
    sessionStorage.removeItem("utilities-platform-demo-network-trace-v1");
    sessionStorage.removeItem("utilities-platform-demo-network-trace-calibration-v1");
    sessionStorage.removeItem("utilities-platform-demo-proposed-edits-v1");
  }
}
