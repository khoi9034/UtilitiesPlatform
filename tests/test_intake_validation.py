import io
import zipfile
from pathlib import Path

import pytest

from app.services.archive_validation_service import ArchiveValidationError, validate_zip_archive
from app.services.upload_validation_service import UploadValidationError, sanitize_filename, validate_metadata, validate_uploaded_file


def write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def test_filename_sanitization_drops_browser_paths() -> None:
    assert sanitize_filename(r"C:\fakepath\Main Lines.zip") == "Main_Lines.zip"


def test_metadata_requires_authorization() -> None:
    with pytest.raises(UploadValidationError, match="Authorization"):
        validate_metadata(
            {
                "submission_name": "x",
                "utility_system": "wastewater",
                "source_type": "approved",
                "source_owner": "owner",
                "source_description": "desc",
                "sensitivity_level": "restricted",
                "authorization_confirmed": False,
            }
        )


def test_shapefile_sidecars_required(tmp_path: Path) -> None:
    path = tmp_path / "bad.zip"
    write_zip(path, {"main.shp": b"x", "main.dbf": b"x"})

    with pytest.raises(ArchiveValidationError, match="sidecars"):
        validate_zip_archive(str(path))


def test_geodatabase_zip_must_have_one_gdb_root(tmp_path: Path) -> None:
    path = tmp_path / "two.zip"
    write_zip(path, {"one.gdb/a": b"x", "two.gdb/a": b"x"})

    with pytest.raises(ArchiveValidationError, match="exactly one"):
        validate_zip_archive(str(path))


def test_csv_upload_detects_spreadsheet(tmp_path: Path) -> None:
    path = tmp_path / "table.csv"
    path.write_text("id,x,y\n1,0,0\n", encoding="utf-8")

    result = validate_uploaded_file(path, "table.csv", path.stat().st_size)

    assert result.source_format == "spreadsheet"


def test_nested_archive_rejected(tmp_path: Path) -> None:
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as archive:
        archive.writestr("inner.txt", b"x")
    path = tmp_path / "outer.zip"
    write_zip(path, {"inner.zip": nested.getvalue(), "main.shp": b"x", "main.shx": b"x", "main.dbf": b"x"})

    with pytest.raises(ArchiveValidationError, match="Forbidden"):
        validate_zip_archive(str(path))
