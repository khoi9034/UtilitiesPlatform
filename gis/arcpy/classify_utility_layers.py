from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

SYSTEM_KEYWORDS = {
    "water": ["water", "wtr", "hydrant", "valve", "meter", "tank", "pressure"],
    "wastewater": ["sewer", "sanitary", "ss_", "ww", "wastewater", "manhole", "gravity", "force_main", "lift", "invert", "u_s_node", "d_s_node"],
    "stormwater": ["storm", "drain", "culvert", "inlet", "outfall", "ditch", "pond"],
    "telecom": ["fiber", "telecom", "conduit", "handhole", "pedestal", "splice"],
    "electric": ["electric", "power", "transformer", "pole", "switchgear"],
    "gas": ["gas", "valve", "regulator"],
    "reference": ["parcel", "address", "road", "building", "boundary", "easement", "right_of_way"],
}

SUBBASIN_CANDIDATES = [
    "wastewater / operational_areas / sewer_basin / subbasin",
    "stormwater / drainage_areas / drainage_basin / subbasin",
]

ASSET_HIERARCHY = {
    "water_main": ("distribution_network", "pipe", "water_main"),
    "transmission_main": ("transmission_network", "pipe", "transmission_main"),
    "distribution_main": ("distribution_network", "pipe", "distribution_main"),
    "valve": ("appurtenances", "control", "valve"),
    "hydrant": ("appurtenances", "fire_protection", "hydrant"),
    "meter": ("services", "meter", "meter"),
    "service_line": ("services", "pipe", "service_line"),
    "tank": ("storage", "storage_structure", "tank"),
    "pump_station": ("facilities", "pump_station", "pump_station"),
    "pressure_zone": ("operational_areas", "pressure_zone", "pressure_zone"),
    "gravity_main": ("gravity_network", "pipe", "gravity_main"),
    "force_main": ("force_network", "pipe", "force_main"),
    "manhole": ("structures", "access_structure", "manhole"),
    "cleanout": ("structures", "access_structure", "cleanout"),
    "lift_station": ("facilities", "lift_station", "lift_station"),
    "storm_pipe": ("drainage_network", "pipe", "storm_pipe"),
    "inlet": ("structures", "inlet", "inlet"),
    "catch_basin": ("structures", "inlet", "catch_basin"),
    "storm_manhole": ("structures", "access_structure", "storm_manhole"),
    "culvert": ("drainage_network", "crossing", "culvert"),
    "headwall": ("structures", "outlet_structure", "headwall"),
    "outfall": ("structures", "outlet_structure", "outfall"),
    "ditch": ("drainage_network", "open_channel", "ditch"),
    "channel": ("drainage_network", "open_channel", "channel"),
    "pond": ("storage", "storage_area", "pond"),
    "fiber_cable": ("fiber_network", "cable", "fiber_cable"),
    "conduit": ("civil_network", "conduit", "conduit"),
    "handhole": ("structures", "access_structure", "handhole"),
    "pedestal": ("structures", "cabinet", "pedestal"),
    "cabinet": ("structures", "cabinet", "cabinet"),
    "splice": ("fiber_network", "splice", "splice"),
    "node": ("network_nodes", "node", "node"),
    "service_location": ("services", "service_location", "service_location"),
    "parcels": ("shared_reference", "parcel", "parcel"),
    "addresses": ("shared_reference", "address", "address"),
    "road_centerlines": ("shared_reference", "transportation", "road_centerline"),
    "buildings": ("shared_reference", "structure", "building"),
    "municipal_boundaries": ("shared_reference", "boundary", "municipal_boundary"),
    "easements": ("shared_reference", "property_interest", "easement"),
    "right_of_way": ("shared_reference", "property_interest", "right_of_way"),
}

