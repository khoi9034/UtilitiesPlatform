import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.utility_assets.mapping_review import (
    geometry_compatibility,
    normalize_material,
    normalize_status,
    parse_diameter,
    proposed_preview_id,
    recommend_layer,
    service as mapping_review,
)
from app.services.utility_assets.service import UtilityAssetError, UtilityAssetService

client = TestClient(app)


def _seed_reviewed_layers(root: Path) -> None:
    with mapping_review.connect() as connection:
        connection.execute(
            """INSERT INTO intake_submissions
            (submission_id, submission_name, original_filename, stored_filename, utility_system,
             source_type, source_format, source_owner, source_description, sensitivity_level,
             authorization_confirmed, file_size_bytes, sha256, current_status, current_stage,
             inventory_status, classification_status, staging_status, created_at, updated_at)
            VALUES ('TEST-MAPPING-001', 'Synthetic mapping source', 'synthetic.zip', 'synthetic.zip',
                    'mixed', 'synthetic', 'zip', 'Synthetic Owner', 'Synthetic records only',
                    'restricted', 1, 10, 'synthetic-sha-v1', 'reviewed', 'raw', 'complete',
                    'reviewed', 'not_approved', '2026-01-01', '2026-01-01')"""
        )
        connection.execute(
            """INSERT INTO inspection_runs
            (inspection_run_id, submission_id, status, started_at, completed_at,
             retryable, child_layer_count, table_count)
            VALUES ('inspection-1', 'TEST-MAPPING-001', 'completed', '2026-01-01',
                    '2026-01-01', 0, 3, 0)"""
        )
        _seed_layer(
            connection, "water-layer", "water", "distribution_main", "polyline",
            "network_asset", ["SOURCE_ID", "DIAMETER", "MATERIAL", "STATUS"],
        )
        _seed_layer(
            connection, "wastewater-layer", "wastewater", "gravity_main", "polyline",
            "network_asset", ["SOURCE_ID", "FROM_NODE", "TO_NODE", "INVERTIN", "INVERTOUT"],
        )
        _seed_layer(
            connection, "ambiguous-layer", "review_required", "unknown", "polyline",
            "unknown", ["SOURCE_ID", "SIZE"],
        )
        connection.commit()


