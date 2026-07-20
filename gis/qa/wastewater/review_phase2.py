from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .review_core import (
        REVIEW_DISPOSITIONS,
        WORKFLOW_STATUSES,
        default_review_priority,
        dependency_explanation,
        finding_class,
        issue_fingerprint,
        possible_missing_dependency,
        priority_sort_key,
    )
except ImportError:  # pragma: no cover - direct script execution
    from review_core import (  # type: ignore
        REVIEW_DISPOSITIONS,
        WORKFLOW_STATUSES,
        default_review_priority,
        dependency_explanation,
        finding_class,
        issue_fingerprint,
        possible_missing_dependency,
        priority_sort_key,
    )

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = Path(r"C:\UtilitiesPlatform_Data")
REVIEW_DB_NAME = "wastewater_review.sqlite"


def read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def reports_root(data_root: Path) -> Path:
    return data_root / "05_qa" / "reports"


def review_db_path(data_root: Path) -> Path:
    return data_root / "05_qa" / "review" / REVIEW_DB_NAME


def connect_review_db(data_root: Path) -> sqlite3.Connection:
    path = review_db_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    init_review_db(connection)
    return connection


def init_review_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS issue_reviews (
            issue_fingerprint TEXT PRIMARY KEY,
            issue_id TEXT NOT NULL,
            workflow_status TEXT NOT NULL DEFAULT 'open',
            disposition TEXT NOT NULL DEFAULT 'unreviewed',
            reviewer TEXT NOT NULL DEFAULT '',
            assigned_to TEXT NOT NULL DEFAULT '',
            review_priority TEXT NOT NULL DEFAULT 'normal',
            review_notes TEXT NOT NULL DEFAULT '',
            evidence_notes TEXT NOT NULL DEFAULT '',
            reviewed_at TEXT NOT NULL DEFAULT '',
            resolved_at TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            source_confirmation TEXT NOT NULL DEFAULT '',
            field_verification_required INTEGER NOT NULL DEFAULT 0,
            engineering_review_required INTEGER NOT NULL DEFAULT 0,
            rule_adjustment_candidate INTEGER NOT NULL DEFAULT 0,
            first_seen_run_id TEXT NOT NULL,
            latest_seen_run_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            latest_seen_at TEXT NOT NULL,
            occurrence_count INTEGER NOT NULL DEFAULT 1,
            currently_present INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS review_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_fingerprint TEXT NOT NULL,
            issue_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT NOT NULL,
            new_value TEXT NOT NULL,
            changed_by TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS review_comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_fingerprint TEXT NOT NULL,
            commenter TEXT NOT NULL,
            comment_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_fingerprint TEXT NOT NULL,
            assigned_to TEXT NOT NULL,
            assigned_by TEXT NOT NULL,
            assigned_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rule_feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_code TEXT NOT NULL,
            issue_fingerprint TEXT NOT NULL,
            feedback_type TEXT NOT NULL,
            comment TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attachment_metadata (
            attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_fingerprint TEXT NOT NULL,
            attachment_name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            description TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS component_reviews (
            component_id TEXT PRIMARY KEY,
            classification TEXT NOT NULL DEFAULT 'unknown',
            workflow_status TEXT NOT NULL DEFAULT 'open',
            reviewer TEXT NOT NULL DEFAULT '',
            reviewer_notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        """
    )
    connection.commit()


def load_reviews(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {row["issue_fingerprint"]: dict(row) for row in connection.execute("SELECT * FROM issue_reviews")}


def sync_issue_reviews(connection: sqlite3.Connection, issues: list[dict[str, Any]], run_id: str, seen_at: str) -> None:
    connection.execute("UPDATE issue_reviews SET currently_present = 0")
    existing = load_reviews(connection)
    for issue in issues:
        fingerprint = issue_fingerprint(issue)
        issue["issue_fingerprint"] = fingerprint
        current = existing.get(fingerprint)
        if current:
            occurrence_count = int(current["occurrence_count"]) + (0 if current["latest_seen_run_id"] == run_id else 1)
            connection.execute(
                """
                UPDATE issue_reviews
                   SET issue_id = ?, latest_seen_run_id = ?, latest_seen_at = ?, occurrence_count = ?,
                       currently_present = 1, updated_at = ?
                 WHERE issue_fingerprint = ?
                """,
                (issue.get("issue_id", ""), run_id, seen_at, occurrence_count, seen_at, fingerprint),
            )
        else:
            priority = default_review_priority(issue)
            connection.execute(
                """
                INSERT INTO issue_reviews (
                    issue_fingerprint, issue_id, review_priority, first_seen_run_id, latest_seen_run_id,
                    first_seen_at, latest_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (fingerprint, issue.get("issue_id", ""), priority, run_id, run_id, seen_at, seen_at, seen_at, seen_at),
            )
            connection.execute(
                """
                INSERT INTO review_history (
                    issue_fingerprint, issue_id, event_type, field_name, old_value, new_value, changed_by, changed_at, notes
                ) VALUES (?, ?, 'created', 'issue_fingerprint', '', ?, 'system', ?, 'Initial active finding record created.')
                """,
                (fingerprint, issue.get("issue_id", ""), fingerprint, seen_at),
            )
    connection.commit()


def enrich_issues(issues: list[dict[str, Any]], reviews: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for issue in issues:
        row = dict(issue)
        fingerprint = row.get("issue_fingerprint") or issue_fingerprint(row)
        review = reviews.get(fingerprint, {})
        row.update(
            {
                "issue_fingerprint": fingerprint,
                "finding_class": finding_class(row),
                "possible_missing_dependency": possible_missing_dependency(row),
                "dependency_explanation": dependency_explanation(row),
                "workflow_status": review.get("workflow_status", "open"),
                "disposition": review.get("disposition", "unreviewed"),
                "review_priority": review.get("review_priority", default_review_priority(row)),
                "first_seen_run_id": review.get("first_seen_run_id", row.get("run_id", "")),
                "latest_seen_run_id": review.get("latest_seen_run_id", row.get("run_id", "")),
                "first_seen_at": review.get("first_seen_at", row.get("created_at", "")),
                "latest_seen_at": review.get("latest_seen_at", row.get("created_at", "")),
                "occurrence_count": review.get("occurrence_count", 1),
                "currently_present": bool(review.get("currently_present", 1)),
            }
        )
        enriched.append(row)
    return enriched


def rule_threshold(rule: dict[str, Any]) -> str:
    params = rule.get("parameters") or {}
    return ", ".join(f"{key}={value}" for key, value in params.items())


def calibration_rows(issues: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        by_rule[str(issue.get("rule_code", ""))].append(issue)
    rows = []
    for rule in rules:
        code = rule["rule_code"]
        findings = by_rule.get(code, [])
        total = len(findings)
        reviewed = [item for item in findings if (item.get("disposition") or "unreviewed") not in {"", "unreviewed", "under_review"}]
        confirmed = sum(1 for item in findings if item.get("disposition") == "confirmed_defect")
        likely = sum(1 for item in findings if item.get("disposition") == "likely_defect")
        false_positive = sum(1 for item in findings if item.get("disposition") == "false_positive")
        limitations = sum(1 for item in findings if item.get("disposition") == "source_data_limitation")
        expected = sum(1 for item in findings if item.get("disposition") == "expected_condition")
        reviewed_count = len(reviewed)
        rows.append(
            {
                "rule_code": code,
                "rule_version": "wastewater_v1",
                "total_findings": total,
                "reviewed_findings": reviewed_count,
                "confirmed_defects": confirmed,
                "likely_defects": likely,
                "false_positives": false_positive,
                "source_limitations": limitations,
                "expected_conditions": expected,
                "unresolved_findings": total - reviewed_count,
                "confirmation_rate": round((confirmed + likely) / reviewed_count, 4) if reviewed_count else 0,
                "false_positive_rate": round(false_positive / reviewed_count, 4) if reviewed_count else 0,
                "review_coverage": round(reviewed_count / total, 4) if total else 0,
                "current_severity": rule.get("severity", ""),
                "proposed_severity": "",
                "threshold": rule_threshold(rule),
                "proposed_threshold": "",
                "reviewer_comments": "",
                "calibration_status": "not_reviewed" if reviewed_count == 0 else "sampling",
            }
        )
    return rows


def build_review_sample(issues: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    randomizer = random.Random(seed)
    selected: dict[str, dict[str, Any]] = {}

    def add(items: list[dict[str, Any]], reason: str, limit: int | None = None) -> None:
        pool = list(items)
        if limit is not None and len(pool) > limit:
            pool = randomizer.sample(pool, limit)
        for item in pool:
            row = dict(item)
            row["sample_reason"] = reason
            row["issue_fingerprint"] = row.get("issue_fingerprint") or issue_fingerprint(row)
            selected.setdefault(row["issue_fingerprint"], row)

    add([item for item in issues if item.get("severity") == "high"], "all high-severity findings when manageable")
    for severity, per_rule in [("medium", 20), ("low", 10)]:
        by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for issue in issues:
            if issue.get("severity") == severity:
                by_rule[str(issue.get("rule_code", ""))].append(issue)
        for rule_code, rows in by_rule.items():
            if len(rows) >= per_rule:
                add(rows, f"{per_rule} {severity}-severity findings for {rule_code}", per_rule)
    add([item for item in issues if item.get("rule_code") == "WW_NET_006"], "all isolated pipe findings")
    add([item for item in issues if item.get("rule_code") == "WW_NET_007"], "all isolated manhole findings")
    add([item for item in issues if item.get("rule_code") in {"WW_NET_001", "WW_NET_003"}], "all unmatched endpoint findings when manageable")
    return sorted(selected.values(), key=priority_sort_key)


def build_components(data_root: Path, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = reports_root(data_root)
    components_path = root / "wastewater_network_components.csv"
    if not components_path.exists():
        return []
    map_data = read_json(root / "wastewater_map_layers.json", {"pipes": [], "manholes": []})
    pipes = {str(item.get("objectid")): item for item in map_data.get("pipes", [])}
    manholes = {str(item.get("objectid")): item for item in map_data.get("manholes", [])}
    issue_counts = Counter(str(issue.get("source_objectid", "")) for issue in issues if issue.get("rule_code") in {"WW_NET_001", "WW_NET_003"})
    rows = []
    with components_path.open(newline="", encoding="utf-8") as handle:
        for component in csv.DictReader(handle):
            pipe_ids = [item for item in component.get("pipe_objectids", "").split(";") if item]
            manhole_ids = [item for item in component.get("manhole_objectids", "").split(";") if item]
            geometries = [pipes[item]["geometry"] for item in pipe_ids if item in pipes] + [manholes[item]["geometry"] for item in manhole_ids if item in manholes]
            xs, ys = geometry_points(geometries)
            total_length = sum(float((pipes[item].get("geometry") or {}).get("length") or 0) for item in pipe_ids if item in pipes)
            unmatched = sum(issue_counts[item] for item in pipe_ids)
            pipe_count = int(component.get("pipe_count") or 0)
            manhole_count = int(component.get("manhole_count") or 0)
            total_assets = pipe_count + manhole_count
            rows.append(
                {
                    "component_id": component.get("component_id", ""),
                    "pipe_count": pipe_count,
                    "manhole_count": manhole_count,
                    "total_asset_count": total_assets,
                    "approximate_network_length": round(total_length, 2),
                    "bounding_extent": extent(xs, ys),
                    "center_x": round(sum(xs) / len(xs), 2) if xs else "",
                    "center_y": round(sum(ys) / len(ys), 2) if ys else "",
                    "nearest_other_component_distance": "",
                    "unmatched_endpoints": unmatched,
                    "isolated_status": "isolated" if total_assets <= 1 else "connected_component",
                    "likely_classification": "primary_network" if total_assets > 500 else "unknown",
                    "review_status": "open",
                    "reviewer_notes": "",
                }
            )
    add_nearest_distances(rows)
    return rows


def geometry_points(geometries: list[dict[str, Any]]) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for geometry in geometries:
        if geometry.get("type") == "point":
            xs.append(float(geometry.get("x") or 0))
            ys.append(float(geometry.get("y") or 0))
        for path in geometry.get("paths") or []:
            for x, y in path:
                xs.append(float(x))
                ys.append(float(y))
    return xs, ys


def extent(xs: list[float], ys: list[float]) -> str:
    if not xs or not ys:
        return ""
    return json.dumps({"xmin": round(min(xs), 2), "ymin": round(min(ys), 2), "xmax": round(max(xs), 2), "ymax": round(max(ys), 2)}, separators=(",", ":"))


def add_nearest_distances(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row["center_x"] == "":
            continue
        distances = []
        for other in rows:
            if other is row or other["center_x"] == "":
                continue
            dx = float(row["center_x"]) - float(other["center_x"])
            dy = float(row["center_y"]) - float(other["center_y"])
            distances.append((dx * dx + dy * dy) ** 0.5)
        row["nearest_other_component_distance"] = round(min(distances), 2) if distances else ""


def data_owner_questions(field_rows: list[dict[str, str]]) -> str:
    wanted = {
        "wastewater_gravity_main": ["WSACC_ID", "U_S_NODE", "D_S_NODE", "SZ", "MA", "STATUS", "TYPE", "YR", "INVERTIN", "INVERTOUT", "LENGTH", "SRCENT"],
        "wastewater_manhole": ["NEW_ID", "WSACC_ID", "RIM_ELEV", "INVERTOUT", "STATUS", "YR", "MH_Audit", "SRCENT"],
    }
    by_layer_field = {(row["source_layer"], row["source_field"]): row for row in field_rows if row.get("source_field")}
    lines = ["# Wastewater Data Owner Questions", "", "Do not pre-fill the confirmation fields. A data owner or steward should complete them.", ""]
    for layer, fields in wanted.items():
        lines.extend([f"## {layer}", ""])
        for field in fields:
            row = by_layer_field.get((layer, field), {})
            meaning = row.get("semantic_role", "unconfirmed")
            completeness = f"{100 - float(row.get('null_percentage') or 0):.2f}% populated" if row else "not profiled"
            lines.extend(
                [
                    f"### {field}",
                    f"- Current inferred meaning: {meaning}",
                    f"- Confidence: {row.get('confidence', 'unavailable')}",
                    f"- Observed completeness: {completeness}",
                    "- Why confirmation matters: Standardization must not assume units, code lists, or authoritative identifiers without owner confirmation.",
                    f"- Question for data owner: What does `{field}` mean, and is it authoritative for wastewater standardization?",
                    "- Response:",
                    "- Confirmed meaning:",
                    "- Confirmed unit:",
                    "- Confirmed code list:",
                    "",
                ]
            )
    return "\n".join(lines)


def standardization_mappings(field_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    mapping = {
        ("wastewater_gravity_main", "asset_id"): "source_asset_id",
        ("wastewater_gravity_main", "upstream_manhole_id"): "upstream_node_id",
        ("wastewater_gravity_main", "downstream_manhole_id"): "downstream_node_id",
        ("wastewater_gravity_main", "diameter"): "diameter_value",
        ("wastewater_gravity_main", "material"): "material_code",
        ("wastewater_gravity_main", "lifecycle_status"): "lifecycle_status",
        ("wastewater_gravity_main", "operational_status"): "operational_status",
        ("wastewater_gravity_main", "install_date"): "installation_year",
        ("wastewater_gravity_main", "upstream_invert"): "upstream_invert",
        ("wastewater_gravity_main", "downstream_invert"): "downstream_invert",
        ("wastewater_gravity_main", "length"): "source_length",
        ("wastewater_gravity_main", "owner"): "source_entity",
        ("wastewater_manhole", "asset_id"): "source_asset_id",
        ("wastewater_manhole", "facility_id"): "alternate_source_id",
        ("wastewater_manhole", "rim_elevation"): "rim_elevation",
        ("wastewater_manhole", "invert_elevation"): "outlet_invert",
        ("wastewater_manhole", "lifecycle_status"): "lifecycle_status",
        ("wastewater_manhole", "operational_status"): "operational_status",
        ("wastewater_manhole", "install_date"): "installation_year",
        ("wastewater_manhole", "condition"): "audit_status",
        ("wastewater_manhole", "owner"): "source_entity",
    }
    rows = []
    for row in field_rows:
        target = mapping.get((row.get("source_layer", ""), row.get("semantic_role", "")))
        if not target:
            continue
        unavailable = row.get("confidence") == "unavailable"
        rows.append(
            {
                "source_layer": row.get("source_layer", ""),
                "source_field": row.get("source_field", ""),
                "source_alias": row.get("field_alias", ""),
                "target_field": target,
                "mapping_type": "direct" if not unavailable else "unavailable",
                "transformation": "none",
                "unit_conversion": "requires confirmation" if target in {"diameter_value", "upstream_invert", "downstream_invert", "rim_elevation", "outlet_invert", "source_length"} else "none",
                "code_translation": "requires confirmation" if target in {"material_code", "lifecycle_status", "operational_status", "audit_status"} else "none",
                "confidence": row.get("confidence", ""),
                "data_owner_confirmation_required": "true",
                "blocked_reason": "source field unavailable" if unavailable else "",
                "approved_to_standardize": "false",
                "reviewer": "",
                "reviewed_at": "",
                "notes": "",
            }
        )
    return rows


def readiness(mappings: list[dict[str, Any]], dependencies: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    by_field = {row["target_field"]: row for row in mappings}
    fields: dict[str, dict[str, str]] = {}
    schema = read_json(ROOT / "config" / "schemas" / "wastewater_standard_v1.json", {})
    for layer in ("gravity_main", "manhole"):
        for field in schema.get("layers", {}).get(layer, {}).get("fields", []):
            name = field["name"]
            mapping = by_field.get(name)
            if not mapping and name in {"utility_system", "network_group", "asset_category", "asset_subcategory", "source_layer", "source_objectid", "processing_run_id", "geometry"}:
                state = "ready_with_warning"
                reason = "System-populated value; confirmation still required before loading standardized data."
            elif not mapping:
                state = "unavailable"
                reason = "No source mapping proposed in this phase."
            elif mapping["blocked_reason"]:
                state = "blocked"
                reason = mapping["blocked_reason"]
            elif mapping["unit_conversion"] != "none" or mapping["code_translation"] != "none":
                state = "awaiting_data_owner_confirmation"
                reason = "Unit or code-list meaning must be confirmed."
            else:
                state = "awaiting_data_owner_confirmation"
                reason = "Mapping is plausible but not approved."
            fields[f"{layer}.{name}"] = {"state": state, "reason": reason}
    missing_dependencies = [item["dependency_code"] for item in dependencies.get("dependencies", []) if not item.get("currently_available")]
    return {
        "standardization_status": "pending_human_review",
        "fields": fields,
        "fields_ready_to_map_directly": [key for key, value in fields.items() if value["state"] == "ready"],
        "fields_requiring_unit_confirmation": [row["target_field"] for row in mappings if row["unit_conversion"] != "none"],
        "fields_requiring_code_translation": [row["target_field"] for row in mappings if row["code_translation"] != "none"],
        "fields_unavailable": [key for key, value in fields.items() if value["state"] == "unavailable"],
        "fields_blocked": [key for key, value in fields.items() if value["state"] == "blocked"],
        "dependencies_still_missing": missing_dependencies,
        "records_eligible_for_preview": 0,
        "records_requiring_review": sum(summary.get("input_feature_counts", {}).values()),
        "writes_to_standardized_gdb": False,
        "writes_to_curated_gdb": False,
    }


def write_phase2_reports(data_root: Path, seed: int) -> dict[str, Any]:
    root = reports_root(data_root)
    root.mkdir(parents=True, exist_ok=True)
    summary = read_json(root / "wastewater_qa_summary.json", {})
    issues = read_json(root / "wastewater_qa_issues.json", {"issues": []}).get("issues", [])
    rules = read_json(ROOT / "config" / "qa_rules" / "wastewater_v1.json", {"rules": []}).get("rules", [])
    dependencies = read_json(ROOT / "config" / "utility_dependencies" / "wastewater.json", {"dependencies": []})
    now = datetime.now().isoformat(timespec="seconds")
    run_id = summary.get("run_id", "")
    with connect_review_db(data_root) as connection:
        sync_issue_reviews(connection, issues, run_id, now)
        reviews = load_reviews(connection)
    enriched = enrich_issues(issues, reviews)
    write_json(root / "wastewater_issue_fingerprints.json", {"run_id": run_id, "issues": enriched})

    calibration = calibration_rows(enriched, rules)
    write_json(root / "wastewater_rule_calibration.json", {"generated_at": now, "rows": calibration})
    write_csv(root / "wastewater_rule_calibration.csv", calibration, list(calibration[0].keys()) if calibration else [])
    (root / "wastewater_rule_calibration.md").write_text(calibration_markdown(calibration), encoding="utf-8")

    sample = build_review_sample(enriched, seed)
    sample_fields = ["issue_fingerprint", "issue_id", "sample_reason", "review_priority", "rule_code", "severity", "confidence", "category", "finding_class", "source_layer", "source_asset_id", "source_objectid", "description", "workflow_status", "disposition"]
    write_csv(root / "wastewater_review_sample.csv", sample, sample_fields)
    (root / "wastewater_review_plan.md").write_text(review_plan_markdown(sample), encoding="utf-8")

    field_rows = list(csv.DictReader((root / "wastewater_field_mapping.csv").open(newline="", encoding="utf-8"))) if (root / "wastewater_field_mapping.csv").exists() else []
    (root / "wastewater_data_owner_questions.md").write_text(data_owner_questions(field_rows), encoding="utf-8")

    mappings = standardization_mappings(field_rows)
    mapping_fields = ["source_layer", "source_field", "source_alias", "target_field", "mapping_type", "transformation", "unit_conversion", "code_translation", "confidence", "data_owner_confirmation_required", "blocked_reason", "approved_to_standardize", "reviewer", "reviewed_at", "notes"]
    write_json(root / "wastewater_standardization_mapping.json", {"generated_at": now, "mappings": mappings})
    write_csv(root / "wastewater_standardization_mapping.csv", mappings, mapping_fields)

    readiness_payload = readiness(mappings, dependencies, summary)
    write_json(root / "wastewater_standardization_readiness.json", readiness_payload)
    (root / "wastewater_standardization_readiness.md").write_text(readiness_markdown(readiness_payload), encoding="utf-8")

    components = build_components(data_root, enriched)
    component_fields = ["component_id", "pipe_count", "manhole_count", "total_asset_count", "approximate_network_length", "bounding_extent", "nearest_other_component_distance", "unmatched_endpoints", "isolated_status", "likely_classification", "review_status", "reviewer_notes"]
    write_json(root / "wastewater_network_component_review.json", {"generated_at": now, "components": components})
    write_csv(root / "wastewater_network_component_review.csv", components, component_fields)

    pipeline = {
        "utility_system": "wastewater",
        "stages": [
            {"stage": "Raw", "state": "complete"},
            {"stage": "Inventoried", "state": "complete"},
            {"stage": "Staged", "state": "complete"},
            {"stage": "QA Evaluated", "state": "complete"},
            {"stage": "Human Review", "state": "in_progress"},
            {"stage": "Standardization Ready", "state": "pending"},
            {"stage": "Standardized", "state": "not_started"},
            {"stage": "Curated", "state": "not_started"},
            {"stage": "Exported", "state": "not_started"},
        ],
        "message": "Datasets cannot skip stages because lineage, QA evidence, review decisions, and authorization gates protect downstream trust.",
    }
    write_json(root / "wastewater_trust_pipeline.json", pipeline)
    return {"issues": len(enriched), "sample": len(sample), "components": len(components), "review_db": str(review_db_path(data_root))}


def calibration_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# Wastewater Rule Calibration", "", "Rules are not changed automatically from small review samples.", "", "| Rule | Findings | Reviewed | Confirmed | False positives | Coverage | Status |", "|---|---:|---:|---:|---:|---:|---|"]
    for row in rows:
        lines.append(f"| {row['rule_code']} | {row['total_findings']} | {row['reviewed_findings']} | {row['confirmed_defects']} | {row['false_positives']} | {row['review_coverage']} | {row['calibration_status']} |")
    return "\n".join(lines) + "\n"


def review_plan_markdown(sample: list[dict[str, Any]]) -> str:
    by_reason = Counter(item["sample_reason"] for item in sample)
    lines = ["# Wastewater Review Plan", "", f"Sample size: {len(sample)}", "", "Findings are candidates until reviewed by a human steward.", ""]
    for reason, count in sorted(by_reason.items()):
        lines.append(f"- {reason}: {count}")
    return "\n".join(lines) + "\n"


def readiness_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Wastewater Standardization Readiness",
            "",
            f"Status: {payload['standardization_status']}",
            "",
            f"Records eligible for preview: {payload['records_eligible_for_preview']}",
            f"Records requiring review: {payload['records_requiring_review']}",
            "",
            "No records were written to Utility_Standardized.gdb or Utility_Master.gdb.",
            "",
            f"Fields requiring unit confirmation: {len(payload['fields_requiring_unit_confirmation'])}",
            f"Fields requiring code translation: {len(payload['fields_requiring_code_translation'])}",
            f"Unavailable fields: {len(payload['fields_unavailable'])}",
            f"Blocked fields: {len(payload['fields_blocked'])}",
            f"Missing dependencies: {', '.join(payload['dependencies_still_missing'])}",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Wastewater Data Health Phase 2 review and standardization-readiness artifacts.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--seed", type=int, default=20260720)
    args = parser.parse_args()
    result = write_phase2_reports(args.data_root, args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
