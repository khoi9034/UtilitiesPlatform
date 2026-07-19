from __future__ import annotations

import argparse
import logging

from common import configure_logging, initialize_storage, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the external Utilities Platform data storage workspace.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without writing files.")
    args = parser.parse_args()

    configure_logging()
    config = load_config()
    result = initialize_storage(config, dry_run=args.dry_run)

    logging.info("Storage root: %s", config.master_data_root)
    for name, status in result["geodatabases"].items():
        logging.info("%s: %s", name, status)

    if any(status == "pending_arcpy_unavailable" for status in result["geodatabases"].values()):
        logging.warning("ArcPy was not available; file geodatabases were not created.")
        logging.warning(
            'Run from ArcGIS Pro Python when available: "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe" scripts\\data_storage\\initialize_data_storage.py'
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