def _seed_layer(
    connection, layer_id: str, domain: str, subcategory: str,
    geometry: str, role: str, fields: list[str],
) -> None:
    profiles = [
        {
            "name": field, "alias": field.replace("_", " ").title(), "type": "String",
            "length": 50, "nullable": True, "required": False, "domain": "",
        }
        for field in fields
    ]
    source_name = "Synthetic Sewer Main" if domain == "review_required" else f"Synthetic {subcategory}"
    connection.execute(
        """INSERT INTO inspected_layers
        (layer_id, submission_id, container_id, source_layer_name, source_layer_alias,
         object_type, geometry_type, record_count, spatial_reference_name,
         spatial_reference_wkid, field_count, field_profile_json, domain_profile_json,
         subtype_profile_json, relationship_profile_json, likely_id_fields_json,
         likely_status_fields_json, likely_date_fields_json, likely_dimension_fields_json,
         likely_owner_fields_json, operational_role, classification_status,
         duplicate_status, coordinate_status, sensitivity_status, staging_status,
         latest_review_status, created_at, updated_at)
        VALUES (?, 'TEST-MAPPING-001', 'container-1', ?, ?, 'feature_class', ?, 4,
                'Synthetic projected coordinate system', 9999, ?, ?, '{}', '{}', '[]',
                '["SOURCE_ID"]', '["STATUS"]', '[]', '["DIAMETER"]', '[]', ?,
                'reviewed', 'no_duplicate_candidate', 'coordinate_ready',
                'inherited_from_package', 'not_approved', 'in_review',
                '2026-01-01', '2026-01-01')""",
        (
            layer_id, source_name, source_name, geometry, len(profiles),
            json.dumps(profiles), role,
        ),
    )
    connection.execute(
        """INSERT INTO layer_classification_candidates
        (candidate_id, layer_id, rank, utility_system, network_group, asset_category,
         asset_subcategory, operational_role, lifecycle_representation,
         owner_or_jurisdiction, confidence, score, evidence_json, warnings_json,
         rule_version, rule_code, created_at)
        VALUES (?, ?, 1, ?, 'network', 'pipe', ?, ?, 'existing',
                'Synthetic Owner', ?, ?, '[]', '[]', 'synthetic-v1', 'TEST-001',
                '2026-01-01')""",
        (
            f"candidate-{layer_id}", layer_id, domain, subcategory, role,
            "high" if domain != "review_required" else "low",
            0.95 if domain != "review_required" else 0.4,
        ),
    )
    connection.execute(
        """INSERT INTO automated_layer_state
        (layer_id, submission_id, automation_run_id, canonical_layer_name,
         source_prefix_tokens_json, classification_tokens_json, taxonomy_status,
         taxonomy_decision, approved_utility_system, approved_network_group,
         approved_asset_category, approved_asset_subcategory, approved_operational_role,
         approved_lifecycle_representation, taxonomy_confidence, taxonomy_evidence_json,
         coordinate_status, sensitivity_status, duplicate_status, owner_candidate,
         owner_confidence, owner_status, staging_readiness, staging_blockers_json,
         approved_for_staging, updated_at)
        VALUES (?, 'TEST-MAPPING-001', 'automation-1', ?, '[]', '[]', ?, 'reviewed',
                ?, 'network', 'pipe', ?, ?, 'existing', ?, '[]', 'coordinate_ready',
                'inherited_from_package', 'no_duplicate_candidate', 'Synthetic Owner',
                'medium', 'provisional', 'human_review_required',
                '["final staging approval required"]', 0, '2026-01-01')""",
        (
            layer_id, source_name,
            "approved" if domain != "review_required" else "deferred",
            domain, subcategory, role,
            "high" if domain != "review_required" else "low",
        ),
    )
    connection.execute(
        """INSERT INTO staging_plan_items
        (staging_plan_item_id, submission_id, layer_id, proposed_target_name,
         approved_for_staging, approval_status)
        VALUES (?, 'TEST-MAPPING-001', ?, ?, 0, 'not_approved')""",
        (f"stage-{layer_id}", layer_id, f"synthetic_{layer_id}"),
    )


def test_recommendations_normalization_and_geometry_are_conservative() -> None:
    ambiguous = recommend_layer(
        {
            "layer_id": "layer-1", "source_layer_name": "Synthetic Sewer Main",
            "source_layer_alias": "", "geometry_type": "polyline", "field_profile_json": "[]",
        },
        {"approved_utility_system": "wastewater", "approved_asset_subcategory": "unknown"},
        [],
    )

    assert ambiguous["recommended_asset_class"] == "unknown_wastewater_line"
    assert {item["asset_class"] for item in ambiguous["class_candidates"]} == {
        "gravity_main", "force_main", "pressure_sewer",
    }
    assert ambiguous["confidence"] == "low"
    assert geometry_compatibility("distribution_main", "polyline")["status"] == "compatible"
    assert geometry_compatibility("manhole", "polyline")["status"] == "incompatible"
    assert normalize_material("Ductile Iron")["target_value"] == "ductile_iron"
    assert normalize_material("Uncommon Synthetic Material")["status"] == "needs_review"
    assert normalize_status("In Service", "operational", "water")["target_value"] == "in_service"
    assert parse_diameter("12", "")["canonical_unit"] == "unknown"
    assert parse_diameter("300", "mm", "inch")["conversion_used"] == "millimeter_to_inch"
    assert proposed_preview_id("submission", "layer", "1", "water_main", 1) == proposed_preview_id(
        "submission", "layer", "1", "water_main", 1,
    )


