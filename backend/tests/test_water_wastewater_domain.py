import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import source_adapters
from app.services.connectivity_qa.rules import (
    build_graph,
    evaluate_rule,
    rule_availability,
    rule_profile,
)
from app.services.network_trace.engine import trace_graph
from app.services.network_trace.models import normalize_request
from app.services.network_trace.profiles import trace_definition, trace_types
from app.services.proposed_edits.engine import catalog as proposal_catalog
from app.services.source_inspection.models import SourceLayer
from app.services.source_inspection.normalization import classify_layer
from app.services.utility_assets.domain import taxonomy
from app.services.work_orders.engine import catalog as work_order_catalog

client = TestClient(app)


def _asset(vertical: str, asset_id: str, asset_class: str, **attributes: object) -> dict:
    return {
        "asset_id": asset_id,
        "canonical_name": asset_id,
        "source_asset_identifier": attributes.pop("source_asset_identifier", asset_id),
        "utility_vertical": vertical,
        "asset_class": asset_class,
        "geometry_type": attributes.pop("geometry_type", "polyline" if "main" in asset_class or "line" in asset_class else "point"),
        "lifecycle_status": attributes.pop("lifecycle_status", "active"),
        "operational_status": attributes.pop("operational_status", "active"),
        "owner_candidate": "Synthetic Utility",
        "geometry_summary_json": {"spatial_reference": "Synthetic local grid"},
        "canonical_attributes_json": attributes,
    }


def _trace(vertical: str, trace_type: str, start: str, assets: list[dict], relationships: list[dict]) -> dict:
    request = normalize_request(
        vertical,
        {
            "trace_type": trace_type,
            "start_asset_id": start,
            "direction": trace_definition(vertical, trace_type)["default_direction"],
        },
        {item["trace_type"] for item in trace_types(vertical)["items"]},
    )
    graph = {
        "vertical": vertical,
        "nodes": {item["asset_id"]: item for item in assets},
        "selected": assets,
        "selected_ids": {item["asset_id"] for item in assets},
        "relationships": relationships,
        "adjacency": {},
        "edge_by_asset": {},
    }
    return trace_graph(request, trace_definition(vertical, trace_type), graph, [])


def test_domain_taxonomy_and_ambiguous_sewer_classification() -> None:
    shared = taxonomy()
    water = taxonomy("water")
    wastewater = taxonomy("wastewater")
    layer = SourceLayer(
        layer_id="synthetic-sewer",
        submission_id="synthetic-submission",
        container_id="synthetic-container",
        source_layer_name="Sewer_Line",
        geometry_type="polyline",
        field_profile=[{"name": "asset_id"}, {"name": "diameter"}],
    )
    candidates = classify_layer(layer, {"source_owner": "Synthetic Utility"})

    assert {"water", "wastewater", "water_wastewater", "multi_utility", "unknown"} <= set(shared["source_utility_domains"])
    assert {"water_main", "hydrant", "pressure_zone"} <= set(water["asset_classes"])
    assert {"gravity_main", "force_main", "lift_station", "sewer_basin"} <= set(wastewater["asset_classes"])
    assert {item.asset_subcategory for item in candidates[:2]} == {"gravity_main", "force_main"}
    assert all(item.confidence == "low" for item in candidates[:2])
    assert layer.routing_state == "needs_taxonomy_review"


def test_rule_catalogs_are_complete_and_unavailable_evidence_skips() -> None:
    water = rule_profile("water")
    wastewater = rule_profile("wastewater")
    graph = build_graph(
        "wastewater",
        [_asset("wastewater", "ww-1", "gravity_main")],
        [_asset("wastewater", "ww-1", "gravity_main")],
        [],
    )
    slope = next(item for item in wastewater if item["rule_code"] == "WW-010")

    assert len(water) == 26
    assert len(wastewater) == 28
    assert {item["rule_code"] for item in water} >= {"WATER-001", "WATER-018"}
    assert {item["rule_code"] for item in wastewater} >= {"WW-001", "WW-020"}
    assert rule_availability(slope, graph) == (
        False,
        "Unable to determine: required evidence is unavailable (slope).",
    )


