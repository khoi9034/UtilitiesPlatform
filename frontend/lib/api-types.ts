export type SafeGeometry =
  | { type: "point"; x: number; y: number; spatial_reference_wkid?: number }
  | { type: "polyline"; paths: number[][][]; spatial_reference_wkid?: number; length?: number }
  | Record<string, never>;

export type Issue = {
  issue_id: string;
  issue_fingerprint?: string;
  rule_code: string;
  rule_name?: string;
  category: string;
  finding_class?: string;
  severity: string;
  utility_system: string;
  network_group: string;
  asset_category: string;
  asset_subcategory: string;
  source_layer: string;
  source_asset_id: string;
  source_objectid: string;
  related_asset_id?: string;
  related_objectid?: string;
  description: string;
  why_it_matters?: string;
  recommended_action?: string;
  detection_method?: string;
  threshold_used?: string;
  confidence: string;
  review_status?: string;
  workflow_status?: string;
  disposition?: string;
  reviewer?: string;
  assigned_to?: string;
  review_priority?: string;
  review_notes?: string;
  evidence_notes?: string;
  due_date?: string;
  source_confirmation?: string;
  field_verification_required?: boolean;
  engineering_review_required?: boolean;
  rule_adjustment_candidate?: boolean;
  dependency_explanation?: string;
  possible_missing_dependency?: string;
  first_seen_at?: string;
  latest_seen_at?: string;
  first_seen_run_id?: string;
  latest_seen_run_id?: string;
  occurrence_count?: number;
  run_id: string;
  created_at?: string;
  safe_geometry?: SafeGeometry;
};

export type IssuesResponse = {
  items: Issue[];
  pagination: { total: number; limit: number; offset: number; has_more: boolean };
  message: string;
};

export type CommandCenterResponse = {
  utility_system: string;
  generated_at: string;
  platform_status: string;
  assets: { total: number | null; by_network_group: Record<string, number>; by_asset_category: Record<string, number> };
  qa: { total_findings: number | null; by_severity: Record<string, number>; open_reviews: number | null; reviewed_findings: number | null; review_sample: number | null; high_priority: number | null };
  network: { endpoint_match_rate: number | null; connected_components: number | null; isolated_pipes: number | null; isolated_manholes: number | null; unmatched_endpoints: number | null };
  pipeline: { current_stage: string; stages: { stage: string; state: string }[] };
  dependencies: { available: number; total: number; missing: string[] };
  recent_runs: Record<string, string>[];
  storage: Record<string, unknown>;
  module_status: { label: string; href: string; status: string }[];
};

export type MapFeature = { objectid?: number; asset_id?: string; issue_id?: string; rule_code?: string; category?: string; severity?: string; source_layer?: string; source_objectid?: string; geometry: SafeGeometry };
export type MapData = { pipes: MapFeature[]; manholes: MapFeature[]; issues: MapFeature[] };
export type CalibrationRow = { rule_code: string; total_findings: number; reviewed_findings: number; confirmed_defects: number; false_positives: number; source_limitations: number; confirmation_rate: number; false_positive_rate: number; review_coverage: number; threshold: string; calibration_status: string };
export type ComponentRow = { component_id: string; pipe_count: number; manhole_count: number; total_asset_count: number; approximate_network_length: number; bounding_extent: string; nearest_other_component_distance: number | string; unmatched_endpoints: number; isolated_status: string; likely_classification: string; review_status: string; review_classification: string; reviewer_notes: string };
export type Readiness = { standardization_status?: string; fields_ready_to_map_directly?: string[]; fields_requiring_unit_confirmation?: string[]; fields_requiring_code_translation?: string[]; fields_unavailable?: string[]; fields_blocked?: string[]; dependencies_still_missing?: string[]; records_eligible_for_preview?: number; records_requiring_review?: number; writes_to_standardized_gdb?: boolean; writes_to_curated_gdb?: boolean };
export type MappingRow = { source_layer: string; source_field: string; source_alias?: string; target_field: string; mapping_type?: string; transformation?: string; confidence: string; unit_conversion: string; code_translation: string; data_owner_confirmation_required?: string; approved_to_standardize: string; blocked_reason: string };
export type RuleRow = { rule_code: string; name: string; category: string; severity: string; enabled: boolean; status?: string; issue_count?: number; skip_reason?: string; parameters: Record<string, unknown>; detection_method: string; limitation: string; recommended_action?: string };
export type NetworkResponse = { summary: Record<string, number>; components?: ComponentRow[]; limitations: string[] };
