from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from .domain import stable_id

SYNTHETIC_NOTICE = "Synthetic training asset; no customer, subscriber, address, or production data."


def synthetic_assets() -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    electric_counts = {
        "substation": 1, "feeder": 2, "feeder_breaker": 2, "switch": 3, "fuse": 2,
        "recloser": 1, "transformer": 8, "pole": 20, "overhead_conductor": 8,
        "underground_conductor": 3, "secondary_conductor": 4, "conduit": 2, "service_point": 8, "junction": 2,
        "attachment": 2, "electric_structure": 2, "reference_boundary": 1,
    }
    telecom_counts = {
        "network_hub": 1, "fiber_cabinet": 2, "fiber_route": 3, "fiber_cable": 4,
        "pole": 8, "conduit": 3, "handhole": 4, "manhole": 1, "splice_closure": 3,
        "splitter": 3, "terminal": 6, "proposed_construction_segment": 1,
        "service_area": 1, "telecom_structure": 2, "reference_boundary": 1,
    }
    for vertical, counts in (("electric_distribution", electric_counts), ("telecom_fiber", telecom_counts)):
        for asset_class, count in counts.items():
            for index in range(1, count + 1):
                assets.append(_asset(vertical, asset_class, index))
    return assets


def _asset(vertical: str, asset_class: str, index: int) -> dict[str, Any]:
    prefix = "ELEC" if vertical == "electric_distribution" else "FIBER"
    source_id = f"{prefix}-{asset_class.upper().replace('_', '-')}-{index:03d}"
    asset_id = stable_id("asset", vertical, "synthetic-v1", source_id)
    lifecycle = "active"
    operational = "energized" if vertical == "electric_distribution" else "active"
    qa_status = "passed"
    review_status = "approved"
    attributes: dict[str, Any] = {}
    evidence: dict[str, Any] = {"value_provenance": "synthetic", "rule_version": "synthetic-assets-v1"}
    if vertical == "electric_distribution":
        feeder_id = "" if asset_class == "transformer" and index == 8 else f"FEEDER-{1 + index % 2}"
        attributes = {
            "feeder_id": feeder_id, "circuit_id": f"CIR-{1 + index % 2}", "phase": "AX" if asset_class == "transformer" and index == 7 else ("ABC" if index % 3 == 0 else "A"),
            "nominal_voltage": 12.47, "operating_voltage": 12.47, "normally_open": asset_class == "switch" and index == 3,
            "device_state": "open" if asset_class == "switch" and index == 3 else "closed",
            "placement_type": "underground" if asset_class in {"underground_conductor", "conduit"} else "overhead",
            "conduit_id": "" if asset_class == "underground_conductor" and index == 3 else ("CONDUIT-1" if asset_class == "underground_conductor" else ""),
            "energized_status": "energized", "customer_count_safe_aggregate": index * 4 if asset_class == "transformer" else None,
        }
        if asset_class == "switch" and index == 3:
            operational = "normally_open"
        if (asset_class == "overhead_conductor" and index == 8) or (asset_class == "transformer" and index in {7, 8}) or (asset_class == "underground_conductor" and index == 3):
            qa_status, review_status = "warning", "needs_review"
        if asset_class == "attachment" and index == 2:
            lifecycle, qa_status = "retired", "warning"
    else:
        attributes = {
            "route_id": f"ROUTE-{1 + index % 3}", "cable_id": source_id if asset_class == "fiber_cable" else "",
            "cable_type": "single_mode", "fiber_count": 144 if index % 2 else 288,
            "strand_start": 1, "strand_end": 144 if index % 2 else 288, "placement_type": "underground",
            "from_structure_id": f"STRUCT-{index:02d}",
            "to_structure_id": "" if (asset_class == "fiber_cable" and index == 4) or asset_class == "proposed_construction_segment" else f"STRUCT-{index + 1:02d}",
            "total_capacity": 32, "used_capacity": 24, "reserved_capacity": 4,
            "available_capacity": 9 if asset_class == "terminal" and index == 6 else 4,
            "construction_status": "proposed" if asset_class == "proposed_construction_segment" else "installed",
            "network_tier": "distribution", "hub_id": "HUB-001",
        }
        if asset_class == "proposed_construction_segment":
            lifecycle, operational, qa_status, review_status = "proposed", "proposed", "warning", "needs_review"
        if (asset_class == "fiber_cable" and index in {3, 4}) or (asset_class == "terminal" and index == 6):
            qa_status, review_status = "warning", "needs_review"
        if asset_class == "fiber_cable" and index == 3:
            lifecycle, operational = "retired", "retired"
    geometry_type = "polyline" if asset_class in {"feeder", "overhead_conductor", "underground_conductor", "secondary_conductor", "conduit", "fiber_route", "fiber_cable", "proposed_construction_segment"} else "polygon" if asset_class in {"reference_boundary", "service_area"} else "point"
    now = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc).isoformat()
    return {
        "asset_id": asset_id, "utility_vertical": vertical, "asset_class": asset_class,
        "asset_subtype": "synthetic_v1", "canonical_name": source_id, "display_name": source_id,
        "geometry_type": geometry_type, "lifecycle_status": lifecycle, "operational_status": operational,
        "owner_candidate": "Synthetic Utility", "owner_status": "confirmed", "jurisdiction": "Synthetic Service Area",
        "source_system": "synthetic_generator", "source_submission_id": f"DEMO-{prefix}-001",
        "source_layer_id": f"demo-{vertical}-{asset_class}", "source_record_id": str(index),
        "source_asset_identifier": source_id, "parent_asset_id": "", "container_asset_id": "",
        "connected_from_asset_id": "", "connected_to_asset_id": "", "network_level": "distribution",
        "work_order_id": "", "qa_status": qa_status, "review_status": review_status,
        "sensitivity": "public_demo", "confidence": "high", "installation_date": "",
        "retirement_date": "", "last_inspected_at": "", "last_reviewed_at": "",
        "created_at": now, "updated_at": now, "notes": SYNTHETIC_NOTICE,
        "source_attributes_json": {"synthetic_source_id": source_id},
        "canonical_attributes_json": attributes,
        "geometry_summary_json": {"geometry_type": geometry_type, "safe_extent": [index, index, index + 1, index + 1]},
        "evidence_json": evidence, "is_synthetic": True,
    }


