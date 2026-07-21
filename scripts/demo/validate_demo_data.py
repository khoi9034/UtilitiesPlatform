from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DENIED_TEXT = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"C:\\",
        r"C:/",
        r"\.sde\b",
        r"\.(shp|shx|dbf|prj|cpg)\b",
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        r"(password|secret|access[_-]?token|api[_-]?key|connection[_-]?string)\s*[:=]",
        r"Utility_Staging|Wastewater_QA|UtilitiesPlatform_Data",
    ]
]

DENIED_KEYS = {
    "source_path",
    "connection_string",
    "password",
    "secret",
    "token",
    "access_token",
    "api_key",
    "email",
    "globalid",
    "objectid_1",
    "wsacc_id",
    "u_s_node",
    "d_s_node",
    "src_ent",
    "srcent",
}

ALLOWED_KEYS = {
    "access_structure",
    "active",
    "applicable_layer",
    "approved_for_analysis",
    "approved_for_export",
    "approved_for_public_use",
    "approved_to_stage",
    "approved_to_standardize",
    "asset_category",
    "asset_id",
    "asset_subcategory",
    "assets",
    "assigned_to",
    "available",
    "average_endpoint_to_manhole_distance",
    "blocked_reason",
    "by_asset_category",
    "by_network_group",
    "by_severity",
    "by_utility_system",
    "calibration_status",
    "category",
    "category_metrics",
    "classification_confidence",
    "code_translation",
    "command-center.json",
    "complete",
    "completed_at",
    "confidence",
    "confirmed_defects",
    "connected_components",
    "coordinate_system",
    "created_at",
    "current_severity",
    "current_stage",
    "currently_present",
    "curated",
    "data-health-summary.json",
    "data_classification",
    "data_owner_confirmation_required",
    "dataset_id",
    "dataset_name",
    "datasets",
    "dependencies",
    "dependencies_still_missing",
    "description",
    "detail",
    "detection_method",
    "disclaimer",
    "disposition",
    "effect",
    "enabled",
    "endpoint_match_rate",
    "engineering_review_required",
    "evidence_notes",
    "export_folder_available",
    "false_positive_rate",
    "false_positives",
    "field_verification_required",
    "fields_blocked",
    "fields_ready_to_map_directly",
    "fields_requiring_code_translation",
    "fields_requiring_unit_confirmation",
    "fields_unavailable",
    "files",
    "finding_class",
    "first_seen_at",
    "first_seen_run_id",
    "format",
    "generated_at",
    "geodatabases",
    "geometry",
    "geometry_type",
    "gravity_network",
    "high",
    "high_priority",
    "input_feature_counts",
    "issue_count",
    "issue_fingerprint",
    "issue_id",
    "issues",
    "issues_by_category",
    "issues_by_severity",
    "item_count",
    "items",
    "label",
    "last_processed",
    "latest_seen_at",
    "latest_seen_run_id",
    "layer_count",
    "layer_name",
    "length",
    "limitation",
    "limitations",
    "likely_classification",
    "likely_classifications",
    "likely_defects",
    "live_system_connected",
    "low",
    "manhole_count",
    "manholes",
    "map.json",
    "master",
    "master_root_available",
    "matched_pipe_endpoints",
    "maximum_endpoint_to_manhole_distance",
    "medium",
    "message",
    "metadata",
    "method",
    "missing",
    "mode",
    "name",
    "nearest_other_component_distance",
    "network",
    "network.json",
    "network_group",
    "not_started",
    "notes",
    "objectid",
    "open_reviews",
    "ordering",
    "output_workspace",
    "parameters",
    "pagination",
    "paths",
    "pipe",
    "pipe_count",
    "pipes",
    "platform_status",
    "possible_missing_dependency",
    "primary_network",
    "process_name",
    "proposed_severity",
    "proposed_threshold",
    "public_demo",
    "qa",
    "raw",
    "raw_folder_available",
    "reason",
    "recommended_action",
    "recommended_classification",
    "record_count",
    "record_totals_by_system",
    "records",
    "records_eligible_for_preview",
    "records_read",
    "records_requiring_review",
    "records_written",
    "related_asset_id",
    "related_objectid",
    "required_semantic_fields",
    "review-queue.json",
    "review_coverage",
    "review_notes",
    "review_priority",
    "review_status",
    "review_classification",
    "review_required",
    "review_required_layers",
    "review_sample",
    "reviewed_findings",
    "reviewer",
    "reviewer_comments",
    "reviewer_notes",
    "rule_adjustment_candidate",
    "rule_code",
    "rule_name",
    "rule_version",
    "rules",
    "rules.json",
    "run_id",
    "run_status",
    "safe_geometry",
    "sanitized_and_synthetic",
    "severity",
    "source_asset_id",
    "source_format",
    "source_layer",
    "source_objectid",
    "source_name",
    "spatial_reference",
    "spatial_reference_wkid",
    "stage",
    "stage-summary.json",
    "stage-items.json",
    "staged_input_layers",
    "stages",
    "staging",
    "staging_folder_available",
    "standardization",
    "standardization.json",
    "standardization_status",
    "standardized",
    "standardized_folder_available",
    "started_at",
    "state",
    "status",
    "storage",
    "structures",
    "subcategory",
    "supported_modules",
    "summary",
    "target_field",
    "target_layer_name",
    "threshold",
    "threshold_used",
    "total",
    "total_asset_count",
    "total_connected_components",
    "total_findings",
    "total_issues",
    "transformation",
    "trust-pipeline.json",
    "type",
    "unmatched_endpoints",
    "unmatched_pipe_endpoints",
    "unit_conversion",
    "utility_system",
    "value",
    "version",
    "warnings",
    "why_it_matters",
    "workflow_status",
    "writes_persisted",
    "writes_to_curated_gdb",
    "writes_to_standardized_gdb",
    "x",
    "y",
}