ASSET_KEYWORDS = {
    "water_main": ["water_main", "wtr_main"],
    "transmission_main": ["transmission"],
    "distribution_main": ["distribution"],
    "valve": ["valve"],
    "hydrant": ["hydrant"],
    "meter": ["meter"],
    "service_line": ["service", "lateral"],
    "tank": ["tank"],
    "pump_station": ["pump_station", "pump station"],
    "pressure_zone": ["pressure_zone", "pressure zone"],
    "gravity_main": ["gravity", "sewer_main", "ss_main", "pipes", "pipe"],
    "force_main": ["force"],
    "manhole": ["manhole", "mh"],
    "cleanout": ["cleanout"],
    "lift_station": ["lift"],
    "storm_pipe": ["storm_pipe", "sd_pipe"],
    "inlet": ["inlet"],
    "catch_basin": ["catch_basin", "catch basin"],
    "storm_manhole": ["storm_manhole", "storm manhole"],
    "culvert": ["culvert"],
    "headwall": ["headwall"],
    "outfall": ["outfall"],
    "ditch": ["ditch"],
    "channel": ["channel"],
    "pond": ["pond"],
    "fiber_cable": ["fiber"],
    "conduit": ["conduit"],
    "handhole": ["handhole"],
    "pedestal": ["pedestal"],
    "cabinet": ["cabinet"],
    "splice": ["splice"],
    "node": ["node"],
    "service_location": ["service_location", "service location"],
    "parcels": ["parcel"],
    "addresses": ["address"],
    "road_centerlines": ["road", "centerline"],
    "buildings": ["building"],
    "municipal_boundaries": ["boundary"],
    "easements": ["easement"],
    "right_of_way": ["right_of_way", "row"],
    "subbasin": ["subbasin"],
}


def taxonomy_row(
    utility_system: str,
    network_group: str,
    asset_category: str,
    asset_subcategory: str,
    confidence: str,
    likely_classifications: str = "",
    recommended_classification: str = "",
    classification_notes: str = "",
) -> dict[str, str]:
    return {
        "utility_system": utility_system,
        "network_group": network_group,
        "asset_category": asset_category,
        "asset_subcategory": asset_subcategory,
        "classification_confidence": confidence,
        "likely_classifications": likely_classifications,
        "recommended_classification": recommended_classification,
        "classification_notes": classification_notes,
    }


def classify_layer(
    layer_name: str,
    field_names: list[str] | None = None,
    geometry_type: str = "",
    source_context: str = "",
) -> dict[str, str]:
    name_text = " ".join([source_context, layer_name]).lower()
    text = " ".join([source_context, layer_name, geometry_type, *(field_names or [])]).lower()
    if "subbasin" in name_text or ("basin" in name_text and "polygon" in geometry_type.lower()):
        return taxonomy_row(
            "review_required",
            "review_required",
            "review_required",
            "subbasin",
            "review_required",
            likely_classifications="; ".join(SUBBASIN_CANDIDATES),
            classification_notes="Subbasin layers can describe wastewater sewer basins or stormwater drainage basins; review required.",
        )

    system_scores = {
        system: sum(1 for keyword in keywords if keyword in text)
        for system, keywords in SYSTEM_KEYWORDS.items()
    }
    system = max(system_scores, key=system_scores.get)
    score = system_scores[system]
    if score == 0:
        return taxonomy_row("unknown", "unknown", "unknown", "unknown", "unknown")

    asset_subcategory = "unknown"
    for category, keywords in ASSET_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            asset_subcategory = category
            break

    confidence = "high" if score >= 2 and asset_subcategory != "unknown" else "medium"
    if system in {"gas", "water"} and text.count("valve") == 1 and score == 1:
        confidence = "low"
    network_group, asset_category, asset_subcategory = ASSET_HIERARCHY.get(
        asset_subcategory, ("general", "unknown", asset_subcategory)
    )
    if network_group == "shared_reference":
        system = "shared_reference"
    return taxonomy_row(system, network_group, asset_category, asset_subcategory, confidence)


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify inventoried utility layers from a JSON inventory file.")
    parser.add_argument("--input", required=True, help="Inventory JSON path.")
    parser.add_argument("--output", required=True, help="Classified JSON output path.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    for layer in data.get("layers", []):
        layer.update(classify_layer(layer.get("layer_name", ""), layer.get("field_names", []), layer.get("geometry_type", "")))
    Path(args.output).write_text(json.dumps(data, indent=2), encoding="utf-8")
    logging.info("Wrote classified inventory to %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
