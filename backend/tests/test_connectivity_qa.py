import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.connectivity_qa import service
from app.services.connectivity_qa.rules import (
    REVIEW_STATUSES,
    build_graph,
    evaluate_rule,
    graph_fingerprint,
    rule_profile,
)

client = TestClient(app)


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vertical: str = "electric_distribution") -> dict:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    response = client.post(f"/api/connectivity-qa/{vertical}/runs", json={"actor": "test reviewer"})
    assert response.status_code == 200
    return response.json()


def test_profiles_are_allowlisted_and_complete() -> None:
    electric = rule_profile("electric_distribution")
    telecom = rule_profile("telecom_fiber")

    assert len(electric) == 23
    assert len(telecom) == 24
    assert {item["rule_code"] for item in electric} >= {"SHARED-001", "SHARED-008", "ELEC-001", "ELEC-015"}
    assert {item["rule_code"] for item in telecom} >= {"SHARED-001", "TEL-001", "TEL-016"}
    assert {"open", "acknowledged", "accepted_risk", "false_positive", "superseded"} <= set(REVIEW_STATUSES)
    with pytest.raises(ValueError, match="Unsupported"):
        rule_profile("wastewater")


def test_graph_preserves_direction_branches_and_parallel_relationships() -> None:
    assets = [
        {"asset_id": "a", "utility_vertical": "electric_distribution", "asset_class": "feeder", "canonical_attributes_json": {}},
        {"asset_id": "b", "utility_vertical": "electric_distribution", "asset_class": "switch", "canonical_attributes_json": {}},
        {"asset_id": "c", "utility_vertical": "electric_distribution", "asset_class": "transformer", "canonical_attributes_json": {}},
    ]
    relationships = [
        {"relationship_id": "r1", "from_asset_id": "a", "to_asset_id": "b", "relationship_type": "feeds", "direction": "forward", "provisional": False},
        {"relationship_id": "r2", "from_asset_id": "a", "to_asset_id": "b", "relationship_type": "protected_by", "direction": "forward", "provisional": False},
        {"relationship_id": "r3", "from_asset_id": "a", "to_asset_id": "c", "relationship_type": "feeds", "direction": "unknown_direction", "provisional": False},
    ]
    graph = build_graph("electric_distribution", assets, assets, relationships)
    direction_rule = next(item for item in rule_profile("electric_distribution") if item["rule_code"] == "ELEC-011")

    assert graph["adjacency"]["a"] == {"b", "c"}
    assert len(graph["edge_by_asset"]["b"]) == 2
    findings = evaluate_rule(direction_rule, graph)
    assert len(findings) == 1
    assert findings[0]["relationship_id"] == "r3"


def test_run_is_deterministic_reusable_and_forceable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _run(tmp_path, monkeypatch)
    second = client.post("/api/connectivity-qa/electric_distribution/runs", json={"actor": "test reviewer"}).json()
    forced = client.post("/api/connectivity-qa/electric_distribution/runs", json={"actor": "test reviewer", "force_recalculate": True}).json()

    assert first["status"] == "succeeded"
    assert first["summary"]["findings_count"] > 0
    assert first["qa_run_id"] == second["qa_run_id"]
    assert second["reused"] is True
    assert forced["qa_run_id"] != first["qa_run_id"]
    assert forced["run_fingerprint"] == first["run_fingerprint"]
    assert forced["summary"]["by_rule"] == first["summary"]["by_rule"]
    assert len({item["finding_id"] for item in service.findings("electric_distribution", {"limit": 500})["items"]}) == forced["summary"]["findings_count"]


def test_expected_synthetic_findings_and_safe_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    electric = _run(tmp_path, monkeypatch)
    telecom = _run(tmp_path, monkeypatch, "telecom_fiber")
    electric_rules = electric["summary"]["by_rule"]
    telecom_rules = telecom["summary"]["by_rule"]

    assert electric_rules["ELEC-001"] >= 1
    assert electric_rules["ELEC-003"] == 1
    assert electric_rules["ELEC-005"] == 1
    assert electric_rules["ELEC-007"] == 1
    assert electric_rules["ELEC-012"] == 1
    assert electric_rules["SHARED-004"] == 1
    assert telecom_rules["TEL-001"] == 1
    assert telecom_rules["TEL-003"] >= 1
    assert telecom_rules["TEL-005"] == 1
    assert telecom_rules["TEL-012"] == 1
    assert telecom_rules["TEL-013"] == 1
    assert telecom_rules["TEL-014"] == 1

    response = client.get("/api/connectivity-qa/electric_distribution/findings?severity=error&blocking=true&limit=2")
    assert response.status_code == 200
    assert len(response.json()["items"]) <= 2
    assert all(item["severity"] == "error" and item["blocking"] for item in response.json()["items"])
    assert "source_path" not in response.text
    assert "C:\\\\" not in response.text
    assert "geometry_reference" not in response.text


