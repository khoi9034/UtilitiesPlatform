from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import fields
from pathlib import Path
from typing import Any

from app.services import data_storage_service, intake_registry_service
from app.services.review_automation.models import POLICY_MODES, RULE_VERSION, StageResult
from app.services.review_automation.name_normalization import normalize_package_names
from app.services.source_inspection import normalization
from app.services.source_inspection import registry as inspection_registry
from app.services.source_inspection.models import ClassificationCandidate, SourceLayer, StagingPlanItem

REFERENCE_SYSTEMS = {"shared_reference", "environmental_regulatory", "planning_reference"}
SENSITIVE_FIELD_TOKENS = {"password", "credential", "connectionstring", "ssn", "email", "phone", "customername", "accountnumber"}
JSON_FIELDS = {
    "extent_summary": ("extent_summary_json", {}),
    "field_profile": ("field_profile_json", []),
    "domain_profile": ("domain_profile_json", {}),
    "subtype_profile": ("subtype_profile_json", {}),
    "relationship_profile": ("relationship_profile_json", []),
    "likely_id_fields": ("likely_id_fields_json", []),
    "likely_status_fields": ("likely_status_fields_json", []),
    "likely_date_fields": ("likely_date_fields_json", []),
    "likely_dimension_fields": ("likely_dimension_fields_json", []),
    "likely_owner_fields": ("likely_owner_fields_json", []),
    "domain_names": ("domain_names_json", []),
}
logger = logging.getLogger(__name__)


