from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "data_storage"))

from common import load_config
from gis.qa.wastewater.attribute_checks import (
    conflicting_status_issues,
    invalid_diameter_issues,
    invalid_domain_issues,
    missing_field_issues,
    safe_asset_id,
)
from gis.qa.wastewater.field_mapping import (
    build_field_mapping,
    mapping_lookup,
    profiles_from_records,
    role_available,
    write_mapping_reports,
)
from gis.qa.wastewater.flow_checks import missing_invert_issues, slope_conflict_issues, slope_issues, uphill_issues
from gis.qa.wastewater.geometry_checks import (
    duplicate_geometry_issues,
    feet_to_source_units,
    invalid_geometry_issues,
    multipart_issues,
    null_geometry_issues,
    pipe_anomaly_issues,
    short_pipe_issues,
)
from gis.qa.wastewater.identity_checks import duplicate_id_issues, identity_metrics, missing_id_issues
from gis.qa.wastewater.issue_writer import append_processing_history, dedupe_issues, now_iso, write_geodatabase_issues, write_issue_files
from gis.qa.wastewater.network_checks import analyze_network
from gis.qa.wastewater.summarize_results import write_network_reports, write_qa_summary

SCRIPT_VERSION = "wastewater_data_health_v1"
PIPE_LAYER = "wastewater_gravity_main"
MANHOLE_LAYER = "wastewater_manhole"


