from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

SYSTEM_KEYWORDS = {
    "water": ["water", "wtr", "hydrant", "valve", "meter", "tank", "pressure"],
    "wastewater": ["sewer", "sanitary", "ss_", "ww", "wastewater", "manhole", "gravity", "force_main", "lift", "invert", "u_s_node", "d_s_node"],
    "stormwater": ["storm", "drain", "culvert", "inlet", "outfall", "ditch", "pond", "subbasin"],
    "telecom": ["fiber", "telecom", "conduit", "handhole", "pedestal", "splice"],
    "electric": ["electric", "power", "transformer", "pole", "switchgear"],
    "gas": ["gas", "valve", "regulator"],
    "reference": ["parcel", "address", "road", "building", "boundary", "easement", "right_of_way"],
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


def classify_layer(layer_name: str, field_names: list[str] | None = None, geometry_type: str = "") -> dict[str, str]:
    text = " ".join([layer_name, geometry_type, *(field_names or [])]).lower()
    system_scores = {
        system: sum(1 for keyword in keywords if keyword in text)
        for system, keywords in SYSTEM_KEYWORDS.items()
    }
    system = max(system_scores, key=system_scores.get)
    score = system_scores[system]
    if score == 0:
        return {"utility_type": "unknown", "asset_category": "unknown", "classification_confidence": "unknown"}

    asset_category = "unknown"
    for category, keywords in ASSET_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            asset_category = category
            break

    confidence = "high" if score >= 2 and asset_category != "unknown" else "medium"
    if system in {"gas", "water"} and text.count("valve") == 1 and score == 1:
        confidence = "low"
    if asset_category == "subbasin":
        confidence = "medium"
    return {"utility_type": system, "asset_category": asset_category, "classification_confidence": confidence}


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
