import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.connectivity_qa import service as connectivity_qa
from app.services.network_trace import service
from app.services.network_trace.engine import trace_graph
from app.services.network_trace.models import normalize_request
from app.services.network_trace.profiles import relationship_category, trace_definition, trace_types

client = TestClient(app)


def _asset(asset_id: str, asset_class: str, **values: object) -> dict:
    return {
        "asset_id": asset_id,
        "canonical_name": asset_id,
        "utility_vertical": "electric_distribution",
        "asset_class": asset_class,
        "lifecycle_status": values.pop("lifecycle_status", "active"),
        "operational_status": values.pop("operational_status", "energized"),
        "canonical_attributes_json": values,
    }


def _request(**values: object) -> dict:
    payload = {
        "trace_type": "ELEC-TRACE-001",
        "start_asset_id": "feeder",
        "direction": "downstream",
        **values,
    }
    return normalize_request(
        "electric_distribution",
        payload,
        {item["trace_type"] for item in trace_types("electric_distribution")["items"]},
    )


def _graph(assets: list[dict], relationships: list[dict]) -> dict:
    return {
        "vertical": "electric_distribution",
        "nodes": {item["asset_id"]: item for item in assets},
        "selected": assets,
        "selected_ids": {item["asset_id"] for item in assets},
        "relationships": relationships,
        "adjacency": {},
        "edge_by_asset": {},
    }


def _relationship(left: str, right: str, relation_id: str, provisional: bool = False) -> dict:
    return {
        "relationship_id": relation_id,
        "from_asset_id": left,
        "to_asset_id": right,
        "relationship_type": "feeds",
        "direction": "forward",
        "provisional": provisional,
    }


def _calibrated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    for vertical in ("electric_distribution", "telecom_fiber"):
        qa = connectivity_qa.run(vertical, {"actor": "trace test"})
        connectivity_qa.calibrate(vertical, qa["qa_run_id"], {"actor": "trace test"})


def test_trace_profiles_and_relationship_semantics_are_allowlisted() -> None:
    electric = trace_types("electric_distribution")
    telecom = trace_types("telecom_fiber")

    assert len(electric["items"]) == 7
    assert len(telecom["items"]) == 8
    assert relationship_category("feeds") == "operational_flow"
    assert relationship_category("routed_through") == "containment_context"
    assert relationship_category("reference_for") == "reference_context"
    assert relationship_category("made_up") == "prohibited_relationship"
    with pytest.raises(ValueError, match="Unsupported"):
        trace_definition("electric_distribution", "TEL-TRACE-001")


def test_request_rejects_executable_inputs_and_unbounded_limits() -> None:
    with pytest.raises(ValueError, match="filesystem"):
        _request(path="C:/private/source.gdb")
    with pytest.raises(ValueError, match="between"):
        _request(max_assets=1001)
    with pytest.raises(ValueError, match="must be one of"):
        _request(qa_policy="run_python")
    with pytest.raises(ValueError, match="Unsupported"):
        _request(graph_definition={"nodes": []})


def test_open_device_stops_without_changing_the_graph() -> None:
    assets = [
        _asset("feeder", "feeder", feeder_id="F-1", phase="ABC", operating_voltage=12.47),
        _asset("switch", "switch", operational_status="normally_open", feeder_id="F-1", phase="ABC", operating_voltage=12.47),
        _asset("service", "service_point", feeder_id="F-1", phase="A", operating_voltage=12.47),
    ]
    relationships = [_relationship("feeder", "switch", "r1"), _relationship("switch", "service", "r2")]
    before = json.dumps({"assets": assets, "relationships": relationships}, sort_keys=True)

    result = trace_graph(_request(), trace_definition("electric_distribution", "ELEC-TRACE-001"), _graph(assets, relationships), [])

    assert result["outcome"] == "blocked"
    assert result["paths"][0]["stopping_reason"] == "open_device"
    assert json.dumps({"assets": assets, "relationships": relationships}, sort_keys=True) == before


