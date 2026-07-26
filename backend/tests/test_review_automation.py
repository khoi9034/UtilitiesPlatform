import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.review_automation import engine
from app.services.review_automation.engine import (
    apply_sensitivity_inheritance,
    evaluate_coordinates,
    evaluate_taxonomy,
)
from app.services.review_automation.name_normalization import normalize_package_names
from app.services.source_inspection.models import ClassificationCandidate, SourceLayer

client = TestClient(app)


def upload_and_inspect(tmp_path: Path, monkeypatch) -> str:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in [
            "Sample.gdb/Town_A_ForceMains.fc",
            "Sample.gdb/Town_A_GravityMains.fc",
            "Sample.gdb/Town_B_Sewer.fc",
            "Sample.gdb/TownBSewer.fc",
            "Sample.gdb/WaterLine_WGS84.fc",
            "Sample.gdb/Churches.fc",
        ]:
            archive.writestr(name, b"synthetic")
    response = client.post(
        "/api/intake/submissions",
        data={
            "submission_name": "Synthetic Automation Source",
            "utility_system": "mixed",
            "source_type": "approved_source_package",
            "source_owner": "Synthetic Owner",
            "source_description": "Synthetic metadata-only review automation test.",
            "sensitivity_level": "restricted",
            "project_id": "TEST",
            "submitted_by": "tester",
            "authorization_confirmed": "true",
        },
        files=[("files", ("Sample.zip", buffer.getvalue(), "application/zip"))],
    )
    submission_id = response.json()["submissions"][0]["submission_id"]
    assert client.post(f"/api/intake/submissions/{submission_id}/inspect").status_code == 200
    return submission_id


def test_automated_review_runs_once_and_reuses_unchanged_results(tmp_path: Path, monkeypatch) -> None:
    submission_id = upload_and_inspect(tmp_path, monkeypatch)
    first = client.post(
        f"/api/intake/submissions/{submission_id}/automated-review",
        json={"policy_mode": "conservative", "force_recalculate": True, "preserve_manual_overrides": True},
    )
    second = client.post(f"/api/intake/submissions/{submission_id}/automated-review", json={})
    summary = client.get(f"/api/intake/submissions/{submission_id}/automated-review/summary")
    plan = client.get(f"/api/intake/submissions/{submission_id}/staging-plan")
    history = client.get(f"/api/intake/submissions/{submission_id}/automated-review/runs")

    assert first.status_code == 200
    assert first.json()["status"] == "complete"
    assert first.json()["layers_processed"] == 6
    assert first.json()["sensitivity_inherited"] == 6
    assert first.json()["duplicate_groups"] >= 1
    assert len(first.json()["stages"]) == 10
    assert len(first.json()["decisions"]) == 36
    assert second.json()["status"] == "unchanged"
    assert second.json()["reused_run_id"] == first.json()["automation_run_id"]
    assert len(history.json()["items"]) == 2
    assert all(item["approved_for_staging"] is False for item in plan.json()["items"])
    assert all(item["sensitivity_status"] == "inherited_from_package" for item in summary.json()["layers"])
    assert all(item["owner_status"] in {"provisional", "needs_owner_confirmation"} for item in summary.json()["layers"])
    assert "C:\\" not in summary.text


def test_manual_override_is_preserved_and_request_rejects_extra_fields(tmp_path: Path, monkeypatch) -> None:
    submission_id = upload_and_inspect(tmp_path, monkeypatch)
    layers = client.get(f"/api/intake/submissions/{submission_id}/layers?limit=50").json()["items"]
    layer = layers[0]
    override = client.patch(
        f"/api/intake/submissions/{submission_id}/layers/{layer['layer_id']}/review",
        json={
            "workflow_status": "decision_recorded",
            "classification_decision": "manual_override",
            "approved_utility_system": "shared_reference",
            "approved_network_group": "community_reference",
            "approved_asset_category": "place",
            "approved_asset_subcategory": "community_place",
            "reviewer": "tester",
            "review_notes": "Synthetic override.",
        },
    )
    run = client.post(
        f"/api/intake/submissions/{submission_id}/automated-review",
        json={"force_recalculate": True, "preserve_manual_overrides": True},
    )
    summary = client.get(f"/api/intake/submissions/{submission_id}/automated-review/summary").json()
    blocked = client.post(
        f"/api/intake/submissions/{submission_id}/automated-review",
        json={"rule_path": "not-allowed"},
    )

    state = next(item for item in summary["layers"] if item["layer_id"] == layer["layer_id"])
    assert override.status_code == 200
    assert run.status_code == 200
    assert state["taxonomy_decision"] == "manual_override_preserved"
    assert blocked.status_code == 422

    client.patch(
        f"/api/intake/submissions/{submission_id}/layers/{layers[1]['layer_id']}/review",
        json={"workflow_status": "deferred", "classification_decision": "deferred", "reviewer": "tester"},
    )
    assert client.post(f"/api/intake/submissions/{submission_id}/automated-review/rerun", json={}).status_code == 200
    recalculated = client.get(f"/api/intake/submissions/{submission_id}/automated-review/summary").json()
    deferred_state = next(item for item in recalculated["layers"] if item["layer_id"] == layers[1]["layer_id"])
    assert deferred_state["taxonomy_decision"] != "deferred"


