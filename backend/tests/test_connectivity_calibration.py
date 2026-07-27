import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.connectivity_qa import service
from app.services.connectivity_qa.calibration import (
    CALIBRATION_RULE_VERSION,
    DISPLAY_PRIORITIES,
    EXTERNAL_MAPPING_STATUSES,
    FINDING_ROLES,
    ISSUE_FAMILIES,
    TRACE_IMPACTS,
)

client = TestClient(app)


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vertical: str = "electric_distribution") -> tuple[dict, dict]:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    qa = client.post(
        f"/api/connectivity-qa/{vertical}/runs",
        json={"actor": "calibration-test", "force_recalculate": True},
    ).json()
    calibrated = client.post(
        f"/api/connectivity-qa/{vertical}/runs/{qa['qa_run_id']}/calibrate",
        json={"preserve_review_decisions": True},
    )
    assert calibrated.status_code == 200
    return qa, calibrated.json()


def test_calibration_taxonomy_and_expectation_manifest() -> None:
    manifest = json.loads(
        (Path(__file__).parents[2] / "config" / "qa_rules" / "connectivity_synthetic_expectations_v1.json").read_text()
    )
    assert CALIBRATION_RULE_VERSION == "connectivity-calibration-v1"
    assert {"conductor_connectivity", "cable_endpoint", "capacity_consistency"} <= set(ISSUE_FAMILIES)
    assert {"primary", "consequence", "independent", "informational"} <= set(FINDING_ROLES)
    assert {"stops_trace", "limits_trace", "no_trace_effect"} <= set(TRACE_IMPACTS)
    assert set(DISPLAY_PRIORITIES) == {"immediate", "high", "normal", "low", "informational"}
    assert "conceptually_mappable" in EXTERNAL_MAPPING_STATUSES
    assert len(manifest["electric_distribution"]["intentional_scenarios"]) == 8
    assert len(manifest["telecom_fiber"]["intentional_scenarios"]) == 6


def test_raw_findings_remain_immutable_and_groups_are_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qa, calibrated = _run(tmp_path, monkeypatch)
    with service.connect() as connection:
        before = [
            tuple(row) for row in connection.execute(
                """SELECT finding_id, finding_fingerprint, rule_code, severity, blocking, asset_id,
                related_asset_id, relationship_id, explanation, evidence_json
                FROM connectivity_qa_findings WHERE qa_run_id = ? ORDER BY finding_id""",
                (qa["qa_run_id"],),
            ).fetchall()
        ]
    groups = client.get("/api/connectivity-qa/electric_distribution/issue-groups?limit=500").json()["items"]
    forced = client.post(
        f"/api/connectivity-qa/electric_distribution/runs/{qa['qa_run_id']}/calibrate",
        json={"force_recalculate": True},
    ).json()
    forced_groups = client.get(
        f"/api/connectivity-qa/electric_distribution/issue-groups?calibration_run_id={forced['calibration_run_id']}&limit=500"
    ).json()["items"]
    with service.connect() as connection:
        after = [
            tuple(row) for row in connection.execute(
                """SELECT finding_id, finding_fingerprint, rule_code, severity, blocking, asset_id,
                related_asset_id, relationship_id, explanation, evidence_json
                FROM connectivity_qa_findings WHERE qa_run_id = ? ORDER BY finding_id""",
                (qa["qa_run_id"],),
            ).fetchall()
        ]
    assert before == after
    assert qa["summary"]["findings_count"] == 113
    assert calibrated["summary"]["technical_findings"] == qa["summary"]["findings_count"]
    assert len(groups) < qa["summary"]["findings_count"]
    assert [item["issue_group_id"] for item in groups] == [item["issue_group_id"] for item in forced_groups]
    assert sum(item["technical_finding_count"] for item in groups) == qa["summary"]["findings_count"]
    with service.connect() as connection:
        active = connection.execute(
            """SELECT issue_group_id, COUNT(*) count FROM connectivity_qa_issue_groups
            WHERE utility_vertical = ? AND superseded = 0 GROUP BY issue_group_id""",
            ("electric_distribution",),
        ).fetchall()
    assert len(active) == len(forced_groups)
    assert all(row["count"] == 1 for row in active)