ALLOWED_KEYS.update(
    {
        "allowlist",
        "approximate_network_length",
        "attributes",
        "bounding_extent",
        "catalog_available",
        "component_id",
        "components",
        "confirmation_rate",
        "configured",
        "connected_component_count",
        "connectivity",
        "curated_folder_available",
        "demo_snapshot_loaded",
        "denominator",
        "dependency_explanation",
        "endpoint_tolerance",
        "expected_conditions",
        "has_more",
        "href",
        "identity",
        "input_layer",
        "isolated_manholes",
        "isolated_pipes",
        "isolated_status",
        "largest_component_size",
        "layers",
        "lineage",
        "limit",
        "mapping_type",
        "mappings",
        "module_status",
        "numerator",
        "occurrence_count",
        "offset",
        "output",
        "pipeline",
        "readiness",
        "recent_runs",
        "recommendation",
        "recommended_staging_layers",
        "review_classification",
        "review_required_layers",
        "reviewer_notes",
        "reviewed_at",
        "rows",
        "runs",
        "seed",
        "sensitivity_level",
        "skip_reason",
        "skipped_checks",
        "source",
        "source_alias",
        "source_field",
        "source_layer_name",
        "source_limitations",
        "sources_discovered",
        "summary",
        "unresolved_findings",
        "wastewater",
        "wastewater_gravity_main",
        "wastewater_manhole",
    }
)

ALLOWED_KEYS.update(
    {
        "accepted_formats",
        "actor",
        "arcpy_available",
        "authorization_confirmed",
        "blockers",
        "cad",
        "classification_status",
        "compressed_size_bytes",
        "current_status",
        "demo_sample",
        "demo-layer-churches",
        "demo-layer-town-a-force-mains",
        "demo-layer-waterline",
        "demo-upl-20260720-a1b2c3d4",
        "duplicate_of_submission_id",
        "event_id",
        "event_type",
        "extension",
        "extensions",
        "file_size_bytes",
        "file_geodatabase",
        "geopackage",
        "inventory_completed_at",
        "inventory_started_at",
        "inventory_status",
        "inventory_support",
        "intake-capabilities.json",
        "intake-events.json",
        "intake-submissions.json",
        "loose_shapefile",
        "maximum_upload_bytes",
        "metadata_only",
        "mime_type",
        "nested_archives",
        "new_status",
        "next_required_action",
        "original_filename",
        "packaging",
        "packaging_requirements",
        "password_protected_archives",
        "pdf",
        "previous_status",
        "project_id",
        "raw_registered_at",
        "relative_role",
        "safe_filename",
        "sde_connections",
        "sha256_prefix",
        "shapefile",
        "size_bytes",
        "source_description",
        "source_owner",
        "source_type",
        "staging_status",
        "spreadsheet",
        "submission_id",
        "submission_name",
        "synthetic_package",
        "updated_at",
        "upload_enabled",
        "validation_status",
    }
)