def test_independent_policy_stages_are_conservative() -> None:
    names = normalize_package_names(
        [
            "enterprise_GIS_DBO_CHA_Septic_Tank",
            "enterprise_GIS_DBO_CHA_Pump_Tank",
            "enterprise_GIS_DBO_WSACC_Manholes",
            "enterprise_GIS_DBO_Mt_Pleasant_ForceMain",
            "enterprise_GIS_DBO_Mt_Pleasant_GravityMain",
        ]
    )
    assert names["enterprise_GIS_DBO_CHA_Septic_Tank"]["canonical_layer_name"] == "CHA_Septic_Tank"

    layer = SourceLayer(
        layer_id="force",
        submission_id="submission",
        container_id="container",
        source_layer_name="ForceMain_WGS84",
        geometry_type="polyline",
        field_profile=[{"name": "unique_id"}, {"name": "length"}],
        spatial_reference_name="NAD_1983_StatePlane_North_Carolina_FIPS_3200_Feet",
        spatial_reference_wkid=2264,
        coordinate_status="name_and_metadata_conflict",
    )
    candidate = ClassificationCandidate(
        candidate_id="candidate",
        layer_id="force",
        rank=1,
        utility_system="wastewater",
        network_group="pressurized_network",
        asset_category="pipe",
        asset_subcategory="force_main",
        operational_role="network_asset",
        lifecycle_representation="existing",
        owner_or_jurisdiction="Harrisburg",
        confidence="high",
        score=0.94,
        evidence=["Name rule matched."],
    )
    assert evaluate_taxonomy(layer, [candidate], None)["status"] == "approved"
    assert evaluate_coordinates(layer)["status"] == "coordinate_name_conflict"
    assert evaluate_coordinates(layer)["blocker"]
    sensitivity = apply_sensitivity_inheritance("restricted", [layer])["force"]
    assert sensitivity["status"] == "inherited_from_package"
    assert sensitivity["public_use_allowed"] is False
    assert sensitivity["export_allowed"] is False


def test_human_owner_acknowledgement_persists_without_staging_approval(tmp_path: Path, monkeypatch) -> None:
    submission_id = upload_and_inspect(tmp_path, monkeypatch)
    assert client.post(f"/api/intake/submissions/{submission_id}/automated-review", json={"force_recalculate": True}).status_code == 200
    first_summary = client.get(f"/api/intake/submissions/{submission_id}/automated-review/summary").json()
    state = first_summary["layers"][0]
    review = client.patch(
        f"/api/intake/submissions/{submission_id}/layers/{state['layer_id']}/review",
        json={
            "workflow_status": "classification_approved",
            "classification_decision": "manual_override",
            "approved_utility_system": state["approved_utility_system"],
            "approved_network_group": state["approved_network_group"],
            "approved_asset_category": state["approved_asset_category"],
            "approved_asset_subcategory": state["approved_asset_subcategory"],
            "approved_operational_role": state["approved_operational_role"],
            "approved_lifecycle_representation": state["approved_lifecycle_representation"],
            "approved_owner_or_jurisdiction": state["owner_candidate"],
            "owner_decision": "acknowledge_provisional",
            "reviewer": "tester",
            "review_notes": "Synthetic provisional-owner acknowledgement.",
        },
    )
    rerun = client.post(f"/api/intake/submissions/{submission_id}/automated-review/rerun", json={})
    second_summary = client.get(f"/api/intake/submissions/{submission_id}/automated-review/summary").json()
    updated = next(item for item in second_summary["layers"] if item["layer_id"] == state["layer_id"])

    assert review.status_code == 200
    assert rerun.status_code == 200
    assert updated["owner_status"] == "confirmed"
    assert "Final staging reviewer must acknowledge provisional ownership." not in updated["staging_blockers"]
    assert all(not item["approved_for_staging"] for item in second_summary["layers"])


def test_failure_is_safe_and_retryable(tmp_path: Path, monkeypatch) -> None:
    submission_id = upload_and_inspect(tmp_path, monkeypatch)
    original = engine.recalculate_taxonomy
    monkeypatch.setattr(engine, "recalculate_taxonomy", lambda *_args: (_ for _ in ()).throw(RuntimeError("private path should not escape")))
    failed = client.post(f"/api/intake/submissions/{submission_id}/automated-review", json={"force_recalculate": True})
    inspection = client.get(f"/api/intake/submissions/{submission_id}/inspection-status")
    monkeypatch.setattr(engine, "recalculate_taxonomy", original)
    retry = client.post(f"/api/intake/submissions/{submission_id}/automated-review/rerun", json={})

    assert failed.status_code == 500
    assert "private path" not in failed.text
    assert inspection.json()["inspection_status"] == "complete"
    assert retry.status_code == 200
