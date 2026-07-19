from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Report field profile output path from the inventory workflow.")
    parser.add_argument("--report-root", default=r"C:\UtilitiesPlatform_Data\05_qa\reports")
    args = parser.parse_args()

    path = Path(args.report_root) / "field_profile_summary.csv"
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.info(json.dumps({"field_profile_summary": str(path), "exists": path.exists()}))
    return 0 if path.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
