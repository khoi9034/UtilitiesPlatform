from __future__ import annotations

import argparse
import logging

from common import append_catalog_row, configure_logging, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Register an approved dataset in the local catalog without copying it.")
    parser.add_argument("--name", required=True, help="Dataset display name.")
    parser.add_argument("--utility-type", required=True, help="water, wastewater, stormwater, telecom, electric, gas, reference, or general.")
    parser.add_argument("--asset-category", required=True, help="Asset category such as gravity_main or valve.")
    parser.add_argument("--source-format", required=True, help="Source format such as file_geodatabase, shapefile, gpkg, cad, csv, or pdf.")
    parser.add_argument("--source-path", required=True, help="Approved source path under C:\\UtilitiesPlatform_Data.")
    parser.add_argument("--source-layer-name", default="", help="Layer/table name in the source when applicable.")
    parser.add_argument("--sensitivity-level", required=True, help="Sensitivity level such as internal, restricted, or public.")
    parser.add_argument("--current-stage", required=True, help="Current storage stage such as raw, staging, standardized, curated, or export.")
    parser.add_argument("--source-owner", default="")
    parser.add_argument("--source-system", default="")
    parser.add_argument("--geometry-type", default="")
    parser.add_argument("--coordinate-system", default="")
    parser.add_argument("--unique-id-field", default="")
    parser.add_argument("--record-count", default="")
    parser.add_argument("--access-level", default="")
    parser.add_argument("--refresh-frequency", default="")
    parser.add_argument("--date-received", default="")
    parser.add_argument("--date-inventoried", default="")
    parser.add_argument("--last-processed", default="")
    parser.add_argument("--approved-for-analysis", action="store_true")
    parser.add_argument("--approved-for-export", action="store_true")
    parser.add_argument("--approved-for-public-use", action="store_true")
    parser.add_argument("--notes", default="")
    parser.add_argument("--allow-duplicate", action="store_true", help="Allow an identical dataset registration.")
    args = parser.parse_args()

    configure_logging()
    config = load_config()
    row = {
        "dataset_name": args.name,
        "utility_type": args.utility_type,
        "asset_category": args.asset_category,
        "source_format": args.source_format,
        "source_path": args.source_path,
        "source_owner": args.source_owner,
        "source_system": args.source_system,
        "source_layer_name": args.source_layer_name,
        "geometry_type": args.geometry_type,
        "coordinate_system": args.coordinate_system,
        "unique_id_field": args.unique_id_field,
        "record_count": args.record_count,
        "sensitivity_level": args.sensitivity_level,
        "access_level": args.access_level,
        "refresh_frequency": args.refresh_frequency,
        "date_received": args.date_received,
        "date_inventoried": args.date_inventoried,
        "last_processed": args.last_processed,
        "current_stage": args.current_stage,
        "approved_for_analysis": str(args.approved_for_analysis).lower(),
        "approved_for_export": str(args.approved_for_export).lower(),
        "approved_for_public_use": str(args.approved_for_public_use).lower(),
        "notes": args.notes,
    }

    try:
        dataset_id = append_catalog_row(config, row, allow_duplicate=args.allow_duplicate)
    except ValueError as exc:
        logging.error("%s", exc)
        return 1
    logging.info("Registered dataset %s", dataset_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
