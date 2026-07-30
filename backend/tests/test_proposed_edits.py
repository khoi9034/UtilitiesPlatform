import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.proposed_edits import service
from app.services.proposed_edits import engine

client = TestClient(app)


def _scenario(vertical: str, code: str) -> dict:
    items = client.get(f"/api/proposed-edits/{vertical}").json()["items"]
    item = next(item for item in items if item["scenario_code"] == code)
    return client.get(f"/api/proposed-edits/{vertical}/{item['proposal_id']}").json()


def test_catalog_scenarios_and_real_engine_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    types = client.get("/api/proposed-edits/types").json()
    electric = client.get("/api/proposed-edits/electric_distribution").json()["items"]
    telecom = client.get("/api/proposed-edits/telecom_fiber").json()["items"]

    assert len(electric) == 8
    assert len(telecom) == 9
    assert "replace_asset" in client.get("/api/proposed-edits/operation-types").json()["operation_types"]
    assert types["proposal_rule_version"] == "proposed-edit-rules-v1"
    assert _scenario("electric_distribution", "E-EDIT-001")["analysis_status"] == "complete"
    assert _scenario("telecom_fiber", "T-EDIT-001")["analysis_status"] == "complete"
    assert _scenario("electric_distribution", "E-EDIT-008")["validation_status"] == "failed"
    assert _scenario("telecom_fiber", "T-EDIT-009")["validation_status"] == "failed"


def test_overlay_is_deterministic_and_does_not_modify_canonical_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    with service.connect() as connection:
        proposal = service._row(connection, "electric_distribution", _scenario("electric_distribution", "E-EDIT-003")["proposal_id"])
        assets, relationships = service._graph(connection, "electric_distribution")
        operations = service._operations(connection, proposal["proposal_id"], proposal["proposal_version"])
    before = json.dumps({"assets": assets, "relationships": relationships}, sort_keys=True)

    first = engine.apply_overlay("electric_distribution", assets, relationships, operations)
    second = engine.apply_overlay("electric_distribution", assets, relationships, operations)

    assert first["overlay_fingerprint"] == second["overlay_fingerprint"]
    assert first["assets"] != assets
    assert json.dumps({"assets": assets, "relationships": relationships}, sort_keys=True) == before
    assert first["notice"].startswith("Proposed overlay")


def test_unsafe_operation_and_invalid_vertical_fail_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    proposal = _scenario("electric_distribution", "E-EDIT-001")

    unsafe = client.post(
        f"/api/proposed-edits/electric_distribution/{proposal['proposal_id']}/operations",
        json={"operation_type": "add_note", "reason": "run", "script": "remove everything"},
    )
    path = client.post(
        f"/api/proposed-edits/electric_distribution/{proposal['proposal_id']}/operations",
        json={"operation_type": "add_note", "reason": "C:\\private\\source.gdb"},
    )

    assert unsafe.status_code == 422
    assert path.status_code == 422
    assert client.get("/api/proposed-edits/gas").status_code == 404


def test_create_is_deterministic_and_submitted_version_is_immutable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    payload = {
        "proposal_type": "manual_investigation",
        "title": "Synthetic review candidate",
        "summary": "No operational action.",
        "created_by": "Proposal Author",
    }
    first = client.post("/api/proposed-edits/electric_distribution", json=payload).json()
    second = client.post("/api/proposed-edits/electric_distribution", json=payload).json()
    assert first["proposal_id"] == second["proposal_id"]

    add = client.post(
        f"/api/proposed-edits/electric_distribution/{first['proposal_id']}/operations",
        json={
            "operation_type": "request_manual_investigation",
            "target_asset_id": _scenario("electric_distribution", "E-EDIT-001")["operations"][0]["from_asset_id"],
            "reason": "Review synthetic evidence.",
        },
    )
    assert add.status_code == 200
    assert client.post(f"/api/proposed-edits/electric_distribution/{first['proposal_id']}/validate", json={"actor": "Proposal Author"}).status_code == 200
    assert client.post(f"/api/proposed-edits/electric_distribution/{first['proposal_id']}/analyze", json={"actor": "Proposal Author"}).status_code == 200
    assert client.post(f"/api/proposed-edits/electric_distribution/{first['proposal_id']}/submit", json={"actor": "Proposal Author"}).status_code == 200
    locked = client.post(
        f"/api/proposed-edits/electric_distribution/{first['proposal_id']}/operations",
        json={"operation_type": "add_note", "target_asset_id": add.json()["target_asset_id"], "reason": "Too late."},
    )
    version = client.post(
        f"/api/proposed-edits/electric_distribution/{first['proposal_id']}/new-version",
        json={"created_by": "Proposal Author", "reason": "Revise locked proposal."},
    )
    assert locked.status_code == 409
    assert version.status_code == 200
    assert version.json()["proposal_version"] == 2
    assert version.json()["status"] == "draft"