ALLOWED_KEYS.update(
    {
        "angular_unit",
        "approval_status",
        "approved_for_staging",
        "arcpy_full_schema_supported",
        "attachment_count",
        "attachment_status",
        "authoritative_layer_id",
        "blocker",
        "candidate_id",
        "child_layer_count",
        "classification_candidates",
        "comparison_type",
        "container_id",
        "container_name",
        "coordinate_status",
        "domain_count",
        "domain_names",
        "duplicate-groups.json",
        "duplicate_group_id",
        "duplicate_status",
        "editor_tracking_status",
        "evidence",
        "fallback",
        "feature_dataset",
        "field_count",
        "has_m",
        "has_z",
        "inspected_at",
        "inspection_run_id",
        "inspection_status",
        "layer-classification-candidates.json",
        "layer_id",
        "lifecycle_representation",
        "linear_unit",
        "likely_date_fields",
        "likely_dimension_fields",
        "likely_id_fields",
        "likely_owner_fields",
        "likely_status_fields",
        "member_role",
        "members",
        "mixed",
        "object_type",
        "operational_role",
        "owner_or_jurisdiction",
        "package_utility_system",
        "projection_required",
        "proposed_or_existing_signal",
        "proposed_target_name",
        "relationship_count",
        "rank",
        "routing_state",
        "schema_support",
        "score",
        "sensitivity_status",
        "similarity_score",
        "source-inspection-status.json",
        "source_inspection_adapters",
        "source_layer_alias",
        "source_owner_prefix",
        "source_schema",
        "source_spatial_reference",
        "spatial_reference_count",
        "spatial_reference_name",
        "staging-plan.json",
        "staging_plan_item_id",
        "staged_at",
        "staged_output_name",
        "submission-layers.json",
        "subtype_count",
        "target_asset_category",
        "target_asset_subcategory",
        "target_network_group",
        "target_owner_or_jurisdiction",
        "target_spatial_reference",
        "target_utility_system",
        "table_count",
    }
)


def validate_demo_root(demo_root: Path, protected_extent: tuple[float, float, float, float] | None = None) -> list[str]:
    errors: list[str] = []
    if not demo_root.exists():
        return [f"Demo root does not exist: {demo_root}"]
    for path in sorted(demo_root.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        errors.extend(f"{path.name}: denied text pattern {pattern.pattern}" for pattern in DENIED_TEXT if pattern.search(text))
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON: {exc}")
            continue
        errors.extend(f"{path.name}: field is not allowlisted: {key}" for key in sorted(collect_keys(data) - ALLOWED_KEYS))
        errors.extend(f"{path.name}: denied field name: {key}" for key in sorted(collect_keys(data) & DENIED_KEYS))
        if protected_extent:
            for x, y in collect_points(data):
                if inside_extent(x, y, protected_extent):
                    errors.append(f"{path.name}: coordinate falls inside protected extent: {x},{y}")
    errors.extend(validate_map_counts(demo_root / "map.json"))
    return errors


def collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key).lower() for key in value} | set().union(*(collect_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(collect_keys(item) for item in value)) if value else set()
    return set()


def collect_points(value: Any) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if isinstance(value, dict):
        if isinstance(value.get("x"), (int, float)) and isinstance(value.get("y"), (int, float)):
            points.append((float(value["x"]), float(value["y"])))
        for path in value.get("paths", []):
            points.extend((float(x), float(y)) for x, y in path if isinstance(x, (int, float)) and isinstance(y, (int, float)))
        for item in value.values():
            points.extend(collect_points(item))
    elif isinstance(value, list):
        for item in value:
            points.extend(collect_points(item))
    return points


def inside_extent(x: float, y: float, extent: tuple[float, float, float, float]) -> bool:
    min_x, min_y, max_x, max_y = extent
    return min_x <= x <= max_x and min_y <= y <= max_y


def validate_map_counts(map_path: Path) -> list[str]:
    if not map_path.exists():
        return ["map.json is missing"]
    data = json.loads(map_path.read_text(encoding="utf-8"))
    pipe_count = len(data.get("pipes", []))
    manhole_count = len(data.get("manholes", []))
    errors = []
    if not 40 <= pipe_count <= 80:
        errors.append(f"map.json: expected 40-80 synthetic pipes, found {pipe_count}")
    if not 35 <= manhole_count <= 70:
        errors.append(f"map.json: expected 35-70 synthetic manholes, found {manhole_count}")
    return errors


def parse_extent(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--protected-extent must be minx,miny,maxx,maxy")
    return parts[0], parts[1], parts[2], parts[3]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate committed Utilities Platform portfolio demo data.")
    parser.add_argument("--demo-root", type=Path, default=Path("frontend/demo-data"))
    parser.add_argument("--protected-extent", help="Optional minx,miny,maxx,maxy extent that demo coordinates must avoid.")
    args = parser.parse_args()
    errors = validate_demo_root(args.demo_root, parse_extent(args.protected_extent))
    if errors:
        print("Demo data validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Demo data validation passed: {args.demo_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
