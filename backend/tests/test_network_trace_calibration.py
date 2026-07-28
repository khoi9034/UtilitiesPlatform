import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.connectivity_qa import service as connectivity_qa
from app.services.network_trace import service
from app.services.network_trace.calibration import (
    CALIBRATION_VERSION,
    CONFIG,
    calibrate_trace,
    calibration_fingerprint,
    load_calibration_config,
)

client = TestClient(app)


def _run(trace_type: str = "ELEC-TRACE-001", **values: object) -> dict:
    return {
        "trace_run_id": "trace-1",
        "input_fingerprint": "raw-fingerprint",
        "request_fingerprint": "request-fingerprint",
        "utility_vertical": "electric_distribution",
        "trace_type": trace_type,
        "start_asset_id": "start",
        "target_asset_id": "",
        "outcome": "complete",
        "confidence": "high",
        "status": "succeeded",
        "warnings_count": 0,
        "blockers_count": 0,
        **values,
    }


def _path(
    rank: int = 1,
    *,
    end: str = "terminal",
    reason: str = "terminal_reached",
    status: str = "complete",
    warnings: list[dict] | None = None,
    blockers: list[dict] | None = None,
    provisional: bool = False,
) -> dict:
    return {
        "trace_path_id": f"path-{rank}",
        "path_rank": rank,
        "path_status": status,
        "start_asset_id": "start",
        "end_asset_id": end,
        "asset_ids": ["start", end] if end != "start" else ["start"],
        "relationship_ids": [f"rel-{rank}"] if end != "start" else [],
        "stopping_reason": reason,
        "warnings": warnings or [],
        "blockers": blockers or [],
        "provisional": provisional,
    }


def _condition(code: str, *, group: str = "", asset: str = "terminal") -> dict:
    return {
        "code": code,
        "message": code.replace("_", " "),
        "asset_id": asset,
        "relationship_id": "",
        "issue_group_id": group,
    }


def _step(path: str = "path-1", group: str = "") -> dict:
    return {
        "trace_step_id": f"step-{path}",
        "trace_path_id": path,
        "sequence": 1,
        "decision": "stop",
        "decision_reason": "terminal_reached",
        "qa_issue_group_ids": [group] if group else [],
    }


def _event(index: int, *, group: str = "", asset: str = "terminal") -> dict:
    return {
        "trace_event_id": f"event-{index}",
        "event_type": "warning",
        "asset_id": asset,
        "relationship_id": "",
        "issue_group_id": group,
        "message": "Repeated calibrated QA evidence.",
    }


def _group(group_id: str, *, assets: list[str], impact: str = "advisory") -> dict:
    return {
        "issue_group_id": group_id,
        "issue_family": "provisional_evidence",
        "primary_rule_code": "SHARED-004",
        "group_title": "Provisional relationship evidence",
        "group_summary": "The relationship still requires confirmation.",
        "trace_impact": impact,
        "trace_impact_reason": "Review provisional evidence.",
        "review_status": "open",
        "recommended_action": "Confirm the relationship with the data owner.",
        "affected_asset_ids": assets,
        "affected_relationship_ids": [],
    }


def test_config_and_fingerprint_are_allowlisted_and_deterministic(tmp_path: Path) -> None:
    loaded = load_calibration_config()
    run, paths, steps, events, groups = _run(), [_path()], [_step()], [], []
    first = calibration_fingerprint(run, paths, steps, events, groups)

    assert loaded["version"] == CALIBRATION_VERSION
    assert "stopping_condition" in loaded["warning_scopes"]
    assert "endpoint_failure" in loaded["event_categories"]
    assert "python" not in json.dumps(loaded).lower()
    assert first == calibration_fingerprint(run, copy.deepcopy(paths), steps, events, groups)
    assert first != calibration_fingerprint(run, [_path(end="other")], steps, events, groups)

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"version":"broken"}', encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        load_calibration_config(invalid)


def test_background_warning_does_not_change_complete_result_or_high_confidence() -> None:
    result = calibrate_trace(
        _run(warnings_count=99), [_path()], [_step()], [], [_group("group-bg", assets=["off-path"])],
    )["result"]

    assert result["calibrated_outcome"] == "complete"
    assert result["calibrated_confidence"] == "high"
    assert result["background_warning_count"] == 1
    assert result["path_specific_warning_count"] == 0


def test_path_advisory_is_grouped_with_repeated_evidence() -> None:
    warning = _condition("advisory", group="group-1")
    calibrated = calibrate_trace(
        _run(outcome="complete_with_warnings", confidence="low", warnings_count=3),
        [_path(warnings=[warning])],
        [_step(group="group-1")],
        [_event(1, group="group-1"), _event(2, group="group-1")],
        [_group("group-1", assets=["terminal"])],
    )
    event = next(item for item in calibrated["events"] if item["issue_group_ids"] == ["group-1"])

    assert calibrated["result"]["calibrated_outcome"] == "complete_with_warnings"
    assert calibrated["result"]["calibrated_confidence"] == "medium"
    assert event["repeated_count"] == 4
    assert event["path_ids"] == ["path-1"]
    assert event["evidence"]["first_affected_step"] == 1
    assert event["source_event_ids"] == ["event-1", "event-2"]


