from __future__ import annotations

from pathlib import Path

from app.core.local_storage import DEFAULT_DATA_ROOT, configured_data_root, local_path_error
from scripts import validate_local_storage


def test_local_repository_and_data_root_pass(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "Projects" / "UtilitiesPlatform"
    data = tmp_path / "UtilitiesPlatform_Data"
    repo.mkdir(parents=True)
    (data / "02_staging").mkdir(parents=True)
    monkeypatch.setattr(validate_local_storage, "discover_cloud_utility_folders", lambda: [])

    report = validate_local_storage.validate(repo, data, enforce_expected_paths=False)

    assert report["valid"] is True


def test_default_data_root_is_local() -> None:
    assert local_path_error(DEFAULT_DATA_ROOT, must_exist=False) == ""


def test_onedrive_and_documents_roots_fail() -> None:
    assert "cloud-synchronized" in local_path_error(
        Path(r"C:\Users\test\OneDrive\UtilitiesPlatform_Data"), must_exist=False,
    )
    assert "Documents" in local_path_error(
        Path(r"C:\Users\test\Documents\UtilitiesPlatform_Data"), must_exist=False,
    )


def test_resolved_link_into_onedrive_fails() -> None:
    error = local_path_error(
        Path(r"C:\UtilitiesPlatform_Data"),
        resolved_path=Path(r"C:\Users\test\OneDrive\Runtime"),
        must_exist=False,
    )

    assert "cloud-synchronized" in error


def test_repository_inside_onedrive_fails() -> None:
    error = local_path_error(Path(r"C:\Users\test\OneDrive\Projects\UtilitiesPlatform"), must_exist=False)

    assert "cloud-synchronized" in error


def test_public_output_rejects_local_paths(tmp_path: Path) -> None:
    output = tmp_path / "frontend" / "out"
    output.mkdir(parents=True)
    (output / "index.html").write_text(r"C:\UtilitiesPlatform_Data", encoding="utf-8")

    assert validate_local_storage.public_output_violations(tmp_path) == ["index.html"]


def test_no_documents_fallback_or_folder_creation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("UTILITY_DATA_ROOT", raising=False)
    documents = tmp_path / "Documents"

    assert configured_data_root() == DEFAULT_DATA_ROOT
    assert not documents.exists()


def test_empty_cloud_shell_is_inactive_but_working_file_is_active(tmp_path: Path) -> None:
    folder = tmp_path / "OneDrive" / "Documents" / "Utilities Platform"
    (folder / ".git").mkdir(parents=True)

    assert validate_local_storage.has_active_content(folder) is False
    (folder / "README.md").write_text("synthetic", encoding="utf-8")
    assert validate_local_storage.has_active_content(folder) is True