def synthetic_relationships(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(assets)
    relationships: list[dict[str, Any]] = []
    by_vertical = {
        vertical: [row for row in rows if row["utility_vertical"] == vertical]
        for vertical in ("electric_distribution", "telecom_fiber")
    }
    for vertical, items in by_vertical.items():
        relationship_type = "feeds" if vertical == "electric_distribution" else "connects_to"
        for index, (left, right) in enumerate(zip(items, items[1:]), 1):
            if "ELEC-OVERHEAD-CONDUCTOR-008" in {left["canonical_name"], right["canonical_name"]}:
                continue
            provisional = (
                vertical == "electric_distribution" and index == 11
            ) or (
                vertical == "telecom_fiber"
                and left["asset_class"] == "splice_closure"
                and left["source_record_id"] == "1"
            )
            source = "rule_inferred" if provisional else "source"
            relationships.append({
                "relationship_id": stable_id("rel", left["asset_id"], right["asset_id"], relationship_type),
                "from_asset_id": left["asset_id"], "to_asset_id": right["asset_id"],
                "relationship_type": relationship_type, "direction": "forward",
                "confidence": "medium" if provisional else "high", "source": source,
                "provisional": provisional, "confirmed_by": "", "confirmed_at": "",
                "evidence_json": {"value_provenance": source, "synthetic": True},
                "created_at": left["created_at"],
            })
    electric_retired = next(row for row in rows if row["canonical_name"] == "ELEC-ATTACHMENT-002")
    electric_segment = next(row for row in rows if row["canonical_name"] == "ELEC-OVERHEAD-CONDUCTOR-001")
    telecom_retired = next(row for row in rows if row["canonical_name"] == "FIBER-FIBER-CABLE-003")
    telecom_terminal = next(row for row in rows if row["canonical_name"] == "FIBER-TERMINAL-001")
    for left, right, relationship_type in (
        (electric_retired, electric_segment, "reference_for"),
        (telecom_retired, telecom_terminal, "terminates_at"),
    ):
        relationships.append({
            "relationship_id": stable_id("rel", left["asset_id"], right["asset_id"], relationship_type),
            "from_asset_id": left["asset_id"], "to_asset_id": right["asset_id"],
            "relationship_type": relationship_type, "direction": "forward", "confidence": "high",
            "source": "source", "provisional": False, "confirmed_by": "", "confirmed_at": "",
            "evidence_json": {"value_provenance": "synthetic", "intentional_review_candidate": "retired_to_active"},
            "created_at": left["created_at"],
        })
    by_name = {row["canonical_name"]: row for row in rows}
    for left_name, right_name in (
        ("ELEC-SWITCH-002", "ELEC-OVERHEAD-CONDUCTOR-002"),
        ("ELEC-OVERHEAD-CONDUCTOR-004", "ELEC-UNDERGROUND-CONDUCTOR-002"),
        ("ELEC-SWITCH-002", "ELEC-FUSE-002"),
        ("ELEC-TRANSFORMER-008", "ELEC-JUNCTION-002"),
        ("ELEC-JUNCTION-002", "ELEC-SECONDARY-CONDUCTOR-002"),
        ("ELEC-SECONDARY-CONDUCTOR-004", "ELEC-SERVICE-POINT-002"),
        ("FIBER-FIBER-CABLE-002", "FIBER-SPLICE-CLOSURE-001"),
        ("FIBER-FIBER-CABLE-002", "FIBER-SPLICE-CLOSURE-002"),
    ):
        left, right = by_name[left_name], by_name[right_name]
        relationship_type = "feeds" if left["utility_vertical"] == "electric_distribution" else "connects_to"
        relationships.append({
            "relationship_id": stable_id("rel", left["asset_id"], right["asset_id"], relationship_type),
            "from_asset_id": left["asset_id"], "to_asset_id": right["asset_id"],
            "relationship_type": relationship_type, "direction": "forward", "confidence": "high",
            "source": "synthetic_trace_fixture", "provisional": False, "confirmed_by": "",
            "confirmed_at": "", "evidence_json": {
                "value_provenance": "synthetic",
                "purpose": "deterministic_network_trace_scenario",
            },
            "created_at": left["created_at"],
        })
    return relationships
