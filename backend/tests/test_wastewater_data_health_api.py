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
    (reports / "wastewater_rule_calibration.json").write_text(json.dumps({"rows": [{"rule_code": "WW_ID_003", "total_findings": 1, "reviewed_findings": 0, "confirmed_defects": 0, "false_positives": 0, "source_limitations": 0, "confirmation_rate": 0, "false_positive_rate": 0, "review_coverage": 0, "threshold": "", "calibration_status": "not_reviewed"}]}), encoding="utf-8")
    with (reports / "wastewater_review_sample.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["issue_id", "rule_code"])
        writer.writeheader()
        writer.writerow({"issue_id": issue_id, "rule_code": "WW_ID_003"})
    (reports / "wastewater_network_component_review.json").write_text(json.dumps({"components": [{"component_id": "1", "pipe_count": 1, "manhole_count": 1, "total_asset_count": 2, "unmatched_endpoints": 0, "likely_classification": "primary_network"}]}), encoding="utf-8")
    (reports / "wastewater_standardization_readiness.json").write_text(json.dumps({"standardization_status": "pending_human_review", "writes_to_standardized_gdb": False, "writes_to_curated_gdb": False, "fields_unavailable": [], "fields_blocked": []}), encoding="utf-8")
    (reports / "wastewater_standardization_mapping.json").write_text(json.dumps({"mappings": [{"source_layer": "wastewater_gravity_main", "source_field": "ASSET", "target_field": "source_asset_id", "approved_to_standardize": "false"}]}), encoding="utf-8")
    (reports / "wastewater_data_owner_questions.md").write_text("# Questions\n", encoding="utf-8")
    (reports / "wastewater_trust_pipeline.json").write_text(json.dumps({"stages": [{"stage": "Raw", "state": "complete"}]}), encoding="utf-8")
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

    ok = client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"workflow_status": "decision_recorded", "disposition": "confirmed_defect", "reviewer": "tester"})
    forbidden = client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"source_layer": "edit"})
    invalid = client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"review_status": "bad"})

    assert ok.status_code == 200
    assert ok.json()["workflow_status"] == "decision_recorded"
    assert ok.json()["disposition"] == "confirmed_defect"
    assert forbidden.status_code == 422
    assert invalid.status_code == 422


def test_wastewater_no_results_and_runs_are_sanitized(tmp_path: Path, monkeypatch) -> None:
    write_reports(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    no_results = client.get("/api/data-health/wastewater/issues", params={"rule_code": "NOPE"}).json()
    disposition = client.get("/api/data-health/wastewater/issues", params={"disposition": "unreviewed"})
    runs = client.get("/api/data-health/wastewater/runs")

    assert no_results["items"] == []
    assert "No wastewater QA issues" in no_results["message"]
    assert disposition.status_code == 200
    assert disposition.json()["pagination"]["total"] == 2
    assert runs.status_code == 200
    assert "hidden.gdb" not in runs.text
    assert runs.json()["runs"][0]["input_layer"] == "wastewater_gravity_main"


def test_phase2_review_routes_and_batch_update_are_safe(tmp_path: Path, monkeypatch) -> None:
    issue_id = write_reports(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    queue = client.get("/api/review/wastewater/queue")
    batch = client.patch(
        "/api/review/wastewater/issues/batch",
        json={"issue_ids": [issue_id], "workflow_status": "assigned", "disposition": "needs_field_verification", "assigned_to": "steward"},
    )
    calibration = client.get("/api/review/wastewater/calibration")
    sample = client.get("/api/review/wastewater/sample")
    questions = client.get("/api/review/wastewater/data-owner-questions")
    component = client.patch("/api/data-health/wastewater/components/1", json={"classification": "primary_network", "workflow_status": "decision_recorded"})
    readiness = client.get("/api/standardization/wastewater/readiness")
    mappings = client.get("/api/standardization/wastewater/mappings")
    pipeline = client.get("/api/trust-pipeline/wastewater")

    assert queue.status_code == 200
    assert queue.json()["items"][0]["issue_fingerprint"]
    assert "hidden.gdb" not in queue.text
    assert batch.status_code == 200
    assert batch.json()["updated_count"] == 1
    assert calibration.json()["rows"][0]["calibration_status"] == "not_reviewed"
    assert sample.json()["total"] == 1
    assert questions.json()["markdown"].startswith("# Questions")
    assert component.status_code == 200
    assert component.json()["review_classification"] == "primary_network"
    assert readiness.json()["writes_to_standardized_gdb"] is False
    assert mappings.json()["mappings"][0]["approved_to_standardize"] == "false"
    assert pipeline.json()["stages"][0]["state"] == "complete"


def test_command_center_aggregates_are_safe(tmp_path: Path, monkeypatch) -> None:
    write_reports(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    response = client.get("/api/platform/command-center", params={"utility_system": "wastewater"})
    not_onboarded = client.get("/api/platform/command-center", params={"utility_system": "telecom"})

    assert response.status_code == 200
    assert response.json()["qa"]["total_findings"] == 2
    assert response.json()["qa"]["open_reviews"] == 2
    assert "hidden.gdb" not in response.text
    assert not_onboarded.json()["platform_status"] == "not_onboarded"


def test_review_history_is_immutable_for_metadata_changes(tmp_path: Path, monkeypatch) -> None:
    issue_id = write_reports(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"workflow_status": "in_review", "reviewer": "one"})
    client.patch(f"/api/data-health/wastewater/issues/{issue_id}", json={"workflow_status": "resolved", "reviewer": "one"})

    import sqlite3

    db_path = tmp_path / "05_qa" / "review" / "wastewater_review.sqlite"
    with sqlite3.connect(db_path) as connection:
        history_count = connection.execute("SELECT COUNT(*) FROM review_history WHERE event_type IN ('status_changed', 'resolved')").fetchone()[0]

    assert history_count >= 2
