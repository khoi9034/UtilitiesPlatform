import csv
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def write_reports(root: Path) -> str:
    reports = root / "05_qa" / "reports"
    reports.mkdir(parents=True)
    issue_id = "issue-1"
    issues = [
        {
            "issue_id": issue_id,
            "rule_code": "WW_ID_003",
            "rule_name": "Missing pipe asset ID",
            "category": "Identity",
            "severity": "high",
            "utility_system": "wastewater",
            "network_group": "gravity_network",
            "asset_category": "pipe",
            "asset_subcategory": "gravity_main",
            "source_layer": "wastewater_gravity_main",
            "source_asset_id": "",
            "source_objectid": "7",
            "related_asset_id": "",
            "related_objectid": "",
            "description": "Missing ID",
            "why_it_matters": "Identity is required.",
            "recommended_action": "Populate ID.",
            "detection_method": "Blank check.",
            "threshold_used": "",
            "confidence": "high",
            "review_status": "open",
            "reviewer": "",
            "reviewed_at": "",
            "resolution_notes": "",
            "run_id": "run-1",
            "created_at": "2026-07-20T00:00:00",
            "geometry": {"type": "point", "x": 1, "y": 2, "source_path": "hidden"},
            "source_path": str(root / "hidden.gdb"),
        },
        {
            "issue_id": "issue-2",
            "rule_code": "WW_ATTR_002",
            "rule_name": "Missing pipe material",
            "category": "Attributes",
            "severity": "medium",
            "utility_system": "wastewater",
            "network_group": "gravity_network",
            "asset_category": "pipe",
            "asset_subcategory": "gravity_main",
            "source_layer": "wastewater_gravity_main",
            "source_asset_id": "PIPE-2",
            "source_objectid": "8",
            "description": "Missing material",
            "why_it_matters": "Material supports planning.",
            "recommended_action": "Populate material.",
            "detection_method": "Blank check.",
            "threshold_used": "",
            "confidence": "high",
            "review_status": "open",
            "run_id": "run-1",
            "created_at": "2026-07-20T00:00:00",
            "geometry": {},
        },
    ]
    (reports / "wastewater_qa_issues.json").write_text(json.dumps({"issues": issues}), encoding="utf-8")
    (reports / "wastewater_qa_summary.json").write_text(
        json.dumps({"run_id": "run-1", "rule_results": [{"rule_code": "WW_ID_003", "status": "executed", "issue_count": 1}], "total_issues": 2}),
        encoding="utf-8",
    )
    (reports / "wastewater_network_summary.json").write_text(json.dumps({"total_connected_components": 1}), encoding="utf-8")
    with (reports / "wastewater_network_components.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["component_id", "pipe_count", "manhole_count", "pipe_objectids", "manhole_objectids"])
        writer.writeheader()
        writer.writerow({"component_id": "1", "pipe_count": "1", "manhole_count": "1"})
    (reports / "wastewater_map_layers.json").write_text(json.dumps({"pipes": [], "manholes": [], "issues": []}), encoding="utf-8")
    admin = root / "00_admin"
    admin.mkdir()
    with (admin / "processing_history.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["run_id", "dataset_id", "process_name", "input_path", "output_path", "started_at", "completed_at", "status", "records_read", "records_written", "warnings", "errors", "operator", "script_version", "notes"],
        )
        writer.writeheader()
        writer.writerow({"run_id": "run-1", "process_name": "Wastewater Data Health V1", "input_path": str(root / "hidden.gdb" / "wastewater_gravity_main"), "output_path": str(root / "05_qa" / "Wastewater_QA.gdb")})
    return issue_id


def test_wastewater_issue_filtering_pagination_and_safe_serialization(tmp_path: Path, monkeypatch) -> None:
    issue_id = write_reports(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    response = client.get("/api/data-health/wastewater/issues", params={"severity": "high", "limit": 1})
    payload = response.json()

    assert response.status_code == 200
    assert payload["pagination"]["total"] == 1
    assert payload["items"][0]["issue_id"] == issue_id
    assert "source_path" not in response.text
    assert "hidden.gdb" not in response.text


def test_wastewater_issue_patch_restrictions_and_status_validation(tmp_path: Path, monkeypatch) -> None:
    issue_id = write_reports(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    ok = client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"review_status": "confirmed_issue", "reviewer": "tester"})
    forbidden = client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"source_layer": "edit"})
    invalid = client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"review_status": "bad"})

    assert ok.status_code == 200
    assert ok.json()["review_status"] == "confirmed_issue"
    assert forbidden.status_code == 422
    assert invalid.status_code == 422


def test_wastewater_no_results_and_runs_are_sanitized(tmp_path: Path, monkeypatch) -> None:
    write_reports(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    no_results = client.get("/api/data-health/wastewater/issues", params={"rule_code": "NOPE"}).json()
    runs = client.get("/api/data-health/wastewater/runs")

    assert no_results["items"] == []
    assert "No wastewater QA issues" in no_results["message"]
    assert runs.status_code == 200
    assert "hidden.gdb" not in runs.text
    assert runs.json()["runs"][0]["input_layer"] == "wastewater_gravity_main"
