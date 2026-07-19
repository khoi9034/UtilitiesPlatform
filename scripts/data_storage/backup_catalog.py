from __future__ import annotations

import argparse
import logging

from common import REPO_ROOT, backup_file, configure_logging, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up catalog CSV files and local storage configuration.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configure_logging()
    config = load_config()
    destination = config.backup_root / "catalog"
    files = [
        config.data_catalog,
        config.processing_history,
        config.export_registry,
        REPO_ROOT / "config" / "data_storage.local.json",
    ]
    for source in files:
        backup = backup_file(source, destination, dry_run=args.dry_run)
        if backup:
            logging.info("Backup target: %s", backup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