def test_water_and_wastewater_findings_are_conservative() -> None:
    water_assets = [
        _asset("water", "main", "water_main", diameter=8, material="PVC"),
        _asset("water", "service-a", "service_line", source_asset_identifier="DUP"),
        _asset("water", "service-b", "service_line", source_asset_identifier="DUP"),
    ]
    water_graph = build_graph("water", water_assets, water_assets, [])
    duplicate = next(item for item in rule_profile("water") if item["rule_code"] == "WATER-002")
    isolated = next(item for item in rule_profile("water") if item["rule_code"] == "WATER-010")

    wastewater_assets = [
        _asset(
            "wastewater",
            "gravity",
            "gravity_main",
            diameter=8,
            material="PVC",
            slope=-0.1,
            upstream_invert=100,
            downstream_invert=101,
        ),
        _asset("wastewater", "manhole", "manhole"),
    ]
    wastewater_graph = build_graph("wastewater", wastewater_assets, wastewater_assets, [])
    slope = next(item for item in rule_profile("wastewater") if item["rule_code"] == "WW-010")
    invert = next(item for item in rule_profile("wastewater") if item["rule_code"] == "WW-012")

    assert len(evaluate_rule(duplicate, water_graph)) == 1
    assert len(evaluate_rule(isolated, water_graph)) == 2
    assert len(evaluate_rule(slope, wastewater_graph)) == 1
    assert len(evaluate_rule(invert, wastewater_graph)) == 1


def test_water_valve_and_wastewater_downstream_traces_are_read_only() -> None:
    water_assets = [
        _asset("water", "valve", "isolation_valve", operational_status="closed"),
        _asset("water", "main", "water_main"),
        _asset("water", "service", "service_line"),
    ]
    water_relationships = [
        {"relationship_id": "w1", "from_asset_id": "valve", "to_asset_id": "main", "relationship_type": "connects_to", "direction": "forward", "provisional": False},
        {"relationship_id": "w2", "from_asset_id": "main", "to_asset_id": "service", "relationship_type": "feeds", "direction": "forward", "provisional": False},
    ]
    before = json.dumps([water_assets, water_relationships], sort_keys=True)
    water = _trace("water", "WATER-TRACE-005", "valve", water_assets, water_relationships)

    wastewater_assets = [
        _asset("wastewater", "mh", "manhole"),
        _asset("wastewater", "main", "gravity_main"),
        _asset("wastewater", "plant", "treatment_facility"),
    ]
    wastewater_relationships = [
        {"relationship_id": "s1", "from_asset_id": "mh", "to_asset_id": "main", "relationship_type": "flows_to", "direction": "forward", "provisional": False},
        {"relationship_id": "s2", "from_asset_id": "main", "to_asset_id": "plant", "relationship_type": "flows_to", "direction": "forward", "provisional": False},
    ]
    wastewater = _trace("wastewater", "WW-TRACE-001", "mh", wastewater_assets, wastewater_relationships)

    assert water["outcome"] == "complete"
    assert water["paths"][0]["end_asset_id"] == "service"
    assert wastewater["outcome"] == "complete"
    assert wastewater["paths"][0]["stopping_reason"] == "terminal_reached"
    assert json.dumps([water_assets, water_relationships], sort_keys=True) == before
    assert trace_definition("water", "WATER-TRACE-005")["hydraulic_simulation"] is False


def test_catalogs_adapters_and_safe_apis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "smart_ds_manifest.json").read_text(encoding="utf-8")
    )
    smart_ds = source_adapters.inspect_manifest("nrel_smart_ds", fixture)

    assert smart_ds["status"] == "dry_run_complete"
    assert smart_ds["records_read"] == smart_ds["records_written"] == 0
    assert smart_ds["approved_for_import"] is False
    assert "add_main" in proposal_catalog("water")["proposal_types"]
    assert "add_gravity_main" in proposal_catalog("wastewater")["proposal_types"]
    assert "hydrant_and_valve_installation" in work_order_catalog("water")["work_order_types"]
    assert "emergency_blockage_repair" in work_order_catalog("wastewater")["work_order_types"]

    for metadata in (
        {"note": "C:\\private\\source"},
        {"Path": "private-source"},
        {"Source_Path": "private-source"},
        {"note": "../private/source"},
        {"note": "file:///private/source"},
    ):
        with pytest.raises(ValueError, match="Filesystem"):
            source_adapters.inspect_manifest("nrel_smart_ds", {**fixture, "metadata": metadata})
    with pytest.raises(ValueError, match="physical OSP"):
        source_adapters.inspect_manifest(
            "fcc_broadband_availability",
            {
                "source_type": "fcc_broadband_availability",
                "source_role": "service_availability",
                "domain": "telecom_fiber",
                "datasets": [{"source_asset_type": "coverage", "canonical_asset_class": "fiber_cable"}],
            },
        )

    domain = client.get("/api/utility-domains/water-wastewater/summary")
    adapters = client.get("/api/source-adapters")
    assert domain.status_code == adapters.status_code == 200
    assert domain.json()["canonical_assets"] == 0
    assert domain.json()["human_approval_required"] is True
    assert str(tmp_path) not in domain.text
    assert "C:\\\\" not in adapters.text
