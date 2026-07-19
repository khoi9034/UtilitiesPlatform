import csv
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def write_catalog(root: Path) -> None:
    admin = root / "00_admin"
    admin.mkdir(parents=True)
    fields = [
        "dataset_id",
        "dataset_name",
        "utility_type",
        "asset_category",
        "source_format",
        "source_path",
        "source_owner",
        "source_system",
        "source_layer_name",
        "geometry_type",
        "coordinate_system",
        "unique_id_field",
        "record_count",
        "sensitivity_level",
        "access_level",
        "refresh_frequency",
        "date_received",
        "date_inventoried",
        "last_processed",
        "current_stage",
        "approved_for_analysis",
        "approved_for_export",
        "approved_for_public_use",
        "notes",
    ]
    with (admin / "data_catalog.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "dataset_id": "abc",
                "dataset_name": "Restricted Water Mains",
                "utility_type": "water",
                "asset_category": "main",
                "source_format": "file_geodatabase",
                "source_path": str(root / "01_raw" / "geodatabases" / "Secret.gdb"),
                "geometry_type": "polyline",
                "coordinate_system": "NAD83",
                "record_count": "10",
                "sensitivity_level": "restricted",
                "current_stage": "raw",
                "approved_for_analysis": "true",
                "approved_for_export": "false",
                "approved_for_public_use": "false",
                "date_inventoried": "2026-07-19",
                "last_processed": "",
                "notes": "sensitive internal note",
            }
        )


def test_storage_api_returns_safe_catalog_without_source_path(tmp_path: Path, monkeypatch) -> None:
    write_catalog(tmp_path)
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    (tmp_path / "01_raw").mkdir()
    (tmp_path / "02_staging").mkdir()
    (tmp_path / "03_standardized").mkdir()
    (tmp_path / "04_curated").mkdir()
    (tmp_path / "06_exports").mkdir()

    response = client.get("/api/storage/catalog")
    payload = response.json()

    assert response.status_code == 200
    assert payload["datasets"][0]["dataset_name"] == "Restricted Water Mains"
    assert "source_path" not in payload["datasets"][0]
    assert "Secret.gdb" not in response.text
    assert "sensitive internal note" not in response.text


def test_storage_summary_empty_catalog(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    response = client.get("/api/storage/catalog/summary")
    payload = response.json()

    assert response.status_code == 200
    assert payload["total_datasets"] == 0
    assert payload["by_utility_type"] == {}
    assert payload["message"] == "No utility datasets have been registered yet."
