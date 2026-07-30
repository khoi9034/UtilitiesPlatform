export type MappingCandidate = {
  submission_id: string;
  source_layer_id: string;
  source_layer: string;
  recommended_domain: string;
  source_role: string;
  recommended_asset_class: string;
  recommended_asset_subtype: string;
  domain_confidence: string;
  taxonomy_confidence: string;
  geometry_status: string;
  coordinate_status: string;
  sensitivity_status: string;
  duplicate_status: string;
  owner_status: string;
  jurisdiction_status: string;
  staging_status: string;
  eligibility_state: string;
  plan_id: string;
  plan_status: string;
  blocker_count: number;
  updated_at: string;
};

export type MappingField = {
  mapping_id: string;
  source_field: string;
  source_alias: string;
  sample_safe_type_summary?: string;
  target_field: string;
  transformation_type: string;
  source_unit: string;
  target_unit: string;
  mapping_status: string;
  confidence: string;
  evidence_json: Record<string, unknown>;
  reviewer_type: string;
  human_override: boolean;
  notes: string;
};

export type ValueMapping = {
  value_mapping_id: string;
  source_field: string;
  source_value: string;
  target_field: string;
  target_value: string;
  transformation_type: string;
  confidence: string;
  review_status: string;
  human_override: boolean;
};

export type Eligibility = {
  state: string;
  gates: Record<string, { status: string; reason: string }>;
  active_blockers: string[];
  approved_plan: boolean;
  creation_enabled: false;
  creation_disabled_reason: string;
  staging_approval_required: true;
};

export type MappingReviewPlan = {
  plan_id: string;
  plan_version: number;
  submission_id: string;
  inspection_run_id: string;
  source_layer_id: string;
  utility_domain: string;
  source_role: string;
  target_asset_class: string;
  target_asset_subtype: string;
  mapping_rule_version: string;
  plan_fingerprint: string;
  status: string;
  domain_confidence: string;
  taxonomy_confidence: string;
  geometry_status: string;
  coordinate_status: string;
  sensitivity_status: string;
  duplicate_status: string;
  owner_status: string;
  jurisdiction_status: string;
  staging_status: string;
  preview_record_count: number;
  mapped_field_count: number;
  unmapped_field_count: number;
  warning_count: number;
  blocker_count: number;
  approved_plan: boolean;
  approved_by: string;
  approved_at: string;
  source_fingerprint_status: string;
  warnings: string[];
  blockers: Record<string, string>;
  source_evidence: Record<string, string | number | boolean>;
  recommendation: {
    recommended_domain: string;
    alternative_domains: string[];
    recommended_asset_class: string;
    recommended_asset_subtype: string;
    evidence_categories: string[];
    contradictory_evidence: string[];
    class_candidates: Array<{ asset_class: string; score: number }>;
    geometry_compatibility: Record<string, string>;
  };
  decisions: Record<string, string | boolean>;
  field_mappings: MappingField[];
  value_mappings: ValueMapping[];
  eligibility: Eligibility;
  creation_enabled: false;
  history: Array<Record<string, string | number>>;
  created_at: string;
  updated_at: string;
};

export type MappingPreview = {
  plan_id: string;
  preview_mode: string;
  items: Array<Record<string, unknown>>;
  aggregate: Record<string, unknown>;
  records_read: number;
  records_previewed: number;
  canonical_assets_created: number;
  raw_coordinates_included: false;
  local_paths_included: false;
  source_geometry_modified: false;
  message: string;
};

const sessionKey = "utilities-platform-demo-mapping-review-v1";
const timestamp = "2026-07-30T14:00:00Z";

export function demoMappingPlans(): MappingReviewPlan[] {
  const updates = readSession<Record<string, Partial<MappingReviewPlan>>>(sessionKey, {});
  return basePlans().map((plan) => ({ ...plan, ...updates[plan.plan_id] }));
}

