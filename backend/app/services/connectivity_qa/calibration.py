from __future__ import annotations

import json
import sqlite3
import uuid
from collections import Counter, defaultdict
from typing import Any

from app.services import intake_registry_service
from app.services.utility_assets.domain import stable_fingerprint, stable_id

CALIBRATION_RULE_VERSION = "connectivity-calibration-v1"
GROUPING_RULE_VERSION = "connectivity-grouping-v1"
DEPENDENCY_MAP_VERSION = "connectivity-dependencies-v1"
PRIORITY_RULE_VERSION = "connectivity-priority-v1"
TRACE_IMPACT_VERSION = "connectivity-trace-impact-v1"

ISSUE_FAMILIES = (
    "missing_identifier", "missing_endpoint", "disconnected_network", "invalid_relationship",
    "duplicate_relationship", "lifecycle_conflict", "provisional_evidence", "incompatible_vertical",
    "containment_gap", "structure_support_gap", "membership_conflict", "attribute_conflict",
    "operational_state", "trace_readiness", "unsupported_condition", "feeder_assignment",
    "circuit_assignment", "phase_compatibility", "voltage_compatibility", "transformer_connectivity",
    "protective_device", "conductor_connectivity", "electric_structure", "electric_placement",
    "cable_endpoint", "cable_termination", "route_continuity", "strand_allocation",
    "capacity_consistency", "splice_connectivity", "terminal_connectivity", "cabinet_connectivity",
    "telecom_structure", "telecom_placement", "proposed_construction",
)
FINDING_ROLES = ("primary", "contributing", "consequence", "corroborating", "informational", "independent")
TRACE_IMPACTS = ("stops_trace", "limits_trace", "introduces_ambiguity", "advisory", "no_trace_effect", "not_evaluated")
DISPLAY_PRIORITIES = ("immediate", "high", "normal", "low", "informational")
EXTERNAL_MAPPING_STATUSES = ("not_mapped", "conceptually_mappable", "adapter_required", "unsupported", "unknown")
REVIEW_ACTIONS = {
    "acknowledge": "acknowledged",
    "defer": "deferred",
    "accept-risk": "accepted_risk",
    "mark-false-positive": "false_positive",
    "reopen": "open",
}


def _meta(
    family: str,
    action: str,
    precedence: int,
    trace: str,
    category: str,
    hint: str,
    mapping: str = "conceptually_mappable",
) -> tuple[str, str, int, str, str, str, str]:
    return family, action, precedence, trace, category, mapping, hint


RULE_CALIBRATION = {
    "SHARED-001": _meta("missing_endpoint", "repair_connectivity", 1, "stops_trace", "network_connectivity", "network connectivity validation"),
    "SHARED-002": _meta("invalid_relationship", "correct_relationship", 3, "stops_trace", "relationship_integrity", "network connectivity validation"),
    "SHARED-003": _meta("duplicate_relationship", "deduplicate_relationship", 3, "advisory", "relationship_integrity", "network connectivity validation"),
    "SHARED-004": _meta("provisional_evidence", "confirm_relationship", 9, "introduces_ambiguity", "evidence_quality", "network connectivity validation"),
    "SHARED-005": _meta("lifecycle_conflict", "confirm_lifecycle", 5, "stops_trace", "lifecycle_integrity", "lifecycle conflict review"),
    "SHARED-006": _meta("incompatible_vertical", "correct_taxonomy", 3, "stops_trace", "taxonomy_integrity", "network connectivity validation", "adapter_required"),
    "SHARED-007": _meta("missing_identifier", "assign_identifier", 1, "limits_trace", "identity_integrity", "network connectivity validation"),
    "SHARED-008": _meta("attribute_conflict", "confirm_lifecycle", 7, "advisory", "attribute_integrity", "lifecycle conflict review"),
    "ELEC-001": _meta("conductor_connectivity", "repair_connectivity", 2, "stops_trace", "electric_connectivity", "network connectivity validation"),
    "ELEC-002": _meta("conductor_connectivity", "repair_connectivity", 2, "stops_trace", "electric_connectivity", "network connectivity validation"),
    "ELEC-003": _meta("feeder_assignment", "confirm_feeder", 6, "limits_trace", "electric_membership", "feeder membership validation"),
    "ELEC-004": _meta("transformer_connectivity", "repair_primary_connection", 2, "stops_trace", "electric_connectivity", "network connectivity validation"),
    "ELEC-005": _meta("phase_compatibility", "confirm_phase", 7, "stops_trace", "electric_phase", "phase consistency review"),
    "ELEC-006": _meta("voltage_compatibility", "confirm_voltage", 7, "stops_trace", "electric_voltage", "phase consistency review"),
    "ELEC-007": _meta("containment_gap", "confirm_conduit", 4, "limits_trace", "electric_containment", "network connectivity validation"),
    "ELEC-008": _meta("electric_structure", "confirm_structure", 4, "advisory", "electric_structure", "network connectivity validation"),
    "ELEC-009": _meta("membership_conflict", "review_feeder_boundary", 6, "introduces_ambiguity", "electric_membership", "feeder membership validation"),
    "ELEC-010": _meta("membership_conflict", "review_feeder_boundary", 6, "introduces_ambiguity", "electric_membership", "feeder membership validation"),
    "ELEC-011": _meta("invalid_relationship", "confirm_direction", 3, "introduces_ambiguity", "relationship_integrity", "device-state-aware continuity"),
    "ELEC-012": _meta("operational_state", "retain_operational_context", 8, "no_trace_effect", "electric_device_state", "device-state-aware continuity"),
    "ELEC-013": _meta("protective_device", "confirm_device_type", 7, "limits_trace", "electric_protection", "device-state-aware continuity"),
    "ELEC-014": _meta("lifecycle_conflict", "confirm_lifecycle", 5, "stops_trace", "lifecycle_integrity", "lifecycle conflict review"),
    "ELEC-015": _meta("electric_placement", "confirm_placement", 7, "advisory", "electric_placement", "network connectivity validation"),
    "TEL-001": _meta("cable_endpoint", "repair_connectivity", 2, "stops_trace", "telecom_connectivity", "cable endpoint validation"),
    "TEL-002": _meta("cable_termination", "repair_connectivity", 3, "stops_trace", "telecom_connectivity", "cable endpoint validation"),
    "TEL-003": _meta("strand_allocation", "review_strand_allocation", 7, "stops_trace", "fiber_allocation", "fiber allocation validation"),
    "TEL-004": _meta("capacity_consistency", "reconcile_capacity", 7, "stops_trace", "telecom_capacity", "capacity consistency"),
    "TEL-005": _meta("capacity_consistency", "reconcile_capacity", 7, "introduces_ambiguity", "telecom_capacity", "capacity consistency"),
    "TEL-006": _meta("strand_allocation", "review_strand_allocation", 7, "stops_trace", "fiber_allocation", "fiber allocation validation"),
    "TEL-007": _meta("splice_connectivity", "repair_connectivity", 2, "stops_trace", "telecom_connectivity", "cable endpoint validation"),
    "TEL-008": _meta("terminal_connectivity", "repair_connectivity", 2, "stops_trace", "telecom_connectivity", "cable endpoint validation"),
    "TEL-009": _meta("cabinet_connectivity", "confirm_route", 6, "limits_trace", "telecom_membership", "network connectivity validation"),
    "TEL-010": _meta("containment_gap", "confirm_conduit", 4, "limits_trace", "telecom_containment", "network connectivity validation"),
    "TEL-011": _meta("structure_support_gap", "confirm_support", 4, "advisory", "telecom_structure", "network connectivity validation"),
    "TEL-012": _meta("proposed_construction", "complete_design", 2, "limits_trace", "proposed_connectivity", "cable endpoint validation"),
    "TEL-013": _meta("lifecycle_conflict", "confirm_lifecycle", 5, "stops_trace", "lifecycle_integrity", "lifecycle conflict review"),
    "TEL-014": _meta("provisional_evidence", "confirm_relationship", 9, "introduces_ambiguity", "evidence_quality", "network connectivity validation"),
    "TEL-015": _meta("capacity_consistency", "reconcile_capacity", 7, "stops_trace", "telecom_capacity", "capacity consistency"),
    "TEL-016": _meta("telecom_placement", "confirm_placement", 7, "advisory", "telecom_placement", "network connectivity validation"),
}