def parse_args() -> argparse.Namespace:
    config = load_config()
    parser = argparse.ArgumentParser(description="Run Wastewater Data Health V1 against staged gravity mains and manholes.")
    parser.add_argument("--execute", action="store_true", help="Required to write reports and QA geodatabase outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Preview the QA run without writing outputs.")
    parser.add_argument("--rules", default=str(REPO_ROOT / "config" / "qa_rules" / "wastewater_v1.json"))
    parser.add_argument("--output-gdb", default=str(config.qa_root / "Wastewater_QA.gdb"))
    parser.add_argument("--reports-root", default=str(config.qa_root / "reports"))
    parser.add_argument("--endpoint-tolerance", type=float, help="Endpoint match tolerance in feet.")
    parser.add_argument("--warning-tolerance", type=float, help="Endpoint warning tolerance in feet.")
    parser.add_argument("--short-pipe-threshold", type=float, help="Short pipe threshold in feet.")
    parser.add_argument("--replace-output", action="store_true", help="Replace generated QA feature classes if they already exist.")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    execute = args.execute and not args.dry_run
    run_id = str(uuid.uuid4())
    started_at = now_iso()
    config = load_config()
    staging_gdb = config.staging_geodatabase
    reports_root = Path(args.reports_root)
    output_gdb = Path(args.output_gdb)
    rules_config = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    defaults = rules_config.get("defaults", {})
    endpoint_feet = args.endpoint_tolerance if args.endpoint_tolerance is not None else float(defaults.get("endpoint_tolerance_feet", 3))
    warning_feet = args.warning_tolerance if args.warning_tolerance is not None else float(defaults.get("warning_tolerance_feet", 10))
    short_feet = args.short_pipe_threshold if args.short_pipe_threshold is not None else float(defaults.get("short_pipe_threshold_feet", 5))

    try:
        import arcpy  # type: ignore
    except ImportError:
        logging.error("ArcPy is required. Run with ArcGIS Pro Python.")
        return 1

    layers = {
        PIPE_LAYER: staging_gdb / PIPE_LAYER,
        MANHOLE_LAYER: staging_gdb / MANHOLE_LAYER,
    }
    missing = [str(path) for path in layers.values() if not arcpy.Exists(str(path))]
    if missing:
        logging.error("Missing staged wastewater layers: %s", "; ".join(missing))
        return 1

    extracted: dict[str, dict[str, Any]] = {}
    for layer_name, path in layers.items():
        extracted[layer_name] = extract_layer(arcpy, layer_name, path)
    spatial_reference_wkid = next((meta["spatial_reference_wkid"] for meta in (item["meta"] for item in extracted.values()) if meta["spatial_reference_wkid"]), 3857)
    linear_unit = extracted[PIPE_LAYER]["meta"].get("linear_unit", "Meter")
    endpoint_units = feet_to_source_units(endpoint_feet, linear_unit)
    warning_units = feet_to_source_units(warning_feet, linear_unit)
    short_units = feet_to_source_units(short_feet, linear_unit)
    threshold_labels = {
        "endpoint": f"{endpoint_feet:g} feet ({endpoint_units:.3f} {linear_unit})",
        "warning": f"{warning_feet:g} feet ({warning_units:.3f} {linear_unit})",
        "short": f"{short_feet:g} feet ({short_units:.3f} {linear_unit})",
    }

    mapping_rows: list[dict[str, str]] = []
    layer_meta: dict[str, Any] = {}
    domain_values: dict[str, dict[str, set[str]]] = {}
    for layer_name, data in extracted.items():
        profiles = profiles_from_records(data["fields"], data["records"])
        mapping_rows.extend(build_field_mapping(layer_name, profiles))
        layer_meta[layer_name] = data["meta"] | {"fields": data["fields"], "profiles": {name: profile.__dict__ for name, profile in profiles.items()}}
        domain_values[layer_name] = data["domain_values"]

    rules = {rule["rule_code"]: rule for rule in rules_config["rules"] if rule.get("enabled", True)}
    pipe_map = mapping_lookup(mapping_rows, PIPE_LAYER)
    manhole_map = mapping_lookup(mapping_rows, MANHOLE_LAYER)
    pipes = extracted[PIPE_LAYER]["records"]
    manholes = extracted[MANHOLE_LAYER]["records"]
    issues: list[dict[str, Any]] = []
    rule_results: list[dict[str, Any]] = []

    for rule in rules_config["rules"]:
        if not rule.get("enabled", True):
            rule_results.append(rule_result(rule, "skipped", "Rule disabled.", 0))
            continue
        code = rule["rule_code"]
        before = len(issues)
        skip_reason = support_skip_reason(rule, mapping_rows, domain_values)
        if skip_reason:
            rule_results.append(rule_result(rule, "skipped", skip_reason, 0))
            continue
        if code.startswith("WW_NET_"):
            continue
        dispatch_rule(code, rule, issues, pipes, manholes, pipe_map, manhole_map, domain_values, run_id, started_at, short_units, threshold_labels)
        rule_results.append(rule_result(rule, "executed", "", len(issues) - before))

    network_summary, components, network_issues = analyze_network(
        pipes,
        manholes,
        rules,
        run_id,
        started_at,
        endpoint_units,
        warning_units,
        threshold_labels["endpoint"],
        threshold_labels["warning"],
        pipe_map.get("asset_id"),
        manhole_map.get("asset_id"),
        int(defaults.get("high_endpoint_degree", 6)),
    )
    issues.extend(network_issues)
    by_code = Counter(issue["rule_code"] for issue in network_issues)
    for rule in rules_config["rules"]:
        if rule.get("enabled", True) and rule["rule_code"].startswith("WW_NET_"):
            rule_results.append(rule_result(rule, "executed", "", by_code.get(rule["rule_code"], 0)))

    issues = dedupe_issues(issues)
    completed_at = now_iso()
    run_info = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "run_status": "completed",
        "script_version": SCRIPT_VERSION,
        "dry_run": not execute,
        "endpoint_tolerance": threshold_labels["endpoint"],
        "warning_tolerance": threshold_labels["warning"],
        "short_pipe_threshold": threshold_labels["short"],
    }
    category_metrics = build_category_metrics(pipes, manholes, pipe_map, manhole_map, issues, network_summary)

    if not execute:
        logging.info("Dry run complete. %s issue(s) would be written. Add --execute to create outputs.", len(issues))
        return 0

    reports_root.mkdir(parents=True, exist_ok=True)
    write_mapping_reports(
        mapping_rows,
        reports_root / "wastewater_field_mapping.csv",
        reports_root / "wastewater_field_mapping.json",
        reports_root / "wastewater_schema_review.md",
        layer_meta,
    )
    write_issue_files(issues, reports_root / "wastewater_qa_issues.csv", reports_root / "wastewater_qa_issues.json", reports_root / "wastewater_qa_issues.geojson")
    write_network_reports(network_summary, components, reports_root)
    write_qa_summary(
        reports_root=reports_root,
        run_info=run_info,
        layer_meta=layer_meta,
        mapping_rows=mapping_rows,
        rules_evaluated=rule_results,
        issues=issues,
        network_summary=network_summary,
        category_metrics=category_metrics,
    )
    write_map_layers(reports_root / "wastewater_map_layers.json", pipes, manholes, issues)
    gdb_counts = write_geodatabase_issues(output_gdb, issues, spatial_reference_wkid, replace_output=args.replace_output)
    append_history(config.processing_history, run_id, layers, output_gdb, started_at, completed_at, extracted, len(issues), gdb_counts)
    logging.info("Wastewater QA complete. Run %s wrote %s issues.", run_id, len(issues))
    return 0


