import json
from pathlib import Path

from gis.qa.wastewater.attribute_checks import invalid_diameter_issues
from gis.qa.wastewater.field_mapping import build_field_mapping, profiles_from_records
from gis.qa.wastewater.geometry_checks import feet_to_source_units, short_pipe_issues
from gis.qa.wastewater.identity_checks import duplicate_id_issues, missing_id_issues
from gis.qa.wastewater.issue_writer import dedupe_issues, make_issue
from gis.qa.wastewater.network_checks import analyze_network
from gis.qa.wastewater.run_wastewater_qa import support_skip_reason

ROOT = Path(__file__).resolve().parents[1]


def rule(code: str) -> dict:
    rules = json.loads((ROOT / "config" / "qa_rules" / "wastewater_v1.json").read_text(encoding="utf-8"))["rules"]
    return next(item for item in rules if item["rule_code"] == code)


def pipe(objectid: int, asset_id: str = "P1", geometry: dict | None = None, **attrs: object) -> dict:
    return {
        "objectid": objectid,
        "attributes": {"ASSET": asset_id, "DIA": attrs.get("diameter", 8), "UP": attrs.get("up", 10), "DOWN": attrs.get("down", 9)},
        "geometry": geometry or {"type": "polyline", "paths": [[[0, 0], [10, 0]]], "length": 10, "spatial_reference_wkid": 3857},
    }


def manhole(objectid: int, x: float, y: float, asset_id: str = "M1") -> dict:
    return {"objectid": objectid, "attributes": {"ASSET": asset_id}, "geometry": {"type": "point", "x": x, "y": y, "spatial_reference_wkid": 3857}}


def test_qa_rule_configuration_parses() -> None:
    config = json.loads((ROOT / "config" / "qa_rules" / "wastewater_v1.json").read_text(encoding="utf-8"))

    assert config["version"] == "wastewater_v1"
    assert {item["rule_code"] for item in config["rules"]} >= {"WW_ID_001", "WW_NET_001", "WW_FLOW_005"}


def test_field_mapping_confidence_and_unavailable_fields() -> None:
    fields = [
        {"name": "WSACC_ID", "alias": "WSACC_ID", "type": "String", "length": 20, "nullable": True, "required": False, "domain": ""},
        {"name": "SZ", "alias": "SZ", "type": "Integer", "length": 4, "nullable": True, "required": False, "domain": ""},
    ]
    profiles = profiles_from_records(fields, [{"WSACC_ID": "A", "SZ": 8}, {"WSACC_ID": "", "SZ": 10}])
    rows = build_field_mapping("wastewater_gravity_main", profiles)

    assert next(row for row in rows if row["semantic_role"] == "asset_id")["confidence"] == "high"
    assert next(row for row in rows if row["semantic_role"] == "project_id")["confidence"] == "unavailable"


def test_missing_and_duplicate_id_logic() -> None:
    records = [pipe(1, ""), pipe(2, "A"), pipe(3, "A")]

    assert len(missing_id_issues(records, "ASSET", rule("WW_ID_003"), "run", "now", "wastewater_gravity_main")) == 1
    assert len(duplicate_id_issues(records, "ASSET", rule("WW_ID_004"), "run", "now", "wastewater_gravity_main")) == 2


def test_invalid_diameter_logic() -> None:
    records = [pipe(1, "A", diameter=0), pipe(2, "B", diameter=8), pipe(3, "C", diameter=400)]

    issues = invalid_diameter_issues(records, "DIA", rule("WW_ATTR_004"), "run", "now", "ASSET")

    assert [issue["source_objectid"] for issue in issues] == ["1", "3"]


def test_unit_conversion_and_short_segment_logic() -> None:
    threshold = feet_to_source_units(5, "Meter")
    records = [pipe(1, "A", {"type": "polyline", "paths": [[[0, 0], [1, 0]]], "length": 1, "spatial_reference_wkid": 3857})]

    assert round(threshold, 4) == 1.524
    assert short_pipe_issues(records, threshold, "5 feet", rule("WW_GEOM_003"), "run", "now", "ASSET")


def test_endpoint_matching_warning_and_component_logic() -> None:
    rules = {code: rule(code) for code in ["WW_NET_001", "WW_NET_002", "WW_NET_003", "WW_NET_004", "WW_NET_005", "WW_NET_006", "WW_NET_007", "WW_NET_008"]}
    pipes = [pipe(1, "A", {"type": "polyline", "paths": [[[0, 0], [10, 0]]], "length": 10, "spatial_reference_wkid": 3857})]
    manholes = [manhole(1, 0.5, 0, "M1"), manhole(2, 100, 100, "M2")]

    summary, components, issues = analyze_network(pipes, manholes, rules, "run", "now", 1, 2, "1 unit", "2 units", "ASSET", "ASSET")

    assert summary["matched_pipe_endpoints"] == 1
    assert summary["unmatched_pipe_endpoints"] == 1
    assert summary["isolated_manholes"] == 1
    assert len(components) == 2
    assert {issue["rule_code"] for issue in issues} >= {"WW_NET_001", "WW_NET_003", "WW_NET_007"}


def test_duplicate_issue_prevention() -> None:
    sample = make_issue(
        run_id="run",
        created_at="now",
        rule=rule("WW_ID_003"),
        source_layer="wastewater_gravity_main",
        source_asset_id="A",
        source_objectid=1,
        description="duplicate",
        geometry={},
    )

    assert len(dedupe_issues([sample, sample])) == 1


def test_skipped_rule_explanations() -> None:
    rows = [{"source_layer": "wastewater_gravity_main", "semantic_role": "slope", "source_field": "", "confidence": "unavailable"}]

    assert "Required semantic field slope" in support_skip_reason(rule("WW_FLOW_005"), rows, {"wastewater_gravity_main": {}, "wastewater_manhole": {}})


def test_frontend_uses_reusable_utility_health_components() -> None:
    page = (ROOT / "frontend" / "app" / "data-health" / "page.tsx").read_text(encoding="utf-8")

    assert "function UtilityHealthSummary" in page
    assert "function IssueExplorer" in page
    assert "function UtilityMap" in page