def test_electric_root_causes_priorities_and_roles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run(tmp_path, monkeypatch)
    groups = client.get("/api/connectivity-qa/electric_distribution/issue-groups?limit=500").json()["items"]
    conductor = next(item for item in groups if item["primary_rule_code"] == "ELEC-001")
    conductor_detail = client.get(
        f"/api/connectivity-qa/electric_distribution/issue-groups/{conductor['issue_group_id']}"
    ).json()
    membership = next(item for item in groups if item["primary_rule_code"] == "ELEC-009" and "ELEC-010" in item["related_rule_codes"])
    lifecycle = next(item for item in groups if item["primary_rule_code"] == "SHARED-005")
    normally_open = next(item for item in groups if item["primary_rule_code"] == "ELEC-012")

    assert [item["rule_code"] for item in conductor_detail["members"]] == ["ELEC-001", "ELEC-002"]
    assert conductor_detail["members"][0]["finding_role"] == "primary"
    assert conductor_detail["members"][1]["finding_role"] == "consequence"
    assert conductor["trace_impact"] == "stops_trace"
    assert conductor["display_priority"] == "high"
    assert membership["issue_family"] == "membership_conflict"
    assert lifecycle["related_rule_codes"] == ["ELEC-014"]
    assert normally_open["highest_severity"] == "info"
    assert normally_open["display_priority"] == "informational"
    assert normally_open["trace_impact"] == "no_trace_effect"


def test_telecom_grouping_preserves_distinct_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qa, calibrated = _run(tmp_path, monkeypatch, "telecom_fiber")
    groups = client.get("/api/connectivity-qa/telecom_fiber/issue-groups?limit=500").json()["items"]
    codes = {item["primary_rule_code"] for item in groups}
    lifecycle = next(item for item in groups if item["primary_rule_code"] == "SHARED-005" and "TEL-013" in item["related_rule_codes"])
    provisional = next(item for item in groups if item["primary_rule_code"] == "SHARED-004")

    assert qa["summary"]["findings_count"] == 26
    assert calibrated["summary"]["technical_findings"] == 26
    assert {"TEL-001", "TEL-003", "TEL-005", "TEL-012"} <= codes
    assert lifecycle["related_rule_codes"] == ["TEL-013"]
    assert provisional["related_rule_codes"] == ["TEL-014"]
    assert next(item for item in groups if item["primary_rule_code"] == "TEL-003")["issue_family"] == "strand_allocation"
    assert next(item for item in groups if item["primary_rule_code"] == "TEL-005")["issue_family"] == "capacity_consistency"
    assert sum(item["technical_finding_count"] for item in groups) == 26


def test_calibration_reuse_filters_and_safe_serialization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qa, first = _run(tmp_path, monkeypatch)
    reused = client.post(
        f"/api/connectivity-qa/electric_distribution/runs/{qa['qa_run_id']}/calibrate",
        json={"force_recalculate": False},
    ).json()
    filtered = client.get(
        "/api/connectivity-qa/electric_distribution/issue-groups"
        "?trace_impact=stops_trace&effective_blocking=true&limit=2"
    ).json()
    detail = client.get(
        f"/api/connectivity-qa/electric_distribution/issue-groups/{filtered['items'][0]['issue_group_id']}"
    )

    assert reused["reused"] is True
    assert reused["calibration_run_id"] == first["calibration_run_id"]
    assert reused["message"] == "No QA findings or calibration rules changed"
    assert filtered["pagination"]["total"] >= len(filtered["items"]) == 2
    assert all(item["trace_impact"] == "stops_trace" and item["effective_blocking"] for item in filtered["items"])
    assert "source_path" not in detail.text
    assert "geometry_reference" not in detail.text
    assert "C:\\\\" not in detail.text
    assert detail.json()["graph_context"]["geometry"] == "logical_relationship_view_only"
    target = next(
        item for item in client.get("/api/connectivity-qa/electric_distribution/issue-groups?limit=500").json()["items"]
        if item["affected_asset_ids"] and item["affected_relationship_ids"]
    )
    for field, value in (
        ("issue_family", target["issue_family"]),
        ("severity", target["highest_severity"]),
        ("display_priority", target["display_priority"]),
        ("trace_impact", target["trace_impact"]),
        ("review_status", target["review_status"]),
        ("asset_id", target["affected_asset_ids"][0]),
        ("relationship_id", target["affected_relationship_ids"][0]),
        ("primary_rule_code", target["primary_rule_code"]),
    ):
        items = client.get(f"/api/connectivity-qa/electric_distribution/issue-groups?{field}={value}&limit=500").json()["items"]
        assert target["issue_group_id"] in {item["issue_group_id"] for item in items}


