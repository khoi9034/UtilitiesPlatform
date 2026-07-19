import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from common import (
    DATA_CATALOG_COLUMNS,
    append_catalog_row,
    create_file_geodatabases,
    default_config,
    initialize_storage,
    read_catalog,
    validate_storage,
)

ROOT = Path(__file__).resolve().parents[1]


def test_storage_path_configuration_uses_temp_root(tmp_path: Path) -> None:
    config = default_config(tmp_path)

    assert config.master_data_root == tmp_path.resolve()
    assert config.raw_root == tmp_path / "01_raw"
    assert config.master_geodatabase == tmp_path / "04_curated" / "Utility_Master.gdb"


def test_catalog_creation_and_folder_validation(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    initialize_storage(config)
    report = validate_storage(config)

    assert config.data_catalog.exists()
    assert config.processing_history.exists()
    assert config.export_registry.exists()
    assert not report["missing_directories"]
    assert report["valid"] is True


def test_catalog_files_are_not_overwritten(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    config.admin_root.mkdir(parents=True)
    config.data_catalog.write_text("do_not_replace\n", encoding="utf-8")

    initialize_storage(config)

    assert config.data_catalog.read_text(encoding="utf-8") == "do_not_replace\n"


def test_dataset_registration_and_duplicate_prevention(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    initialize_storage(config)
    row = {
        "dataset_name": "Wastewater Gravity Mains",
        "utility_type": "wastewater",
        "asset_category": "gravity_main",
        "source_format": "file_geodatabase",
        "source_path": str(config.raw_root / "geodatabases" / "Example.gdb"),
        "source_layer_name": "GravityMain",
        "sensitivity_level": "restricted",
        "current_stage": "raw",
    }

    dataset_id = append_catalog_row(config, row)

    assert dataset_id
    assert len(read_catalog(config)) == 1
    with pytest.raises(ValueError, match="Duplicate"):
        append_catalog_row(config, row)


def test_missing_arcpy_marks_geodatabases_pending(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    initialize_storage(config)

    statuses = create_file_geodatabases(config)

    assert set(statuses.values()) == {"pending_arcpy_unavailable"}
    assert not config.master_geodatabase.exists()


def test_export_package_refuses_restricted_public_export_without_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = default_config(tmp_path)
    initialize_storage(config)
    dataset_id = append_catalog_row(
        config,
        {
            "dataset_name": "Restricted Main",
            "utility_type": "water",
            "asset_category": "main",
            "source_format": "file_geodatabase",
            "source_path": str(config.raw_root / "geodatabases" / "Restricted.gdb"),
            "sensitivity_level": "restricted",
            "current_stage": "raw",
        },
    )
    env = {**dict(**__import__("os").environ), "UTILITY_DATA_ROOT": str(tmp_path)}
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "data_storage" / "create_export_package.py"),
            "--dataset-id",
            dataset_id,
            "--export-name",
            "portfolio_export",
            "--export-format",
            "geojson",
            "--destination",
            str(config.exports_root / "sanitized_portfolio"),
            "--purpose",
            "Portfolio",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 1
    assert "Restricted datasets require" in result.stderr


def test_catalog_headers_match_required_columns(tmp_path: Path) -> None:
    config = default_config(tmp_path)
    initialize_storage(config)

    with config.data_catalog.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == DATA_CATALOG_COLUMNS
