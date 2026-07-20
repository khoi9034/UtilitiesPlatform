from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def write_network_reports(network_summary: dict[str, Any], components: list[dict[str, Any]], reports_root: Path) -> None:
    (reports_root / "wastewater_network_summary.json").write_text(json.dumps(network_summary, indent=2), encoding="utf-8")
    with (reports_root / "wastewater_network_components.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["component_id", "pipe_count", "manhole_count", "pipe_objectids", "manhole_objectids"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for component in components:
            writer.writerow({field: component.get(field, "") for field in fields})
    lines = [
        "# Wastewater Network Analysis",
        "",
        "This is proximity-based connectivity analysis. It is not authoritative topology and is not an ArcGIS Utility Network.",
        "",
        f"- Total connected components: {network_summary.get('total_connected_components', 0)}",
        f"- Largest component size: {network_summary.get('largest_component_size', 0)}",
        f"- Isolated pipes: {network_summary.get('isolated_pipes', 0)}",
        f"- Isolated manholes: {network_summary.get('isolated_manholes', 0)}",
        f"- Matched pipe endpoints: {network_summary.get('matched_pipe_endpoints', 0)}",
        f"- Unmatched pipe endpoints: {network_summary.get('unmatched_pipe_endpoints', 0)}",
        f"- Endpoint match rate: {network_summary.get('endpoint_match_rate', 0):.2%}",
        f"- Average endpoint-to-manhole distance: {network_summary.get('average_endpoint_to_manhole_distance', 0)} source units",
        f"- Maximum endpoint-to-manhole distance: {network_summary.get('maximum_endpoint_to_manhole_distance', 0)} source units",
        "",
        "## Limitations",
        "",
        "- Source geometry may not be snapped.",
        "- Crossings do not automatically mean connectivity.",
        "- Force mains, lift stations, services, treatment facilities, and project records are not included in V1.",
        "- Flow direction depends on mapped invert fields and is not inferred from digitized geometry.",
    ]
    (reports_root / "wastewater_network_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_qa_summary(
    *,
    reports_root: Path,
    run_info: dict[str, Any],
    layer_meta: dict[str, Any],
    mapping_rows: list[dict[str, str]],
    rules_evaluated: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    network_summary: dict[str, Any],
    category_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    issues_by_severity = dict(Counter(issue["severity"] for issue in issues))
    issues_by_category = dict(Counter(issue["category"] for issue in issues))
    issues_by_rule = dict(Counter(issue["rule_code"] for issue in issues))
    summary = {
        **run_info,
        "staged_input_layers": list(layer_meta),
        "input_feature_counts": {layer: meta.get("record_count", 0) for layer, meta in layer_meta.items()},
        "spatial_reference": next((meta.get("spatial_reference", "") for meta in layer_meta.values()), ""),
        "mapped_semantic_fields": [row for row in mapping_rows if row["confidence"] != "unavailable"],
        "unavailable_semantic_fields": [row for row in mapping_rows if row["confidence"] == "unavailable"],
        "rules_evaluated": len(rules_evaluated),
        "rules_executed": sum(1 for row in rules_evaluated if row["status"] == "executed"),
        "rules_skipped": sum(1 for row in rules_evaluated if row["status"] == "skipped"),
        "rule_results": rules_evaluated,
        "total_issues": len(issues),
        "issues_by_severity": issues_by_severity,
        "issues_by_category": issues_by_category,
        "issues_by_rule": issues_by_rule,
        "affected_pipes": len({issue["source_objectid"] for issue in issues if issue["source_layer"] == "wastewater_gravity_main"}),
        "affected_manholes": len({issue["source_objectid"] for issue in issues if issue["source_layer"] == "wastewater_manhole"}),
        "endpoint_match_rate": network_summary.get("endpoint_match_rate", 0),
        "connected_component_count": network_summary.get("total_connected_components", 0),
        "largest_component_size": network_summary.get("largest_component_size", 0),
        "isolated_pipes": network_summary.get("isolated_pipes", 0),
        "isolated_manholes": network_summary.get("isolated_manholes", 0),
        "unmatched_endpoints": network_summary.get("unmatched_pipe_endpoints", 0),
        "category_metrics": category_metrics,
        "limitations": [
            "Proximity graph is not authoritative utility topology.",
            "No source geometry is snapped or repaired.",
            "WSACC_Subbasins_Cabarrus_Only remains review_required and is excluded from this QA run.",
            "Force mains, lift stations, service laterals, treatment facilities, inspections, and project records are not included in V1.",
        ],
        "recommended_next_actions": [
            "Review high-severity identity and endpoint issues first.",
            "Confirm semantic field mappings with the data steward.",
            "Normalize status, material, and diameter domains before curated promotion.",
        ],
    }
    (reports_root / "wastewater_qa_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (reports_root / "wastewater_qa_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            if isinstance(value, (str, int, float)):
                writer.writerow({"metric": key, "value": value})
    write_markdown_report(reports_root / "wastewater_qa_report.md", summary)
    return summary


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    top_rules = sorted(summary["issues_by_rule"].items(), key=lambda item: (-item[1], item[0]))[:10]
    lines = [
        "# Wastewater QA Report",
        "",
        f"- Run ID: {summary['run_id']}",
        f"- Run date: {summary['started_at']}",
        f"- Run status: {summary['run_status']}",
        f"- Total issues: {summary['total_issues']}",
        f"- Endpoint match rate: {summary['endpoint_match_rate']:.2%}",
        f"- Connected components: {summary['connected_component_count']}",
        f"- Largest component size: {summary['largest_component_size']}",
        "",
        "## Input Layers",
        *[f"- {layer}: {count} features" for layer, count in summary["input_feature_counts"].items()],
        "",
        "## Category Metrics",
    ]
    for category, metric in summary["category_metrics"].items():
        lines.append(f"- {category}: {metric.get('summary', '')}")
    lines += [
        "",
        "## Issues By Severity",
        *[f"- {severity}: {count}" for severity, count in sorted(summary["issues_by_severity"].items())],
        "",
        "## Issues By Category",
        *[f"- {category}: {count}" for category, count in sorted(summary["issues_by_category"].items())],
        "",
        "## Top Issue Rules",
        *[f"- {rule}: {count}" for rule, count in top_rules],
        "",
        "## Skipped Rules",
        *[
            f"- {rule['rule_code']}: {rule['skip_reason']}"
            for rule in summary["rule_results"]
            if rule["status"] == "skipped"
        ],
        "",
        "## Limitations",
        *[f"- {item}" for item in summary["limitations"]],
        "",
        "## Recommended Next Actions",
        *[f"- {item}" for item in summary["recommended_next_actions"]],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