export function demoMappingCandidates(): { items: MappingCandidate[]; summary: Record<string, number>; message: string } {
  const plans = demoMappingPlans();
  const items = plans.map((plan) => ({
    submission_id: plan.submission_id,
    source_layer_id: plan.source_layer_id,
    source_layer: String(plan.source_evidence.source_layer),
    recommended_domain: plan.utility_domain,
    source_role: plan.source_role,
    recommended_asset_class: plan.target_asset_class,
    recommended_asset_subtype: plan.target_asset_subtype,
    domain_confidence: plan.domain_confidence,
    taxonomy_confidence: plan.taxonomy_confidence,
    geometry_status: plan.geometry_status,
    coordinate_status: plan.coordinate_status,
    sensitivity_status: plan.sensitivity_status,
    duplicate_status: plan.duplicate_status,
    owner_status: plan.owner_status,
    jurisdiction_status: plan.jurisdiction_status,
    staging_status: plan.staging_status,
    eligibility_state: plan.eligibility.state,
    plan_id: plan.plan_id,
    plan_status: plan.status,
    blocker_count: plan.blocker_count,
    updated_at: plan.updated_at,
  }));
  return {
    items,
    summary: {
      water_candidate_layers: items.filter((item) => item.recommended_domain === "water").length,
      wastewater_candidate_layers: items.filter((item) => item.recommended_domain === "wastewater").length,
      ambiguous_layers: items.filter((item) => item.recommended_domain === "water_wastewater").length,
      reference_layers: items.filter((item) => item.source_role === "reference_inventory").length,
      ineligible_layers: 0,
      plans_created: items.length,
      plans_review_ready: items.filter((item) => item.plan_status === "review_ready").length,
      plans_blocked: items.filter((item) => item.blocker_count > 1).length,
    },
    message: "Synthetic mapping recommendations loaded without source records or backend requests.",
  };
}

export function demoMappingGet(pathname: string, params: URLSearchParams): unknown {
  if (pathname === "/api/utility-assets/water-wastewater/mapping-candidates") return demoMappingCandidates();
  if (pathname === "/api/utility-assets/mapping-plans") {
    const expected = params.get("utility_domain");
    const items = demoMappingPlans().filter((plan) => !expected || plan.utility_domain === expected);
    return { items };
  }
  if (pathname.endsWith("/water-wastewater/mapping-candidates")) {
    const submissionId = decodeURIComponent(pathname.split("/")[4] ?? "");
    const all = demoMappingCandidates();
    return { ...all, items: all.items.filter((item) => item.submission_id === submissionId) };
  }
  const plan = planForPath(pathname);
  if (!plan) throw new Error("Synthetic mapping plan not found.");
  if (pathname.endsWith("/fields")) return { plan_id: plan.plan_id, items: plan.field_mappings };
  if (pathname.endsWith("/values")) return { plan_id: plan.plan_id, items: plan.value_mappings };
  if (pathname.endsWith("/preview")) return demoPreview(plan);
  if (pathname.endsWith("/canonicalization-eligibility")) return plan.eligibility;
  if (pathname.endsWith("/safe-summary")) return safeSummary(plan);
  if (pathname.endsWith("/mapping-recommendations")) {
    return {
      submission_id: plan.submission_id,
      source_layer_id: plan.source_layer_id,
      source_evidence: plan.source_evidence,
      recommendation: plan.recommendation,
      field_recommendations: plan.field_mappings,
      source_geometry_modified: false,
    };
  }
  if (pathname.endsWith("/mapping-plan")) return plan;
  throw new Error(`No synthetic mapping data for ${pathname}`);
}

