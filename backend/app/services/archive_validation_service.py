from __future__ import annotations

import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

FORBIDDEN_ARCHIVE_EXTENSIONS = {
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
    ".zip",
}


@dataclass(frozen=True)
class ArchiveValidationResult:
    source_format: str
    files: list[dict[str, object]]
    warnings: list[str] = field(default_factory=list)


class ArchiveValidationError(ValueError):
    pass


def validate_zip_archive(
    path: str,
    *,
    max_members: int = 5000,
    max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024,
    max_compression_ratio: int = 100,
) -> ArchiveValidationResult:
    try:
        with zipfile.ZipFile(path) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if not members:
                raise ArchiveValidationError("ZIP archive is empty.")
            if len(members) > max_members:
                raise ArchiveValidationError("ZIP archive contains too many files.")
            total_uncompressed = sum(info.file_size for info in members)
            if total_uncompressed > max_uncompressed_bytes:
                raise ArchiveValidationError("ZIP archive uncompressed size exceeds the configured limit.")
            files = [_validate_member(info, max_compression_ratio) for info in members]
    except zipfile.BadZipFile as exc:
        raise ArchiveValidationError("ZIP archive could not be read.") from exc

    gdb_roots = _gdb_roots(files)
    if gdb_roots:
        if len(gdb_roots) != 1:
            raise ArchiveValidationError("File geodatabase ZIP must contain exactly one .gdb directory.")
        root = next(iter(gdb_roots))
        if any(not str(item["safe_filename"]).startswith(f"{root}/") for item in files):
            raise ArchiveValidationError("File geodatabase ZIP may not contain unrelated files outside the .gdb directory.")
        return ArchiveValidationResult(source_format="file_geodatabase", files=files)

    shapefile_sets = _shapefile_sets(files)
    complete_sets = [stem for stem, extensions in shapefile_sets.items() if {".shp", ".shx", ".dbf"}.issubset(extensions)]
    if complete_sets:
        warnings = [] if all(".prj" in shapefile_sets[stem] for stem in complete_sets) else ["Projection file is missing for at least one shapefile."]
        return ArchiveValidationResult(source_format="shapefile", files=files, warnings=warnings)
    if shapefile_sets:
        raise ArchiveValidationError("Shapefile ZIP must include .shp, .shx, and .dbf sidecars.")
    raise ArchiveValidationError("ZIP must contain a complete shapefile package or exactly one file geodatabase.")


def _validate_member(info: zipfile.ZipInfo, max_compression_ratio: int) -> dict[str, object]:
    name = info.filename.replace("\\", "/")
    path = PurePosixPath(name)
    if name.startswith(("/", "\\")) or ":" in path.parts[0] or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveValidationError(f"Unsafe archive path refused: {info.filename}")
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        raise ArchiveValidationError(f"Symbolic link refused in archive: {info.filename}")
    if info.flag_bits & 0x1:
        raise ArchiveValidationError("Encrypted or password-protected archives are not supported.")
    extension = path.suffix.lower()
    if extension in FORBIDDEN_ARCHIVE_EXTENSIONS:
        raise ArchiveValidationError(f"Forbidden file type inside archive: {extension}")
    if info.compress_size and info.file_size / max(info.compress_size, 1) > max_compression_ratio:
        raise ArchiveValidationError("ZIP archive compression ratio exceeds the configured safeguard.")
    return {
        "safe_filename": str(path),
        "extension": extension,
        "size_bytes": info.file_size,
        "compressed_size_bytes": info.compress_size,
    }


def _gdb_roots(files: list[dict[str, object]]) -> set[str]:
    roots: set[str] = set()
    for item in files:
        parts = str(item["safe_filename"]).split("/")
        for index, part in enumerate(parts):
            if part.lower().endswith(".gdb"):
                roots.add("/".join(parts[: index + 1]))
                break
    return roots


def _shapefile_sets(files: list[dict[str, object]]) -> dict[str, set[str]]:
    sets: dict[str, set[str]] = {}
    for item in files:
        path = PurePosixPath(str(item["safe_filename"]))
        if path.suffix.lower() in {".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".xml"}:
            sets.setdefault(str(path.with_suffix("")).lower(), set()).add(path.suffix.lower())
    return sets
