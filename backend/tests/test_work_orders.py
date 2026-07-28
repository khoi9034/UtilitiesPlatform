from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _scenario(vertical: str, code: str) -> dict:
    items = client.get(f"/api/work-orders/{vertical}").json()["items"]
    item = next(item for item in items if item["scenario_code"] == code)
    return client.get(f"/api/work-orders/{vertical}/{item['work_order_id']}").json()


def test_catalog_and_synthetic_scenarios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    assert len(client.get("/api/work-orders/electric_distribution").json()["items"]) == 6
    assert len(client.get("/api/work-orders/telecom_fiber").json()["items"]) == 7
    assert "conductor_connection" in client.get("/api/work-orders/types/electric_distribution").json()["work_order_types"]
    assert "splice_verification" in client.get("/api/work-orders/inspection-types").json()["inspection_types"]
    assert _scenario("electric_distribution", "E-WO-001")["proposal_approved"] is True
    assert _scenario("electric_distribution", "E-WO-005")["readiness"] == "blocked"
    assert _scenario("telecom_fiber", "T-WO-006")["readiness"] == "blocked"


def test_operational_creation_requires_approved_proposal_and_manual_investigation_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    blocked = _scenario("electric_distribution", "E-WO-005")
    rejected = client.post("/api/work-orders/electric_distribution", json={
        "proposal_id": blocked["linked_proposal_id"],
        "work_order_type": "transformer_replacement",
        "title": "Blocked replacement", "created_by": "Synthetic Planner",
    })
    manual = client.post("/api/work-orders/electric_distribution", json={
        "work_order_type": "manual_investigation",
        "title": "Review synthetic record", "created_by": "Synthetic Planner",
    })
    assert rejected.status_code == 409
    assert manual.status_code == 200
    assert manual.json()["linked_proposal_id"] == ""
    assert manual.json()["steps"] == []


def test_release_gates_version_lock_and_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    work_order = _scenario("electric_distribution", "E-WO-001")
    base = f"/api/work-orders/electric_distribution/{work_order['work_order_id']}"

    assert client.post(f"{base}/release", json={"actor": "Synthetic Planner"}).status_code == 409
    assert client.post(f"{base}/submit", json={"actor": "Synthetic Planner"}).status_code == 200
    assert client.post(f"{base}/start-review", json={"actor": "Synthetic Reviewer"}).status_code == 200
    approved = client.post(f"{base}/approve-release", json={
        "actor": "Synthetic Final Reviewer", "notes": "Approved synthetic job definition.",
    })
    released = client.post(f"{base}/release", json={"actor": "Synthetic Final Reviewer"})
    assert approved.status_code == 200
    assert released.status_code == 200
    assert released.json()["locked"] is True
    assert released.json()["readiness"] == "released"
    assignment = released.json()["assignments"][0]
    assert client.delete(f"{base}/assignments/{assignment['assignment_id']}").status_code == 409
    versioned = client.post(f"{base}/new-version", json={
        "actor": "Synthetic Planner", "reason": "Controlled amendment.",
    })
    assert versioned.status_code == 200
    assert versioned.json()["work_order_version"] == 2
    assert len(versioned.json()["history"]) >= 1


def test_implementation_conformance_reuses_qa_and_trace_without_network_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    work_order = _scenario("electric_distribution", "E-WO-001")
    base = f"/api/work-orders/electric_distribution/{work_order['work_order_id']}"
    with client:
        client.post(f"{base}/submit", json={"actor": "Synthetic Planner"})
        client.post(f"{base}/start-review", json={"actor": "Synthetic Reviewer"})
        client.post(f"{base}/approve-release", json={"actor": "Synthetic Final Reviewer", "notes": "Approved."})
        client.post(f"{base}/release", json={"actor": "Synthetic Final Reviewer"})
        client.post(f"{base}/start-work", json={"actor": "Synthetic GIS Technician"})
        before = json.dumps(client.get("/api/utility-assets?utility_vertical=electric_distribution&limit=500").json(), sort_keys=True)
        implementation = client.post(f"{base}/record-implementation", json={"recorded_by": "Synthetic GIS Technician"})
        conformance = client.post(f"{base}/run-conformance", json={})
        qa = client.post(f"{base}/run-post-work-qa", json={})
        traces = client.post(f"{base}/run-post-work-traces", json={})
        after = json.dumps(client.get("/api/utility-assets?utility_vertical=electric_distribution&limit=500").json(), sort_keys=True)
    assert implementation.json()["status"] == "simulated_overlay_only"
    assert implementation.json()["notice"].startswith("Synthetic implementation record")
    assert conformance.json()["status"] == "conformant"
    assert qa.json()["status"] in {"passed", "passed_with_warnings"}
    assert traces.json()["status"] == "passed"
    assert before == after


def test_nonconformance_and_closeout_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    work_order = _scenario("telecom_fiber", "T-WO-002")
    base = f"/api/work-orders/telecom_fiber/{work_order['work_order_id']}"
    client.post(f"{base}/submit", json={"actor": "Synthetic Planner"})
    client.post(f"{base}/start-review", json={"actor": "Synthetic Reviewer"})
    client.post(f"{base}/approve-release", json={"actor": "Synthetic Final Reviewer", "notes": "Approved."})
    client.post(f"{base}/release", json={"actor": "Synthetic Final Reviewer"})
    operation_id = work_order["steps"][0]["source_operation_id"]
    client.post(f"{base}/record-implementation", json={
        "completed_operation_ids": [], "skipped_operation_ids": [operation_id],
        "recorded_by": "Synthetic GIS Technician",
    })
    conformance = client.post(f"{base}/run-conformance", json={})
    closeout = client.post(f"{base}/submit-closeout", json={"actor": "Synthetic Reviewer"})
    assert conformance.json()["status"] == "conformant_with_conditions"
    assert closeout.status_code == 409


def test_safe_evidence_package_and_closed_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    closed = _scenario("telecom_fiber", "T-WO-001")
    base = f"/api/work-orders/telecom_fiber/{closed['work_order_id']}"
    unsafe = client.post(f"{base}/evidence", json={
        "evidence_type": "safe_attachment_metadata", "title": "Unsafe",
        "recorded_by": "Synthetic Inspector", "attachment_name": "run.ps1",
    })
    package = client.post(f"{base}/job-package", json={"actor": "Synthetic Reviewer"})
    receipt = client.get(f"{base}/completion-receipt")
    assert unsafe.status_code == 422
    assert package.status_code == 200
    assert package.json()["executable"] is False
    serialized = package.text.lower()
    assert not any(value in serialized for value in ("c:\\\\", "http://", "https://", "\"command\"", "\"sql\""))
    assert receipt.status_code == 200
    assert receipt.json()["disclaimer"].startswith("Completion receipt records")
