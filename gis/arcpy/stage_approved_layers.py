from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "data_storage"))

from common import ensure_under_root, load_config


def source_feature(row: dict[str, str], catalog_row: dict[str, str]) -> str:
    source_path = Path(catalog_row["source_path"])
    source_format = catalog_row.get("source_format", "")
    if source_format == "shapefile":
        return str(source_path)
    if source_format == "file_geodatabase":
        return str(source_path / row["source_layer_name"])
    return str(source_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy allowlisted layers into staging only when approved_to_stage is true.")
    parser.add_argument("--allowlist", default=r"C:\UtilitiesPlatform_Data\00_admin\staging_allowlist.csv")
    parser.add_argument("--execute", action="store_true", help="Required to copy layers.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config()
    allowlist_path = ensure_under_root(Path(args.allowlist), config.master_data_root)
    catalog_rows = list(csv.DictReader(config.data_catalog.open(newline="", encoding="utf-8")))
    catalog = {row["dataset_id"]: row for row in catalog_rows}
    approved = [row for row in csv.DictReader(allowlist_path.open(newline="", encoding="utf-8")) if row.get("approved_to_stage", "").lower() == "true"]
    if not approved:
        logging.info("No approved layers to stage.")
        return 0
    if not args.execute:
        logging.info("Dry run: %s layer(s) approved. Add --execute to copy.", len(approved))
        return 0

    import arcpy  # type: ignore

    for row in approved:
        catalog_row = catalog.get(row["dataset_id"])
        if not catalog_row:
            logging.error("Dataset ID not found in catalog: %s", row["dataset_id"])
            return 1
        output = ensure_under_root(config.staging_geodatabase / row["target_layer_name"], config.master_data_root)
        logging.info("Copying %s to %s", row["source_layer_name"], output)
        arcpy.conversion.ExportFeatures(source_feature(row, catalog_row), str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