def extract_layer(arcpy: Any, layer_name: str, path: Path) -> dict[str, Any]:
    description = arcpy.Describe(str(path))
    fields = [
        {
            "name": field.name,
            "alias": field.aliasName,
            "type": field.type,
            "length": field.length,
            "nullable": bool(field.isNullable),
            "required": bool(field.required),
            "domain": field.domain or "",
        }
        for field in arcpy.ListFields(str(path))
    ]
    attribute_fields = [field["name"] for field in fields if field["type"] not in {"Geometry", "Blob", "Raster", "OID"}]
    records = []
    cursor_fields = ["OID@", "SHAPE@"] + attribute_fields
    with arcpy.da.SearchCursor(str(path), cursor_fields) as cursor:
        for row in cursor:
            objectid, geometry, *values = row
            attributes = dict(zip(attribute_fields, values))
            records.append({"objectid": objectid, "attributes": attributes, "geometry": serialize_geometry(geometry, description)})
    meta = {
        "layer_name": layer_name,
        "record_count": len(records),
        "geometry_type": getattr(description, "shapeType", ""),
        "spatial_reference": getattr(getattr(description, "spatialReference", None), "name", ""),
        "spatial_reference_wkid": int(getattr(getattr(description, "spatialReference", None), "factoryCode", 3857) or 3857),
        "linear_unit": getattr(getattr(description, "spatialReference", None), "linearUnitName", ""),
        "has_z": bool(getattr(description, "hasZ", False)),
        "has_m": bool(getattr(description, "hasM", False)),
        "editor_tracking_enabled": bool(getattr(description, "editorTrackingEnabled", False)),
        "attachments": bool(getattr(description, "hasAttachments", False)),
        "globalid": getattr(description, "globalIDFieldName", ""),
        "indexes": [index_info(index) for index in arcpy.ListIndexes(str(path))],
        "subtypes": {str(key): value.get("Name", "") for key, value in arcpy.da.ListSubtypes(str(path)).items()},
    }
    return {"fields": fields, "records": records, "meta": meta, "domain_values": layer_domains(arcpy, path, fields)}


def serialize_geometry(geometry: Any, description: Any) -> dict[str, Any]:
    wkid = int(getattr(getattr(description, "spatialReference", None), "factoryCode", 3857) or 3857)
    if geometry is None:
        return {"type": getattr(description, "shapeType", "").lower(), "is_empty": True, "spatial_reference_wkid": wkid}
    if getattr(description, "shapeType", "") == "Point":
        point = geometry.firstPoint
        return {
            "type": "point",
            "x": float(point.X),
            "y": float(point.Y),
            "is_empty": bool(getattr(geometry, "isEmpty", False)),
            "is_multipart": False,
            "spatial_reference_wkid": wkid,
        }
    paths = []
    for part in geometry:
        coords = [[float(point.X), float(point.Y)] for point in part if point]
        if coords:
            paths.append(coords)
    return {
        "type": "polyline",
        "paths": paths,
        "length": float(getattr(geometry, "length", 0) or 0),
        "is_empty": bool(getattr(geometry, "isEmpty", False)) or not paths,
        "is_multipart": bool(getattr(geometry, "isMultipart", False)),
        "spatial_reference_wkid": wkid,
    }


def index_info(index: Any) -> dict[str, Any]:
    return {
        "name": index.name,
        "fields": [getattr(field, "name", str(field)) for field in index.fields],
        "unique": bool(index.isUnique),
        "ascending": bool(index.isAscending),
    }


def layer_domains(arcpy: Any, path: Path, fields: list[dict[str, Any]]) -> dict[str, set[str]]:
    workspace = path.parent
    domains = {domain.name: set(getattr(domain, "codedValues", {}).keys()) for domain in arcpy.da.ListDomains(str(workspace))}
    return {field["name"]: domains[field["domain"]] for field in fields if field.get("domain") in domains}


