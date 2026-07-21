from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.source_inspection.models import ClassificationCandidate, DuplicateGroup, SourceLayer, StagingPlanItem

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RULES_PATH = REPO_ROOT / "config" / "taxonomy" / "utility_layer_rules_v1.json"
UTILITY_ABBREVIATIONS = {
    "wastewater": "ww",
    "water": "water",
    "stormwater": "sw",
    "telecom": "tel",
    "electric": "elec",
    "gas": "gas",
    "shared_reference": "ref",
    "environmental_regulatory": "env",
    "planning_reference": "plan",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_id(*parts: object, prefix: str = "") -> str:
    digest = hashlib.sha1("|".join(str(part).strip().lower() for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}" if prefix else digest


def load_rules(path: Path = DEFAULT_RULES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_layers(layers: list[SourceLayer], submission: dict[str, object], *, rules: dict[str, Any] | None = None) -> dict[str, list[ClassificationCandidate]]:
    rules = rules or load_rules()
    output: dict[str, list[ClassificationCandidate]] = {}
    for layer in layers:
        candidates = classify_layer(layer, submission, rules=rules)
        top = candidates[0]
        layer.operational_role = top.operational_role
        layer.lifecycle_representation = top.lifecycle_representation
        layer.owner_or_jurisdiction = top.owner_or_jurisdiction
        layer.classification_status = top.confidence
        layer.routing_state = routing_state(top, candidates)
        output[layer.layer_id] = candidates
    return output


def classify_layer(layer: SourceLayer, submission: dict[str, object], *, rules: dict[str, Any] | None = None) -> list[ClassificationCandidate]:
    rules = rules or load_rules()
    now = utc_now()
    text = classification_text(layer)
    lifecycle = lifecycle_signal(layer.source_layer_name)
    owner = owner_candidate(text, rules) or safe_unknown(str(submission.get("source_owner", "")))
    candidates: list[ClassificationCandidate] = []
    for rule in rules.get("classification_rules", []):
        if not any(re.search(pattern, text, re.IGNORECASE) for pattern in rule.get("name_patterns", [])):
            continue
        for rank_offset, target in enumerate(rule.get("candidates") or [rule.get("candidate", {})]):
            role = lifecycle_role(target.get("operational_role", "unknown"), lifecycle)
            confidence = adjusted_confidence(str(rule.get("confidence", "low")), layer, target)
            evidence = [str(rule.get("evidence", "Rule matched source metadata."))]
            warnings = []
            if str(rule.get("rule_code", "")).endswith("WATERLINE_AMBIGUOUS"):
                warnings.append("Ambiguous WaterLine naming requires data-owner or field confirmation.")
            if layer.spatial_reference_name == "unknown":
                warnings.append("Spatial reference unavailable; coordinate review may be required.")
            candidates.append(
                ClassificationCandidate(
                    candidate_id=f"{layer.layer_id}:cand:{len(candidates) + 1}",
                    layer_id=layer.layer_id,
                    rank=0,
                    utility_system=str(target.get("utility_system", "review_required")),
                    network_group=str(target.get("network_group", "unknown")),
                    asset_category=str(target.get("asset_category", "unknown")),
                    asset_subcategory=str(target.get("asset_subcategory", "unknown")),
                    operational_role=role,
                    lifecycle_representation=lifecycle,
                    owner_or_jurisdiction=owner,
                    confidence=confidence,
                    score=float(rule.get("score", 0.5)) - (rank_offset * 0.03),
                    evidence=evidence + source_evidence(layer, owner),
                    warnings=warnings,
                    rule_version=str(rules.get("rule_version", "")),
                    rule_code=str(rule.get("rule_code", "")),
                    created_at=now,
                )
            )
    if not candidates:
        candidates.append(
            ClassificationCandidate(
                candidate_id=f"{layer.layer_id}:cand:1",
                layer_id=layer.layer_id,
                rank=1,
                utility_system="review_required",
                network_group="unknown",
                asset_category="unknown",
                asset_subcategory="unknown",
                operational_role="unknown",
                lifecycle_representation=lifecycle,
                owner_or_jurisdiction=owner,
                confidence="unavailable",
                score=0.0,
                evidence=["No configured classification rule matched safe layer metadata."],
                warnings=["Data-owner confirmation is required before staging."],
                rule_version=str(rules.get("rule_version", "")),
                rule_code="ULR_UNAVAILABLE",
                created_at=now,
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    for index, candidate in enumerate(candidates, start=1):
        candidate.rank = index
        candidate.candidate_id = f"{layer.layer_id}:cand:{index}"
    return candidates


def classification_text(layer: SourceLayer) -> str:
    field_names = " ".join(str(field.get("name", "")) for field in layer.field_profile)
    field_aliases = " ".join(str(field.get("alias", "")) for field in layer.field_profile)
    return " ".join([layer.source_layer_name, layer.source_layer_alias, layer.feature_dataset, field_names, field_aliases]).lower()


def owner_candidate(text: str, rules: dict[str, Any]) -> str:
    for item in rules.get("owner_or_jurisdiction_patterns", []):
        if re.search(str(item.get("pattern", "")), text, re.IGNORECASE):
            return str(item.get("value", "unknown"))
    return ""


def safe_unknown(value: str) -> str:
    value = value.strip()
    return value if value and value.lower() not in {"unknown", "mixed"} else "unknown"


def lifecycle_signal(name: str) -> str:
    lowered = name.lower()
    if lowered.startswith("proposed_") or lowered.startswith("proposed-") or "proposed" in lowered:
        return "proposed"
    if lowered.endswith("_final") or lowered.endswith("-final") or "final" in lowered:
        return "final_as_built"
    return "existing"


def lifecycle_role(role: str, lifecycle: str) -> str:
    return "proposed_design" if lifecycle == "proposed" and role == "network_asset" else role


def adjusted_confidence(confidence: str, layer: SourceLayer, target: dict[str, Any]) -> str:
    name = normalize_name(layer.source_layer_name)
    if name in {"waterline", "waterlines"} and target.get("utility_system") == "water":
        fields = {str(field.get("name", "")).lower() for field in layer.field_profile}
        if fields & {"diameter", "diam", "size", "sz", "material", "ma", "status"}:
            return "medium"
        return "low"
    return confidence


def source_evidence(layer: SourceLayer, owner: str) -> list[str]:
    evidence = [f"Source layer name: {layer.source_layer_name}"]
    if layer.source_layer_alias:
        evidence.append(f"Alias: {layer.source_layer_alias}")
    if owner != "unknown":
        evidence.append(f"Owner or jurisdiction signal: {owner}")
    if layer.geometry_type and layer.geometry_type != "unknown":
        evidence.append(f"Geometry type: {layer.geometry_type}")
    return evidence


def routing_state(candidate: ClassificationCandidate, candidates: list[ClassificationCandidate]) -> str:
    if candidate.utility_system == "out_of_scope":
        return "out_of_scope_candidate"
    if candidate.utility_system == "shared_reference":
        return "shared_reference_candidate"
    if candidate.utility_system == "environmental_regulatory":
        return "environmental_reference_candidate"
    if candidate.utility_system == "planning_reference":
        return "planning_reference_candidate"
    if len(candidates) > 1 and candidate.confidence in {"low", "medium"}:
        return "needs_taxonomy_review"
    if candidate.confidence == "high":
        return "ready_for_classification_review"
    if candidate.confidence == "medium":
        return "needs_taxonomy_review"
    if candidate.confidence == "low":
        return "needs_source_owner_confirmation"
    return "needs_data_owner_confirmation"


def coordinate_status(layer: SourceLayer, spatial_reference_names: set[str]) -> str:
    name = (layer.spatial_reference_name or "").lower()
    if not name or name == "unknown":
        return "unknown_spatial_reference"
    if "wgs" in layer.source_layer_name.lower() and "wgs" not in name and "4326" not in str(layer.spatial_reference_wkid or ""):
        return "name_and_metadata_conflict"
    if len(spatial_reference_names) > 1:
        return "mixed_source_spatial_references"
    return "coordinate_ready"


def apply_coordinate_status(layers: list[SourceLayer]) -> None:
    spatial_refs = {layer.spatial_reference_name for layer in layers if layer.spatial_reference_name and layer.spatial_reference_name != "unknown"}
    for layer in layers:
        layer.coordinate_status = coordinate_status(layer, spatial_refs)
        if layer.coordinate_status not in {"coordinate_ready", "mixed_source_spatial_references"} and layer.routing_state == "ready_for_classification_review":
            layer.routing_state = "needs_coordinate_review"


def detect_duplicate_groups(submission_id: str, layers: list[SourceLayer]) -> list[DuplicateGroup]:
    groups: list[DuplicateGroup] = []
    by_signature: dict[str, list[SourceLayer]] = defaultdict(list)
    for layer in layers:
        by_signature[duplicate_signature(layer.source_layer_name)].append(layer)
    for signature, members in by_signature.items():
        if len(members) < 2:
            continue
        group_id = f"dup-{stable_id(submission_id, signature)}"
        groups.append(
            DuplicateGroup(
                duplicate_group_id=group_id,
                submission_id=submission_id,
                comparison_type="normalized_name",
                confidence="medium",
                status="potential_duplicate",
                recommended_action="Human review should decide whether one layer is authoritative, legacy, a view, or a separate representation.",
                members=[
                    {
                        "duplicate_group_id": group_id,
                        "layer_id": layer.layer_id,
                        "member_role": "candidate",
                        "similarity_score": 0.86,
                        "notes": "Normalized layer names are highly similar; no authoritative source was selected.",
                    }
                    for layer in members
                ],
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        for layer in members:
            layer.duplicate_status = "potential_duplicate"
            layer.routing_state = "potential_duplicate"
    return groups


def duplicate_signature(name: str) -> str:
    normalized = normalize_name(name)
    replacements = {
        "sewer": "wwpipe",
        "pipes": "wwpipe",
        "pipe": "wwpipe",
        "line": "wwpipe",
        "lines": "wwpipe",
        "water": "waterpipe",
        "mh": "manhole",
        "manholes": "manhole",
        "mains": "main",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


def normalize_name(value: str) -> str:
    value = re.sub(r"(_|-)?wgs84$", "", value.strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def create_plan_items(submission_id: str, layers: list[SourceLayer], candidates_by_layer: dict[str, list[ClassificationCandidate]]) -> list[StagingPlanItem]:
    used: set[str] = set()
    items: list[StagingPlanItem] = []
    for layer in layers:
        top = candidates_by_layer[layer.layer_id][0]
        target_name = unique_target_name(top, used)
        blocker = staging_blocker(layer, top)
        items.append(
            StagingPlanItem(
                staging_plan_item_id=f"stage-{stable_id(submission_id, layer.layer_id)}",
                submission_id=submission_id,
                layer_id=layer.layer_id,
                proposed_target_name=target_name,
                target_utility_system=top.utility_system,
                target_network_group=top.network_group,
                target_asset_category=top.asset_category,
                target_asset_subcategory=top.asset_subcategory,
                target_owner_or_jurisdiction=top.owner_or_jurisdiction,
                source_spatial_reference=layer.spatial_reference_name,
                target_spatial_reference=layer.spatial_reference_name,
                projection_required=False,
                approved_for_staging=False,
                approval_status="blocked" if blocker else "awaiting_review",
                blocker=blocker,
            )
        )
    return items


def unique_target_name(candidate: ClassificationCandidate, used: set[str]) -> str:
    prefix = UTILITY_ABBREVIATIONS.get(candidate.utility_system, "review")
    owner = "" if candidate.owner_or_jurisdiction == "unknown" else f"_{candidate.owner_or_jurisdiction}"
    base = clean_gdb_name(f"{prefix}_{candidate.asset_subcategory}{owner}")
    name = base[:60]
    index = 2
    while name in used:
        suffix = f"_{index}"
        name = f"{base[:60 - len(suffix)]}{suffix}"
        index += 1
    used.add(name)
    return name


def clean_gdb_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value.lower()).strip("_")
    value = re.sub(r"_+", "_", value)
    if not value or not re.match(r"^[A-Za-z]", value):
        value = f"layer_{value}"
    if value.lower() in {"table", "select", "from", "where"}:
        value = f"up_{value}"
    return value


def staging_blocker(layer: SourceLayer, candidate: ClassificationCandidate) -> str:
    blockers: list[str] = []
    if candidate.confidence in {"low", "unavailable"}:
        blockers.append("classification requires data-owner confirmation")
    if layer.duplicate_status == "potential_duplicate":
        blockers.append("duplicate review unresolved")
    if layer.coordinate_status in {"unknown_spatial_reference", "suspicious_extent", "name_and_metadata_conflict"}:
        blockers.append("coordinate review required")
    if layer.sensitivity_status != "sensitivity_review_complete":
        blockers.append("sensitivity review required")
    return "; ".join(blockers)
