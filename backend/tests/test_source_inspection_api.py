import io
import json
import sqlite3
import subprocess
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
    assert good_review.json()["classification_status"] == "classification_approved"
    assert approval.status_code == 200
    assert approval.json()["approved_for_staging"] is False
    assert "coordinate review" in approval.json()["blocker"]

    excluded = client.patch(
        f"/api/intake/submissions/{submission_id}/layers/{layer_id}/review",
        json={"classification_decision": "excluded", "workflow_status": "decision_recorded", "reviewer": "tester"},
    )
    assert excluded.status_code == 200
    assert excluded.json()["classification_status"] == "excluded"
    assert excluded.json()["routing_state"] == "excluded"


def test_real_file_gdb_retry_uses_existing_submission_and_versions_failures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    entries = {
        "Synthetic.gdb/gdb": b"system",
        "Synthetic.gdb/a00000001.gdbtable": b"table",
        "Synthetic.gdb/a00000001.gdbtablx": b"index",
    }
    upload = client.post(
        "/api/intake/submissions/directory",
        data={**metadata(), "relative_paths": list(entries)},
        files=[("files", (Path(name).name, content, "application/octet-stream")) for name, content in entries.items()],
    )
    submission_id = upload.json()["submissions"][0]["submission_id"]

    from app.services.source_inspection import runner

    payload = {
        "status": "blocked",
        "safe_error_code": "arcpy_license_unavailable",
        "safe_message": "ArcGIS Pro licensing is not initialized for the inspection worker.",
        "retryable": True,
    }
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args, returncode=2, stdout=f"{runner.WORKER_RESULT_PREFIX}{json.dumps(payload)}\n", stderr="not exposed"),
    )

    first = client.post(f"/api/intake/submissions/{submission_id}/inspect")
    second = client.post(f"/api/intake/submissions/{submission_id}/inspect")
    detail = client.get(f"/api/intake/submissions/{submission_id}").json()

    assert first.status_code == second.status_code == 200
    assert detail["current_status"] == "inspection_blocked"
    assert detail["raw_registered_at"]
    assert detail["error_category"] == "arcpy_license_unavailable"
    assert (tmp_path / "01_raw" / "submissions" / submission_id / "original" / "Synthetic.gdb").is_dir()
    with sqlite3.connect(tmp_path / "00_admin" / "intake" / "utility_intake.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM inspection_runs WHERE submission_id = ?", (submission_id,)).fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM inspected_layers WHERE submission_id = ?", (submission_id,)).fetchone()[0] == 0