def test_group_review_history_and_compatible_recalibration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qa, _ = _run(tmp_path, monkeypatch)
    group = client.get(
        "/api/connectivity-qa/electric_distribution/issue-groups?trace_impact=stops_trace&limit=1"
    ).json()["items"][0]
    path = f"/api/connectivity-qa/electric_distribution/issue-groups/{group['issue_group_id']}"

    assert client.post(f"{path}/accept-risk", json={"reviewer": "Reviewer"}).status_code == 422
    reviewed = client.post(
        f"{path}/accept-risk",
        json={"reviewer": "Reviewer", "rationale": "Synthetic evidence reviewed for calibration."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "accepted_risk"
    assert all(item["review_status"] == "accepted_risk" for item in reviewed.json()["members"])
    assert len(reviewed.json()["history"]) == len(reviewed.json()["members"])

    forced = client.post(
        f"/api/connectivity-qa/electric_distribution/runs/{qa['qa_run_id']}/calibrate",
        json={"force_recalculate": True, "preserve_review_decisions": True},
    ).json()
    same = client.get(
        f"/api/connectivity-qa/electric_distribution/issue-groups/{group['issue_group_id']}"
    ).json()
    assert forced["reused"] is False
    assert same["review_status"] == "accepted_risk"
    reopened = client.post(f"{path}/reopen", json={"reviewer": "Reviewer"})
    assert reopened.status_code == 200
    assert reopened.json()["review_status"] == "open"
    assert reopened.json()["history"][-1]["action"] == "reopen"


def test_member_review_updates_derived_group_state_without_changing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _run(tmp_path, monkeypatch)
    group = next(
        item for item in client.get("/api/connectivity-qa/electric_distribution/issue-groups?limit=500").json()["items"]
        if item["technical_finding_count"] > 1
    )
    detail = client.get(
        f"/api/connectivity-qa/electric_distribution/issue-groups/{group['issue_group_id']}"
    ).json()
    finding = detail["members"][0]
    evidence = finding["evidence"]

    reviewed = client.post(
        f"/api/connectivity-qa/electric_distribution/findings/{finding['finding_id']}/acknowledge",
        json={"reviewer": "Member Reviewer"},
    )
    updated = client.get(
        f"/api/connectivity-qa/electric_distribution/issue-groups/{group['issue_group_id']}"
    ).json()

    assert reviewed.status_code == 200
    assert updated["review_status"] == "mixed"
    assert {item["review_status"] for item in updated["members"]} == {"open", "acknowledged"}
    assert next(item for item in updated["members"] if item["finding_id"] == finding["finding_id"])["evidence"] == evidence
    assert updated["history"][-1]["action"] == "member_review_synchronized"
    client.post(
        f"/api/connectivity-qa/electric_distribution/runs/{updated['qa_run_id']}/calibrate",
        json={"force_recalculate": True, "preserve_review_decisions": True},
    ).raise_for_status()
    recalibrated = client.get(
        f"/api/connectivity-qa/electric_distribution/issue-groups/{group['issue_group_id']}"
    ).json()
    assert recalibrated["review_status"] == "mixed"


def test_changed_membership_supersedes_old_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qa, first = _run(tmp_path, monkeypatch)
    group = client.get(
        "/api/connectivity-qa/electric_distribution/issue-groups?primary_rule_code=ELEC-001&limit=1"
    ).json()["items"][0]
    with service.connect() as connection:
        source = connection.execute(
            "SELECT * FROM connectivity_qa_findings WHERE qa_run_id = ? AND finding_id = ?",
            (qa["qa_run_id"], group["primary_finding_id"]),
        ).fetchone()
        values = dict(source)
        values.update({
            "finding_id": "synthetic-extra-finding",
            "finding_fingerprint": "synthetic-extra-fingerprint",
            "rule_code": "ELEC-002",
            "short_title": "Conductor endpoint missing",
        })
        columns = list(values)
        connection.execute(
            f"INSERT INTO connectivity_qa_findings ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            tuple(values[column] for column in columns),
        )
        connection.commit()
    changed = client.post(
        f"/api/connectivity-qa/electric_distribution/runs/{qa['qa_run_id']}/calibrate",
        json={"force_recalculate": True},
    ).json()
    with service.connect() as connection:
        superseded = connection.execute(
            """SELECT superseded FROM connectivity_qa_issue_groups
            WHERE calibration_run_id = ? AND issue_group_id = ?""",
            (first["calibration_run_id"], group["issue_group_id"]),
        ).fetchone()[0]
    assert changed["summary"]["technical_findings"] == qa["summary"]["findings_count"] + 1
    assert superseded == 1


def test_calibration_rejects_unsafe_inputs_and_unsupported_vertical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qa, _ = _run(tmp_path, monkeypatch)
    unsafe = client.post(
        f"/api/connectivity-qa/electric_distribution/runs/{qa['qa_run_id']}/calibrate",
        json={"expression": "__import__('os')"},
    )
    unsupported = client.get("/api/connectivity-qa/gas/calibration/status")
    missing = client.post(
        "/api/connectivity-qa/electric_distribution/runs/not-a-run/calibrate",
        json={},
    )
    assert unsafe.status_code == 422
    assert unsupported.status_code == 404
    assert missing.status_code == 404