def test_branching_is_deterministic_and_not_automatically_ambiguous() -> None:
    assets = [
        _asset("feeder", "feeder", feeder_id="F-1"),
        _asset("left", "service_point", feeder_id="F-1"),
        _asset("right", "service_point", feeder_id="F-1"),
    ]
    relationships = [_relationship("feeder", "right", "r2"), _relationship("feeder", "left", "r1")]

    result = trace_graph(_request(), trace_definition("electric_distribution", "ELEC-TRACE-001"), _graph(assets, relationships), [])

    assert result["outcome"] == "complete"
    assert [item["end_asset_id"] for item in result["paths"]] == ["left", "right"]
    assert any(event["event_type"] == "branch_detected" for event in result["events"])


def test_calibrated_trace_effects_and_provisional_policy() -> None:
    assets = [_asset("feeder", "feeder"), _asset("service", "service_point")]
    relationships = [_relationship("feeder", "service", "r1", provisional=True)]
    group = {
        "issue_group_id": "group-1",
        "affected_asset_ids": ["service"],
        "affected_relationship_ids": [],
        "trace_impact": "stops_trace",
        "trace_impact_reason": "Synthetic blocking evidence.",
        "review_status": "open",
    }
    strict = trace_graph(_request(), trace_definition("electric_distribution", "ELEC-TRACE-001"), _graph(assets, relationships), [group])
    diagnostic = trace_graph(_request(qa_policy="diagnostic"), trace_definition("electric_distribution", "ELEC-TRACE-001"), _graph(assets, relationships), [group])
    excluded = trace_graph(_request(provisional_relationship_policy="exclude"), trace_definition("electric_distribution", "ELEC-TRACE-001"), _graph(assets, relationships), [])
    only_path = trace_graph(_request(provisional_relationship_policy="require_when_only_path"), trace_definition("electric_distribution", "ELEC-TRACE-001"), _graph(assets, relationships), [])

    assert strict["outcome"] == "blocked"
    assert diagnostic["outcome"] == "complete_with_warnings"
    assert diagnostic["provisional_segments"] == 1
    assert excluded["outcome"] == "no_path"
    assert only_path["outcome"] == "complete_with_warnings"


def test_lifecycle_limits_cycles_and_closed_device_behavior() -> None:
    assets = [
        _asset("feeder", "feeder"),
        _asset("switch", "switch", operational_status="closed"),
        _asset("service", "service_point", lifecycle_status="retired"),
    ]
    relationships = [
        _relationship("feeder", "switch", "r1"),
        _relationship("switch", "service", "r2"),
        _relationship("switch", "feeder", "r-cycle"),
    ]
    graph = _graph(assets, relationships)
    active = trace_graph(_request(), trace_definition("electric_distribution", "ELEC-TRACE-001"), graph, [])
    historical = trace_graph(
        _request(lifecycle_mode="historical", operational_mode="diagnostic"),
        trace_definition("electric_distribution", "ELEC-TRACE-001"),
        graph,
        [],
    )
    limited = trace_graph(
        _request(max_depth=1),
        trace_definition("electric_distribution", "ELEC-TRACE-001"),
        graph,
        [],
    )

    assert active["outcome"] == "blocked"
    assert historical["outcome"] == "complete"
    assert historical["confidence"] == "medium"
    assert any(event["event_type"] == "cycle_detected" for event in historical["events"])
    assert limited["paths"][0]["stopping_reason"] == "maximum_depth"