def test_candidate_counts_and_plan_creation_before_staging(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    _seed_reviewed_layers(tmp_path)

    candidates = client.get("/api/intake/submissions/TEST-MAPPING-001/water-wastewater/mapping-candidates")
    created = client.post(
        "/api/intake/submissions/TEST-MAPPING-001/layers/water-layer/mapping-plan",
        json={"actor": "reviewer"},
    )
    plan = created.json()

    assert candidates.status_code == 200
    assert candidates.json()["summary"]["water_candidate_layers"] == 1
    assert candidates.json()["summary"]["wastewater_candidate_layers"] == 1
    assert candidates.json()["summary"]["ambiguous_layers"] == 1
    assert created.status_code == 200
    assert plan["utility_domain"] == "water"
    assert plan["target_asset_class"] == "distribution_main"
    assert plan["approved_plan"] is False
    assert plan["blockers"]["staging_blocker"]
    assert plan["creation_enabled"] is False
    assert "source_path" not in created.text
    assert "C:\\\\" not in created.text

    rerun = client.post(
        "/api/intake/submissions/TEST-MAPPING-001/layers/water-layer/mapping-plan",
        json={"actor": "reviewer"},
    ).json()
    assert rerun["plan_id"] == plan["plan_id"]
    assert rerun["plan_fingerprint"] == plan["plan_fingerprint"]


def test_mapping_review_workflow_approves_plan_but_not_creation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    _seed_reviewed_layers(tmp_path)
    path = "/api/intake/submissions/TEST-MAPPING-001/layers/water-layer/mapping-plan"
    plan = client.post(path, json={"actor": "reviewer"}).json()
    fields = plan["field_mappings"]
    reviewed_fields = [
        {
            **item,
            "mapping_status": "accepted" if item["target_field"] in {
                "source_asset_identifier", "nominal_diameter", "material", "lifecycle_status",
            } else item["mapping_status"],
            "human_override": True,
            "reviewer_type": "human",
        }
        for item in fields
    ]
    mapped = client.put(f"{path}/fields", json={"actor": "reviewer", "mappings": reviewed_fields})
    values = client.put(
        f"{path}/values",
        json={
            "actor": "reviewer",
            "mappings": [
                {
                    "source_field": "MATERIAL", "source_value": "PVC",
                    "target_field": "material", "target_value": "pvc",
                    "transformation_type": "domain_mapping", "confidence": "high",
                    "review_status": "accepted", "human_override": True,
                },
                {
                    "source_field": "STATUS", "source_value": "ACTIVE",
                    "target_field": "lifecycle_status", "target_value": "active",
                    "transformation_type": "lifecycle_mapping", "confidence": "high",
                    "review_status": "accepted", "human_override": True,
                },
            ],
        },
    )
    reviewed = client.post(
        f"{path}/recalculate",
        json={
            "actor": "reviewer", "owner_status": "confirmed",
            "jurisdiction_status": "confirmed", "sensitivity_status": "confirmed",
            "domain_confirmed": True, "taxonomy_confirmed": True,
            "source_role_confirmed": True,
        },
    )
    approved = client.post(
        f"{path}/approve",
        json={"approved_by": "reviewer", "reason": "Synthetic test review complete."},
    )
    preview = client.post(f"{path}/preview")
    eligibility = client.get(
        "/api/intake/submissions/TEST-MAPPING-001/layers/water-layer/canonicalization-eligibility",
    )

    assert mapped.status_code == values.status_code == reviewed.status_code == approved.status_code == 200
    assert approved.json()["status"] == "approved_plan"
    assert approved.json()["approved_plan"] is True
    assert approved.json()["blockers"]["staging_blocker"]
    assert eligibility.json()["state"] == "approved_plan_staging_blocked"
    assert eligibility.json()["creation_enabled"] is False
    assert preview.json()["preview_mode"] == "aggregate_only"
    assert preview.json()["records_read"] == preview.json()["canonical_assets_created"] == 0
    assert preview.json()["raw_coordinates_included"] is False
    assert "Preview only" in preview.json()["message"]


def test_unsafe_mappings_and_unsupported_targets_are_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    _seed_reviewed_layers(tmp_path)
    path = "/api/intake/submissions/TEST-MAPPING-001/layers/water-layer/mapping-plan"
    client.post(path, json={"actor": "reviewer"})

    for payload in (
        {"actor": "reviewer", "mappings": [{"source_field": "SOURCE_ID", "target_field": "source_asset_identifier", "transformation_type": "python"}]},
        {"actor": "reviewer", "mappings": [{"source_field": "SOURCE_ID", "target_field": "source_asset_identifier", "transformation_type": "direct", "script": "print(1)"}]},
        {"actor": "reviewer", "mappings": [{"source_field": "SOURCE_ID", "target_field": "unsupported_field", "transformation_type": "direct"}]},
        {"actor": "reviewer", "mappings": [{"source_field": "C:\\private\\source", "target_field": "source_asset_identifier", "transformation_type": "direct"}]},
    ):
        assert client.put(f"{path}/fields", json=payload).status_code == 422


def test_new_version_preserves_history_and_stale_source_is_detected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    _seed_reviewed_layers(tmp_path)
    path = "/api/intake/submissions/TEST-MAPPING-001/layers/wastewater-layer/mapping-plan"
    first = client.post(path, json={"actor": "reviewer"}).json()
    second = client.post(f"{path}/new-version", json={"actor": "reviewer", "reason": "Synthetic version test."}).json()

    assert second["plan_version"] == 2
    assert second["plan_id"] != first["plan_id"]
    assert any(event["action"] == "plan_version_created" for event in second["history"])

    with mapping_review.connect() as connection:
        connection.execute(
            "UPDATE intake_submissions SET sha256='synthetic-sha-v2' WHERE submission_id='TEST-MAPPING-001'",
        )
        connection.commit()
    eligibility = client.get(
        "/api/intake/submissions/TEST-MAPPING-001/layers/wastewater-layer/canonicalization-eligibility",
    ).json()
    assert eligibility["gates"]["stale_source"]["status"] == "blocked"


def test_mapping_review_api_routes_and_creation_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    _seed_reviewed_layers(tmp_path)
    layer = "/api/intake/submissions/TEST-MAPPING-001/layers/water-layer"
    plan_path = f"{layer}/mapping-plan"
    created = client.post(plan_path, json={"actor": "reviewer"}).json()

    assert client.get("/api/utility-assets/water-wastewater/mapping-candidates").status_code == 200
    assert client.get("/api/utility-assets/mapping-plans?utility_domain=water").json()["items"][0]["plan_id"] == created["plan_id"]
    assert client.get("/api/intake/submissions/TEST-MAPPING-001/water-wastewater/mapping-candidates").status_code == 200
    assert client.get(f"{layer}/mapping-recommendations").status_code == 200
    assert client.get(plan_path).status_code == 200
    assert client.get(f"{plan_path}/fields").status_code == 200
    assert client.get(f"{plan_path}/values").status_code == 200
    assert client.get(f"{plan_path}/preview").status_code == 200
    assert client.get(f"{plan_path}/safe-summary").status_code == 200
    assert client.get(f"{layer}/canonicalization-eligibility").status_code == 200
    assert client.post(f"{plan_path}/submit", json={"actor": "reviewer"}).status_code == 200
    assert client.post(f"{plan_path}/start-review", json={"actor": "reviewer"}).status_code == 200
    assert client.post(f"{plan_path}/request-revision", json={"actor": "reviewer"}).status_code == 200
    assert client.post(f"{plan_path}/defer", json={"actor": "reviewer"}).status_code == 200
    assert client.post(f"{plan_path}/reject", json={"actor": "reviewer"}).status_code == 200
    assert client.post(f"{plan_path}/unsupported", json={"actor": "reviewer"}).status_code == 404

    service = UtilityAssetService()
    with mapping_review.connect() as connection:
        with pytest.raises(UtilityAssetError, match="mapping-plan approval"):
            service._require_water_wastewater_creation_gates(
                connection, "TEST-MAPPING-001", "water-layer",
            )
