from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_ARCPY_PYTHON = Path(r"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a synthetic direct FileGDB directory-upload smoke test.")
    parser.add_argument("--arcpy-python", type=Path, default=DEFAULT_ARCPY_PYTHON)
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    if not args.arcpy_python.exists():
        print(f"SKIP ArcPy Python not found: {args.arcpy_python}")
        return 0

    temp_context = tempfile.TemporaryDirectory(prefix=".tmp_arcpy_directory_upload_", dir=REPO_ROOT, ignore_cleanup_errors=True)
    temp_root = Path(temp_context.name)
    try:
        source_root = temp_root / "source"
        data_root = temp_root / "data_root"
        source_root.mkdir()
        data_root.mkdir()
        source_gdb = source_root / "SyntheticUpload.gdb"

        run_arcpy(args.arcpy_python, make_create_script(temp_root), {"SMOKE_SOURCE_ROOT": str(source_root)})
        upload_result = upload_directory(source_gdb, data_root)
        run_arcpy(
            args.arcpy_python,
            make_verify_script(temp_root),
            {"SMOKE_SOURCE_GDB": str(source_gdb), "SMOKE_RAW_GDB": upload_result["raw_gdb"]},
        )
        inspection_result = inspect_existing_submission(upload_result["submission_id"], data_root)
        upload_result.update(inspection_result)
        print(json.dumps(upload_result, indent=2))
        print("ArcPy synthetic directory upload smoke passed.")
        return 0
    finally:
        if args.keep_temp:
            print(f"Temp workspace kept: {temp_root}")
        else:
            temp_context.cleanup()
            if temp_root.exists():
                print(f"Temp cleanup deferred by a Windows file lock: {temp_root}")


def run_arcpy(arcpy_python: Path, script_path: Path, extra_env: dict[str, str]) -> None:
    env = {**os.environ, **extra_env}
    result = subprocess.run([str(arcpy_python), str(script_path)], cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode:
        raise SystemExit(result.returncode)


def make_create_script(temp_root: Path) -> Path:
    path = temp_root / "create_synthetic_gdb.py"
    path.write_text(
        """
from __future__ import annotations
import os
import arcpy

root = os.environ["SMOKE_SOURCE_ROOT"]
gdb = arcpy.management.CreateFileGDB(root, "SyntheticUpload.gdb").getOutput(0)
fc = arcpy.management.CreateFeatureclass(gdb, "smoke_points", "POINT", spatial_reference=4326).getOutput(0)
arcpy.management.AddField(fc, "ASSET_ID", "TEXT", field_length=32)
with arcpy.da.InsertCursor(fc, ["SHAPE@XY", "ASSET_ID"]) as rows:
    rows.insertRow([(-80.5, 35.4), "SYN-001"])
    rows.insertRow([(-80.6, 35.5), "SYN-002"])
print(gdb)
""".strip(),
        encoding="utf-8",
    )
    return path


def upload_directory(source_gdb: Path, data_root: Path) -> dict[str, str]:
    os.environ["UTILITY_DATA_ROOT"] = str(data_root)
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.main import app

    paths = sorted(path for path in source_gdb.rglob("*") if path.is_file())
    relative_paths = [path.relative_to(source_gdb.parent).as_posix() for path in paths]
    handles = []
    try:
        files = []
        for path in paths:
            handle = path.open("rb")
            handles.append(handle)
            files.append(("files", (path.name, handle, "application/octet-stream")))
        with TestClient(app) as client:
            response = client.post(
                "/api/intake/submissions/directory",
                data={
                    "submission_name": "ArcPy Synthetic FileGDB Folder",
                    "utility_system": "wastewater",
                    "source_type": "approved_source_package",
                    "source_owner": "Synthetic Owner",
                    "source_description": "Synthetic ArcPy smoke-test FileGDB.",
                    "sensitivity_level": "restricted",
                    "project_id": "ARCPY-SMOKE",
                    "submitted_by": "automated-smoke-test",
                    "authorization_confirmed": "true",
                    "relative_paths": relative_paths,
                },
                files=files,
            )
    finally:
        for handle in handles:
            handle.close()
    if response.status_code != 200:
        raise SystemExit(f"upload failed: {response.status_code} {response.text}")

    submission = response.json()["submissions"][0]
    raw_original = data_root / "01_raw" / "submissions" / submission["submission_id"] / "original"
    raw_gdbs = list(raw_original.glob("*.gdb"))
    manifest = raw_original.parent / "submission_manifest.json"
    if len(raw_gdbs) != 1 or not manifest.exists():
        raise SystemExit("raw registration or manifest missing")
    return {"submission_id": submission["submission_id"], "source_format": submission["source_format"], "raw_gdb": str(raw_gdbs[0])}


def make_verify_script(temp_root: Path) -> Path:
    path = temp_root / "verify_synthetic_gdb.py"
    path.write_text(
        """
from __future__ import annotations
import os
import arcpy

source_fc = os.path.join(os.environ["SMOKE_SOURCE_GDB"], "smoke_points")
raw_fc = os.path.join(os.environ["SMOKE_RAW_GDB"], "smoke_points")
source_count = int(arcpy.management.GetCount(source_fc).getOutput(0))
raw_count = int(arcpy.management.GetCount(raw_fc).getOutput(0))
if source_count != 2 or raw_count != source_count:
    raise SystemExit(f"count mismatch: source={source_count} raw={raw_count}")
print(f"ArcPy smoke verified source_count={source_count} raw_count={raw_count}")
""".strip(),
        encoding="utf-8",
    )
    return path


def inspect_existing_submission(submission_id: str, data_root: Path) -> dict[str, str]:
    os.environ["UTILITY_DATA_ROOT"] = str(data_root)
    from app.services.source_inspection import registry, runner

    result = runner.inspect_submission(submission_id, actor="automated-smoke-test")
    layers = registry.all_layers(data_root, submission_id)
    if result["inspection_status"] != "complete" or len(layers) != 1 or layers[0]["record_count"] != 2:
        raise SystemExit(f"inspection mismatch: {result} layers={len(layers)}")
    return {"inspection_status": str(result["inspection_status"]), "inspected_child_layers": str(len(layers))}


if __name__ == "__main__":
    raise SystemExit(main())
