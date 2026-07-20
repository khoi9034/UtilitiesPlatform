import csv
import json
import sqlite3
from pathlib import Path

from gis.qa.wastewater.review_core import dependency_explanation, finding_class, issue_fingerprint
from gis.qa.wastewater.review_phase2 import (
    build_review_sample,
    calibration_rows,
    connect_review_db,
    standardization_mappings,
    sync_issue_reviews,
    write_phase2_reports,
)


def issue(**overrides: object) -> dict:
    row = {
        "issue_id": "issue-1",
        "rule_code": "WW_NET_001",
        "category": "Connectivity",
        "severity": "high",
        "confidence": "high",
        "utility_system": "wastewater",
        "source_layer": "wastewater_gravity_main",
        "source_asset_id": "",
        "source_objectid": "1",
        "related_asset_id": "",
        "related_objectid": "",
        "threshold_used": "3 feet",
        "run_id": "run-1",
        "created_at": "2026-07-20T00:00:00",
        "geometry": {"type": "point", "x": 10, "y": 20},
    }
    row.update(overrides)
    return row


def write_minimal_reports(root: Path) -> None:
    reports = root / "05_qa" / "reports"
    reports.mkdir(parents=True)
    issues = [issue(), issue(issue_id="issue-2", rule_code="WW_ATTR_006", category="Attributes", severity="low", source_objectid="2")]
    (reports / "wastewater_qa_issues.json").write_text(json.dumps({"issues": issues}), encoding="utf-8")
    (reports / "wastewater_qa_summary.json").write_text(json.dumps({"run_id": "run-1", "completed_at": "2026-07-20T00:00:00", "input_feature_counts": {"a": 2}}), encoding="utf-8")
    (reports / "wastewater_map_layers.json").write_text(
        json.dumps(
            {
                "pipes": [{"objectid": 1, "geometry": {"type": "polyline", "paths": [[[0, 0], [3, 4]]], "length": 5}}],
                "manholes": [{"objectid": 1, "geometry": {"type": "point", "x": 0, "y": 0}}],
            }
        ),
        encoding="utf-8",
    )
    with (reports / "wastewater_network_components.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["component_id", "pipe_count", "manhole_count", "pipe_objectids", "manhole_objectids"])
        writer.writeheader()
        writer.writerow({"component_id": "1", "pipe_count": "1", "manhole_count": "1", "pipe_objectids": "1", "manhole_objectids": "1"})
    with (reports / "wastewater_field_mapping.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_layer", "source_field", "field_alias", "semantic_role", "confidence", "null_percentage"])
        writer.writeheader()
        writer.writerow({"source_layer": "wastewater_gravity_main", "source_field": "SZ", "field_alias": "SZ", "semantic_role": "diameter", "confidence": "high", "null_percentage": "0"})


def test_issue_fingerprint_is_stable_and_collision_resistant() -> None:
    original = issue()
    repeat = issue(issue_id="new-run-issue", run_id="run-2")
    different_asset = issue(source_objectid="2")
    different_location = issue(geometry={"type": "point", "x": 11, "y": 20})

    assert issue_fingerprint(original) == issue_fingerprint(repeat)
    assert issue_fingerprint(original) != issue_fingerprint(different_asset)
    assert issue_fingerprint(original) != issue_fingerprint(different_location)


def test_duplicate_active_finding_prevention(tmp_path: Path) -> None:
    rows = [issue()]
    with connect_review_db(tmp_path) as connection:
        sync_issue_reviews(connection, rows, "run-1", "now")
        sync_issue_reviews(connection, rows, "run-1", "now")
        count = connection.execute("SELECT COUNT(*) FROM issue_reviews").fetchone()[0]
        occurrence_count = connection.execute("SELECT occurrence_count FROM issue_reviews").fetchone()[0]

    assert count == 1
    assert occurrence_count == 1


def test_source_limitation_classification_and_dependency_explanation() -> None:
    completeness = issue(rule_code="WW_ATTR_006", category="Attributes")
    connectivity = issue(rule_code="WW_NET_001")

    assert finding_class(completeness) == "attribute_completeness_gap"
    assert "Missing unknown data" in dependency_explanation(connectivity)


def test_calibration_sample_and_standardization_defaults() -> None:
    rows = [issue(), issue(issue_id="issue-2", rule_code="WW_ATTR_006", category="Attributes", severity="low", source_objectid="2")]
    rules = [{"rule_code": "WW_NET_001", "severity": "high", "parameters": {}}, {"rule_code": "WW_ATTR_006", "severity": "low", "parameters": {}}]
    mappings = standardization_mappings(
        [{"source_layer": "wastewater_gravity_main", "source_field": "SZ", "field_alias": "SZ", "semantic_role": "diameter", "confidence": "high"}]
    )

    assert calibration_rows(rows, rules)[0]["review_coverage"] == 0
    assert [item["issue_id"] for item in build_review_sample(rows, 42)] == [item["issue_id"] for item in build_review_sample(rows, 42)]
    assert mappings[0]["approved_to_standardize"] == "false"
    assert mappings[0]["unit_conversion"] == "requires confirmation"


def test_phase2_report_generation_does_not_enable_standardized_writes(tmp_path: Path) -> None:
    write_minimal_reports(tmp_path)

    result = write_phase2_reports(tmp_path, seed=7)
    readiness = json.loads((tmp_path / "05_qa" / "reports" / "wastewater_standardization_readiness.json").read_text(encoding="utf-8"))

    assert result["issues"] == 2
    assert result["components"] == 1
    assert readiness["writes_to_standardized_gdb"] is False
    assert readiness["writes_to_curated_gdb"] is False
    assert (tmp_path / "05_qa" / "review" / "wastewater_review.sqlite").exists()
    with sqlite3.connect(tmp_path / "05_qa" / "review" / "wastewater_review.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM issue_reviews").fetchone()[0] == 2