def test_normal_branches_and_true_upstream_ambiguity_are_separate() -> None:
    paths = [_path(1, end="terminal-a"), _path(2, end="terminal-b")]
    downstream = calibrate_trace(_run(outcome="ambiguous", confidence="low"), paths, [], [], [])["result"]
    upstream = calibrate_trace(
        _run(trace_type="ELEC-TRACE-002", outcome="ambiguous", confidence="low"),
        [
            _path(1, end="source-a", reason="source_reached"),
            _path(2, end="source-b", reason="source_reached"),
        ],
        [], [], [],
    )["result"]

    assert downstream["calibrated_outcome"] == "complete"
    assert downstream["normal_branch_count"] == 1
    assert downstream["ambiguous_branch_count"] == 0
    assert upstream["calibrated_outcome"] == "ambiguous"
    assert upstream["ambiguous_branch_count"] == 1
    assert upstream["branch_analysis"]["divergence_step"] == 1


@pytest.mark.parametrize(
    ("paths", "expected_outcome", "expected_confidence"),
    [
        ([_path(status="blocked", reason="missing_endpoint", blockers=[_condition("missing_endpoint")])], "blocked", "low"),
        ([_path(status="partial", reason="no_traversable_edge", end="middle")], "partial", "low"),
        ([_path(status="partial", reason="no_traversable_edge", end="start")], "no_path", "indeterminate"),
    ],
)
def test_blocked_partial_and_no_path_outcomes(
    paths: list[dict],
    expected_outcome: str,
    expected_confidence: str,
) -> None:
    result = calibrate_trace(_run(outcome=expected_outcome), paths, [], [], [])["result"]

    assert result["calibrated_outcome"] == expected_outcome
    assert result["calibrated_confidence"] == expected_confidence
    if expected_outcome == "blocked":
        assert result["primary_stopping_category"] == "endpoint_failure"
        assert result["recommended_edit_category"] == "connect_endpoint"


def test_persistence_reuse_force_filters_receipt_and_raw_immutability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    qa = connectivity_qa.run("electric_distribution", {"actor": "calibration test"})
    connectivity_qa.calibrate("electric_distribution", qa["qa_run_id"], {"actor": "calibration test"})
    with service.connect() as connection:
        start_id = connection.execute(
            "SELECT asset_id FROM canonical_utility_assets WHERE canonical_name = 'ELEC-FEEDER-001'"
        ).fetchone()[0]
    raw = service.run("electric_distribution", {
        "trace_type": "ELEC-TRACE-001",
        "start_asset_id": start_id,
        "qa_policy": "diagnostic",
    })
    with service.connect() as connection:
        before = {
            table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in ("network_trace_runs", "network_trace_paths", "network_trace_steps", "network_trace_events")
        }

    first = client.post(
        f"/api/network-trace/electric_distribution/runs/{raw['trace_run_id']}/calibrate",
        json={"force_recalculate": False},
    )
    reused = client.post(
        f"/api/network-trace/electric_distribution/runs/{raw['trace_run_id']}/calibrate",
        json={"force_recalculate": False},
    )
    forced = client.post(
        f"/api/network-trace/electric_distribution/runs/{raw['trace_run_id']}/calibrate",
        json={"force_recalculate": True},
    )

    assert first.status_code == reused.status_code == forced.status_code == 200
    assert reused.json()["reused"] is True
    assert forced.json()["calibration_run_id"] != first.json()["calibration_run_id"]
    assert forced.json()["supersedes_calibration_run_id"] == first.json()["calibration_run_id"]
    assert first.json()["result"]["original_outcome"] == raw["outcome"]
    assert first.json()["result"]["trace_run_id"] == raw["trace_run_id"]
    events = client.get(
        f"/api/network-trace/electric_distribution/runs/{raw['trace_run_id']}/calibrated-events",
        params={"scope": "network_background", "limit": 5},
    )
    assert events.status_code == 200
    assert all(item["scope"] == "network_background" for item in events.json()["items"])
    assert client.get(
        f"/api/network-trace/electric_distribution/runs/{raw['trace_run_id']}/calibrated-safe-summary"
    ).json()["trace_calibration_version"] == CALIBRATION_VERSION
    assert client.post(
        f"/api/network-trace/electric_distribution/runs/{raw['trace_run_id']}/calibrate",
        json={"path": "C:/private/source.gdb"},
    ).status_code == 422
    with service.connect() as connection:
        after = {
            table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in before
        }
        assert connection.execute(
            "SELECT COUNT(*) FROM network_trace_calibration_history WHERE trace_run_id = ?",
            (raw["trace_run_id"],),
        ).fetchone()[0] == 4
        assert connection.execute(
            """SELECT COUNT(*) FROM network_trace_calibration_runs
            WHERE trace_run_id = ? AND status = 'succeeded'""", (raw["trace_run_id"],),
        ).fetchone()[0] == 2
    assert before == after
    assert str(tmp_path) not in first.text
