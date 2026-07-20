from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.responses import ComponentReviewUpdate, IssueReviewUpdate

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from gis.qa.wastewater.review_core import (  # noqa: E402
    REVIEW_DISPOSITIONS,
    WORKFLOW_STATUSES,
    default_review_priority,
    dependency_explanation,
    finding_class,
    issue_fingerprint,
    possible_missing_dependency,
    priority_sort_key,
)
from gis.qa.wastewater.review_phase2 import (  # noqa: E402
    build_components,
    build_review_sample,
    calibration_rows,
    connect_review_db,
    enrich_issues,
    load_reviews,
    sync_issue_reviews,
)

ALLOWED_REVIEW_STATUSES = WORKFLOW_STATUSES
COMPONENT_CLASSIFICATIONS = {
    "primary_network",
    "legitimate_secondary_network",
    "likely_missing_connection",
    "missing_dependent_layer",
    "incomplete_source_coverage",
    "private_or_external_network",
    "isolated_asset_group",
    "unknown",
}
SAFE_ISSUE_FIELDS = [
    "issue_id",
    "issue_fingerprint",
    "rule_code",
    "rule_name",
    "category",
    "finding_class",
    "severity",
    "utility_system",
    "network_group",
    "asset_category",
    "asset_subcategory",
    "source_layer",
    "source_asset_id",
    "source_objectid",
    "related_asset_id",
    "related_objectid",
    "description",
    "why_it_matters",
    "recommended_action",
    "detection_method",
    "threshold_used",
    "confidence",
    "review_status",
    "workflow_status",
    "disposition",
    "reviewer",
    "assigned_to",
    "review_priority",
    "review_notes",
    "evidence_notes",
    "reviewed_at",
    "resolved_at",
    "due_date",
    "source_confirmation",
    "field_verification_required",
    "engineering_review_required",
    "rule_adjustment_candidate",
    "resolution_notes",
    "possible_missing_dependency",
    "dependency_explanation",
    "first_seen_run_id",
    "latest_seen_run_id",
    "first_seen_at",
    "latest_seen_at",
    "occurrence_count",
    "currently_present",
    "run_id",
    "created_at",
]


def reports_root() -> Path:
    return data_root() / "05_qa" / "reports"


def data_root() -> Path:
    return Path(os.getenv("UTILITY_DATA_ROOT", r"C:\UtilitiesPlatform_Data"))


def summary() -> dict[str, Any]:
    path = reports_root() / "wastewater_qa_summary.json"
    if not path.exists():
        return {"configured": False, "message": "Wastewater QA has not been executed yet."}
    return json.loads(path.read_text(encoding="utf-8"))


def rules() -> dict[str, Any]:
    config_path = REPO_ROOT / "config" / "qa_rules" / "wastewater_v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    results = {row["rule_code"]: row for row in summary().get("rule_results", [])}
    return {
        "version": config.get("version", ""),
        "rules": [rule | results.get(rule["rule_code"], {"status": "not_run", "issue_count": 0, "skip_reason": ""}) for rule in config["rules"]],
    }