export function demoMappingPost(pathname: string, body: Record<string, unknown>): unknown {
  const plan = planForPath(pathname);
  if (!plan) throw new Error("Synthetic mapping plan not found.");
  if (pathname.endsWith("/preview")) return demoPreview(plan);
  if (pathname.endsWith("/new-version")) {
    return updateDemoMappingPlan(plan.plan_id, {
      plan_version: plan.plan_version + 1,
      status: "draft",
      approved_plan: false,
      history: [...plan.history, history("plan_version_created", String(body.actor || "Demo Reviewer"))],
    });
  }
  if (pathname.endsWith("/recalculate")) {
    const decisions = Object.fromEntries(
      Object.entries(body).filter((entry): entry is [string, string | boolean] =>
        typeof entry[1] === "string" || typeof entry[1] === "boolean",
      ),
    );
    return updateDemoMappingPlan(plan.plan_id, {
      decisions: { ...plan.decisions, ...decisions },
      status: plan.status === "approved_plan" ? "mapping_review_required" : plan.status,
      approved_plan: false,
      history: [...plan.history, history("recommendations_recalculated", String(body.actor || "Demo Reviewer"))],
    });
  }
  const action = pathname.split("/").pop() ?? "";
  if (action === "approve") {
    const unresolved = Object.entries(plan.blockers).filter(([key, value]) => key !== "staging_blocker" && value);
    if (unresolved.length) throw new Error("Resolve non-staging blockers before approving this synthetic plan.");
    return updateDemoMappingPlan(plan.plan_id, {
      status: "approved_plan",
      approved_plan: true,
      approved_by: String(body.approved_by || "Demo Reviewer"),
      approved_at: timestamp,
      eligibility: { ...plan.eligibility, state: "approved_plan_staging_blocked", approved_plan: true },
      history: [...plan.history, history("plan_approve", String(body.approved_by || "Demo Reviewer"))],
    });
  }
  const statuses: Record<string, string> = {
    submit: "under_review", "start-review": "under_review",
    "request-revision": "mapping_review_required", defer: "deferred", reject: "rejected",
  };
  if (statuses[action]) {
    return updateDemoMappingPlan(plan.plan_id, {
      status: statuses[action],
      approved_plan: false,
      history: [...plan.history, history(`plan_${action}`, String(body.actor || "Demo Reviewer"))],
    });
  }
  if (pathname.endsWith("/mapping-plan")) return plan;
  throw new Error(`No synthetic mapping action for ${pathname}`);
}

export function demoMappingPut(pathname: string, body: Record<string, unknown>): unknown {
  const plan = planForPath(pathname);
  if (!plan) throw new Error("Synthetic mapping plan not found.");
  if (pathname.endsWith("/fields")) {
    const mappings = (body.mappings as MappingField[] | undefined) ?? plan.field_mappings;
    const mapped = mappings.filter((item) => item.mapping_status === "accepted" && item.transformation_type !== "unmapped").length;
    return updateDemoMappingPlan(plan.plan_id, {
      field_mappings: mappings,
      mapped_field_count: mapped,
      unmapped_field_count: mappings.filter((item) => item.transformation_type === "unmapped").length,
      status: "mapping_review_required",
      approved_plan: false,
      history: [...plan.history, history("field_mappings_updated", String(body.actor || "Demo Reviewer"))],
    });
  }
  if (pathname.endsWith("/values")) {
    const mappings = (body.mappings as ValueMapping[] | undefined) ?? plan.value_mappings;
    return updateDemoMappingPlan(plan.plan_id, {
      value_mappings: mappings,
      status: "mapping_review_required",
      approved_plan: false,
      history: [...plan.history, history("value_mappings_updated", String(body.actor || "Demo Reviewer"))],
    });
  }
  throw new Error(`No synthetic mapping update for ${pathname}`);
}

export function updateDemoMappingPlan(planId: string, changes: Partial<MappingReviewPlan>): MappingReviewPlan {
  const updates = readSession<Record<string, Partial<MappingReviewPlan>>>(sessionKey, {});
  updates[planId] = { ...updates[planId], ...changes, updated_at: timestamp };
  writeSession(sessionKey, updates);
  const updated = demoMappingPlans().find((plan) => plan.plan_id === planId);
  if (!updated) throw new Error("Synthetic mapping plan not found.");
  return updated;
}

export function resetDemoMappingReview() {
  if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(sessionKey);
}

