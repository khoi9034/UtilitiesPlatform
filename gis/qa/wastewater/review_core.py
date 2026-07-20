from __future__ import annotations

import hashlib
import json
from typing import Any

WORKFLOW_STATUSES = {
    "open",
    "assigned",
    "in_review",
    "decision_recorded",
    "resolved",
    "reopened",
    "deferred",
}

REVIEW_DISPOSITIONS = {
    "unreviewed",
    "under_review",
    "confirmed_defect",
    "likely_defect",
    "false_positive",
    "source_data_limitation",
    "expected_condition",
    "missing_dependent_data",
    "needs_field_verification",
    "needs_engineering_review",
    "deferred",
    "resolved",
}

FINDING_CLASS_BY_RULE = {
    "WW_ATTR_002": "attribute_completeness_gap",
    "WW_ATTR_006": "attribute_completeness_gap",
    "WW_FLOW_002": "attribute_completeness_gap",
    "WW_FLOW_003": "attribute_completeness_gap",
}

DEPENDENCY_BY_RULE = {
    "WW_NET_001": "unknown",
    "WW_NET_002": "service_lateral",
    "WW_NET_003": "external_jurisdiction_network",
    "WW_NET_004": "unknown",
    "WW_NET_005": "force_main",
    "WW_NET_006": "force_main",
    "WW_NET_007": "service_lateral",
    "WW_NET_008": "unknown",
}


def normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def geometry_signature(geometry: dict[str, Any]) -> str:
    if geometry.get("type") == "point":
        return f"pt:{round(float(geometry.get('x') or 0), 2)}:{round(float(geometry.get('y') or 0), 2)}"
    if geometry.get("type") == "polyline":
        paths = geometry.get("paths") or []
        if not paths or not paths[0]:
            return "line:empty"
        first = paths[0][0]
        last = paths[-1][-1]
        length = round(float(geometry.get("length") or 0), 2)
        return f"line:{round(float(first[0]), 2)}:{round(float(first[1]), 2)}:{round(float(last[0]), 2)}:{round(float(last[1]), 2)}:{length}"
    return "geom:none"


def issue_fingerprint(issue: dict[str, Any], threshold_version: str | None = None) -> str:
    asset_key = issue.get("source_asset_id") or issue.get("source_objectid") or ""
    related_key = issue.get("related_asset_id") or issue.get("related_objectid") or ""
    parts = {
        "utility_system": normalized_text(issue.get("utility_system")),
        "source_layer": normalized_text(issue.get("source_layer")),
        "asset_key": normalized_text(asset_key),
        "rule_code": normalized_text(issue.get("rule_code")),
        "related_key": normalized_text(related_key),
        "geometry": geometry_signature(issue.get("geometry") or issue.get("safe_geometry") or {}),
        "threshold": normalized_text(threshold_version if threshold_version is not None else issue.get("threshold_used")),
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def finding_class(issue: dict[str, Any]) -> str:
    rule_code = str(issue.get("rule_code") or "")
    if rule_code in FINDING_CLASS_BY_RULE:
        return FINDING_CLASS_BY_RULE[rule_code]
    category = str(issue.get("category") or "").lower()
    if category == "geometry":
        return "geometry_defect"
    if category == "connectivity":
        return "network_defect"
    if category == "identity":
        return "record_defect"
    if category == "lineage":
        return "lineage_gap"
    return "record_defect"


def possible_missing_dependency(issue: dict[str, Any]) -> str:
    return DEPENDENCY_BY_RULE.get(str(issue.get("rule_code") or ""), "")


def dependency_explanation(issue: dict[str, Any]) -> str:
    dependency = possible_missing_dependency(issue)
    if not dependency:
        return ""
    return f"Missing {dependency} data could make this proximity-based connectivity finding appear worse; do not dismiss it without review."


def default_review_priority(issue: dict[str, Any]) -> str:
    if issue.get("severity") == "high":
        return "high"
    if issue.get("category") in {"Connectivity", "Geometry"}:
        return "medium"
    return "normal"


def priority_sort_key(issue: dict[str, Any]) -> tuple[int, str]:
    rule_code = str(issue.get("rule_code") or "")
    severity = str(issue.get("severity") or "")
    confidence = str(issue.get("confidence") or "")
    if severity == "high" and confidence == "high":
        rank = 0
    elif rule_code in {"WW_NET_001", "WW_NET_003"}:
        rank = 1
    elif rule_code == "WW_NET_006":
        rank = 2
    elif rule_code == "WW_NET_007":
        rank = 3
    elif str(issue.get("category") or "") == "Identity":
        rank = 4
    elif str(issue.get("category") or "") == "Geometry":
        rank = 5
    elif finding_class(issue) == "attribute_completeness_gap":
        rank = 6
    else:
        rank = 7
    return rank, str(issue.get("issue_id") or "")