def issues(
    *,
    severity: str | None = None,
    category: str | None = None,
    rule_code: str | None = None,
    review_status: str | None = None,
    source_layer: str | None = None,
    run_id: str | None = None,
    asset: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    rows = current_reviewed_issues()
    filtered = [
        row
        for row in rows
        if matches(row, "severity", severity)
        and matches(row, "category", category)
        and matches(row, "rule_code", rule_code)
        and matches(row, "review_status", review_status)
        and matches(row, "source_layer", source_layer)
        and matches(row, "run_id", run_id)
        and matches_asset(row, asset)
    ]
    page = filtered[offset : offset + limit]
    return {
        "items": [safe_issue(row) for row in page],
        "pagination": {"total": len(filtered), "limit": limit, "offset": offset, "has_more": offset + limit < len(filtered)},
        "message": "No wastewater QA issues matched the filters." if not filtered else "Wastewater QA issues loaded.",
    }


def issue_detail(issue_id: str) -> dict[str, Any] | None:
    for row in current_reviewed_issues():
        if row.get("issue_id") == issue_id:
            return safe_issue(row)
    return None


def update_issue(issue_id: str, update: IssueReviewUpdate) -> dict[str, Any] | None:
    issue = next((row for row in current_reviewed_issues() if row.get("issue_id") == issue_id), None)
    if not issue:
        return None
    update_review_record(issue, update)
    return issue_detail(issue_id)


def network() -> dict[str, Any]:
    summary_path = reports_root() / "wastewater_network_summary.json"
    components_path = reports_root() / "wastewater_network_components.csv"
    return {
        "summary": json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {},
        "components": list(csv.DictReader(components_path.open(newline="", encoding="utf-8"))) if components_path.exists() else [],
        "limitations": [
            "Proximity-based connectivity only.",
            "Not authoritative topology or an ArcGIS Utility Network.",
            "Crossings do not automatically mean connectivity.",
        ],
    }


def runs() -> dict[str, Any]:
    history = Path(os.getenv("UTILITY_DATA_ROOT", r"C:\UtilitiesPlatform_Data")) / "00_admin" / "processing_history.csv"
    if not history.exists():
        return {"runs": []}
    with history.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("process_name") == "Wastewater Data Health V1"]
    return {
        "runs": [
            {
                "run_id": row.get("run_id", ""),
                "dataset_id": row.get("dataset_id", ""),
                "process_name": row.get("process_name", ""),
                "input_layer": Path(row.get("input_path", "")).name,
                "output_workspace": Path(row.get("output_path", "")).name,
                "started_at": row.get("started_at", ""),
                "completed_at": row.get("completed_at", ""),
                "status": row.get("status", ""),
                "records_read": row.get("records_read", ""),
                "records_written": row.get("records_written", ""),
                "warnings": row.get("warnings", ""),
                "errors": row.get("errors", ""),
                "operator": row.get("operator", ""),
                "script_version": row.get("script_version", ""),
                "notes": row.get("notes", ""),
            }
            for row in rows
        ]
    }


def map_layers() -> dict[str, Any]:
    path = map_layers_path()
    if not path.exists():
        return {"pipes": [], "manholes": [], "issues": []}
    return _map_layers_cached(str(path), path.stat().st_mtime_ns)


def map_layers_path() -> Path:
    return reports_root() / "wastewater_map_layers.json"


@lru_cache(maxsize=4)
def _map_layers_cached(path: str, mtime_ns: int) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_issues() -> list[dict[str, Any]]:
    path = reports_root() / "wastewater_qa_issues.json"
    if not path.exists():
        return []
    return _load_issues_cached(str(path), path.stat().st_mtime_ns)


@lru_cache(maxsize=4)
def _load_issues_cached(path: str, mtime_ns: int) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8")).get("issues", [])


def safe_issue(row: dict[str, Any]) -> dict[str, Any]:
    output = {field: row.get(field, "") for field in SAFE_ISSUE_FIELDS}
    output["issue_fingerprint"] = output["issue_fingerprint"] or issue_fingerprint(row)
    output["finding_class"] = output["finding_class"] or finding_class(row)
    output["possible_missing_dependency"] = output["possible_missing_dependency"] or possible_missing_dependency(row)
    output["dependency_explanation"] = output["dependency_explanation"] or dependency_explanation(row)
    output["workflow_status"] = output["workflow_status"] or output["review_status"] or "open"
    output["review_status"] = output["workflow_status"]
    output["disposition"] = output["disposition"] or "unreviewed"
    output["review_priority"] = output["review_priority"] or default_review_priority(row)
    output["resolution_notes"] = output["resolution_notes"] or output["review_notes"]
    output["safe_geometry"] = safe_geometry(row.get("geometry", {}))
    return output


def safe_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    if geometry.get("type") == "point":
        return {
            "type": "point",
            "x": geometry.get("x"),
            "y": geometry.get("y"),
            "spatial_reference_wkid": geometry.get("spatial_reference_wkid"),
        }
    if geometry.get("type") == "polyline":
        return {
            "type": "polyline",
            "paths": geometry.get("paths", []),
            "spatial_reference_wkid": geometry.get("spatial_reference_wkid"),
        }
    return {}


def matches(row: dict[str, Any], field: str, expected: str | None) -> bool:
    return not expected or str(row.get(field, "")).lower() == expected.lower()


def matches_asset(row: dict[str, Any], asset: str | None) -> bool:
    if not asset:
        return True
    needle = asset.lower()
    return any(needle in str(row.get(field, "")).lower() for field in ["source_asset_id", "related_asset_id", "source_objectid", "related_objectid"])


