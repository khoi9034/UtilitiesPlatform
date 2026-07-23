from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RESULT_PREFIX = "UTILITY_INSPECTION_RESULT="


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect one validated intake submission with ArcGIS Pro Python.")
    parser.add_argument("--submission-id", required=True)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    os.environ["UTILITY_INSPECTION_ARCGIS_WORKER"] = "1"
    try:
        import arcpy  # type: ignore  # noqa: F401
    except Exception as exc:
        license_error = "license" in str(exc).lower()
        return emit(
            {
                "status": "blocked",
                "safe_error_code": "arcpy_license_unavailable" if license_error else "arcpy_unavailable",
                "safe_message": "ArcGIS Pro licensing is not initialized for the inspection worker." if license_error else "ArcPy could not be initialized by the inspection worker.",
                "retryable": True,
            },
            2,
        )

    try:
        from app.services.source_inspection.runner import inspect_submission

        result = inspect_submission(args.submission_id, actor="arcgis_pro_worker")
        return emit({"status": "complete", "result": result}, 0)
    except Exception as exc:
        return emit(
            {
                "status": "blocked",
                "safe_error_code": "arcgis_inspection_failed",
                "safe_message": f"ArcGIS Pro inspection failed safely ({type(exc).__name__}).",
                "retryable": True,
            },
            3,
        )


def emit(payload: dict[str, object], exit_code: int) -> int:
    print(f"{RESULT_PREFIX}{json.dumps(payload, separators=(',', ':'))}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
