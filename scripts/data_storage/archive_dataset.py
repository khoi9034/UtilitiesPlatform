from __future__ import annotations

import argparse
import logging
import shutil
from datetime import datetime
from pathlib import Path

from common import configure_logging, ensure_under_root, load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy or move obsolete working outputs into archive. Default is dry-run.")
    parser.add_argument("--path", required=True, help="Working output path under C:\\UtilitiesPlatform_Data.")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--move", action="store_true", help="Move instead of copy. Never deletes raw source data automatically.")
    parser.add_argument("--execute", action="store_true", help="Required to write changes.")
    args = parser.parse_args()

    configure_logging()
    config = load_config()
    source = ensure_under_root(Path(args.path), config.master_data_root)
    if not source.exists():
        logging.error("Path does not exist: %s", source)
        return 1
    if str(source).lower().startswith(str(config.raw_root).lower()):
        logging.error("Refusing to archive raw source data automatically.")
        return 1

    destination = config.archive_root / str(datetime.now().year) / source.name
    ensure_under_root(destination, config.master_data_root)
    if not args.execute:
        logging.info("Dry run: would %s %s to %s", "move" if args.move else "copy", source, destination)
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    if args.move:
        shutil.move(str(source), str(destination))
    elif source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)
    logging.info("Archived %s to %s. Reason: %s", source, destination, args.reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