DEPENDENCIES = {
    "ELEC-002": {"ELEC-001"},
    "ELEC-010": {"ELEC-009"},
    "ELEC-014": {"SHARED-005"},
    "TEL-002": {"TEL-001"},
    "TEL-005": {"TEL-004", "TEL-015"},
    "TEL-013": {"SHARED-005"},
    "TEL-014": {"SHARED-004"},
}

GROUP_TITLES = {
    "conductor_connectivity": "Conductor connectivity and endpoints",
    "membership_conflict": "Feeder and circuit assignment conflict",
    "lifecycle_conflict": "Active and retired network conflict",
    "provisional_evidence": "Provisional relationship evidence",
    "cable_endpoint": "Cable endpoint and termination",
    "capacity_consistency": "Capacity values do not reconcile",
    "strand_allocation": "Fiber strand allocation conflict",
}

_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2, "critical": 3}
_TRACE_RANK = {"not_evaluated": 0, "no_trace_effect": 1, "advisory": 2, "introduces_ambiguity": 3, "limits_trace": 4, "stops_trace": 5}


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS connectivity_qa_calibration_runs (
            calibration_run_id TEXT PRIMARY KEY,
            qa_run_id TEXT NOT NULL,
            utility_vertical TEXT NOT NULL,
            calibration_rule_version TEXT NOT NULL,
            input_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            technical_findings_read INTEGER NOT NULL DEFAULT 0,
            issue_groups_created INTEGER NOT NULL DEFAULT 0,
            primary_findings INTEGER NOT NULL DEFAULT 0,
            consequence_findings INTEGER NOT NULL DEFAULT 0,
            independent_findings INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT NOT NULL DEFAULT '[]',
            safe_error_message TEXT NOT NULL DEFAULT '',
            summary_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_connectivity_calibration_runs
            ON connectivity_qa_calibration_runs(utility_vertical, started_at DESC);

        CREATE TABLE IF NOT EXISTS connectivity_qa_issue_groups (
            calibration_run_id TEXT NOT NULL,
            issue_group_id TEXT NOT NULL,
            qa_run_id TEXT NOT NULL,
            utility_vertical TEXT NOT NULL,
            issue_family TEXT NOT NULL,
            root_cause_key TEXT NOT NULL,
            primary_finding_id TEXT NOT NULL,
            member_finding_ids_json TEXT NOT NULL,
            affected_asset_ids_json TEXT NOT NULL,
            affected_relationship_ids_json TEXT NOT NULL,
            primary_rule_code TEXT NOT NULL,
            related_rule_codes_json TEXT NOT NULL,
            group_title TEXT NOT NULL,
            group_summary TEXT NOT NULL,
            highest_severity TEXT NOT NULL,
            effective_blocking INTEGER NOT NULL,
            technical_finding_count INTEGER NOT NULL,
            recommended_action TEXT NOT NULL,
            action_category TEXT NOT NULL,
            display_priority TEXT NOT NULL,
            confidence TEXT NOT NULL,
            root_cause_confidence TEXT NOT NULL,
            trace_impact TEXT NOT NULL,
            trace_impact_reason TEXT NOT NULL,
            calibration_rule_version TEXT NOT NULL,
            canonical_rule_category TEXT NOT NULL,
            external_rule_mapping_status TEXT NOT NULL,
            vendor_equivalent_hints_json TEXT NOT NULL,
            adapter_notes TEXT NOT NULL,
            review_status TEXT NOT NULL DEFAULT 'open',
            review_comment TEXT NOT NULL DEFAULT '',
            reviewed_by TEXT NOT NULL DEFAULT '',
            reviewed_at TEXT NOT NULL DEFAULT '',
            superseded INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            PRIMARY KEY (calibration_run_id, issue_group_id)
        );
        CREATE INDEX IF NOT EXISTS idx_connectivity_issue_groups_filter
            ON connectivity_qa_issue_groups(utility_vertical, issue_family, display_priority, trace_impact, review_status);

        CREATE TABLE IF NOT EXISTS connectivity_qa_group_members (
            calibration_run_id TEXT NOT NULL,
            issue_group_id TEXT NOT NULL,
            finding_id TEXT NOT NULL,
            finding_role TEXT NOT NULL,
            relationship_to_primary TEXT NOT NULL,
            grouping_reason TEXT NOT NULL,
            confidence TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (calibration_run_id, issue_group_id, finding_id)
        );

        CREATE TABLE IF NOT EXISTS connectivity_qa_calibration_history (
            history_id TEXT PRIMARY KEY,
            calibration_run_id TEXT NOT NULL,
            issue_group_id TEXT,
            finding_id TEXT,
            action TEXT NOT NULL,
            prior_value_json TEXT NOT NULL,
            new_value_json TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    connection.commit()


def calibrate(
    connection: sqlite3.Connection,
    vertical: str,
    qa_run_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    if any(key in payload for key in ("rules", "expression", "python", "sql", "path", "url")):
        raise ValueError("Executable or external calibration inputs are not accepted.")
    qa_run = connection.execute(
        "SELECT qa_run_id, utility_vertical, rule_version FROM connectivity_qa_runs WHERE qa_run_id = ? AND utility_vertical = ?",
        (qa_run_id, vertical),
    ).fetchone()
    if not qa_run:
        raise LookupError("Connectivity QA run not found.")
    findings = [dict(row) for row in connection.execute(
        "SELECT * FROM connectivity_qa_findings WHERE qa_run_id = ? ORDER BY finding_fingerprint",
        (qa_run_id,),
    ).fetchall()]
    input_fingerprint = stable_fingerprint(
        qa_run_id,
        sorted(row["finding_fingerprint"] for row in findings),
        DEPENDENCY_MAP_VERSION,
        PRIORITY_RULE_VERSION,
        GROUPING_RULE_VERSION,
        TRACE_IMPACT_VERSION,
    )
    force = bool(payload.get("force_recalculate"))
    if not force:
        existing = connection.execute(
            """SELECT calibration_run_id FROM connectivity_qa_calibration_runs
            WHERE utility_vertical = ? AND input_fingerprint = ? AND status = 'succeeded'
            ORDER BY started_at DESC LIMIT 1""",
            (vertical, input_fingerprint),
        ).fetchone()
        if existing:
            result = calibration_run(connection, vertical, existing["calibration_run_id"])
            result.update({"reused": True, "message": "No QA findings or calibration rules changed"})
            return result

    now = intake_registry_service.utc_now()
    calibration_run_id = str(uuid.uuid4())
    connection.execute(
        """INSERT INTO connectivity_qa_calibration_runs
        (calibration_run_id, qa_run_id, utility_vertical, calibration_rule_version, input_fingerprint,
         status, started_at, technical_findings_read, created_at)
        VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?)""",
        (calibration_run_id, qa_run_id, vertical, CALIBRATION_RULE_VERSION, input_fingerprint, now, len(findings), now),
    )
    try:
        assets = {
            row["asset_id"]: dict(row)
            for row in connection.execute(
                "SELECT asset_id, asset_class, canonical_name, lifecycle_status, operational_status FROM canonical_utility_assets"
            ).fetchall()
        }
        groups = build_issue_groups(vertical, qa_run_id, findings, assets, now)
        preserve = payload.get("preserve_review_decisions", True) is not False
        prior_reviews = _prior_reviews(connection, vertical) if preserve else {}
        for group in groups:
            prior = prior_reviews.get(group["issue_group_id"])
            if prior and prior["reviewed_by"]:
                for field in ("review_status", "review_comment", "reviewed_by", "reviewed_at"):
                    group[field] = prior[field]
            _insert_group(connection, calibration_run_id, group)
        _record_superseded_groups(connection, vertical, calibration_run_id, {item["issue_group_id"] for item in groups}, now)
        summary = calibrated_summary_from_groups(findings, groups)
        role_counts = Counter(
            member["finding_role"] for group in groups for member in group["members"]
        )
        completed = intake_registry_service.utc_now()
        connection.execute(
            """UPDATE connectivity_qa_calibration_runs SET status = 'succeeded', completed_at = ?,
            issue_groups_created = ?, primary_findings = ?, consequence_findings = ?,
            independent_findings = ?, summary_json = ? WHERE calibration_run_id = ?""",
            (
                completed,
                len(groups),
                role_counts["primary"],
                role_counts["consequence"],
                role_counts["independent"],
                _dump(summary),
                calibration_run_id,
            ),
        )
        _calibration_history(
            connection, calibration_run_id, None, None, "calibration_completed", {},
            {"technical_findings": len(findings), "issue_groups": len(groups)}, "system", "calibration_engine", "",
        )
        connection.commit()
    except Exception as exc:
        connection.execute(
            """UPDATE connectivity_qa_calibration_runs SET status = 'failed', completed_at = ?,
            safe_error_message = ? WHERE calibration_run_id = ?""",
            (intake_registry_service.utc_now(), f"{type(exc).__name__}: calibration failed safely", calibration_run_id),
        )
        connection.commit()
        raise
    result = calibration_run(connection, vertical, calibration_run_id)
    result.update({"reused": False, "message": "Connectivity QA calibration completed."})
    return result


def build_issue_groups(
    vertical: str,
    qa_run_id: str,
    findings: list[dict[str, Any]],
    assets: dict[str, dict[str, Any]],
    created_at: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        if finding["rule_code"] not in RULE_CALIBRATION:
            key = f"unsupported_condition:{finding['rule_code']}:{finding.get('asset_id') or finding.get('relationship_id') or finding['finding_id']}"
        else:
            key = _root_key(finding, assets)
        grouped[key].append(finding)

    result: list[dict[str, Any]] = []
    for root_key, members in sorted(grouped.items()):
        members.sort(key=_precedence_key)
        primary = members[0]
        meta = RULE_CALIBRATION.get(
            primary["rule_code"],
            _meta("unsupported_condition", "manual_review", 10, "not_evaluated", "unsupported", "network connectivity validation", "unknown"),
        )
        member_rows = [_member(primary, item, members, created_at) for item in members]
        affected_assets = sorted({
            asset_id for item in members for asset_id in (item.get("asset_id"), item.get("related_asset_id")) if asset_id
        })
        affected_relationships = sorted({item["relationship_id"] for item in members if item.get("relationship_id")})
        highest = max((item["severity"] for item in members), key=lambda value: _SEVERITY_RANK.get(value, -1))
        trace = max((RULE_CALIBRATION.get(item["rule_code"], meta)[3] for item in members), key=lambda value: _TRACE_RANK[value])
        blocking = any(bool(item["blocking"]) for item in members)
        priority = _priority(highest, blocking, trace, member_rows)
        issue_group_id = stable_id(
            "issue-group", vertical, root_key,
            *sorted(item["finding_fingerprint"] for item in members),
            CALIBRATION_RULE_VERSION,
        )
        review_status = _review_status(members)
        family, action, _, _, category, mapping, hint = meta
        result.append({
            "issue_group_id": issue_group_id,
            "qa_run_id": qa_run_id,
            "utility_vertical": vertical,
            "issue_family": family,
            "root_cause_key": root_key,
            "primary_finding_id": primary["finding_id"],
            "member_finding_ids": [item["finding_id"] for item in members],
            "affected_asset_ids": affected_assets,
            "affected_relationship_ids": affected_relationships,
            "primary_rule_code": primary["rule_code"],
            "related_rule_codes": sorted({item["rule_code"] for item in members if item["finding_id"] != primary["finding_id"]}),
            "group_title": GROUP_TITLES.get(family, primary["short_title"]),
            "group_summary": f"{primary['explanation']} {len(members) - 1} related technical finding(s) are retained as evidence." if len(members) > 1 else primary["explanation"],
            "highest_severity": highest,
            "effective_blocking": blocking,
            "technical_finding_count": len(members),
            "recommended_action": primary["recommended_action"],
            "action_category": action,
            "display_priority": priority,
            "confidence": "high" if len(members) == 1 or any(item["relationship_to_primary"] == "confirmed_deterministic_dependency" for item in member_rows) else "medium",
            "root_cause_confidence": "high" if len(members) == 1 or any(item["finding_role"] == "consequence" for item in member_rows) else "medium",
            "trace_impact": trace,
            "trace_impact_reason": _trace_reason(trace, primary["short_title"]),
            "calibration_rule_version": CALIBRATION_RULE_VERSION,
            "canonical_rule_category": category,
            "external_rule_mapping_status": mapping,
            "vendor_equivalent_hints": sorted({RULE_CALIBRATION.get(item["rule_code"], meta)[6] for item in members}),
            "adapter_notes": "Conceptual vendor-neutral mapping only; an organization-specific adapter is required.",
            "review_status": review_status,
            "review_comment": "",
            "reviewed_by": "",
            "reviewed_at": "",
            "superseded": False,
            "created_at": created_at,
            "members": member_rows,
        })
    return result


def calibration_status(connection: sqlite3.Connection, vertical: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT calibration_run_id FROM connectivity_qa_calibration_runs WHERE utility_vertical = ? ORDER BY started_at DESC LIMIT 1",
        (vertical,),
    ).fetchone()
    return calibration_run(connection, vertical, row["calibration_run_id"]) if row else {
        "utility_vertical": vertical,
        "status": "not_started",
        "message": "Connectivity QA findings have not been calibrated.",
    }


def calibration_runs(connection: sqlite3.Connection, vertical: str, limit: int, offset: int) -> dict[str, Any]:
    total = int(connection.execute(
        "SELECT COUNT(*) FROM connectivity_qa_calibration_runs WHERE utility_vertical = ?", (vertical,)
    ).fetchone()[0])
    rows = connection.execute(
        """SELECT * FROM connectivity_qa_calibration_runs WHERE utility_vertical = ?
        ORDER BY started_at DESC LIMIT ? OFFSET ?""", (vertical, limit, offset),
    ).fetchall()
    return {"items": [_safe_calibration_run(dict(row)) for row in rows], "pagination": _pagination(total, limit, offset)}


def calibration_run(connection: sqlite3.Connection, vertical: str, calibration_run_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM connectivity_qa_calibration_runs WHERE utility_vertical = ? AND calibration_run_id = ?",
        (vertical, calibration_run_id),
    ).fetchone()
    if not row:
        raise LookupError("Connectivity QA calibration run not found.")
    result = _safe_calibration_run(dict(row))
    result["history"] = [
        _safe_history(dict(item))
        for item in connection.execute(
            """SELECT * FROM connectivity_qa_calibration_history
            WHERE calibration_run_id = ? AND issue_group_id IS NULL ORDER BY created_at""",
            (calibration_run_id,),
        ).fetchall()
    ]
    return result


def issue_groups(connection: sqlite3.Connection, vertical: str, filters: dict[str, Any]) -> dict[str, Any]:
    calibration_run_id = str(filters.get("calibration_run_id") or "")
    if not calibration_run_id:
        row = connection.execute(
            """SELECT calibration_run_id FROM connectivity_qa_calibration_runs
            WHERE utility_vertical = ? AND status = 'succeeded' ORDER BY started_at DESC LIMIT 1""", (vertical,),
        ).fetchone()
        if not row:
            limit, offset = int(filters.get("limit", 100)), int(filters.get("offset", 0))
            return {"items": [], "pagination": _pagination(0, limit, offset), "message": "Connectivity QA findings have not been calibrated."}
        calibration_run_id = row["calibration_run_id"]
    clauses = ["utility_vertical = ?", "calibration_run_id = ?", "superseded = 0"]
    values: list[Any] = [vertical, calibration_run_id]
    for field in ("issue_family", "highest_severity", "display_priority", "trace_impact", "review_status", "primary_rule_code"):
        value = filters.get("severity") if field == "highest_severity" else filters.get(field)
        if value:
            clauses.append(f"{field} = ?")
            values.append(str(value))
    if filters.get("effective_blocking") is not None:
        clauses.append("effective_blocking = ?")
        values.append(int(bool(filters["effective_blocking"])))
    for parameter, column in (("asset_id", "affected_asset_ids_json"), ("relationship_id", "affected_relationship_ids_json")):
        if filters.get(parameter):
            clauses.append(f"{column} LIKE ?")
            values.append(f'%"{str(filters[parameter])}"%')
    where = " AND ".join(clauses)
    limit, offset = int(filters.get("limit", 100)), int(filters.get("offset", 0))
    total = int(connection.execute(f"SELECT COUNT(*) FROM connectivity_qa_issue_groups WHERE {where}", values).fetchone()[0])
    rows = connection.execute(
        f"""SELECT * FROM connectivity_qa_issue_groups WHERE {where}
        ORDER BY CASE display_priority WHEN 'immediate' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2
                 WHEN 'low' THEN 3 ELSE 4 END,
                 CASE highest_severity WHEN 'critical' THEN 0 WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                 issue_group_id LIMIT ? OFFSET ?""",
        (*values, limit, offset),
    ).fetchall()
    return {
        "items": [_safe_group(dict(row)) for row in rows],
        "pagination": _pagination(total, limit, offset),
        "calibration_run_id": calibration_run_id,
    }


def issue_group(connection: sqlite3.Connection, vertical: str, issue_group_id: str) -> dict[str, Any]:
    row = connection.execute(
        """SELECT g.* FROM connectivity_qa_issue_groups g
        JOIN connectivity_qa_calibration_runs r ON r.calibration_run_id = g.calibration_run_id
        WHERE g.utility_vertical = ? AND g.issue_group_id = ?
        ORDER BY r.started_at DESC, r.rowid DESC LIMIT 1""", (vertical, issue_group_id),
    ).fetchone()
    if not row:
        raise LookupError("Connectivity QA issue group not found.")
    group = _safe_group(dict(row))
    members = connection.execute(
        """SELECT m.finding_role, m.relationship_to_primary, m.grouping_reason,
        m.confidence membership_confidence, f.*
        FROM connectivity_qa_group_members m
        JOIN connectivity_qa_findings f ON f.qa_run_id = ? AND f.finding_id = m.finding_id
        WHERE m.calibration_run_id = ? AND m.issue_group_id = ?
        ORDER BY CASE m.finding_role WHEN 'primary' THEN 0 WHEN 'independent' THEN 1
                 WHEN 'contributing' THEN 2 WHEN 'corroborating' THEN 3
                 WHEN 'consequence' THEN 4 ELSE 5 END, f.rule_code""",
        (group["qa_run_id"], group["calibration_run_id"], issue_group_id),
    ).fetchall()
    group["members"] = [_safe_member_finding(dict(item)) for item in members]
    group["graph_context"] = _group_graph_context(connection, group)
    group["history"] = [
        _safe_history(dict(item))
        for item in connection.execute(
            """SELECT * FROM connectivity_qa_calibration_history
            WHERE calibration_run_id = ? AND issue_group_id = ? ORDER BY created_at""",
            (group["calibration_run_id"], issue_group_id),
        ).fetchall()
    ]
    return group


def review_issue_group(
    connection: sqlite3.Connection,
    vertical: str,
    issue_group_id: str,
    action: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if action not in REVIEW_ACTIONS:
        raise LookupError("Unsupported issue-group review action.")
    payload = payload or {}
    reviewer = str(payload.get("reviewer", "")).strip()[:100]
    reason = str(payload.get("comment") or payload.get("rationale") or "").strip()[:1000]
    if not reviewer:
        raise ValueError("Reviewer is required.")
    if action in {"defer", "accept-risk", "mark-false-positive"} and not reason:
        raise ValueError("A review rationale is required for this action.")
    group = issue_group(connection, vertical, issue_group_id)
    if action == "accept-risk" and group["highest_severity"] == "critical" and not reason:
        raise ValueError("Critical findings require an explicit accepted-risk note.")
    status = REVIEW_ACTIONS[action]
    now = intake_registry_service.utc_now()
    prior = {
        "review_status": group["review_status"],
        "review_comment": group["review_comment"],
        "reviewed_by": group["reviewed_by"],
    }
    for member in group["members"]:
        connection.execute(
            """UPDATE connectivity_qa_findings SET review_status = ?, review_comment = ?,
            reviewed_by = ?, reviewed_at = ?, updated_at = ?
            WHERE qa_run_id = ? AND finding_id = ?""",
            (status, reason, reviewer, now, now, group["qa_run_id"], member["finding_id"]),
        )
        connection.execute(
            """INSERT INTO connectivity_qa_history
            (history_id, qa_run_id, finding_id, action, prior_value_json, new_value_json, actor, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), group["qa_run_id"], member["finding_id"], f"group_{action}",
                _dump({"review_status": member["review_status"]}),
                _dump({"review_status": status}), reviewer, reason, now,
            ),
        )
        _calibration_history(
            connection, group["calibration_run_id"], issue_group_id, member["finding_id"], action,
            prior, {"review_status": status}, "human", reviewer, reason,
        )
    connection.execute(
        """UPDATE connectivity_qa_issue_groups SET review_status = ?, review_comment = ?,
        reviewed_by = ?, reviewed_at = ? WHERE calibration_run_id = ? AND issue_group_id = ?""",
        (status, reason, reviewer, now, group["calibration_run_id"], issue_group_id),
    )
    _refresh_review_summaries(connection, group["qa_run_id"], group["calibration_run_id"])
    connection.commit()
    return issue_group(connection, vertical, issue_group_id)


def synchronize_member_review(
    connection: sqlite3.Connection,
    qa_run_id: str,
    finding_id: str,
    actor: str,
    reason: str,
) -> None:
    groups = connection.execute(
        """SELECT DISTINCT g.calibration_run_id, g.issue_group_id, g.review_status
        FROM connectivity_qa_issue_groups g
        JOIN connectivity_qa_group_members m
          ON m.calibration_run_id = g.calibration_run_id AND m.issue_group_id = g.issue_group_id
        WHERE g.qa_run_id = ? AND m.finding_id = ? AND g.superseded = 0""",
        (qa_run_id, finding_id),
    ).fetchall()
    changed_runs: set[str] = set()
    for group in groups:
        statuses = {
            row["review_status"]
            for row in connection.execute(
                """SELECT f.review_status FROM connectivity_qa_group_members m
                JOIN connectivity_qa_issue_groups g
                  ON g.calibration_run_id = m.calibration_run_id AND g.issue_group_id = m.issue_group_id
                JOIN connectivity_qa_findings f
                  ON f.qa_run_id = g.qa_run_id AND f.finding_id = m.finding_id
                WHERE m.calibration_run_id = ? AND m.issue_group_id = ?""",
                (group["calibration_run_id"], group["issue_group_id"]),
            ).fetchall()
        }
        status = next(iter(statuses)) if len(statuses) == 1 else "mixed"
        if status == group["review_status"]:
            continue
        connection.execute(
            """UPDATE connectivity_qa_issue_groups SET review_status = ?
            WHERE calibration_run_id = ? AND issue_group_id = ?""",
            (status, group["calibration_run_id"], group["issue_group_id"]),
        )
        _calibration_history(
            connection,
            group["calibration_run_id"],
            group["issue_group_id"],
            finding_id,
            "member_review_synchronized",
            {"review_status": group["review_status"]},
            {"review_status": status},
            "human",
            actor,
            reason or "Member-level review changed the derived group state.",
        )
        changed_runs.add(group["calibration_run_id"])
    for calibration_run_id in changed_runs:
        _refresh_review_summaries(connection, qa_run_id, calibration_run_id)


def calibrated_summary(connection: sqlite3.Connection, vertical: str) -> dict[str, Any]:
    status = calibration_status(connection, vertical)
    return status.get("summary", status)


def calibrated_summary_from_groups(findings: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    roles = Counter(member["finding_role"] for group in groups for member in group["members"])
    affected_assets = {item for group in groups for item in group["affected_asset_ids"]}
    affected_relationships = {item for group in groups for item in group["affected_relationship_ids"]}
    rule_diagnostics: dict[str, Any] = {}
    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    member_roles: dict[str, str] = {}
    for group in groups:
        for member in group["members"]:
            member_roles[member["finding_id"]] = member["finding_role"]
    for finding in findings:
        by_rule[finding["rule_code"]].append(finding)
    for code, rows in sorted(by_rule.items()):
        role_counts = Counter(member_roles.get(row["finding_id"], "independent") for row in rows)
        rule_diagnostics[code] = {
            "raw_finding_count": len(rows),
            "unique_affected_assets": len({value for row in rows for value in (row.get("asset_id"), row.get("related_asset_id")) if value}),
            "unique_affected_relationships": len({row["relationship_id"] for row in rows if row.get("relationship_id")}),
            "primary_issue_candidates": role_counts["primary"] + role_counts["independent"],
            "likely_consequence_findings": role_counts["consequence"],
            "duplicate_candidates": role_counts["corroborating"],
            "severity_appropriateness": "preserved",
            "blocking_appropriateness": "preserved_as_technical_evidence",
            "recommended_calibration_action": "Present beneath its deterministic root cause." if role_counts["consequence"] else "Retain as a separate actionable condition.",
        }
    return {
        "calibration_rule_version": CALIBRATION_RULE_VERSION,
        "technical_findings": len(findings),
        "actionable_issue_groups": len(groups),
        "primary_blockers": sum(bool(group["effective_blocking"]) for group in groups),
        "consequence_findings": roles["consequence"],
        "independent_findings": roles["independent"],
        "informational_conditions": roles["informational"],
        "affected_assets": len(affected_assets),
        "affected_relationships": len(affected_relationships),
        "unresolved_primary_groups": sum(group["review_status"] in {"open", "mixed"} for group in groups),
        "acknowledged_primary_groups": sum(group["review_status"] == "acknowledged" for group in groups),
        "accepted_risk_groups": sum(group["review_status"] == "accepted_risk" for group in groups),
        "false_positive_groups": sum(group["review_status"] == "false_positive" for group in groups),
        "findings_hidden_by_display_filters": 0,
        "trace_stopping_groups": sum(group["trace_impact"] == "stops_trace" for group in groups),
        "trace_limiting_groups": sum(group["trace_impact"] == "limits_trace" for group in groups),
        "by_severity": dict(Counter(row["severity"] for row in findings)),
        "by_issue_family": dict(Counter(group["issue_family"] for group in groups)),
        "by_trace_impact": dict(Counter(group["trace_impact"] for group in groups)),
        "by_display_priority": dict(Counter(group["display_priority"] for group in groups)),
        "by_review_status": dict(Counter(group["review_status"] for group in groups)),
        "rule_diagnostics": rule_diagnostics,
        "limitations": [
            "Calibration groups immutable technical findings; it does not suppress, repair, or trace the network.",
            "Root-cause relationships are deterministic candidates based on explicit canonical evidence.",
            "Vendor-equivalent hints are conceptual and require organization-specific adapters.",
        ],
    }


def _root_key(finding: dict[str, Any], assets: dict[str, dict[str, Any]]) -> str:
    code = finding["rule_code"]
    asset_id = str(finding.get("asset_id") or "")
    relationship_id = str(finding.get("relationship_id") or "")
    family = RULE_CALIBRATION[code][0]
    if code in {"ELEC-001", "ELEC-002"}:
        return f"conductor_connectivity:{asset_id}"
    if code in {"ELEC-009", "ELEC-010"}:
        return f"membership_conflict:{relationship_id or asset_id}"
    if code in {"SHARED-005", "ELEC-014", "TEL-013"}:
        return f"lifecycle_conflict:{relationship_id or asset_id}"
    if code in {"SHARED-004", "TEL-014"}:
        return f"provisional_evidence:{relationship_id or asset_id}"
    if code in {"TEL-001", "TEL-002"}:
        cable = next(
            (
                candidate for candidate in (asset_id, finding.get("related_asset_id"))
                if candidate and assets.get(candidate, {}).get("asset_class") == "fiber_cable"
            ),
            asset_id or relationship_id,
        )
        return f"cable_endpoint:{cable}"
    if code in {"TEL-004", "TEL-005", "TEL-015"}:
        return f"capacity_consistency:{asset_id}"
    if code in {"TEL-003", "TEL-006"}:
        return f"strand_allocation:{asset_id}"
    entity = asset_id or relationship_id or finding["finding_id"]
    return f"{family}:{code}:{entity}"


def _precedence_key(finding: dict[str, Any]) -> tuple[int, int, int, str, str]:
    meta = RULE_CALIBRATION.get(finding["rule_code"])
    precedence = meta[2] if meta else 10
    dependency_child = int(finding["rule_code"] in DEPENDENCIES)
    return precedence, dependency_child, -_SEVERITY_RANK.get(finding["severity"], -1), finding["rule_code"], finding["finding_id"]


def _member(
    primary: dict[str, Any],
    finding: dict[str, Any],
    group: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    if len(group) == 1:
        role = "informational" if finding["severity"] == "info" else "independent"
        relation, reason, confidence = "independent", "Separate corrective action or evidence scope.", "high"
    elif finding["finding_id"] == primary["finding_id"]:
        role, relation, reason, confidence = "primary", "root_cause_candidate", "Highest deterministic root-cause precedence in this evidence group.", "high"
    elif primary["rule_code"] in DEPENDENCIES.get(finding["rule_code"], set()):
        role, relation, reason, confidence = "consequence", "confirmed_deterministic_dependency", f"{finding['rule_code']} is an allowlisted consequence of {primary['rule_code']} on the same canonical evidence.", "high"
    elif finding["rule_code"] == primary["rule_code"]:
        role, relation, reason, confidence = "corroborating", "shared_root_cause", "The same rule provides additional evidence for this root-cause key.", "high"
    else:
        role, relation, reason, confidence = "contributing", "possible_dependency", "The finding shares the same explicit asset or relationship and corrective-action family.", "medium"
    return {
        "finding_id": finding["finding_id"],
        "finding_role": role,
        "relationship_to_primary": relation,
        "grouping_reason": reason,
        "confidence": confidence,
        "created_at": created_at,
    }


def _priority(severity: str, blocking: bool, trace: str, members: list[dict[str, Any]]) -> str:
    if trace == "stops_trace" and blocking:
        return "immediate" if severity == "critical" else "high"
    if blocking or trace == "limits_trace":
        return "high"
    if all(item["finding_role"] == "informational" for item in members):
        return "informational"
    if trace in {"no_trace_effect", "advisory"}:
        return "low" if severity in {"info", "warning"} else "normal"
    return "normal"


def _trace_reason(trace: str, title: str) -> str:
    descriptions = {
        "stops_trace": "The condition prevents a defensible future path through the affected evidence.",
        "limits_trace": "A future trace can only proceed to the confirmed evidence boundary.",
        "introduces_ambiguity": "A future trace may continue provisionally but must report ambiguous membership or relationships.",
        "advisory": "The condition remains visible for review but does not independently block continuity.",
        "no_trace_effect": "The condition is operational context that a future trace should honor without treating it as a defect.",
        "not_evaluated": "Trace impact has not been evaluated for this condition.",
    }
    return f"{title}: {descriptions[trace]}"


def _review_status(findings: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("review_status") or "open") for item in findings}
    return statuses.pop() if len(statuses) == 1 else "mixed"


def _insert_group(connection: sqlite3.Connection, calibration_run_id: str, group: dict[str, Any]) -> None:
    connection.execute(
        """INSERT INTO connectivity_qa_issue_groups
        (calibration_run_id, issue_group_id, qa_run_id, utility_vertical, issue_family, root_cause_key,
         primary_finding_id, member_finding_ids_json, affected_asset_ids_json, affected_relationship_ids_json,
         primary_rule_code, related_rule_codes_json, group_title, group_summary, highest_severity,
         effective_blocking, technical_finding_count, recommended_action, action_category, display_priority,
         confidence, root_cause_confidence, trace_impact, trace_impact_reason, calibration_rule_version,
         canonical_rule_category, external_rule_mapping_status, vendor_equivalent_hints_json, adapter_notes,
         review_status, review_comment, reviewed_by, reviewed_at, superseded, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            calibration_run_id, group["issue_group_id"], group["qa_run_id"], group["utility_vertical"],
            group["issue_family"], group["root_cause_key"], group["primary_finding_id"],
            _dump(group["member_finding_ids"]), _dump(group["affected_asset_ids"]),
            _dump(group["affected_relationship_ids"]), group["primary_rule_code"],
            _dump(group["related_rule_codes"]), group["group_title"], group["group_summary"],
            group["highest_severity"], int(group["effective_blocking"]), group["technical_finding_count"],
            group["recommended_action"], group["action_category"], group["display_priority"],
            group["confidence"], group["root_cause_confidence"], group["trace_impact"],
            group["trace_impact_reason"], group["calibration_rule_version"], group["canonical_rule_category"],
            group["external_rule_mapping_status"], _dump(group["vendor_equivalent_hints"]),
            group["adapter_notes"], group["review_status"], group["review_comment"], group["reviewed_by"],
            group["reviewed_at"], int(group["superseded"]), group["created_at"],
        ),
    )
    for member in group["members"]:
        connection.execute(
            """INSERT INTO connectivity_qa_group_members
            (calibration_run_id, issue_group_id, finding_id, finding_role, relationship_to_primary,
             grouping_reason, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                calibration_run_id, group["issue_group_id"], member["finding_id"], member["finding_role"],
                member["relationship_to_primary"], member["grouping_reason"], member["confidence"], member["created_at"],
            ),
        )


def _prior_reviews(connection: sqlite3.Connection, vertical: str) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """SELECT g.* FROM connectivity_qa_issue_groups g
        JOIN connectivity_qa_calibration_runs r ON r.calibration_run_id = g.calibration_run_id
        WHERE g.utility_vertical = ? ORDER BY r.started_at DESC""", (vertical,),
    ).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result.setdefault(row["issue_group_id"], dict(row))
    return result


def _record_superseded_groups(
    connection: sqlite3.Connection,
    vertical: str,
    calibration_run_id: str,
    current_ids: set[str],
    created_at: str,
) -> None:
    previous = connection.execute(
        """SELECT g.calibration_run_id, g.issue_group_id FROM connectivity_qa_issue_groups g
        JOIN connectivity_qa_calibration_runs r ON r.calibration_run_id = g.calibration_run_id
        WHERE g.utility_vertical = ? AND g.calibration_run_id != ? AND g.superseded = 0
        ORDER BY r.started_at DESC""", (vertical, calibration_run_id),
    ).fetchall()
    for row in previous:
        changed = row["issue_group_id"] not in current_ids
        connection.execute(
            """UPDATE connectivity_qa_issue_groups SET superseded = 1
            WHERE calibration_run_id = ? AND issue_group_id = ?""",
            (row["calibration_run_id"], row["issue_group_id"]),
        )
        _calibration_history(
            connection, row["calibration_run_id"], row["issue_group_id"], None,
            "superseded" if changed else "recalibrated",
            {"superseded": False}, {"superseded": True, "recalibrated_at": created_at},
            "system", "calibration_engine",
            "Issue-group membership changed." if changed else "A newer immutable calibration replaced this active group.",
        )


def _refresh_review_summaries(connection: sqlite3.Connection, qa_run_id: str, calibration_run_id: str) -> None:
    qa_row = connection.execute(
        "SELECT summary_json FROM connectivity_qa_runs WHERE qa_run_id = ?", (qa_run_id,)
    ).fetchone()
    qa_summary = _load(qa_row["summary_json"]) if qa_row else {}
    qa_summary["by_review_status"] = dict(Counter(
        row["review_status"] for row in connection.execute(
            "SELECT review_status FROM connectivity_qa_findings WHERE qa_run_id = ?", (qa_run_id,)
        ).fetchall()
    ))
    connection.execute(
        "UPDATE connectivity_qa_runs SET summary_json = ? WHERE qa_run_id = ?", (_dump(qa_summary), qa_run_id)
    )
    run_row = connection.execute(
        "SELECT summary_json FROM connectivity_qa_calibration_runs WHERE calibration_run_id = ?",
        (calibration_run_id,),
    ).fetchone()
    summary = _load(run_row["summary_json"]) if run_row else {}
    summary["by_review_status"] = dict(Counter(
        row["review_status"] for row in connection.execute(
            "SELECT review_status FROM connectivity_qa_issue_groups WHERE calibration_run_id = ?",
            (calibration_run_id,),
        ).fetchall()
    ))
    summary["unresolved_primary_groups"] = sum(
        count for status, count in summary["by_review_status"].items() if status in {"open", "mixed"}
    )
    summary["acknowledged_primary_groups"] = summary["by_review_status"].get("acknowledged", 0)
    summary["accepted_risk_groups"] = summary["by_review_status"].get("accepted_risk", 0)
    summary["false_positive_groups"] = summary["by_review_status"].get("false_positive", 0)
    connection.execute(
        "UPDATE connectivity_qa_calibration_runs SET summary_json = ? WHERE calibration_run_id = ?",
        (_dump(summary), calibration_run_id),
    )


def _group_graph_context(connection: sqlite3.Connection, group: dict[str, Any]) -> dict[str, Any]:
    assets = []
    if group["affected_asset_ids"]:
        placeholders = ",".join("?" for _ in group["affected_asset_ids"])
        assets = [
            dict(row) for row in connection.execute(
                f"""SELECT asset_id, canonical_name, asset_class, lifecycle_status, operational_status
                FROM canonical_utility_assets WHERE asset_id IN ({placeholders})""",
                group["affected_asset_ids"],
            ).fetchall()
        ]
    relationships = []
    if group["affected_relationship_ids"]:
        placeholders = ",".join("?" for _ in group["affected_relationship_ids"])
        relationships = [
            {**dict(row), "provisional": bool(row["provisional"])}
            for row in connection.execute(
                f"""SELECT relationship_id, from_asset_id, to_asset_id, relationship_type, direction,
                confidence, source, provisional FROM utility_asset_relationships
                WHERE relationship_id IN ({placeholders})""",
                group["affected_relationship_ids"],
            ).fetchall()
        ]
    return {
        "assets": assets,
        "relationships": relationships,
        "geometry": "logical_relationship_view_only",
        "disclaimer": "Logical relationship view - not an engineering diagram.",
    }


def _calibration_history(
    connection: sqlite3.Connection,
    calibration_run_id: str,
    issue_group_id: str | None,
    finding_id: str | None,
    action: str,
    prior: Any,
    new: Any,
    actor_type: str,
    actor: str,
    reason: str,
) -> None:
    connection.execute(
        """INSERT INTO connectivity_qa_calibration_history
        (history_id, calibration_run_id, issue_group_id, finding_id, action, prior_value_json,
         new_value_json, actor_type, actor, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()), calibration_run_id, issue_group_id, finding_id, action,
            _dump(prior), _dump(new), actor_type, actor[:100], reason[:1000], intake_registry_service.utc_now(),
        ),
    )


def _safe_calibration_run(row: dict[str, Any]) -> dict[str, Any]:
    row["summary"] = _load(row.pop("summary_json", "{}"))
    row["warnings"] = _load(row.pop("warnings_json", "[]"))
    row.pop("input_fingerprint", None)
    return row


def _safe_group(row: dict[str, Any]) -> dict[str, Any]:
    for field in (
        "member_finding_ids_json", "affected_asset_ids_json", "affected_relationship_ids_json",
        "related_rule_codes_json", "vendor_equivalent_hints_json",
    ):
        row[field.removesuffix("_json")] = _load(row.pop(field, "[]"))
    row["effective_blocking"] = bool(row["effective_blocking"])
    row["superseded"] = bool(row["superseded"])
    return row


def _safe_member_finding(row: dict[str, Any]) -> dict[str, Any]:
    row["blocking"] = bool(row["blocking"])
    row["evidence"] = _load(row.pop("evidence_json", "{}"))
    return row


def _safe_history(row: dict[str, Any]) -> dict[str, Any]:
    row["prior_value"] = _load(row.pop("prior_value_json", "{}"))
    row["new_value"] = _load(row.pop("new_value_json", "{}"))
    return row


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _load(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _pagination(total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"total": total, "limit": limit, "offset": offset, "has_more": offset + limit < total}
