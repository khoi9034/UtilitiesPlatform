import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.utility_assets import service
from app.services.utility_assets.domain import (
    ELECTRIC_OPERATIONAL_STATES,
    LIFECYCLE_STATES,
    RELATIONSHIP_TYPES,
    TELECOM_OPERATIONAL_STATES,
    stable_id,
    validate_mapping,
)

client = TestClient(app)


def test_shared_domain_and_synthetic_registry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    taxonomy = client.get("/api/utility-assets/taxonomy").json()
    assets = client.get("/api/utility-assets?limit=500").json()
    electric = [item for item in assets["items"] if item["utility_vertical"] == "electric_distribution"]
    telecom = [item for item in assets["items"] if item["utility_vertical"] == "telecom_fiber"]

    assert {"active", "retired", "unknown"} <= set(LIFECYCLE_STATES)
    assert {"energized", "normally_open"} <= set(ELECTRIC_OPERATIONAL_STATES)
    assert {"active", "reserved"} <= set(TELECOM_OPERATIONAL_STATES)
    assert {"connects_to", "spliced_to", "feeds"} <= set(RELATIONSHIP_TYPES)
    assert taxonomy["future_verticals"] == ["water", "wastewater", "gas", "stormwater"]
    assert len(electric) == 71
    assert len(telecom) == 43
    assert sum(item["asset_class"] == "secondary_conductor" for item in electric) == 4
    assert all(item["is_synthetic"] for item in assets["items"])
    assert any(item["qa_status"] == "warning" for item in electric)
    assert any(item["qa_status"] == "warning" for item in telecom)
    disconnected = next(item for item in electric if item["canonical_name"] == "ELEC-OVERHEAD-CONDUCTOR-008")
    assert disconnected["relationship_count"] == 0
    assert assets["summary"]["provisional_relationships"] == 2

    electric_detail = client.get(f"/api/utility-assets/{next(item['asset_id'] for item in electric if item['canonical_name'] == 'ELEC-TRANSFORMER-007')}").json()
    telecom_detail = client.get(f"/api/utility-assets/{next(item['asset_id'] for item in telecom if item['canonical_name'] == 'FIBER-FIBER-CABLE-004')}").json()
    assert electric_detail["canonical_attributes_json"]["phase"] == "AX"
    assert telecom_detail["canonical_attributes_json"]["to_structure_id"] == ""


def test_safe_asset_detail_relationships_and_lineage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    item = client.get("/api/utility-assets?utility_vertical=electric_distribution&limit=1").json()["items"][0]
    detail = client.get(f"/api/utility-assets/{item['asset_id']}")
    relationships = client.get(f"/api/utility-assets/{item['asset_id']}/relationships")
    lineage = client.get(f"/api/utility-assets/{item['asset_id']}/lineage")

    assert detail.status_code == 200
    assert "source_attributes_json" in detail.json()
    assert relationships.status_code == 200
    assert lineage.json()["source"]["source_fingerprint"]
    assert "source_path" not in detail.text
    assert "C:\\\\" not in detail.text


def test_mapping_allowlist_rejects_executable_transformations() -> None:
    assert validate_mapping({
        "source_field": "STATUS", "canonical_field": "lifecycle_status",
        "transformation_type": "lifecycle_mapping",
    })["canonical_field"] == "lifecycle_status"
    with pytest.raises(ValueError, match="allowlist"):
        validate_mapping({"source_field": "STATUS", "canonical_field": "lifecycle_status", "transformation_type": "python"})
    with pytest.raises(ValueError, match="Executable"):
        validate_mapping({
            "source_field": "STATUS", "canonical_field": "lifecycle_status",
            "transformation_type": "direct", "expression": "__import__('os')",
        })
    for transformation in ("direct", "renamed", "domain_mapping"):
        mapping = validate_mapping({
            "source_field": "TYPE", "canonical_field": "asset_subtype",
            "transformation_type": transformation, "human_override": True,
        })
        assert mapping["human_override"] is True
    assert validate_mapping({
        "source_field": "LEGACY", "canonical_field": "", "transformation_type": "unmapped",
    })["mapping_status"] == "proposed"


