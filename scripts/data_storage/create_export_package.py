from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from common import append_export_row, configure_logging, ensure_under_root, load_config, read_catalog


def truthy(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a controlled export package folder and manifest.")
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--export-name", required=True)
    parser.add_argument("--export-format", required=True)
    parser.add_argument("--destination", required=True, help="Destination folder under C:\\UtilitiesPlatform_Data.")
    parser.add_argument("--sanitized", action="store_true")
    parser.add_argument("--approved-for-public-use", action="store_true")
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--created-by", default=os.getenv("USERNAME", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configure_logging()
    config = load_config()
    datasets = {row["dataset_id"]: row for row in read_catalog(config)}
    dataset = datasets.get(args.dataset_id)
    if not dataset:
        logging.error("Dataset ID not found: %s", args.dataset_id)
        return 1

    restricted = dataset.get("sensitivity_level", "").lower() == "restricted"
    public_export = args.destination.lower().find("sanitized_portfolio") >= 0 or args.approved_for_public_use
    if restricted and public_export and not (args.sanitized and args.approved_for_public_use):
        logging.error("Restricted datasets require --sanitized and --approved-for-public-use for public exports.")
        return 1

    destination = ensure_under_root(Path(args.destination) / args.export_name, config.master_data_root)
    manifest = {
        "dataset_id": args.dataset_id,
        "export_name": args.export_name,
        "export_format": args.export_format,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sanitized": args.sanitized,
        "approved_for_public_use": args.approved_for_public_use,
        "purpose": args.purpose,
    }
    if args.dry_run:
        logging.info("Would create export package %s", destination)
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (destination / "README.md").write_text(
        "# Export Package\n\nThis folder is a controlled export package. No files are published or uploaded automatically.\n",
        encoding="utf-8",
    )
    export_id = append_export_row(
        config,
        {
            "dataset_id": args.dataset_id,
            "export_name": args.export_name,
            "export_format": args.export_format,
            "export_path": str(destination),
            "created_at": manifest["created_at"],
            "created_by": args.created_by,
            "sanitized": str(args.sanitized).lower(),
            "approved_for_public_use": str(args.approved_for_public_use).lower(),
            "purpose": args.purpose,
        },
    )
    logging.info("Created export package %s at %s", export_id, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
