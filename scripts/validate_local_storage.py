from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.local_storage import LocalStorageError, require_local_path, require_under_root  # noqa: E402

EXPECTED_REPOSITORY = Path(r"C:\Projects\UtilitiesPlatform")
EXPECTED_DATA_ROOT = Path(r"C:\UtilitiesPlatform_Data")
UTILITY_NAME = re.compile(r"utilit(?:y|ies)", re.IGNORECASE)
PUBLIC_PATH_MARKERS = (b"C:\\Users\\", b"C:\\Projects\\", b"C:\\Utilities", b"OneDrive", b"UtilitiesPlatform_Data")
TRACKED_DATA_SUFFIXES = {
    ".db", ".sqlite", ".sde", ".dwg", ".dxf", ".shp", ".shx", ".dbf", ".prj",
    ".cpg", ".gpkg", ".tif", ".tiff", ".xlsx", ".xls", ".zip", ".7z",
}


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def cloud_document_roots() -> list[Path]:
    home = Path.home()
    candidates = [home / "Documents", home / "OneDrive" / "Documents"]
    for name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        value = os.getenv(name)
        if value:
            candidates.append(Path(value) / "Documents")
    return list(dict.fromkeys(path.resolve(strict=False) for path in candidates if path.is_dir()))


def discover_cloud_utility_folders() -> list[Path]:
    folders: list[Path] = []
    for root in cloud_document_roots():
        if "onedrive" not in str(root).casefold():
            continue
        folders.extend(path for path in root.iterdir() if path.is_dir() and UTILITY_NAME.search(path.name))
    return sorted(set(folders), key=lambda path: str(path).casefold())


def has_active_content(folder: Path) -> bool:
    if any(
        path.is_file() and ".git" not in path.relative_to(folder).parts
        for path in folder.rglob("*")
    ):
        return True
    if not (folder / ".git").is_dir():
        return False
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=folder, text=True, capture_output=True, check=False,
    )
    return result.returncode == 0


def tracked_runtime_files(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=repo, text=True, capture_output=True, check=False,
    )
    tracked = []
    for value in result.stdout.splitlines():
        path = Path(value)
        if path.suffix.casefold() in TRACKED_DATA_SUFFIXES or ".gdb" in {part.casefold() for part in path.parts}:
            tracked.append(value)
    return tracked


def configured_paths(repo: Path) -> list[Path]:
    values: list[Path] = []
    env_example = repo / ".env.example"
    if env_example.exists():
        for line in env_example.read_text(encoding="utf-8").splitlines():
            if line.startswith("UTILITY_") and "=" in line:
                name, value = line.split("=", 1)
                if not (name.endswith("_ROOT") or name.endswith("_GDB")):
                    continue
                value = value.strip()
                if value:
                    values.append(Path(value))
    config = repo / "config" / "data_storage.example.json"
    if config.exists():
        values.extend(Path(value) for value in json.loads(config.read_text(encoding="utf-8")).values())
    return values


def public_output_violations(repo: Path) -> list[str]:
    output = repo / "frontend" / "out"
    if not output.exists():
        return []
    violations = []
    for path in output.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in {".html", ".js", ".json", ".css", ".txt"}:
            continue
        content = path.read_bytes().lower()
        if any(marker.lower() in content for marker in PUBLIC_PATH_MARKERS):
            violations.append(str(path.relative_to(output)))
    return violations


def active_cloud_references(repo: Path, cloud_folders: Iterable[Path]) -> list[str]:
    references = []
    needles = [str(path).casefold() for path in cloud_folders]
    if not needles:
        return references
    files = [repo / ".env.example", repo / "config" / "data_storage.example.json"]
    for root in (
        repo / "backend" / "app", repo / "scripts", repo / "frontend" / "app",
        repo / "frontend" / "components", repo / "frontend" / "lib",
        repo / "frontend" / "scripts", repo / ".github",
    ):
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file())
    for path in files:
        try:
            content = path.read_text(encoding="utf-8").casefold()
        except (OSError, UnicodeDecodeError):
            continue
        if any(needle in content for needle in needles):
            references.append(str(path.relative_to(repo)))
    return references


def validate(repo: Path, data_root: Path, *, enforce_expected_paths: bool = True) -> dict[str, object]:
    errors: list[str] = []
    cloud_folders = discover_cloud_utility_folders()
    active_cloud_folders = [path for path in cloud_folders if has_active_content(path)]
    try:
        resolved_repo = require_local_path(repo)
    except LocalStorageError as exc:
        resolved_repo = repo.resolve(strict=False)
        errors.append(f"repository: {exc}")
    try:
        resolved_data = require_local_path(data_root)
    except LocalStorageError as exc:
        resolved_data = data_root.resolve(strict=False)
        errors.append(f"data_root: {exc}")

    if enforce_expected_paths and resolved_repo != EXPECTED_REPOSITORY.resolve(strict=False):
        errors.append("Active repository is not C:\\Projects\\UtilitiesPlatform.")
    if enforce_expected_paths and resolved_data != EXPECTED_DATA_ROOT.resolve(strict=False):
        errors.append("Active runtime data root is not C:\\UtilitiesPlatform_Data.")
    if is_within(resolved_data, resolved_repo):
        errors.append("Runtime data root is inside the Git repository.")
    for path in configured_paths(resolved_repo):
        try:
            require_under_root(path, resolved_data)
        except LocalStorageError as exc:
            errors.append(f"configuration: {exc}")
    if not (resolved_data / "02_staging").is_dir():
        errors.append("Required local staging directory is missing.")

    tracked = tracked_runtime_files(resolved_repo)
    public_paths = public_output_violations(resolved_repo)
    cloud_references = active_cloud_references(resolved_repo, cloud_folders)
    if tracked:
        errors.append("Runtime database or GIS data is tracked by Git.")
    if public_paths:
        errors.append("Public static output contains local path markers.")
    if cloud_references:
        errors.append("Active files reference a discovered cloud Utilities folder.")
    if active_cloud_folders:
        errors.append("An active Utilities repository or data folder remains under synchronized Documents.")

    return {
        "valid": not errors,
        "errors": errors,
        "repository_local": not local_path_error_for_report(resolved_repo),
        "data_root_local": not local_path_error_for_report(resolved_data),
        "data_root_under_repository": is_within(resolved_data, resolved_repo),
        "tracked_runtime_files": tracked,
        "public_output_violations": public_paths,
        "active_cloud_references": cloud_references,
        "cloud_utility_folder_count": len(cloud_folders),
        "active_cloud_folder_count": len(active_cloud_folders),
        "inactive_cloud_shell_count": len(cloud_folders) - len(active_cloud_folders),
        "staging_directory_present": (resolved_data / "02_staging").is_dir(),
    }


def local_path_error_for_report(path: Path) -> str:
    try:
        require_local_path(path)
    except LocalStorageError as exc:
        return str(exc)
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate local-only UtilitiesPlatform code and runtime storage.")
    parser.add_argument("--repo-root", type=Path, default=EXPECTED_REPOSITORY)
    parser.add_argument("--data-root", type=Path, default=EXPECTED_DATA_ROOT)
    args = parser.parse_args()
    report = validate(args.repo_root, args.data_root)
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
