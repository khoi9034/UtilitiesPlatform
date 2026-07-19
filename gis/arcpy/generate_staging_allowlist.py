from __future__ import annotations

import argparse
import logging
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Report the generated staging allowlist location.")
    parser.add_argument("--allowlist", default=r"C:\UtilitiesPlatform_Data\00_admin\staging_allowlist.csv")
    args = parser.parse_args()

    path = Path(args.allowlist)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.info("Staging allowlist: %s", path)
    logging.info("Exists: %s", path.exists())
    return 0 if path.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