def initialize(connection: Any) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS review_automation_runs (
            automation_run_id TEXT PRIMARY KEY, submission_id TEXT NOT NULL, inspection_run_id TEXT NOT NULL,
            input_fingerprint TEXT NOT NULL, reused_run_id TEXT, rule_version TEXT NOT NULL, policy_mode TEXT NOT NULL,
            status TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, layers_processed INTEGER NOT NULL DEFAULT 0,
            taxonomy_approved INTEGER NOT NULL DEFAULT 0, taxonomy_deferred INTEGER NOT NULL DEFAULT 0,
            coordinate_blocked INTEGER NOT NULL DEFAULT 0, duplicate_groups INTEGER NOT NULL DEFAULT 0,
            sensitivity_inherited INTEGER NOT NULL DEFAULT 0, owner_confirmation_required INTEGER NOT NULL DEFAULT 0,
            staging_ready INTEGER NOT NULL DEFAULT 0, staging_blocked INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT, safe_error_code TEXT, safe_error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_review_automation_runs_submission
            ON review_automation_runs(submission_id, started_at);
        CREATE TABLE IF NOT EXISTS review_automation_stage_runs (
            stage_run_id TEXT PRIMARY KEY, automation_run_id TEXT NOT NULL, stage_name TEXT NOT NULL,
            status TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
            records_read INTEGER NOT NULL DEFAULT 0, records_updated INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT, safe_error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_review_automation_stages_run
            ON review_automation_stage_runs(automation_run_id, stage_name);
        CREATE TABLE IF NOT EXISTS automated_layer_decisions (
            decision_id TEXT PRIMARY KEY, automation_run_id TEXT NOT NULL, submission_id TEXT NOT NULL,
            layer_id TEXT NOT NULL, decision_dimension TEXT NOT NULL, prior_value TEXT, recommended_value TEXT,
            applied_value TEXT, decision_type TEXT, confidence TEXT, evidence_json TEXT, blocker_json TEXT,
            rule_code TEXT, rule_version TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_automated_decisions_run
            ON automated_layer_decisions(automation_run_id, layer_id);
        CREATE TABLE IF NOT EXISTS automated_layer_state (
            layer_id TEXT PRIMARY KEY, submission_id TEXT NOT NULL, automation_run_id TEXT NOT NULL,
            canonical_layer_name TEXT NOT NULL, source_prefix_tokens_json TEXT, classification_tokens_json TEXT,
            taxonomy_status TEXT NOT NULL, taxonomy_decision TEXT NOT NULL, approved_utility_system TEXT,
            approved_network_group TEXT, approved_asset_category TEXT, approved_asset_subcategory TEXT,
            approved_operational_role TEXT, approved_lifecycle_representation TEXT, taxonomy_confidence TEXT,
            taxonomy_evidence_json TEXT, coordinate_status TEXT NOT NULL, coordinate_blocker TEXT,
            inherited_sensitivity TEXT, sensitivity_status TEXT NOT NULL, public_use_allowed INTEGER NOT NULL DEFAULT 0,
            export_allowed INTEGER NOT NULL DEFAULT 0, sensitivity_blocker TEXT, duplicate_status TEXT NOT NULL,
            duplicate_group_id TEXT, owner_candidate TEXT, owner_confidence TEXT, owner_status TEXT,
            owner_blocker TEXT, staging_readiness TEXT NOT NULL, staging_blockers_json TEXT,
            approved_for_staging INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
        );
        """
    )
    connection.commit()


def run_automated_review(
    submission_id: str,
    *,
    policy_mode: str = "conservative",
    force_recalculate: bool = False,
    preserve_manual_overrides: bool = True,
) -> dict[str, object]:
    if policy_mode not in POLICY_MODES:
        raise ValueError("V1 supports only the conservative policy.")
    root = data_storage_service.get_storage_paths().root
    submission = intake_registry_service.get_submission(root, submission_id)
    if not submission:
        raise KeyError("Submission not found.")
    snapshot = load_snapshot(root, submission_id)
    validate_inspection(snapshot)
    fingerprint = input_fingerprint(submission_id, snapshot, policy_mode)
    previous = latest_matching_run(root, submission_id, fingerprint)
    if previous and not force_recalculate:
        result = record_unchanged_run(root, snapshot, previous, policy_mode, fingerprint)
        result["message"] = "No source or rule changes detected."
        return result

    run_id = str(uuid.uuid4())
    start_run(root, run_id, snapshot, policy_mode, fingerprint)
    try:
        layers = [source_layer(row) for row in snapshot["layers"]]
        def mark(stage: StageResult) -> None:
            record_stage(root, run_id, stage)

        mark(StageResult("validate_inspection", len(layers), len(layers)))
        sensitivity = apply_sensitivity_inheritance(str(submission.get("sensitivity_level", "restricted")), layers)
        mark(StageResult("apply_sensitivity", len(layers), sum(item["status"] == "inherited_from_package" for item in sensitivity.values())))
        names = normalize_package_names([layer.source_layer_name for layer in layers])
        mark(StageResult("normalize_names", len(layers), len(layers)))
        candidates = recalculate_taxonomy(layers, submission, names)
        manual = snapshot["manual_reviews"] if preserve_manual_overrides else {}
        if force_recalculate:
            manual = {
                layer_id: review for layer_id, review in manual.items()
                if review.get("classification_decision") in {"manual_override", "excluded"}
            }
        taxonomy = {layer.layer_id: evaluate_taxonomy(layer, candidates[layer.layer_id], manual.get(layer.layer_id)) for layer in layers}
        mark(StageResult("classify_layers", len(layers), len(layers)))
        coordinates = {layer.layer_id: evaluate_coordinates(layer) for layer in layers}
        mark(StageResult("evaluate_coordinates", len(layers), len(layers)))
        groups, duplicate_by_layer = evaluate_duplicates(submission_id, layers, names, snapshot["duplicate_groups"])
        mark(StageResult("detect_duplicates", len(layers), len(groups)))
        ownership = {
            layer.layer_id: evaluate_ownership(layer, candidates[layer.layer_id][0], manual.get(layer.layer_id))
            for layer in layers
        }
        mark(StageResult("evaluate_ownership", len(layers), len(layers)))
        states = calculate_staging_readiness(layers, names, taxonomy, coordinates, sensitivity, duplicate_by_layer, ownership)
        mark(StageResult("calculate_staging_readiness", len(layers), len(layers)))
        plan = generate_staging_preview(submission_id, layers, states)
        mark(StageResult("generate_staging_preview", len(layers), len(plan)))
        counts = persist_results(root, run_id, submission_id, layers, states, groups, plan)
        mark(StageResult("write_summary", len(layers), len(states)))
        complete_run(root, run_id, counts)
        intake_registry_service.update_submission(
            root, submission_id, current_status="automated_review_complete",
            classification_status="automation_complete", staging_status="not_approved",
        )
        intake_registry_service.add_event(
            root, event_id=str(uuid.uuid4()), submission_id=submission_id,
            event_type="automated_review_completed", previous_status=str(submission.get("current_status", "")),
            new_status="automated_review_complete",
            message=f"Conservative automated review completed for {len(layers)} inspected layers; final staging approval remains human-only.",
            actor="review_automation",
        )
        result = run_detail(submission_id, run_id) or {}
        result["message"] = "Automated review complete. Review exceptions before any staging approval."
        return result
    except Exception as exc:
        logger.exception("Automated review failed safely for submission %s", submission_id)
        fail_run(root, run_id, exc)
        raise


def load_snapshot(root: Path, submission_id: str) -> dict[str, Any]:
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        container = connection.execute("SELECT * FROM inspection_containers WHERE submission_id=?", (submission_id,)).fetchone()
        layers = connection.execute("SELECT * FROM inspected_layers WHERE submission_id=? ORDER BY source_layer_name", (submission_id,)).fetchall()
        candidates = connection.execute(
            "SELECT * FROM layer_classification_candidates WHERE layer_id IN (SELECT layer_id FROM inspected_layers WHERE submission_id=?) ORDER BY layer_id, rank",
            (submission_id,),
        ).fetchall()
        reviews = connection.execute(
            "SELECT r.* FROM layer_reviews r JOIN inspected_layers l ON l.layer_id=r.layer_id WHERE l.submission_id=? ORDER BY r.created_at DESC",
            (submission_id,),
        ).fetchall()
        groups = connection.execute("SELECT * FROM duplicate_groups WHERE submission_id=?", (submission_id,)).fetchall()
    manual: dict[str, dict[str, Any]] = {}
    for review in reviews:
        row = dict(review)
        if row["layer_id"] not in manual and not str(row.get("reviewer", "")).startswith("review_automation"):
            manual[row["layer_id"]] = row
    return {
        "container": dict(container) if container else {},
        "layers": [dict(row) for row in layers],
        "candidates": [dict(row) for row in candidates],
        "manual_reviews": manual,
        "duplicate_groups": {row["duplicate_group_id"]: dict(row) for row in groups},
    }


def validate_inspection(snapshot: dict[str, Any]) -> None:
    if snapshot["container"].get("inspection_status") not in {"complete", "inspection_complete"}:
        raise ValueError("Source inspection must complete before automated review.")
    if not snapshot["layers"]:
        raise ValueError("No inspected layers are available for automated review.")


def input_fingerprint(submission_id: str, snapshot: dict[str, Any], policy_mode: str) -> str:
    ignored = {
        "classification_status", "duplicate_status", "coordinate_status", "sensitivity_status", "staging_status",
        "routing_state", "latest_review_status", "latest_reviewer", "created_at", "updated_at",
    }
    payload = {
        "submission_id": submission_id,
        "inspection_run_id": snapshot["container"].get("inspection_run_id", ""),
        "layers": [{key: value for key, value in row.items() if key not in ignored} for row in snapshot["layers"]],
        "candidates": snapshot["candidates"],
        "rule_version": RULE_VERSION,
        "policy_mode": policy_mode,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def apply_sensitivity_inheritance(package_sensitivity: str, layers: list[SourceLayer]) -> dict[str, dict[str, Any]]:
    inherited = package_sensitivity if package_sensitivity in {"restricted", "confidential", "internal", "public"} else "restricted"
    output: dict[str, dict[str, Any]] = {}
    for layer in layers:
        field_names = {str(field.get("name", "")).lower().replace("_", "") for field in layer.field_profile}
        conflicts = sorted(token for token in SENSITIVE_FIELD_TOKENS if any(token in name for name in field_names))
        output[layer.layer_id] = {
            "inherited": inherited,
            "status": "needs_sensitivity_review" if conflicts else "inherited_from_package",
            "public_use_allowed": inherited == "public" and not conflicts,
            "export_allowed": inherited == "public" and not conflicts,
            "blocker": f"Potential sensitive field metadata detected: {', '.join(conflicts)}" if conflicts else "",
            "evidence": ["Package sensitivity inherited.", "No raw values were inspected."] if not conflicts else ["Child field names require manual sensitivity review."],
        }
    return output


def recalculate_taxonomy(
    layers: list[SourceLayer], submission: dict[str, Any], names: dict[str, dict[str, object]],
) -> dict[str, list[ClassificationCandidate]]:
    output: dict[str, list[ClassificationCandidate]] = {}
    for layer in layers:
        copy = clone_layer(layer)
        copy.source_layer_name = str(names[layer.source_layer_name]["canonical_layer_name"])
        output[layer.layer_id] = normalization.classify_layer(copy, submission)
        for candidate in output[layer.layer_id]:
            candidate.evidence.append(f"Canonical layer name: {copy.source_layer_name}")
    return output


def evaluate_taxonomy(layer: SourceLayer, candidates: list[ClassificationCandidate], manual: dict[str, Any] | None) -> dict[str, Any]:
    top = candidates[0]
    if manual and manual.get("classification_decision") == "excluded":
        return taxonomy_result("excluded", "excluded", top, ["Human exclusion preserved."], ["Manual decision preserved."])
    if manual and manual.get("classification_decision") == "deferred":
        return taxonomy_result("deferred", "deferred", top, ["Human deferral preserved."], ["Manual decision preserved."])
    if manual and manual.get("classification_decision") == "manual_override":
        top = ClassificationCandidate(
            candidate_id=top.candidate_id, layer_id=layer.layer_id, rank=1,
            utility_system=str(manual.get("approved_utility_system", "")),
            network_group=str(manual.get("approved_network_group", "")),
            asset_category=str(manual.get("approved_asset_category", "")),
            asset_subcategory=str(manual.get("approved_asset_subcategory", "")),
            operational_role=str(manual.get("approved_operational_role", "")),
            lifecycle_representation=str(manual.get("approved_lifecycle_representation", "")),
            owner_or_jurisdiction=str(manual.get("approved_owner_or_jurisdiction", "")),
            confidence="human_confirmed", score=1.0,
        )
        return taxonomy_result("approved", "manual_override_preserved", top, ["Human taxonomy override preserved."], [])

    geometry_ok = geometry_compatible(layer.geometry_type, top)
    field_evidence = corroborating_fields(layer, top)
    contradictory = any(candidate.utility_system != top.utility_system and top.score - candidate.score <= 0.05 for candidate in candidates[1:])
    semantic_conflict = "undergroundstoragetank" in normalization.normalize_name(layer.source_layer_name) and top.utility_system == "water"
    evidence = [*top.evidence]
    if geometry_ok:
        evidence.append(f"Geometry supports {top.asset_category}.")
    if field_evidence:
        evidence.append(f"Corroborating fields: {', '.join(field_evidence)}.")
    blockers: list[str] = []
    if top.confidence != "high":
        blockers.append("Top candidate confidence is not high.")
    if not geometry_ok:
        blockers.append("Geometry is incompatible with the recommendation.")
    if not field_evidence:
        blockers.append("Evidence is not corroborated beyond naming and generic geometry.")
    if contradictory or semantic_conflict:
        blockers.append("Classification evidence is contradictory.")
    if not blockers:
        return taxonomy_result("approved", "reference_approved" if top.utility_system in REFERENCE_SYSTEMS else "approved", top, evidence, [])
    reason = "classification_conflict" if contradictory or semantic_conflict else "needs_data_owner_confirmation" if top.confidence == "unavailable" else "needs_taxonomy_review"
    return taxonomy_result("deferred", reason, top, evidence, blockers)


def taxonomy_result(status: str, decision: str, candidate: ClassificationCandidate, evidence: list[str], blockers: list[str]) -> dict[str, Any]:
    return {"status": status, "decision": decision, "candidate": candidate, "confidence": candidate.confidence, "evidence": evidence, "blockers": blockers}


def geometry_compatible(geometry: str, candidate: ClassificationCandidate) -> bool:
    expected = {
        "pipe": {"polyline"}, "disposal_line": {"polyline"}, "access_structure": {"point"},
        "tank": {"point"}, "well": {"point"}, "treatment_component": {"point"},
        "disposal_area": {"polygon", "polyline"}, "boundary": {"polygon", "polyline"},
    }
    return geometry.lower() in expected.get(candidate.asset_category, {geometry.lower()})


def corroborating_fields(layer: SourceLayer, candidate: ClassificationCandidate) -> list[str]:
    actual = {str(field.get("name", "")).lower().replace("_", "") for field in layer.field_profile}
    tokens = {
        "pipe": {"diameter", "diam", "size", "sz", "material", "ma", "length", "usnode", "dsnode", "assetid", "uniqueid"},
        "force_main": {"diameter", "sz", "material", "ma", "length", "usnode", "dsnode", "uniqueid"},
        "gravity_main": {"diameter", "sz", "material", "ma", "length", "usnode", "dsnode", "invertin", "invertout", "uniqueid"},
        "manhole": {"rimelev", "invertelev", "invertin", "invertout", "newid", "wsaccid"},
        "pump_tank": {"tanksize", "tanktype", "horsepower", "tankmanufacturer"},
        "septic_tank": {"tanksize", "tanktype", "tankmanufacturer"},
        "private_well_point": {"welldepthfeet", "casingdepth", "groutdepth", "welldriller", "gpmflow"},
        "final_well_head": {"welldepthfeet", "casingdepth", "welldriller"},
        "storage_tank": {"capacity", "tanksize", "tanktype", "tankmanufacturer"},
        "distribution_box": {"boxtype", "distributionbox", "boxid"},
        "septic_drain_line": {"trenchwidth", "lineid", "drainfieldid"},
        "pretreatment_unit": {"unittype", "manufacturer", "capacity"},
    }
    expected = tokens.get(candidate.asset_subcategory, set()) | tokens.get(candidate.asset_category, set())
    return sorted(actual & expected)


def evaluate_coordinates(layer: SourceLayer) -> dict[str, Any]:
    status = {
        "name_and_metadata_conflict": "coordinate_name_conflict",
        "mixed_source_spatial_references": "mixed_spatial_reference",
    }.get(layer.coordinate_status, layer.coordinate_status)
    blocker = ""
    if status == "coordinate_name_conflict":
        blocker = f"Layer-name coordinate signal conflicts with {layer.spatial_reference_name} (WKID {layer.spatial_reference_wkid or 'unknown'})."
    elif status != "coordinate_ready":
        blocker = "Coordinate metadata requires human review; no projection or definition was applied."
    return {
        "status": status, "blocker": blocker,
        "evidence": [
            f"Actual spatial reference: {layer.spatial_reference_name}.",
            f"WKID: {layer.spatial_reference_wkid or 'unknown'}.",
            f"Linear unit: {layer.linear_unit or 'unknown'}.",
        ],
    }


def evaluate_duplicates(
    submission_id: str, layers: list[SourceLayer], names: dict[str, dict[str, object]],
    existing: dict[str, dict[str, Any]],
) -> tuple[list[Any], dict[str, dict[str, str]]]:
    copies = [clone_layer(layer) for layer in layers]
    for copy, layer in zip(copies, layers):
        copy.source_layer_name = str(names[layer.source_layer_name]["canonical_layer_name"])
    groups = normalization.detect_duplicate_groups(submission_id, copies)
    by_layer: dict[str, dict[str, str]] = {}
    for group in groups:
        group.comparison_type = "automated_normalized_name"
        previous = existing.get(group.duplicate_group_id)
        if previous and previous.get("status") not in {"", "potential_duplicate"}:
            group.status = str(previous["status"])
            group.authoritative_layer_id = str(previous.get("authoritative_layer_id", ""))
        for member in group.members:
            by_layer[str(member["layer_id"])] = {
                "status": "potential_duplicate", "group_id": group.duplicate_group_id,
                "recommendation": "likely_duplicate",
            }
    return groups, by_layer


def evaluate_ownership(
    layer: SourceLayer, candidate: ClassificationCandidate, manual: dict[str, Any] | None = None,
) -> dict[str, str]:
    owner = candidate.owner_or_jurisdiction or "unknown"
    normalized_owner = normalization.normalize_name(owner)
    source_text = normalization.normalize_name(f"{layer.source_layer_name} {layer.source_layer_alias} {layer.source_owner_prefix}")
    confidence = "high" if normalized_owner and normalized_owner != "unknown" and normalized_owner in source_text else "low"
    if manual and manual.get("owner_decision") == "acknowledge_provisional":
        return {
            "candidate": str(manual.get("approved_owner_or_jurisdiction") or owner),
            "confidence": "human_confirmed",
            "status": "confirmed",
            "blocker": "",
            "evidence": "Human reviewer acknowledged provisional ownership for staging review.",
        }
    return {
        "candidate": owner, "confidence": confidence,
        "status": "provisional" if confidence == "high" else "needs_owner_confirmation",
        "blocker": "Final staging reviewer must acknowledge provisional ownership." if confidence == "high" else "Owner or jurisdiction requires confirmation.",
        "evidence": "Owner inference remains provisional.",
    }


def calculate_staging_readiness(
    layers: list[SourceLayer], names: dict[str, dict[str, object]], taxonomy: dict[str, dict[str, Any]],
    coordinates: dict[str, dict[str, Any]], sensitivity: dict[str, dict[str, Any]],
    duplicates: dict[str, dict[str, str]], ownership: dict[str, dict[str, str]],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for layer in layers:
        tax, coord, sens, owner = taxonomy[layer.layer_id], coordinates[layer.layer_id], sensitivity[layer.layer_id], ownership[layer.layer_id]
        duplicate = duplicates.get(layer.layer_id, {"status": "no_duplicate_candidate", "group_id": "", "recommendation": "unrelated"})
        blockers = [*tax["blockers"]]
        blockers += [value for value in [coord["blocker"], sens["blocker"]] if value]
        if duplicate["status"] == "potential_duplicate":
            blockers.append("Potential duplicate relationship requires individual human review.")
        if tax["status"] == "approved" and owner["blocker"]:
            blockers.append(owner["blocker"])
        if tax["status"] == "excluded":
            readiness = "excluded"
        elif tax["status"] != "approved":
            readiness = "deferred"
        elif coord["blocker"] or sens["blocker"] or duplicate["status"] == "potential_duplicate":
            readiness = "staging_blocked"
        elif owner["status"] != "confirmed":
            readiness = "human_review_required"
        else:
            readiness = "fully_ready_for_staging_review"
        output[layer.layer_id] = {
            "canonical": names[layer.source_layer_name], "taxonomy": tax, "coordinate": coord,
            "sensitivity": sens, "duplicate": duplicate, "owner": owner,
            "readiness": readiness, "blockers": blockers,
        }
    return output


def generate_staging_preview(
    submission_id: str, layers: list[SourceLayer], states: dict[str, dict[str, Any]],
) -> list[StagingPlanItem]:
    used: set[str] = set()
    by_id = {layer.layer_id: layer for layer in layers}
    items: list[StagingPlanItem] = []
    eligible = sorted(
        (key for key, state in states.items() if state["taxonomy"]["status"] == "approved"),
        key=lambda key: by_id[key].source_layer_name.lower(),
    )
    for layer_id in eligible:
        layer, state = by_id[layer_id], states[layer_id]
        candidate: ClassificationCandidate = state["taxonomy"]["candidate"]
        blockers = "; ".join(state["blockers"])
        items.append(
            StagingPlanItem(
                staging_plan_item_id=f"stage-{normalization.stable_id(submission_id, layer_id)}",
                submission_id=submission_id, layer_id=layer_id,
                proposed_target_name=normalization.unique_target_name(candidate, used),
                target_utility_system=candidate.utility_system, target_network_group=candidate.network_group,
                target_asset_category=candidate.asset_category, target_asset_subcategory=candidate.asset_subcategory,
                target_owner_or_jurisdiction=candidate.owner_or_jurisdiction,
                source_spatial_reference=layer.spatial_reference_name,
                target_spatial_reference=layer.spatial_reference_name, projection_required=False,
                approved_for_staging=False, approval_status="blocked" if blockers else "awaiting_human_approval",
                blocker=blockers, reviewer="review_automation", reviewed_at=inspection_registry.utc_now(),
            )
        )
    return items


def persist_results(
    root: Path, run_id: str, submission_id: str, layers: list[SourceLayer],
    states: dict[str, dict[str, Any]], groups: list[Any], plan: list[StagingPlanItem],
) -> dict[str, int]:
    now = inspection_registry.utc_now()
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        connection.execute(
            "DELETE FROM duplicate_group_members WHERE duplicate_group_id IN (SELECT duplicate_group_id FROM duplicate_groups WHERE submission_id=? AND comparison_type='automated_normalized_name')",
            (submission_id,),
        )
        connection.execute("DELETE FROM duplicate_groups WHERE submission_id=? AND comparison_type='automated_normalized_name'", (submission_id,))
        for group in groups:
            inspection_registry.insert_duplicate_group(connection, group)
        eligible = {item.layer_id for item in plan}
        if eligible:
            placeholders = ",".join("?" for _ in eligible)
            connection.execute(
                f"DELETE FROM staging_plan_items WHERE submission_id=? AND approved_for_staging=0 AND layer_id NOT IN ({placeholders})",
                (submission_id, *eligible),
            )
        else:
            connection.execute("DELETE FROM staging_plan_items WHERE submission_id=? AND approved_for_staging=0", (submission_id,))

        for layer in layers:
            state = states[layer.layer_id]
            tax = state["taxonomy"]
            candidate: ClassificationCandidate = tax["candidate"]
            classification = "approved" if tax["status"] == "approved" else tax["status"]
            routing = "reference_approved" if tax["decision"] == "reference_approved" else "classification_approved" if tax["status"] == "approved" else tax["decision"]
            connection.execute(
                """
                UPDATE inspected_layers SET classification_status=?, routing_state=?, coordinate_status=?,
                    sensitivity_status=?, duplicate_status=?, staging_status='not_approved', updated_at=?
                WHERE layer_id=?
                """,
                (classification, routing, state["coordinate"]["status"], state["sensitivity"]["status"], state["duplicate"]["status"], now, layer.layer_id),
            )
            upsert_layer_state(connection, run_id, submission_id, layer, state, candidate, now)
            for row in decision_rows(layer, state):
                connection.execute(
                    """
                    INSERT INTO automated_layer_decisions (
                        decision_id, automation_run_id, submission_id, layer_id, decision_dimension, prior_value,
                        recommended_value, applied_value, decision_type, confidence, evidence_json, blocker_json,
                        rule_code, rule_version, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'automated_recommendation', ?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), run_id, submission_id, layer.layer_id, *row, RULE_VERSION, now),
                )
        for item in plan:
            existing = connection.execute("SELECT approved_for_staging FROM staging_plan_items WHERE staging_plan_item_id=?", (item.staging_plan_item_id,)).fetchone()
            if not existing or not existing["approved_for_staging"]:
                inspection_registry.insert_staging_item(connection, item)
        connection.commit()
    return count_states(states, groups)


def upsert_layer_state(
    connection: Any, run_id: str, submission_id: str, layer: SourceLayer,
    state: dict[str, Any], candidate: ClassificationCandidate, now: str,
) -> None:
    tax = state["taxonomy"]
    connection.execute(
        """
        INSERT INTO automated_layer_state (
            layer_id, submission_id, automation_run_id, canonical_layer_name, source_prefix_tokens_json,
            classification_tokens_json, taxonomy_status, taxonomy_decision, approved_utility_system,
            approved_network_group, approved_asset_category, approved_asset_subcategory,
            approved_operational_role, approved_lifecycle_representation, taxonomy_confidence,
            taxonomy_evidence_json, coordinate_status, coordinate_blocker, inherited_sensitivity,
            sensitivity_status, public_use_allowed, export_allowed, sensitivity_blocker, duplicate_status,
            duplicate_group_id, owner_candidate, owner_confidence, owner_status, owner_blocker,
            staging_readiness, staging_blockers_json, approved_for_staging, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        ON CONFLICT(layer_id) DO UPDATE SET
            automation_run_id=excluded.automation_run_id, canonical_layer_name=excluded.canonical_layer_name,
            source_prefix_tokens_json=excluded.source_prefix_tokens_json, classification_tokens_json=excluded.classification_tokens_json,
            taxonomy_status=excluded.taxonomy_status, taxonomy_decision=excluded.taxonomy_decision,
            approved_utility_system=excluded.approved_utility_system, approved_network_group=excluded.approved_network_group,
            approved_asset_category=excluded.approved_asset_category, approved_asset_subcategory=excluded.approved_asset_subcategory,
            approved_operational_role=excluded.approved_operational_role,
            approved_lifecycle_representation=excluded.approved_lifecycle_representation,
            taxonomy_confidence=excluded.taxonomy_confidence, taxonomy_evidence_json=excluded.taxonomy_evidence_json,
            coordinate_status=excluded.coordinate_status, coordinate_blocker=excluded.coordinate_blocker,
            inherited_sensitivity=excluded.inherited_sensitivity, sensitivity_status=excluded.sensitivity_status,
            public_use_allowed=excluded.public_use_allowed, export_allowed=excluded.export_allowed,
            sensitivity_blocker=excluded.sensitivity_blocker, duplicate_status=excluded.duplicate_status,
            duplicate_group_id=excluded.duplicate_group_id, owner_candidate=excluded.owner_candidate,
            owner_confidence=excluded.owner_confidence, owner_status=excluded.owner_status,
            owner_blocker=excluded.owner_blocker, staging_readiness=excluded.staging_readiness,
            staging_blockers_json=excluded.staging_blockers_json, approved_for_staging=0, updated_at=excluded.updated_at
        """,
        (
            layer.layer_id, submission_id, run_id, state["canonical"]["canonical_layer_name"],
            dumps(state["canonical"]["source_prefix_tokens"]), dumps(state["canonical"]["classification_tokens"]),
            tax["status"], tax["decision"], candidate.utility_system, candidate.network_group,
            candidate.asset_category, candidate.asset_subcategory, candidate.operational_role,
            candidate.lifecycle_representation, tax["confidence"], dumps(tax["evidence"]),
            state["coordinate"]["status"], state["coordinate"]["blocker"], state["sensitivity"]["inherited"],
            state["sensitivity"]["status"], int(state["sensitivity"]["public_use_allowed"]),
            int(state["sensitivity"]["export_allowed"]), state["sensitivity"]["blocker"],
            state["duplicate"]["status"], state["duplicate"]["group_id"], state["owner"]["candidate"],
            state["owner"]["confidence"], state["owner"]["status"], state["owner"]["blocker"],
            state["readiness"], dumps(state["blockers"]), now,
        ),
    )


def decision_rows(layer: SourceLayer, state: dict[str, Any]) -> list[tuple[Any, ...]]:
    tax, candidate = state["taxonomy"], state["taxonomy"]["candidate"]
    return [
        ("taxonomy", layer.classification_status, tax["decision"], tax["status"], tax["confidence"], dumps(tax["evidence"]), dumps(tax["blockers"]), "AUT_TAXONOMY_V1"),
        ("coordinates", layer.coordinate_status, state["coordinate"]["status"], state["coordinate"]["status"], "high", dumps(state["coordinate"]["evidence"]), dumps([state["coordinate"]["blocker"]] if state["coordinate"]["blocker"] else []), "AUT_COORDINATE_V1"),
        ("sensitivity", layer.sensitivity_status, state["sensitivity"]["status"], state["sensitivity"]["status"], "high", dumps(state["sensitivity"]["evidence"]), dumps([state["sensitivity"]["blocker"]] if state["sensitivity"]["blocker"] else []), "AUT_SENSITIVITY_V1"),
        ("duplicates", layer.duplicate_status, state["duplicate"]["recommendation"], state["duplicate"]["status"], "medium", dumps(["Safe metadata similarity only."]), dumps(["Authoritative source remains unresolved."] if state["duplicate"]["status"] == "potential_duplicate" else []), "AUT_DUPLICATE_V1"),
        ("ownership", layer.owner_or_jurisdiction, state["owner"]["candidate"], state["owner"]["status"], state["owner"]["confidence"], dumps([state["owner"]["evidence"]]), dumps([state["owner"]["blocker"]] if state["owner"]["blocker"] else []), "AUT_OWNER_V1"),
        ("staging", layer.staging_status, state["readiness"], "not_approved", "high", dumps([f"Target taxonomy: {candidate.utility_system}/{candidate.network_group}/{candidate.asset_subcategory}."]), dumps(state["blockers"]), "AUT_STAGING_V1"),
    ]


def count_states(states: dict[str, dict[str, Any]], groups: list[Any]) -> dict[str, int]:
    return {
        "layers_processed": len(states),
        "taxonomy_approved": sum(state["taxonomy"]["status"] == "approved" for state in states.values()),
        "taxonomy_deferred": sum(state["taxonomy"]["status"] == "deferred" for state in states.values()),
        "coordinate_blocked": sum(bool(state["coordinate"]["blocker"]) for state in states.values()),
        "duplicate_groups": len(groups),
        "sensitivity_inherited": sum(state["sensitivity"]["status"] == "inherited_from_package" for state in states.values()),
        "owner_confirmation_required": sum(state["owner"]["status"] != "confirmed" for state in states.values()),
        "staging_ready": sum(state["readiness"] == "fully_ready_for_staging_review" for state in states.values()),
        "staging_blocked": sum(state["readiness"] != "fully_ready_for_staging_review" for state in states.values()),
    }


def start_run(root: Path, run_id: str, snapshot: dict[str, Any], policy: str, fingerprint: str) -> None:
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        connection.execute(
            """
            INSERT INTO review_automation_runs (
                automation_run_id, submission_id, inspection_run_id, input_fingerprint,
                rule_version, policy_mode, status, started_at, warnings_json
            ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?, '[]')
            """,
            (run_id, snapshot["container"]["submission_id"], snapshot["container"]["inspection_run_id"], fingerprint, RULE_VERSION, policy, inspection_registry.utc_now()),
        )
        connection.commit()


def record_stage(root: Path, run_id: str, stage: StageResult) -> None:
    now = inspection_registry.utc_now()
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        connection.execute(
            """
            INSERT INTO review_automation_stage_runs (
                stage_run_id, automation_run_id, stage_name, status, started_at, completed_at,
                records_read, records_updated, warnings_json, safe_error_message
            ) VALUES (?, ?, ?, 'complete', ?, ?, ?, ?, ?, '')
            """,
            (str(uuid.uuid4()), run_id, stage.stage_name, now, now, stage.records_read, stage.records_updated, dumps(stage.warnings)),
        )
        connection.commit()


def complete_run(root: Path, run_id: str, counts: dict[str, int]) -> None:
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        assignments = ", ".join(f"{key}=?" for key in counts)
        connection.execute(
            f"UPDATE review_automation_runs SET status='complete', completed_at=?, {assignments} WHERE automation_run_id=?",
            (inspection_registry.utc_now(), *counts.values(), run_id),
        )
        connection.commit()


def fail_run(root: Path, run_id: str, exc: Exception) -> None:
    del exc
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        connection.execute(
            "UPDATE review_automation_runs SET status='failed', completed_at=?, safe_error_code='automation_failed', safe_error_message=? WHERE automation_run_id=?",
            (inspection_registry.utc_now(), "Automated review failed safely; inspection results remain intact.", run_id),
        )
        connection.commit()


def latest_matching_run(root: Path, submission_id: str, fingerprint: str) -> dict[str, Any] | None:
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        row = connection.execute(
            "SELECT * FROM review_automation_runs WHERE submission_id=? AND input_fingerprint=? AND status='complete' ORDER BY completed_at DESC LIMIT 1",
            (submission_id, fingerprint),
        ).fetchone()
    return dict(row) if row else None


def record_unchanged_run(
    root: Path, snapshot: dict[str, Any], previous: dict[str, Any], policy: str, fingerprint: str,
) -> dict[str, Any]:
    run_id, now = str(uuid.uuid4()), inspection_registry.utc_now()
    count_fields = [
        "layers_processed", "taxonomy_approved", "taxonomy_deferred", "coordinate_blocked",
        "duplicate_groups", "sensitivity_inherited", "owner_confirmation_required",
        "staging_ready", "staging_blocked",
    ]
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        connection.execute(
            f"""
            INSERT INTO review_automation_runs (
                automation_run_id, submission_id, inspection_run_id, input_fingerprint, reused_run_id,
                rule_version, policy_mode, status, started_at, completed_at, {", ".join(count_fields)}, warnings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'unchanged', ?, ?, {", ".join("?" for _ in count_fields)}, '[]')
            """,
            (
                run_id, snapshot["container"]["submission_id"], snapshot["container"]["inspection_run_id"],
                fingerprint, previous["automation_run_id"], RULE_VERSION, policy, now, now,
                *(previous[field] for field in count_fields),
            ),
        )
        connection.commit()
    return run_detail(str(snapshot["container"]["submission_id"]), run_id) or {}


def runs(submission_id: str) -> dict[str, object]:
    root = data_storage_service.get_storage_paths().root
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        rows = connection.execute(
            "SELECT * FROM review_automation_runs WHERE submission_id=? ORDER BY started_at DESC", (submission_id,),
        ).fetchall()
    return {"items": [safe_run(dict(row)) for row in rows], "message": "Automation run history loaded." if rows else "No automated review has run."}


def status(submission_id: str) -> dict[str, object]:
    history = runs(submission_id)["items"]
    return run_detail(submission_id, str(history[0]["automation_run_id"])) if history else {
        "submission_id": submission_id, "status": "not_started", "stages": [],
        "message": "Automated review has not run.",
    }


def run_detail(submission_id: str, automation_run_id: str) -> dict[str, object] | None:
    root = data_storage_service.get_storage_paths().root
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        run = connection.execute(
            "SELECT * FROM review_automation_runs WHERE submission_id=? AND automation_run_id=?",
            (submission_id, automation_run_id),
        ).fetchone()
        if not run:
            return None
        stages = connection.execute(
            "SELECT stage_name, status, started_at, completed_at, records_read, records_updated, warnings_json, safe_error_message FROM review_automation_stage_runs WHERE automation_run_id=? ORDER BY rowid",
            (automation_run_id,),
        ).fetchall()
        decisions = connection.execute(
            "SELECT decision_id, layer_id, decision_dimension, prior_value, recommended_value, applied_value, decision_type, confidence, evidence_json, blocker_json, rule_code, rule_version, created_at FROM automated_layer_decisions WHERE automation_run_id=? ORDER BY layer_id, decision_dimension",
            (automation_run_id,),
        ).fetchall()
    payload = safe_run(dict(run))
    payload["stages"] = [safe_stage(dict(row)) for row in stages]
    payload["decisions"] = [safe_decision(dict(row)) for row in decisions]
    return payload


def summary(submission_id: str) -> dict[str, object]:
    root = data_storage_service.get_storage_paths().root
    latest = status(submission_id)
    with inspection_registry.connect(root) as connection:
        initialize(connection)
        rows = connection.execute(
            """
            SELECT s.*, l.source_layer_name, l.geometry_type
            FROM automated_layer_state s JOIN inspected_layers l ON l.layer_id=s.layer_id
            WHERE s.submission_id=? ORDER BY l.source_layer_name
            """,
            (submission_id,),
        ).fetchall()
    states = [safe_state(dict(row)) for row in rows]
    grouped: dict[str, list[dict[str, Any]]] = {
        "taxonomy_ambiguity": [], "coordinate_conflict": [], "duplicate_candidate": [],
        "owner_uncertainty": [], "sensitivity_escalation": [], "unsupported_source": [],
        "out_of_scope_recommendation": [],
    }
    for row in states:
        if row["taxonomy_status"] == "deferred":
            grouped["taxonomy_ambiguity"].append(row)
        if row["coordinate_blocker"]:
            grouped["coordinate_conflict"].append(row)
        if row["duplicate_status"] == "potential_duplicate":
            grouped["duplicate_candidate"].append(row)
        if row["owner_status"] != "confirmed":
            grouped["owner_uncertainty"].append(row)
        if row["sensitivity_blocker"]:
            grouped["sensitivity_escalation"].append(row)
        if row["taxonomy_decision"] == "excluded":
            grouped["out_of_scope_recommendation"].append(row)
    return {
        "latest_run": latest, "rule_version": RULE_VERSION,
        "policy_mode": latest.get("policy_mode", "conservative"), "layers": states,
        "exceptions": grouped,
        "exception_count": len({row["layer_id"] for items in grouped.values() for row in items}),
        "taxonomy_approved_operational": [
            row["source_layer_name"] for row in states
            if row["taxonomy_status"] == "approved" and row["approved_utility_system"] not in REFERENCE_SYSTEMS
        ],
        "taxonomy_approved_reference": [
            row["source_layer_name"] for row in states
            if row["taxonomy_status"] == "approved" and row["approved_utility_system"] in REFERENCE_SYSTEMS
        ],
        "staging_ready_layers": [
            row["source_layer_name"] for row in states if row["staging_readiness"] == "fully_ready_for_staging_review"
        ],
        "message": "Automation summary loaded." if states else "No automated review results are available.",
    }

def clone_layer(layer: SourceLayer) -> SourceLayer:
    return SourceLayer(**{field.name: getattr(layer, field.name) for field in fields(SourceLayer)})


def source_layer(row: dict[str, Any]) -> SourceLayer:
    values = dict(row)
    for target, (source, default) in JSON_FIELDS.items():
        values[target] = loads(values.get(source), default)
    return SourceLayer(**{field.name: values.get(field.name) for field in fields(SourceLayer)})


def safe_run(row: dict[str, Any]) -> dict[str, Any]:
    row["warnings"] = loads(row.pop("warnings_json", ""), [])
    row.pop("input_fingerprint", None)
    return row


def safe_stage(row: dict[str, Any]) -> dict[str, Any]:
    row["warnings"] = loads(row.pop("warnings_json", ""), [])
    return row


def safe_decision(row: dict[str, Any]) -> dict[str, Any]:
    row["evidence"] = loads(row.pop("evidence_json", ""), [])
    row["blockers"] = loads(row.pop("blocker_json", ""), [])
    return row


def safe_state(row: dict[str, Any]) -> dict[str, Any]:
    for key in ["source_prefix_tokens_json", "classification_tokens_json", "taxonomy_evidence_json", "staging_blockers_json"]:
        row[key.removesuffix("_json")] = loads(row.pop(key, ""), [])
    for key in ["public_use_allowed", "export_allowed", "approved_for_staging"]:
        row[key] = bool(row.get(key))
    return row


def dumps(value: Any) -> str:
    return json.dumps(value if value is not None else "", separators=(",", ":"), sort_keys=True)


def loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default