def support_skip_reason(rule: dict[str, Any], mapping_rows: list[dict[str, str]], domain_values: dict[str, dict[str, set[str]]]) -> str:
    targets = target_layers(rule)
    for target in targets:
        if target == "network":
            continue
        for required in rule.get("required_semantic_fields", []):
            if required == "geometry":
                continue
            if required == "domain_fields":
                if not any(domain_values.values()):
                    return "No ArcGIS domains are present on staged wastewater fields."
                continue
            if not role_available(mapping_rows, target, required):
                return f"Required semantic field {required} is unavailable for {target}."
        if rule["rule_code"] == "WW_ATTR_008":
            lookup = mapping_lookup(mapping_rows, target)
            if lookup.get("lifecycle_status") == lookup.get("operational_status"):
                return f"Lifecycle and operational status map to the same source field for {target}."
    return ""


def target_layers(rule: dict[str, Any]) -> list[str]:
    applicable = rule["applicable_layer"]
    if applicable == "both":
        return [PIPE_LAYER, MANHOLE_LAYER]
    if applicable == "network":
        return ["network"]
    return [applicable]


def dispatch_rule(
    code: str,
    rule: dict[str, Any],
    issues: list[dict[str, Any]],
    pipes: list[dict[str, Any]],
    manholes: list[dict[str, Any]],
    pipe_map: dict[str, str],
    manhole_map: dict[str, str],
    domain_values: dict[str, dict[str, set[str]]],
    run_id: str,
    created_at: str,
    short_units: float,
    threshold_labels: dict[str, str],
) -> None:
    if code == "WW_ID_001":
        issues.extend(missing_id_issues(manholes, manhole_map["asset_id"], rule, run_id, created_at, MANHOLE_LAYER))
    elif code == "WW_ID_002":
        issues.extend(duplicate_id_issues(manholes, manhole_map["asset_id"], rule, run_id, created_at, MANHOLE_LAYER))
    elif code == "WW_ID_003":
        issues.extend(missing_id_issues(pipes, pipe_map["asset_id"], rule, run_id, created_at, PIPE_LAYER))
    elif code == "WW_ID_004":
        issues.extend(duplicate_id_issues(pipes, pipe_map["asset_id"], rule, run_id, created_at, PIPE_LAYER))
    elif code in {"WW_ATTR_001", "WW_ATTR_002", "WW_ATTR_003"}:
        role = {"WW_ATTR_001": "diameter", "WW_ATTR_002": "material", "WW_ATTR_003": "lifecycle_status"}[code]
        issues.extend(missing_field_issues(pipes, pipe_map[role], rule, run_id, created_at, PIPE_LAYER, pipe_map.get("asset_id")))
    elif code == "WW_ATTR_004":
        issues.extend(invalid_diameter_issues(pipes, pipe_map["diameter"], rule, run_id, created_at, pipe_map.get("asset_id")))
    elif code == "WW_ATTR_005":
        issues.extend(missing_field_issues(manholes, manhole_map["lifecycle_status"], rule, run_id, created_at, MANHOLE_LAYER, manhole_map.get("asset_id")))
    elif code == "WW_ATTR_006":
        issues.extend(missing_field_issues(pipes, pipe_map["install_date"], rule, run_id, created_at, PIPE_LAYER, pipe_map.get("asset_id")))
        issues.extend(missing_field_issues(manholes, manhole_map["install_date"], rule, run_id, created_at, MANHOLE_LAYER, manhole_map.get("asset_id")))
    elif code == "WW_ATTR_007":
        issues.extend(invalid_domain_issues(pipes, domain_values[PIPE_LAYER], rule, run_id, created_at, PIPE_LAYER, pipe_map.get("asset_id")))
        issues.extend(invalid_domain_issues(manholes, domain_values[MANHOLE_LAYER], rule, run_id, created_at, MANHOLE_LAYER, manhole_map.get("asset_id")))
    elif code == "WW_ATTR_008":
        issues.extend(conflicting_status_issues(pipes, pipe_map["lifecycle_status"], pipe_map["operational_status"], rule, run_id, created_at, PIPE_LAYER, pipe_map.get("asset_id")))
        issues.extend(conflicting_status_issues(manholes, manhole_map["lifecycle_status"], manhole_map["operational_status"], rule, run_id, created_at, MANHOLE_LAYER, manhole_map.get("asset_id")))
    elif code == "WW_GEOM_001":
        issues.extend(null_geometry_issues(pipes, rule, run_id, created_at, PIPE_LAYER))
        issues.extend(null_geometry_issues(manholes, rule, run_id, created_at, MANHOLE_LAYER))
    elif code == "WW_GEOM_002":
        issues.extend(invalid_geometry_issues(pipes, rule, run_id, created_at, PIPE_LAYER))
        issues.extend(invalid_geometry_issues(manholes, rule, run_id, created_at, MANHOLE_LAYER))
    elif code == "WW_GEOM_003":
        issues.extend(short_pipe_issues(pipes, short_units, threshold_labels["short"], rule, run_id, created_at, pipe_map.get("asset_id")))
    elif code == "WW_GEOM_004":
        issues.extend(duplicate_geometry_issues(pipes, rule, run_id, created_at, PIPE_LAYER, pipe_map.get("asset_id")))
    elif code == "WW_GEOM_005":
        issues.extend(duplicate_geometry_issues(manholes, rule, run_id, created_at, MANHOLE_LAYER, manhole_map.get("asset_id")))
    elif code == "WW_GEOM_006":
        issues.extend(multipart_issues(pipes, rule, run_id, created_at, PIPE_LAYER, pipe_map.get("asset_id")))
        issues.extend(multipart_issues(manholes, rule, run_id, created_at, MANHOLE_LAYER, manhole_map.get("asset_id")))
    elif code == "WW_GEOM_007":
        issues.extend(pipe_anomaly_issues(pipes, rule, run_id, created_at, pipe_map.get("asset_id")))
    elif code == "WW_FLOW_001":
        issues.extend(uphill_issues(pipes, pipe_map["upstream_invert"], pipe_map["downstream_invert"], rule, run_id, created_at, pipe_map.get("asset_id")))
    elif code == "WW_FLOW_002":
        issues.extend(missing_invert_issues(pipes, pipe_map["upstream_invert"], rule, run_id, created_at, pipe_map.get("asset_id")))
    elif code == "WW_FLOW_003":
        issues.extend(missing_invert_issues(pipes, pipe_map["downstream_invert"], rule, run_id, created_at, pipe_map.get("asset_id")))
    elif code == "WW_FLOW_004":
        issues.extend(slope_issues(pipes, pipe_map["upstream_invert"], pipe_map["downstream_invert"], pipe_map["length"], rule, run_id, created_at, pipe_map.get("asset_id")))
    elif code == "WW_FLOW_005":
        issues.extend(slope_conflict_issues(pipes, pipe_map["slope"], pipe_map["upstream_invert"], pipe_map["downstream_invert"], pipe_map["length"], rule, run_id, created_at, pipe_map.get("asset_id")))


