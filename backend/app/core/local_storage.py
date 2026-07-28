from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA_ROOT = Path(r"C:\UtilitiesPlatform_Data")
CLOUD_MARKERS = ("onedrive", "dropbox", "google drive", "icloud", "sharepoint")
UNSUPPORTED_FOLDERS = ("documents", "desktop")


class LocalStorageError(RuntimeError):
    pass


def configured_data_root() -> Path:
    return Path(os.getenv("UTILITY_DATA_ROOT", str(DEFAULT_DATA_ROOT)))


def local_path_error(path: Path, *, resolved_path: Path | None = None, must_exist: bool = True) -> str:
    candidate = path.expanduser()
    resolved = resolved_path or candidate.resolve(strict=False)
    parts = [part.casefold() for part in resolved.parts]

    if any(any(part.startswith(marker) for marker in CLOUD_MARKERS) for part in parts):
        return "Local runtime data root must be outside cloud-synchronized folders."
    if any(part in UNSUPPORTED_FOLDERS for part in parts):
        return "Local runtime data root must be outside Documents and Desktop."
    if os.name == "nt" and resolved.drive.casefold() != "c:":
        return "Local runtime data root must resolve to the local C: drive."
    if must_exist and not resolved.is_dir():
        return "Local runtime data root does not exist."
    if must_exist and not os.access(resolved, os.W_OK):
        return "Local runtime data root is not writable."
    return ""


def require_local_path(path: Path, *, must_exist: bool = True) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    error = local_path_error(path, resolved_path=resolved, must_exist=must_exist)
    if error:
        raise LocalStorageError(error)
    return resolved


def require_under_root(path: Path, root: Path, *, must_exist: bool = False) -> Path:
    resolved_root = require_local_path(root)
    resolved = require_local_path(path, must_exist=must_exist)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise LocalStorageError("Configured storage path must remain under the local runtime data root.") from exc
    return resolved


def require_runtime_data_root(*, must_exist: bool = True) -> Path:
    return require_local_path(configured_data_root(), must_exist=must_exist)
