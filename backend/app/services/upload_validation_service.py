from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.services.archive_validation_service import ArchiveValidationError, validate_zip_archive

ALLOWED_SINGLE_EXTENSIONS = {
    ".csv": "spreadsheet",
    ".dwg": "cad",
    ".dxf": "cad",
    ".gpkg": "geopackage",
    ".pdf": "pdf",
    ".xlsx": "spreadsheet",
}

FORBIDDEN_EXTENSIONS = {
    ".7z",
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".js",
    ".msi",
    ".ps1",
    ".rar",
    ".sde",
    ".sh",
    ".vbs",
}

UTILITY_SYSTEMS = {"water", "wastewater", "stormwater", "telecom", "electric", "gas", "shared_reference", "mixed", "unknown", "review_required"}
SENSITIVITY_LEVELS = {"public", "internal", "restricted", "highly_restricted"}


@dataclass(frozen=True)
class UploadValidationResult:
    source_format: str
    extension: str
    files: list[dict[str, object]]
    warnings: list[str] = field(default_factory=list)


class UploadValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "upload_validation_failed",
        safe_item: str = "",
        retryable: bool = True,
        safe_context: dict[str, str | int | bool] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.safe_item = safe_item
        self.retryable = retryable
        self.safe_context = safe_context or {}

    def as_detail(self, *, request_id: str = "") -> dict[str, object]:
        detail: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "safe_context": self.safe_context,
        }
        if self.safe_item:
            detail["safe_item"] = self.safe_item
        if request_id:
            detail["request_id"] = request_id
        return detail


def sanitize_filename(filename: str) -> str:
    display = Path(filename.replace("\\", "/")).name.strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", display).strip("._")
    return safe[:180] or "upload.bin"


def validate_metadata(metadata: dict[str, object]) -> None:
    required = ["submission_name", "utility_system", "source_type", "source_owner", "source_description", "sensitivity_level"]
    missing = [field for field in required if not str(metadata.get(field) or "").strip()]
    if missing:
        raise UploadValidationError(f"Missing required source metadata: {', '.join(missing)}")
    if metadata.get("utility_system") not in UTILITY_SYSTEMS:
        raise UploadValidationError("Unsupported utility system.")
    if metadata.get("sensitivity_level") not in SENSITIVITY_LEVELS:
        raise UploadValidationError("Unsupported sensitivity level.")
    if metadata.get("authorization_confirmed") is not True:
        raise UploadValidationError("Authorization confirmation is required before local storage.")


def validate_uploaded_file(path: Path, original_filename: str, file_size_bytes: int) -> UploadValidationResult:
    safe_name = sanitize_filename(original_filename)
    extension = Path(safe_name).suffix.lower()
    if file_size_bytes <= 0:
        raise UploadValidationError("Uploaded file is empty.")
    if extension in FORBIDDEN_EXTENSIONS:
        raise UploadValidationError(f"Forbidden upload type: {extension}")
    if extension == ".shp":
        raise UploadValidationError("Loose .shp uploads are not accepted. Upload a ZIP containing all shapefile sidecars.")
    if extension == ".sde":
        raise UploadValidationError(".sde connection files are not accepted.")
    if extension == ".zip":
        try:
            archive = validate_zip_archive(str(path))
        except ArchiveValidationError as exc:
            raise UploadValidationError(str(exc)) from exc
        return UploadValidationResult(source_format=archive.source_format, extension=extension, files=archive.files, warnings=archive.warnings)
    source_format = ALLOWED_SINGLE_EXTENSIONS.get(extension)
    if not source_format:
        raise UploadValidationError(f"Unsupported upload type: {extension or 'none'}")
    return UploadValidationResult(
        source_format=source_format,
        extension=extension,
        files=[{"safe_filename": safe_name, "extension": extension, "size_bytes": file_size_bytes}],
    )
