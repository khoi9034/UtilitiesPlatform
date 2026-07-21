from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.data_storage_service import build_stage_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the safe stage-aware data source manifest.")
    parser.add_argument("--dry-run", action="store_true", help="Print the manifest without writing data_stage_manifest.json.")
    args = parser.parse_args()
    manifest = build_stage_manifest(write=not args.dry_run)
    print(json.dumps({"counts": manifest["counts"], "item_count": len(manifest["items"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
