from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.responses import IssueReviewUpdate

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_REVIEW_STATUSES = {
    "open",
    "under_review",
    "confirmed_issue",
    "false_positive",
    "needs_field_verification",
    "needs_engineering_review",
    "resolved",
    "deferred",
}
SAFE_ISSUE_FIELDS = [
    "issue_id",
    "rule_code",
    "rule_name",
    "category",
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
    "reviewer",
    "reviewed_at",
    "resolution_notes",
    "run_id",
    "created_at",
]


def reports_root() -> Path:
    root = Path(os.getenv("UTILITY_DATA_ROOT", r"C:\UtilitiesPlatform_Data"))
    return root / "05_qa" / "reports"


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
    rows = apply_reviews(load_issues())
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
    for row in apply_reviews(load_issues()):
        if row.get("issue_id") == issue_id:
            return safe_issue(row)
    return None


def update_issue(issue_id: str, update: IssueReviewUpdate) -> dict[str, Any] | None:
    if not issue_detail(issue_id):
        return None
    if update.review_status and update.review_status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError("Invalid review status.")
    reviews = read_reviews()
    current = reviews.get(issue_id, {"issue_id": issue_id})
    data = update.model_dump(exclude_unset=True)
    current.update({key: value or "" for key, value in data.items()})
    if "review_status" in data or "reviewer" in data or "resolution_notes" in data:
        current["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
    reviews[issue_id] = current
    write_reviews(reviews)
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


def reviews_path() -> Path:
    return reports_root() / "wastewater_issue_reviews.csv"


def read_reviews() -> dict[str, dict[str, str]]:
    path = reviews_path()
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["issue_id"]: row for row in csv.DictReader(handle)}


def write_reviews(reviews: dict[str, dict[str, str]]) -> None:
    path = reviews_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["issue_id", "review_status", "reviewer", "resolution_notes", "reviewed_at"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in reviews.values())


def apply_reviews(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviews = read_reviews()
    output = []
    for row in rows:
        merged = dict(row)
        review = reviews.get(row.get("issue_id", ""))
        if review:
            merged.update({key: value for key, value in review.items() if key != "issue_id"})
        output.append(merged)
    return output