def rule_result(rule: dict[str, Any], status: str, skip_reason: str, issue_count: int) -> dict[str, Any]:
    return {
        "rule_code": rule["rule_code"],
        "name": rule["name"],
        "category": rule["category"],
        "severity": rule["severity"],
        "applicable_layer": rule["applicable_layer"],
        "status": status,
        "skip_reason": skip_reason,
        "issue_count": issue_count,
        "threshold": json.dumps(rule.get("parameters", {}), sort_keys=True),
        "detection_method": rule["detection_method"],
        "limitation": rule["limitation"],
    }


def build_category_metrics(
    pipes: list[dict[str, Any]],
    manholes: list[dict[str, Any]],
    pipe_map: dict[str, str],
    manhole_map: dict[str, str],
    issues: list[dict[str, Any]],
    network_summary: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    pipe_identity = identity_metrics(pipes, pipe_map.get("asset_id"))
    manhole_identity = identity_metrics(manholes, manhole_map.get("asset_id"))
    material_available = count_present(pipes, pipe_map.get("material"))
    diameter_available = count_present(pipes, pipe_map.get("diameter"), positive=True)
    pipe_status_available = count_present(pipes, pipe_map.get("lifecycle_status"))
    manhole_status_available = count_present(manholes, manhole_map.get("lifecycle_status"))
    source_available = count_present(pipes, "SOURCE") + count_present(manholes, "SOURCE")
    return {
        "Identity": {
            "numerator": pipe_identity["available"] + manhole_identity["available"],
            "denominator": pipe_identity["total"] + manhole_identity["total"],
            "skipped_checks": skipped_count(issues, "Identity"),
            "summary": f"{pipe_identity['available']} of {pipe_identity['total']} gravity mains and {manhole_identity['available']} of {manhole_identity['total']} manholes have mapped asset IDs.",
        },
        "Attributes": {
            "numerator": material_available + diameter_available + pipe_status_available + manhole_status_available,
            "denominator": len(pipes) * 3 + len(manholes),
            "skipped_checks": 0,
            "summary": f"{diameter_available} of {len(pipes)} pipes have usable diameter; {material_available} have material; {pipe_status_available} pipes and {manhole_status_available} manholes have status.",
        },
        "Geometry": {
            "numerator": len(pipes) + len(manholes) - sum(1 for issue in issues if issue["rule_code"] in {"WW_GEOM_001", "WW_GEOM_002"}),
            "denominator": len(pipes) + len(manholes),
            "skipped_checks": 0,
            "summary": f"{len(pipes) + len(manholes)} staged features were screened for null, invalid, short, duplicate, multipart, and anomaly geometry conditions.",
        },
        "Connectivity": {
            "numerator": network_summary.get("matched_pipe_endpoints", 0),
            "denominator": network_summary.get("matched_pipe_endpoints", 0) + network_summary.get("unmatched_pipe_endpoints", 0),
            "skipped_checks": 0,
            "summary": f"{network_summary.get('matched_pipe_endpoints', 0)} of {network_summary.get('matched_pipe_endpoints', 0) + network_summary.get('unmatched_pipe_endpoints', 0)} pipe endpoints matched a manhole within tolerance.",
        },
        "Lineage": {
            "numerator": source_available,
            "denominator": len(pipes) + len(manholes),
            "skipped_checks": 0,
            "summary": f"{source_available} of {len(pipes) + len(manholes)} staged features have nonblank SOURCE lineage values.",
        },
    }


def count_present(records: list[dict[str, Any]], field_name: str | None, positive: bool = False) -> int:
    if not field_name:
        return 0
    total = 0
    for record in records:
        value = record["attributes"].get(field_name)
        if value is None or str(value).strip() in {"", "<Null>", "0"}:
            continue
        if positive:
            try:
                if float(value) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
        total += 1
    return total


def skipped_count(issues: list[dict[str, Any]], category: str) -> int:
    return sum(1 for issue in issues if issue.get("category") == category and issue.get("confidence") == "skipped")


def write_map_layers(path: Path, pipes: list[dict[str, Any]], manholes: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(
            {
                "pipes": [
                    {
                        "objectid": pipe["objectid"],
                        "asset_id": safe_asset_id(pipe, "WSACC_ID"),
                        "geometry": pipe["geometry"],
                    }
                    for pipe in pipes
                ],
                "manholes": [
                    {
                        "objectid": manhole["objectid"],
                        "asset_id": safe_asset_id(manhole, "NEW_ID"),
                        "geometry": manhole["geometry"],
                    }
                    for manhole in manholes
                ],
                "issues": [
                    {
                        "issue_id": issue["issue_id"],
                        "rule_code": issue["rule_code"],
                        "category": issue["category"],
                        "severity": issue["severity"],
                        "source_layer": issue["source_layer"],
                        "source_objectid": issue["source_objectid"],
                        "geometry": issue.get("geometry", {}),
                    }
                    for issue in issues
                    if issue.get("geometry")
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def append_history(
    path: Path,
    run_id: str,
    layers: dict[str, Path],
    output_gdb: Path,
    started_at: str,
    completed_at: str,
    extracted: dict[str, dict[str, Any]],
    issue_count: int,
    gdb_counts: dict[str, int],
) -> None:
    catalog = catalog_by_layer(path.parents[0] / "data_catalog.csv")
    rows = []
    for layer_name, layer_path in layers.items():
        rows.append(
            {
                "run_id": run_id,
                "dataset_id": catalog.get(layer_name, ""),
                "process_name": "Wastewater Data Health V1",
                "input_path": str(layer_path),
                "output_path": str(output_gdb),
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "completed",
                "records_read": extracted[layer_name]["meta"]["record_count"],
                "records_written": issue_count,
                "warnings": "",
                "errors": "",
                "operator": os.getenv("USERNAME", ""),
                "script_version": SCRIPT_VERSION,
                "notes": f"Generated QA outputs: {json.dumps(gdb_counts, sort_keys=True)}",
            }
        )
    append_processing_history(path, rows)


def catalog_by_layer(path: Path) -> dict[str, str]:
    allowlist = path.parent / "staging_allowlist.csv"
    mapping: dict[str, str] = {}
    if allowlist.exists():
        with allowlist.open(newline="", encoding="utf-8") as handle:
            mapping.update({row.get("target_layer_name", ""): row.get("dataset_id", "") for row in csv.DictReader(handle)})
    if not path.exists():
        return mapping
    with path.open(newline="", encoding="utf-8") as handle:
        mapping.update({row.get("source_layer_name", ""): row.get("dataset_id", "") for row in csv.DictReader(handle)})
    return mapping


if __name__ == "__main__":
    raise SystemExit(main())