def test_plan_requires_staging_approval_and_preserves_real_layer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    with service.connect() as connection:
        connection.execute(
            """INSERT INTO intake_submissions
            (submission_id, submission_name, original_filename, stored_filename, utility_system, source_type,
             source_format, source_owner, source_description, sensitivity_level, authorization_confirmed,
             file_size_bytes, sha256, current_status, current_stage, inventory_status, classification_status,
             staging_status, created_at, updated_at)
            VALUES ('REAL-001', 'Synthetic test source', 'test.zip', 'hidden.zip', 'mixed', 'test', 'zip',
                    'Synthetic Owner', 'Synthetic only', 'restricted', 1, 1, 'abc', 'reviewed', 'raw',
                    'complete', 'approved', 'not_approved', '2026-01-01', '2026-01-01')"""
        )
        connection.execute(
            """INSERT INTO inspected_layers
            (layer_id, submission_id, container_id, source_layer_name, geometry_type, record_count, field_count,
             field_profile_json, latest_review_status, staging_status, created_at, updated_at)
            VALUES ('layer-1', 'REAL-001', 'container-1', 'SyntheticLayer', 'point', 1, 1, '[]',
                    'classification_approved', 'not_approved', '2026-01-01', '2026-01-01')"""
        )
        connection.execute(
            """INSERT INTO staging_plan_items
            (staging_plan_item_id, submission_id, layer_id, proposed_target_name, approved_for_staging, approval_status)
            VALUES ('stage-1', 'REAL-001', 'layer-1', 'synthetic_layer', 0, 'not_approved')"""
        )
        connection.commit()

    response = client.post(
        "/api/intake/submissions/REAL-001/layers/layer-1/canonicalization-plan",
        json={"utility_vertical": "electric_distribution", "target_asset_class": "pole"},
    )
    assert response.status_code == 409
    assert "Not eligible for canonicalization" in response.json()["detail"]

    with service.connect() as connection:
        before_layer = dict(connection.execute("SELECT * FROM inspected_layers WHERE layer_id='layer-1'").fetchone())
        connection.execute("UPDATE staging_plan_items SET approved_for_staging=1 WHERE layer_id='layer-1'")
        connection.commit()
    first = service.create_plan("REAL-001", "layer-1", {"utility_vertical": "electric_distribution", "target_asset_class": "pole", "actor": "tester"})
    rerun = service.create_plan("REAL-001", "layer-1", {"utility_vertical": "electric_distribution", "target_asset_class": "pole", "actor": "tester"})
    assert first["plan_fingerprint"] == rerun["plan_fingerprint"]
    assert first["approved_for_canonicalization"] is False

    with service.connect() as connection:
        connection.execute("UPDATE canonicalization_plans SET blockers_json='[\"geometry confirmation required\"]' WHERE plan_id=?", (first["plan_id"],))
        connection.commit()
    mapped = service.update_mappings("REAL-001", "layer-1", {
        "actor": "tester",
        "mappings": [
            {"source_field": "SOURCE_ID", "canonical_field": "source_asset_identifier", "transformation_type": "renamed", "confidence": "high"},
            {"source_field": "STATUS", "canonical_field": "lifecycle_status", "transformation_type": "lifecycle_mapping", "confidence": "medium", "human_override": True},
            {"source_field": "LEGACY", "canonical_field": "", "transformation_type": "unmapped"},
        ],
    })
    assert mapped["blockers"] == ["geometry confirmation required"]
    with pytest.raises(ValueError, match="blockers"):
        service.approve_plan("REAL-001", "layer-1", {"approved_by": "tester"})
    with pytest.raises(ValueError, match="approved plan"):
        service.create_assets("REAL-001", "layer-1", {"actor": "tester"})

    with service.connect() as connection:
        connection.execute("UPDATE canonicalization_plans SET blockers_json='[]', preview_records_json='[{\"source_record_id\":\"1\",\"source_asset_identifier\":\"SYNTH-1\"}]' WHERE plan_id=?", (first["plan_id"],))
        connection.commit()
    service.approve_plan("REAL-001", "layer-1", {"approved_by": "tester", "reason": "Synthetic test approval."})
    with service.connect() as connection:
        connection.execute("UPDATE intake_submissions SET sha256='changed' WHERE submission_id='REAL-001'")
        connection.commit()
    with pytest.raises(ValueError, match="Source metadata changed"):
        service.create_assets("REAL-001", "layer-1", {"actor": "tester"})
    with service.connect() as connection:
        after_layer = dict(connection.execute("SELECT * FROM inspected_layers WHERE layer_id='layer-1'").fetchone())
        history_count = connection.execute("SELECT COUNT(*) FROM canonicalization_history WHERE plan_id=?", (first["plan_id"],)).fetchone()[0]
    assert before_layer["field_profile_json"] == after_layer["field_profile_json"]
    assert before_layer["geometry_type"] == after_layer["geometry_type"]
    assert history_count >= 3


def test_approved_plan_creation_is_deterministic_and_idempotent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    layer_id = "demo-plan-electric_distribution-transformer"
    first = service.create_assets("DEMO-ELEC-001", layer_id, {"actor": "reviewer"})
    second = service.create_assets("DEMO-ELEC-001", layer_id, {"actor": "reviewer"})

    assert first["source_geometry_modified"] is False
    assert first["staging_geometry_modified"] is False
    assert first["published"] is False
    assert first["created_count"] == 3
    assert second["created_count"] == 0
    assert second["existing_count"] == 3
    assert stable_id("asset", "electric_distribution", "DEMO-ELEC-001", layer_id, "1") == stable_id(
        "asset", "electric_distribution", "DEMO-ELEC-001", layer_id, "1",
    )
    with sqlite3.connect(tmp_path / "00_admin" / "intake" / "utility_intake.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM canonicalization_history WHERE action = 'canonical_assets_created'").fetchone()[0] == 2