def test_persisted_trace_reuse_force_history_and_safe_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _calibrated_root(tmp_path, monkeypatch)
    with service.connect() as connection:
        start_id = connection.execute(
            "SELECT asset_id FROM canonical_utility_assets WHERE canonical_name = 'ELEC-FEEDER-001'"
        ).fetchone()[0]
        geometry_before = connection.execute(
            "SELECT asset_id, geometry_summary_json FROM canonical_utility_assets ORDER BY asset_id"
        ).fetchall()
    payload = {
        "trace_type": "ELEC-TRACE-001",
        "start_asset_id": start_id,
        "qa_policy": "diagnostic",
        "requested_by": "Synthetic Reviewer",
    }
    first = client.post("/api/network-trace/electric_distribution/runs", json=payload)
    second = client.post("/api/network-trace/electric_distribution/runs", json=payload)
    forced = client.post(
        "/api/network-trace/electric_distribution/runs",
        json={**payload, "force_recalculate": True},
    )

    assert first.status_code == second.status_code == forced.status_code == 200
    assert first.json()["trace_run_id"] == second.json()["trace_run_id"]
    assert second.json()["reused"] is True
    assert forced.json()["trace_run_id"] != first.json()["trace_run_id"]
    assert [item["action"] for item in first.json()["history"]] == ["run_started", "run_completed"]
    with service.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM network_trace_runs WHERE request_fingerprint = "
            "(SELECT request_fingerprint FROM network_trace_runs WHERE trace_run_id = ?)",
            (first.json()["trace_run_id"],),
        ).fetchone()[0] == 2
        connection.execute(
            """UPDATE utility_asset_relationships SET confidence = 'medium'
            WHERE relationship_id = (
                SELECT r.relationship_id FROM utility_asset_relationships r
                JOIN canonical_utility_assets a ON a.asset_id = r.from_asset_id
                WHERE a.utility_vertical = 'electric_distribution'
                ORDER BY r.relationship_id LIMIT 1
            )"""
        )
        connection.commit()
    changed_graph = client.post("/api/network-trace/electric_distribution/runs", json=payload).json()
    assert changed_graph["trace_run_id"] not in {first.json()["trace_run_id"], forced.json()["trace_run_id"]}
    assert client.get(f"/api/network-trace/electric_distribution/runs/{first.json()['trace_run_id']}/steps").status_code == 200
    receipt = client.get(f"/api/network-trace/electric_distribution/runs/{first.json()['trace_run_id']}/safe-summary")
    assert receipt.status_code == 200
    assert receipt.json()["ordered_safe_asset_ids"]
    assert receipt.json()["input_fingerprint"]
    assert receipt.json()["trace_profile_version"] == "network-trace-profiles-v1"
    assert client.get(f"/api/network-trace/assets/{start_id}/readiness").json()["eligible_trace_types"]
    assert "source_attributes_json" not in first.text
    assert "geometry_reference" not in first.text
    assert str(tmp_path) not in first.text
    with service.connect() as connection:
        geometry_after = connection.execute(
            "SELECT asset_id, geometry_summary_json FROM canonical_utility_assets ORDER BY asset_id"
        ).fetchall()
    assert [(row[0], row[1]) for row in geometry_before] == [(row[0], row[1]) for row in geometry_after]


def test_synthetic_expectation_manifest_runs_without_engine_asset_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _calibrated_root(tmp_path, monkeypatch)
    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "config" / "network_trace_synthetic_expectations.json").read_text()
    )
    with service.connect() as connection:
        asset_ids = {
            row["canonical_name"]: row["asset_id"]
            for row in connection.execute("SELECT asset_id, canonical_name FROM canonical_utility_assets")
        }
    outcomes: dict[str, str] = {}
    for vertical in ("electric_distribution", "telecom_fiber"):
        for scenario in manifest[vertical]:
            payload = {
                key: value for key, value in scenario.items()
                if key not in {"scenario", "start_name", "target_name", "expected_outcomes"}
            }
            payload["start_asset_id"] = asset_ids[scenario["start_name"]]
            if scenario.get("target_name"):
                payload["optional_target_asset_id"] = asset_ids[scenario["target_name"]]
            result = service.run(vertical, payload)
            outcomes[f"{vertical}:{scenario['scenario']}"] = result["outcome"]
            assert result["outcome"] in scenario["expected_outcomes"]
    assert len(outcomes) == 20