function basePlans(): MappingReviewPlan[] {
  return [
    makePlan("DEMO-WATER-MAIN-PLAN", "water", "distribution_main", "operational_inventory"),
    makePlan("DEMO-WATER-VALVE-PLAN", "water", "isolation_valve", "operational_inventory", {
      owner_blocker: "Synthetic owner confirmation is required.",
    }),
    makePlan("DEMO-WATER-HYDRANT-PLAN", "water", "hydrant", "operational_inventory", {
      coordinate_blocker: "Synthetic coordinate evidence requires review.",
    }),
    makePlan("DEMO-WATER-SERVICE-PLAN", "water", "service_line", "operational_inventory", {
      field_mapping_blocker: "Synthetic endpoint field remains unmapped.",
    }, "UNMAPPED_ENDPOINT"),
    makePlan("DEMO-WW-GRAVITY-PLAN", "wastewater", "gravity_main", "operational_inventory", {
      value_mapping_blocker: "Synthetic invert unit requires human confirmation.",
    }, "INVERT_UNIT"),
    makePlan("DEMO-WW-FORCE-PLAN", "wastewater", "force_main", "operational_inventory", {
      taxonomy_blocker: "Synthetic evidence does not conclusively distinguish gravity from force main.",
    }),
    makePlan("DEMO-WW-MANHOLE-PLAN", "wastewater", "manhole", "operational_inventory", {
      jurisdiction_blocker: "Synthetic jurisdiction confirmation is required.",
    }),
    makePlan("DEMO-WW-LIFT-PLAN", "wastewater", "lift_station", "facility_inventory"),
  ];
}

