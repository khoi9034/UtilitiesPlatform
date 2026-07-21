import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def metadata() -> dict[str, str]:
    return {
        "submission_name": "Synthetic Mixed Utility Source",
        "utility_system": "mixed",
        "source_type": "approved_source_package",
        "source_owner": "Synthetic Owner",
        "source_description": "Synthetic mixed file geodatabase package.",
        "sensitivity_level": "restricted",
        "project_id": "TEST",
        "submitted_by": "tester",
        "authorization_confirmed": "true",
    }


def synthetic_gdb_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in [
            "Sample.gdb/Town_A_ForceMains.fc",
            "Sample.gdb/Town_A_GravityMains.fc",
            "Sample.gdb/Town_B_Sewer.fc",
            "Sample.gdb/TownBSewer.fc",
            "Sample.gdb/WaterLine.fc",
            "Sample.gdb/Churches.fc",
        ]:
            archive.writestr(name, b"synthetic")
    return buffer.getvalue()


def test_source_inspection_routes_are_safe_and_layer_based(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    upload = client.post(
        "/api/intake/submissions",
        data=metadata(),
        files=[("files", ("Sample_Mixed_Utility_Source.zip", synthetic_gdb_zip(), "application/zip"))],
    )
    submission_id = upload.json()["submissions"][0]["submission_id"]

    inspect = client.post(f"/api/intake/submissions/{submission_id}/inspect")
    status = client.get(f"/api/intake/submissions/{submission_id}/inspection-status")
    layers = client.get(f"/api/intake/submissions/{submission_id}/layers?limit=50")
    duplicates = client.get(f"/api/intake/submissions/{submission_id}/duplicate-groups")

    assert inspect.status_code == 200
    assert status.json()["child_layer_count"] == 6
    assert layers.json()["pagination"]["total"] == 6
    assert "C:\\" not in layers.text
    assert "source_path" not in layers.text
    assert any(item["source_layer_name"] == "Town_A_ForceMains" and item["utility_system"] == "wastewater" for item in layers.json()["items"])
    assert duplicates.json()["items"]


def test_layer_review_and_staging_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    upload = client.post(
        "/api/intake/submissions",
        data=metadata(),
        files=[("files", ("Sample_Mixed_Utility_Source.zip", synthetic_gdb_zip(), "application/zip"))],
    )
    submission_id = upload.json()["submissions"][0]["submission_id"]
    client.post(f"/api/intake/submissions/{submission_id}/inspect")
    layers = client.get(f"/api/intake/submissions/{submission_id}/layers?search=ForceMains").json()["items"]
    layer_id = layers[0]["layer_id"]

    bad_review = client.patch(
        f"/api/intake/submissions/{submission_id}/layers/{layer_id}/review",
        json={"classification_decision": "manual_override", "reviewer": "tester"},
    )
    good_review = client.patch(
        f"/api/intake/submissions/{submission_id}/layers/{layer_id}/review",
        json={"classification_decision": "approve_top_candidate", "workflow_status": "classification_approved", "sensitivity_decision": "complete", "reviewer": "tester"},
    )
    plan = client.get(f"/api/intake/submissions/{submission_id}/staging-plan").json()["items"]
    item = next(row for row in plan if row["layer_id"] == layer_id)
    approval = client.patch(
        f"/api/intake/submissions/{submission_id}/staging-plan/{item['staging_plan_item_id']}",
        json={"approved_for_staging": True, "reviewer": "tester"},
    )

    assert bad_review.status_code == 422
    assert good_review.status_code == 200
    assert approval.status_code == 200
    assert approval.json()["approved_for_staging"] is False
    assert "coordinate review" in approval.json()["blocker"]