def test_stale_baseline_blocks_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    proposal = _scenario("electric_distribution", "E-EDIT-001")
    with service.connect() as connection:
        connection.execute(
            """UPDATE utility_asset_relationships SET confidence = 'low'
            WHERE relationship_id = (
                SELECT r.relationship_id FROM utility_asset_relationships r
                JOIN canonical_utility_assets a ON a.asset_id = r.from_asset_id
                WHERE a.utility_vertical = 'electric_distribution'
                ORDER BY r.relationship_id LIMIT 1
            )"""
        )
        connection.commit()

    response = client.post(
        f"/api/proposed-edits/electric_distribution/{proposal['proposal_id']}/validate",
        json={"actor": "Proposal Author"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert any(item["code"] == "stale_baseline" for item in response.json()["errors"])


def test_review_approval_and_package_are_plan_only_and_nonexecutable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    proposal = _scenario("telecom_fiber", "T-EDIT-001")
    proposal_id = proposal["proposal_id"]
    with service.connect() as connection:
        canonical_before = [
            tuple(row) for row in connection.execute(
                "SELECT asset_id, canonical_attributes_json, lifecycle_status, operational_status FROM canonical_utility_assets ORDER BY asset_id"
            ).fetchall()
        ]

    assert client.post(f"/api/proposed-edits/telecom_fiber/{proposal_id}/submit", json={"actor": "Demo Author"}).status_code == 200
    assert client.post(f"/api/proposed-edits/telecom_fiber/{proposal_id}/start-review", json={"reviewer": "Technical Reviewer", "reviewer_role": "technical_reviewer"}).status_code == 200
    approved = client.post(
        f"/api/proposed-edits/telecom_fiber/{proposal_id}/approve",
        json={"reviewer": "Final Reviewer", "reviewer_role": "final_approver", "notes": "Synthetic plan reviewed."},
    )
    package = client.post(
        f"/api/proposed-edits/telecom_fiber/{proposal_id}/implementation-package",
        json={"actor": "Final Reviewer", "notes": "Generate descriptive package."},
    )

    assert approved.status_code == 200
    assert approved.json()["approved_not_implemented"] is True
    assert package.status_code == 200
    assert package.json()["executable"] is False
    assert package.json()["descriptive_only"] is True
    assert package.json()["implementation_status"] == "not_implemented"
    assert "adapter_required" == package.json()["external_mapping_status"]
    serialized = package.text.lower()
    assert not any(value in serialized for value in ("c:\\\\", "http://", "https://", "\"sql\"", "\"command\""))
    with service.connect() as connection:
        canonical_after = [
            tuple(row) for row in connection.execute(
                "SELECT asset_id, canonical_attributes_json, lifecycle_status, operational_status FROM canonical_utility_assets ORDER BY asset_id"
            ).fetchall()
        ]
        assert connection.execute("SELECT COUNT(*) FROM proposed_edit_history WHERE proposal_id = ?", (proposal_id,)).fetchone()[0] >= 5
    assert canonical_after == canonical_before
