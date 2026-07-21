from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceContainer:
    submission_id: str
    container_id: str
    container_name: str
    source_format: str
    source_type: str
    package_utility_system: str
    source_owner: str
    project_id: str
    sensitivity_level: str
    inspection_status: str
    spatial_reference_count: int = 0
    child_layer_count: int = 0
    table_count: int = 0
    relationship_count: int = 0
    domain_count: int = 0
    subtype_count: int = 0
    attachment_count: int = 0
    inspection_run_id: str = ""
    inspected_at: str = ""
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceLayer:
    layer_id: str
    submission_id: str
    container_id: str
    source_layer_name: str
    source_layer_alias: str = ""
    source_schema: str = ""
    source_owner_prefix: str = ""
    feature_dataset: str = ""
    object_type: str = "feature_class"
    geometry_type: str = "unknown"
    record_count: int | None = None
    spatial_reference_name: str = "unknown"
    spatial_reference_wkid: int | None = None
    linear_unit: str = ""
    angular_unit: str = ""
    has_z: bool = False
    has_m: bool = False
    extent_summary: dict[str, Any] = field(default_factory=dict)
    field_count: int = 0
    field_profile: list[dict[str, Any]] = field(default_factory=list)
    domain_profile: dict[str, Any] = field(default_factory=dict)
    subtype_profile: dict[str, Any] = field(default_factory=dict)
    relationship_profile: list[dict[str, Any]] = field(default_factory=list)
    likely_id_fields: list[str] = field(default_factory=list)
    likely_status_fields: list[str] = field(default_factory=list)
    likely_date_fields: list[str] = field(default_factory=list)
    likely_dimension_fields: list[str] = field(default_factory=list)
    likely_owner_fields: list[str] = field(default_factory=list)
    domain_names: list[str] = field(default_factory=list)
    subtype_summary: str = ""
    relationship_summary: str = ""
    attachment_status: str = "unknown"
    editor_tracking_status: str = "unknown"
    proposed_or_existing_signal: str = "unknown"
    operational_role: str = "unknown"
    lifecycle_representation: str = "unknown"
    owner_or_jurisdiction: str = "unknown"
    classification_status: str = "review_required"
    duplicate_status: str = "not_evaluated"
    coordinate_status: str = "unknown_spatial_reference"
    sensitivity_status: str = "needs_sensitivity_review"
    staging_status: str = "not_approved"
    routing_state: str = "needs_taxonomy_review"
    latest_review_status: str = ""
    latest_reviewer: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationCandidate:
    candidate_id: str
    layer_id: str
    rank: int
    utility_system: str
    network_group: str
    asset_category: str
    asset_subcategory: str
    operational_role: str
    lifecycle_representation: str
    owner_or_jurisdiction: str
    confidence: str
    score: float
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rule_version: str = ""
    rule_code: str = ""
    created_at: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DuplicateGroup:
    duplicate_group_id: str
    submission_id: str
    comparison_type: str
    confidence: str
    status: str
    recommended_action: str
    authoritative_layer_id: str = ""
    members: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StagingPlanItem:
    staging_plan_item_id: str
    submission_id: str
    layer_id: str
    proposed_target_name: str
    target_utility_system: str
    target_network_group: str
    target_asset_category: str
    target_asset_subcategory: str
    target_owner_or_jurisdiction: str
    source_spatial_reference: str
    target_spatial_reference: str
    projection_required: bool
    approved_for_staging: bool
    approval_status: str
    blocker: str
    reviewer: str = ""
    reviewed_at: str = ""
    staged_output_name: str = ""
    staged_at: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)