def test_review_requires_identity_and_rationale_and_persists_across_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run(tmp_path, monkeypatch)
    finding = client.get("/api/connectivity-qa/electric_distribution/findings?blocking=true&limit=1").json()["items"][0]
    path = f"/api/connectivity-qa/electric_distribution/findings/{finding['finding_id']}"

    assert client.post(f"{path}/accept-risk", json={"reviewer": "Reviewer"}).status_code == 422
    assert client.post(f"{path}/acknowledge", json={}).status_code == 422
    reviewed = client.post(f"{path}/accept-risk", json={"reviewer": "Reviewer", "rationale": "Synthetic expected condition."})
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "accepted_risk"
    assert reviewed.json()["history"][-1]["action"] == "accept-risk"
    summary = client.get(f"/api/connectivity-qa/electric_distribution/runs/{run['qa_run_id']}").json()["summary"]
    assert summary["by_review_status"]["accepted_risk"] == 1
    assert summary["by_review_status"]["open"] == summary["findings_count"] - 1

    forced = client.post("/api/connectivity-qa/electric_distribution/runs", json={"actor": "Reviewer", "force_recalculate": True}).json()
    recurring = client.get(f"/api/connectivity-qa/electric_distribution/findings?qa_run_id={forced['qa_run_id']}&asset_id={finding['asset_id']}&limit=500").json()["items"]
    same = next(item for item in recurring if item["finding_fingerprint"] == finding["finding_fingerprint"])
    assert same["finding_id"] == finding["finding_id"]
    assert same["review_status"] == "accepted_risk"
    assert run["qa_run_id"] != forced["qa_run_id"]


def test_rule_failure_isolated_as_partial_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    module = importlib.import_module("app.services.connectivity_qa.service")
    original = module.evaluate_rule

    def fail_one(rule: dict, graph: dict) -> list[dict]:
        if rule["rule_code"] == "ELEC-006":
            raise RuntimeError("synthetic rule failure")
        return original(rule, graph)

    monkeypatch.setattr(module, "evaluate_rule", fail_one)
    result = service.run("electric_distribution", {"actor": "test reviewer", "force_recalculate": True})
    failed_rule = next(item for item in result["rule_runs"] if item["rule_code"] == "ELEC-006")

    assert result["status"] == "partially_failed"
    assert result["summary"]["error_count"] == 1
    assert failed_rule["status"] == "blocked"
    assert "synthetic rule failure" not in json.dumps(result)
    assert result["summary"]["findings_count"] > 0


def test_no_assets_blocks_safely_and_source_geometry_summary_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    with service.connect() as connection:
        before = connection.execute(
            "SELECT asset_id, geometry_summary_json FROM canonical_utility_assets WHERE utility_vertical='telecom_fiber' ORDER BY asset_id"
        ).fetchall()
    _run(tmp_path, monkeypatch, "telecom_fiber")
    with service.connect() as connection:
        after = connection.execute(
            "SELECT asset_id, geometry_summary_json FROM canonical_utility_assets WHERE utility_vertical='telecom_fiber' ORDER BY asset_id"
        ).fetchall()
        connection.execute("DELETE FROM utility_asset_relationships")
        connection.execute("DELETE FROM canonical_utility_assets")
        connection.commit()
    assert [(row["asset_id"], row["geometry_summary_json"]) for row in before] == [(row["asset_id"], row["geometry_summary_json"]) for row in after]

    blocked = service.run("telecom_fiber", {"actor": "test reviewer", "force_recalculate": True})
    assert blocked["status"] == "blocked"
    assert blocked["summary"]["findings_count"] == 0
    assert len(blocked["rule_runs"]) == 24
    assert all(item["status"] == "skipped" for item in blocked["rule_runs"])
    assert client.post("/api/connectivity-qa/telecom_fiber/trace", json={}).status_code == 404
