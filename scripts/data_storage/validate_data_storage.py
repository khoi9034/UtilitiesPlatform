from __future__ import annotations

import argparse
import json
import logging

from common import configure_logging, load_config, validate_storage, write_validation_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the external Utilities Platform data storage workspace.")
    parser.parse_args()

    configure_logging()
    config = load_config()
    report = validate_storage(config)
    report_path = write_validation_report(config, report)

    logging.info("Validation report: %s", report_path)
    logging.info("Storage valid: %s", report["valid"])
    logging.info("Missing directories: %s", len(report["missing_directories"]))
    logging.info("Missing catalogs: %s", len(report["missing_catalogs"]))
    logging.info("Geodatabases: %s", json.dumps(report["geodatabases"]))
    if report["tracked_production_data_files"]:
        logging.error("Tracked production data-like files: %s", report["tracked_production_data_files"])
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