function makePlan(
  planId: string,
  domain: "water" | "wastewater",
  assetClass: string,
  sourceRole: string,
  extraBlockers: Record<string, string> = {},
  extraField = "",
): MappingReviewPlan {
  const layerId = `demo-${planId.toLowerCase()}`;
  const blockers = {
    domain_blocker: "", taxonomy_blocker: "", geometry_blocker: "",
    coordinate_blocker: "", sensitivity_blocker: "", duplicate_blocker: "",
    owner_blocker: "", jurisdiction_blocker: "", source_role_blocker: "",
    identifier_blocker: "", field_mapping_blocker: "", value_mapping_blocker: "",
    staging_blocker: "Final staging approval is required.", stale_source_blocker: "",
    ...extraBlockers,
  };
  const active = Object.entries(blockers).filter(([, value]) => value).map(([key]) => key);
  const fields: MappingField[] = [
    mapping(planId, "SOURCE_ID", "Source ID", "source_asset_identifier", "normalized_identifier"),
    mapping(planId, "MATERIAL", "Material", "material", "domain_mapping"),
    mapping(planId, "STATUS", "Status", "lifecycle_status", "lifecycle_mapping"),
    mapping(planId, "TYPE", "Type", "asset_subtype", "subtype_mapping"),
  ];
  if (extraField) fields.push({
    ...mapping(planId, extraField, extraField.replaceAll("_", " "), "", "unmapped"),
    mapping_status: "unmapped", confidence: "unavailable",
    notes: "Synthetic field intentionally left unmapped for review.",
  });
  const classCandidates = assetClass === "force_main"
    ? [{ asset_class: "force_main", score: 0.55 }, { asset_class: "gravity_main", score: 0.5 }]
    : [{ asset_class: assetClass, score: 0.95 }];
  const state = active.length === 1 ? "review_ready" : "mapping_blocked";
  return {
    plan_id: planId,
    plan_version: 1,
    submission_id: `DEMO-${domain.toUpperCase()}-MAPPING`,
    inspection_run_id: `demo-inspection-${domain}`,
    source_layer_id: layerId,
    utility_domain: domain,
    source_role: sourceRole,
    target_asset_class: assetClass,
    target_asset_subtype: "synthetic_v1",
    mapping_rule_version: "water-wastewater-mapping-review-v1",
    plan_fingerprint: `synthetic-${planId.toLowerCase()}-v1`,
    status: active.length === 1 ? "review_ready" : "mapping_review_required",
    domain_confidence: "high",
    taxonomy_confidence: extraBlockers.taxonomy_blocker ? "low" : "high",
    geometry_status: "compatible",
    coordinate_status: extraBlockers.coordinate_blocker ? "needs_review" : "confirmed",
    sensitivity_status: "confirmed",
    duplicate_status: "no_duplicate_candidate",
    owner_status: extraBlockers.owner_blocker ? "provisional" : "confirmed",
    jurisdiction_status: extraBlockers.jurisdiction_blocker ? "provisional" : "confirmed",
    staging_status: "not_approved",
    preview_record_count: 3,
    mapped_field_count: 4,
    unmapped_field_count: extraField ? 1 : 0,
    warning_count: active.length - 1,
    blocker_count: active.length,
    approved_plan: false,
    approved_by: "",
    approved_at: "",
    source_fingerprint_status: "current",
    warnings: Object.values(extraBlockers),
    blockers,
    source_evidence: {
      source_layer: `Synthetic ${assetClass.replaceAll("_", " ")} layer`,
      source_layer_id: layerId,
      geometry_type: ["distribution_main", "service_line", "gravity_main", "force_main"].includes(assetClass) ? "polyline" : "point",
      record_count: 12,
      field_count: fields.length,
      domain_count: 2,
      subtypes_available: true,
      lifecycle_signals: true,
      material_signals: true,
      diameter_signals: ["distribution_main", "service_line", "gravity_main", "force_main"].includes(assetClass),
      elevation_signals: domain === "wastewater",
      related_layers_available: true,
      source_review_status: "reviewed",
      sensitivity_status: "confirmed",
      coordinate_status: extraBlockers.coordinate_blocker ? "needs_review" : "confirmed",
      local_paths_included: false,
      raw_coordinates_included: false,
    },
    recommendation: {
      recommended_domain: domain,
      alternative_domains: [],
      recommended_asset_class: assetClass,
      recommended_asset_subtype: "synthetic_v1",
      evidence_categories: ["name", "alias", "geometry", "field_schema", "domains", "subtypes"],
      contradictory_evidence: Object.values(extraBlockers),
      class_candidates: classCandidates,
      geometry_compatibility: { status: "compatible", source_geometry: "synthetic_summary", target_geometry: "compatible" },
    },
    decisions: {
      reviewer_notes: "",
      owner_candidate: "Synthetic Utility",
      jurisdiction_candidate: "Synthetic Service Area",
      source_role_confirmed: true,
      domain_confirmed: !extraBlockers.taxonomy_blocker,
      taxonomy_confirmed: !extraBlockers.taxonomy_blocker,
    },
    field_mappings: fields,
    value_mappings: [
      {
        value_mapping_id: `${planId}-material-pvc`,
        source_field: "MATERIAL", source_value: "PVC", target_field: "material",
        target_value: "pvc", transformation_type: "domain_mapping",
        confidence: "high", review_status: "accepted", human_override: true,
      },
      {
        value_mapping_id: `${planId}-status-active`,
        source_field: "STATUS", source_value: "ACTIVE", target_field: "lifecycle_status",
        target_value: "active", transformation_type: "lifecycle_mapping",
        confidence: "high", review_status: "accepted", human_override: true,
      },
    ],
    eligibility: {
      state,
      gates: Object.fromEntries(Object.entries(blockers).map(([key, value]) => [
        key.replace("_blocker", ""),
        { status: value ? "blocked" : "passed", reason: value || "Synthetic gate satisfied." },
      ])),
      active_blockers: active,
      approved_plan: false,
      creation_enabled: false,
      creation_disabled_reason: "Canonical asset creation is disabled pending final staging approval.",
      staging_approval_required: true,
    },
    creation_enabled: false,
    history: [history("plan_created", "Demo System")],
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function mapping(
  planId: string, sourceField: string, alias: string,
  targetField: string, transformation: string,
): MappingField {
  return {
    mapping_id: `${planId}-${sourceField.toLowerCase()}`,
    source_field: sourceField,
    source_alias: alias,
    sample_safe_type_summary: sourceField === "DIAMETER" ? "numeric" : "coded text",
    target_field: targetField,
    transformation_type: transformation,
    source_unit: sourceField === "DIAMETER" ? "unknown" : "",
    target_unit: sourceField === "DIAMETER" ? "unknown" : "",
    mapping_status: targetField ? "accepted" : "unmapped",
    confidence: targetField ? "high" : "unavailable",
    evidence_json: { categories: ["synthetic_field_name", "synthetic_alias"] },
    reviewer_type: "human",
    human_override: false,
    notes: targetField ? "Synthetic demonstration mapping." : "",
  };
}

function demoPreview(plan: MappingReviewPlan): MappingPreview {
  const items = Array.from({ length: 3 }, (_, index) => ({
    preview_id: `${plan.plan_id}-preview-${index + 1}`,
    proposed_canonical_identifier: `SYNTHETIC-${plan.utility_domain.toUpperCase()}-${plan.target_asset_class.toUpperCase()}-${index + 1}`,
    label: "Proposed canonical identifier - not created.",
    canonical_class: plan.target_asset_class,
    mapped_asset_identifier: `SYNTHETIC-SOURCE-${index + 1}`,
    selected_safe_mapped_fields: { material: "pvc", lifecycle_status: "active" },
    mapping_confidence: "high",
    warnings: plan.warnings,
    blockers: plan.eligibility.active_blockers,
    lineage: { plan_id: plan.plan_id, mapping_version: plan.mapping_rule_version },
    preview_only: true,
  }));
  return {
    plan_id: plan.plan_id,
    preview_mode: "synthetic_records",
    items,
    aggregate: { source_record_count: 12, records_previewed: items.length },
    records_read: items.length,
    records_previewed: items.length,
    canonical_assets_created: 0,
    raw_coordinates_included: false,
    local_paths_included: false,
    source_geometry_modified: false,
    message: "Preview only - no canonical asset has been created.",
  };
}

function planForPath(pathname: string): MappingReviewPlan | undefined {
  const parts = pathname.split("/");
  const submissionIndex = parts.indexOf("submissions");
  const layerIndex = parts.indexOf("layers");
  if (submissionIndex < 0 || layerIndex < 0) return undefined;
  const submissionId = decodeURIComponent(parts[submissionIndex + 1] ?? "");
  const layerId = decodeURIComponent(parts[layerIndex + 1] ?? "");
  return demoMappingPlans().find((plan) => plan.submission_id === submissionId && plan.source_layer_id === layerId);
}

function safeSummary(plan: MappingReviewPlan) {
  return {
    plan_id: plan.plan_id,
    plan_version: plan.plan_version,
    utility_domain: plan.utility_domain,
    source_role: plan.source_role,
    target_asset_class: plan.target_asset_class,
    status: plan.status,
    mapped_field_count: plan.mapped_field_count,
    unmapped_field_count: plan.unmapped_field_count,
    warning_count: plan.warning_count,
    blocker_count: plan.blocker_count,
    approved_plan: plan.approved_plan,
    eligibility: plan.eligibility,
    creation_enabled: false,
    updated_at: plan.updated_at,
  };
}

function history(action: string, actor: string): Record<string, string | number> {
  return {
    history_id: `demo-history-${action}-${actor.replaceAll(" ", "-").toLowerCase()}`,
    plan_version: 1,
    action,
    actor_type: actor === "Demo System" ? "system" : "human",
    actor,
    reason: "Synthetic demonstration event.",
    created_at: timestamp,
  };
}

function readSession<T>(key: string, fallback: T): T {
  if (typeof sessionStorage === "undefined") return fallback;
  try {
    return JSON.parse(sessionStorage.getItem(key) ?? "") as T;
  } catch {
    return fallback;
  }
}

function writeSession(key: string, value: unknown) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(key, JSON.stringify(value));
}