def current_reviewed_issues() -> list[dict[str, Any]]:
    issues = load_issues()
    if not issues:
        return []
    run_id = str(summary().get("run_id") or "")
    seen_at = str(summary().get("completed_at") or datetime.now().isoformat(timespec="seconds"))
    with connect_review_db(data_root()) as connection:
        sync_issue_reviews(connection, issues, run_id, seen_at)
        reviews = load_reviews(connection)
    return enrich_issues(issues, reviews)


def update_review_record(issue: dict[str, Any], update: IssueReviewUpdate) -> None:
    data = update.model_dump(exclude_unset=True)
    if "review_status" in data:
        data["workflow_status"] = data.pop("review_status")
    if "resolution_notes" in data:
        data["review_notes"] = data.pop("resolution_notes")
    if data.get("workflow_status") and data["workflow_status"] not in WORKFLOW_STATUSES:
        raise ValueError("Invalid workflow status.")
    if data.get("disposition") and data["disposition"] not in REVIEW_DISPOSITIONS:
        raise ValueError("Invalid disposition.")
    allowed = {
        "workflow_status",
        "disposition",
        "reviewer",
        "assigned_to",
        "review_priority",
        "review_notes",
        "evidence_notes",
        "due_date",
        "source_confirmation",
        "field_verification_required",
        "engineering_review_required",
        "rule_adjustment_candidate",
    }
    data = {key: value for key, value in data.items() if key in allowed}
    if not data:
        return
    now = datetime.now().isoformat(timespec="seconds")
    fingerprint = issue.get("issue_fingerprint") or issue_fingerprint(issue)
    with connect_review_db(data_root()) as connection:
        current = connection.execute("SELECT * FROM issue_reviews WHERE issue_fingerprint = ?", (fingerprint,)).fetchone()
        if current is None:
            sync_issue_reviews(connection, [issue], str(issue.get("run_id", "")), now)
            current = connection.execute("SELECT * FROM issue_reviews WHERE issue_fingerprint = ?", (fingerprint,)).fetchone()
        assert current is not None
        changed_by = str(data.get("reviewer") or current["reviewer"] or "api")
        updates: dict[str, Any] = {}
        for key, value in data.items():
            stored = int(value) if isinstance(value, bool) else (value or "")
            if str(current[key]) != str(stored):
                updates[key] = stored
                connection.execute(
                    """
                    INSERT INTO review_history (
                        issue_fingerprint, issue_id, event_type, field_name, old_value, new_value, changed_by, changed_at, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fingerprint,
                        issue.get("issue_id", ""),
                        history_event_type(key, str(stored)),
                        key,
                        str(current[key]),
                        str(stored),
                        changed_by,
                        now,
                        "Review metadata update.",
                    ),
                )
        if updates:
            if "disposition" in updates and updates["disposition"] not in {"unreviewed", "under_review"}:
                updates.setdefault("reviewed_at", now)
            if updates.get("workflow_status") == "resolved" or updates.get("disposition") == "resolved":
                updates.setdefault("resolved_at", now)
            updates["updated_at"] = now
            assignments = ", ".join(f"{key} = ?" for key in updates)
            connection.execute(f"UPDATE issue_reviews SET {assignments} WHERE issue_fingerprint = ?", [*updates.values(), fingerprint])
        connection.commit()


def history_event_type(field: str, value: str) -> str:
    if field == "workflow_status" and value == "reopened":
        return "reopened"
    if field == "workflow_status" and value == "resolved":
        return "resolved"
    if field == "workflow_status":
        return "status_changed"
    if field == "disposition":
        return "disposition_changed"
    if field == "reviewer":
        return "reviewer_changed"
    if "notes" in field:
        return "notes_changed"
    return "metadata_changed"


def batch_update_issue_reviews(issue_ids: list[str], update: IssueReviewUpdate) -> dict[str, Any]:
    if not issue_ids:
        raise ValueError("At least one issue ID is required.")
    by_id = {row.get("issue_id", ""): row for row in current_reviewed_issues()}
    updated = []
    missing = []
    for issue_id in issue_ids:
        issue = by_id.get(issue_id)
        if not issue:
            missing.append(issue_id)
            continue
        update_review_record(issue, update)
        updated.append(issue_id)
    return {"updated_count": len(updated), "updated_issue_ids": updated, "missing_issue_ids": missing}


def review_queue(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    rows = sorted(current_reviewed_issues(), key=priority_sort_key)
    page = rows[offset : offset + limit]
    return {
        "items": [safe_issue(row) for row in page],
        "pagination": {"total": len(rows), "limit": limit, "offset": offset, "has_more": offset + limit < len(rows)},
        "ordering": [
            "high severity and high confidence",
            "unmatched endpoints",
            "isolated pipes",
            "isolated manholes",
            "identity issues",
            "geometry issues",
            "attribute completeness findings",
        ],
    }


def calibration() -> dict[str, Any]:
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "rows": calibration_rows(current_reviewed_issues(), rules().get("rules", []))}


def review_sample() -> dict[str, Any]:
    path = reports_root() / "wastewater_review_sample.csv"
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    else:
        rows = [safe_issue(row) for row in build_review_sample(current_reviewed_issues(), 20260720)]
    return {"items": rows, "total": len(rows), "seed": 20260720}


def data_owner_questions() -> dict[str, str]:
    path = reports_root() / "wastewater_data_owner_questions.md"
    return {"markdown": path.read_text(encoding="utf-8") if path.exists() else ""}


def standardization_readiness() -> dict[str, Any]:
    path = reports_root() / "wastewater_standardization_readiness.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"standardization_status": "not_generated"}


def standardization_mappings() -> dict[str, Any]:
    path = reports_root() / "wastewater_standardization_mapping.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"mappings": []}


def trust_pipeline() -> dict[str, Any]:
    path = reports_root() / "wastewater_trust_pipeline.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
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
    }


def components(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    path = reports_root() / "wastewater_network_component_review.json"
    rows = json.loads(path.read_text(encoding="utf-8")).get("components", []) if path.exists() else build_components(data_root(), current_reviewed_issues())
    reviews = component_review_rows()
    for row in rows:
        review = reviews.get(str(row.get("component_id", "")), {})
        row["review_status"] = review.get("workflow_status", row.get("review_status", "open"))
        row["review_classification"] = review.get("classification", row.get("likely_classification", "unknown"))
        row["reviewer"] = review.get("reviewer", "")
        row["reviewer_notes"] = review.get("reviewer_notes", row.get("reviewer_notes", ""))
    page = rows[offset : offset + limit]
    return {"items": page, "pagination": {"total": len(rows), "limit": limit, "offset": offset, "has_more": offset + limit < len(rows)}}


def component_detail(component_id: str) -> dict[str, Any] | None:
    return next((row for row in components(limit=10000)["items"] if str(row.get("component_id")) == component_id), None)


def update_component(component_id: str, update: ComponentReviewUpdate) -> dict[str, Any] | None:
    if component_detail(component_id) is None:
        return None
    data = update.model_dump(exclude_unset=True)
    if data.get("workflow_status") and data["workflow_status"] not in WORKFLOW_STATUSES:
        raise ValueError("Invalid workflow status.")
    if data.get("classification") and data["classification"] not in COMPONENT_CLASSIFICATIONS:
        raise ValueError("Invalid component classification.")
    now = datetime.now().isoformat(timespec="seconds")
    with connect_review_db(data_root()) as connection:
        current = connection.execute("SELECT * FROM component_reviews WHERE component_id = ?", (component_id,)).fetchone()
        existing = dict(current) if current else {"classification": "unknown", "workflow_status": "open", "reviewer": "", "reviewer_notes": ""}
        merged = {**existing, **{key: value or "" for key, value in data.items()}, "updated_at": now}
        connection.execute(
            """
            INSERT INTO component_reviews (component_id, classification, workflow_status, reviewer, reviewer_notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(component_id) DO UPDATE SET
                classification = excluded.classification,
                workflow_status = excluded.workflow_status,
                reviewer = excluded.reviewer,
                reviewer_notes = excluded.reviewer_notes,
                updated_at = excluded.updated_at
            """,
            (component_id, merged["classification"], merged["workflow_status"], merged["reviewer"], merged["reviewer_notes"], now),
        )
        connection.commit()
    return component_detail(component_id)


def component_review_rows() -> dict[str, dict[str, Any]]:
    with connect_review_db(data_root()) as connection:
        return {str(row["component_id"]): dict(row) for row in connection.execute("SELECT * FROM component_reviews")}
