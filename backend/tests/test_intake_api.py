import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def metadata() -> dict[str, str]:
    return {
        "submission_name": "Synthetic Gravity Main Source",
        "utility_system": "wastewater",
        "source_type": "approved_source_package",
        "source_owner": "Synthetic Owner",
        "source_description": "Synthetic package for intake tests.",
        "sensitivity_level": "restricted",
        "project_id": "TEST",
        "submitted_by": "tester",
        "authorization_confirmed": "true",
    }


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def shapefile_package() -> bytes:
    return zip_bytes(
        {
            "gravity/gravity.shp": b"synthetic-shp",
            "gravity/gravity.shx": b"synthetic-shx",
            "gravity/gravity.dbf": b"synthetic-dbf",
            "gravity/gravity.prj": b"synthetic-prj",
        }
    )


def test_streamed_upload_registers_raw_manifest_and_catalog(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    response = client.post(
        "/api/intake/submissions",
        data=metadata(),
        files=[("files", ("Gravity Source.zip", shapefile_package(), "application/zip"))],
    )
    payload = response.json()

    assert response.status_code == 200
    submission = payload["submissions"][0]
    assert submission["current_status"] == "registered_raw"
    assert submission["source_format"] == "shapefile"
    assert "C:\\" not in response.text
    assert (tmp_path / "00_admin" / "intake" / "utility_intake.sqlite").exists()
    assert (tmp_path / "01_raw" / "submissions" / submission["submission_id"] / "submission_manifest.json").exists()
    assert "source_path" not in response.text


def test_duplicate_hash_requires_explicit_version_registration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    package = shapefile_package()

    first = client.post("/api/intake/submissions", data=metadata(), files=[("files", ("Gravity.zip", package, "application/zip"))])
    duplicate = client.post("/api/intake/submissions", data=metadata(), files=[("files", ("Gravity Copy.zip", package, "application/zip"))])

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()["submissions"][0]["current_status"] == "duplicate_detected"
    assert duplicate.json()["submissions"][0]["duplicate_of_submission_id"] == first.json()["submissions"][0]["submission_id"]


def test_zip_path_traversal_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    package = zip_bytes({"../evil.shp": b"x", "evil.shx": b"x", "evil.dbf": b"x"})

    response = client.post("/api/intake/submissions", data=metadata(), files=[("files", ("Bad.zip", package, "application/zip"))])

    assert response.status_code == 422
    assert "Unsafe archive path" in response.text
    assert not list((tmp_path / "temp" / "uploads").glob("*"))


def test_loose_shapefile_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))

    response = client.post("/api/intake/submissions", data=metadata(), files=[("files", ("bad.shp", b"x", "application/octet-stream"))])

    assert response.status_code == 422
    assert "Loose .shp" in response.text


def test_inventory_action_uses_inspection_copy_and_keeps_safe_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    response = client.post("/api/intake/submissions", data=metadata(), files=[("files", ("Gravity.zip", shapefile_package(), "application/zip"))])
    submission_id = response.json()["submissions"][0]["submission_id"]

    inventory = client.post(f"/api/intake/submissions/{submission_id}/inventory")
    detail = client.get(f"/api/intake/submissions/{submission_id}")
    events = client.get(f"/api/intake/submissions/{submission_id}/events")

    assert inventory.status_code == 200
    assert detail.json()["inventory_status"] == "complete"
    assert any(event["event_type"] == "inventory_completed" for event in events.json()["events"])
    assert "01_raw" not in detail.text
    report = tmp_path / "01_raw" / "submissions" / submission_id / "reports" / "inventory_report.json"
    assert json.loads(report.read_text(encoding="utf-8"))["inventory_scope"] == "inspection_copy_only"


def test_stage_browser_routes_return_safe_raw_items(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    upload = client.post("/api/intake/submissions", data=metadata(), files=[("files", ("Gravity.zip", shapefile_package(), "application/zip"))])
    submission_id = upload.json()["submissions"][0]["submission_id"]

    stages = client.get("/api/data-sources/stages")
    items = client.get("/api/data-sources/items?stage=raw")

    assert stages.status_code == 200
    assert items.status_code == 200
    assert any(item["item_id"] == f"submission:{submission_id}" for item in items.json()["items"])
    assert "C:\\" not in items.text


def directory_files(entries: dict[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (Path(name).name, content, "application/octet-stream")) for name, content in entries.items()]


def test_directory_upload_registers_one_file_gdb_package(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    entries = {
        "Synthetic.gdb/gdb": b"gdb-system",
        "Synthetic.gdb/a00000001.gdbtable": b"table",
        "Synthetic.gdb/a00000001.gdbtablx": b"index",
    }

    response = client.post(
        "/api/intake/submissions/directory",
        data={**metadata(), "relative_paths": list(entries)},
        files=directory_files(entries),
    )
    payload = response.json()

    assert response.status_code == 200
    submission = payload["submissions"][0]
    raw_gdb = tmp_path / "01_raw" / "submissions" / submission["submission_id"] / "original" / "Synthetic.gdb"
    manifest = tmp_path / "01_raw" / "submissions" / submission["submission_id"] / "submission_manifest.json"
    assert submission["current_status"] == "registered_raw"
    assert submission["source_format"] == "file_geodatabase"
    assert raw_gdb.is_dir()
    assert json.loads(manifest.read_text(encoding="utf-8"))["package_mode"] == "directory"
    detail = client.get(f"/api/intake/submissions/{submission['submission_id']}")
    stages = client.get("/api/data-sources/stages")
    items = client.get("/api/data-sources/items?stage=raw")
    assert detail.status_code == 200
    assert stages.status_code == 200
    assert items.status_code == 200
    assert any(item["item_id"] == f"submission:{submission['submission_id']}" for item in items.json()["items"])
    assert "source_path" not in response.text
    assert "C:\\" not in response.text
    assert "source_path" not in detail.text
    assert "C:\\" not in detail.text
    assert "C:\\" not in items.text


def test_directory_upload_rejects_path_count_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    response = client.post(
        "/api/intake/submissions/directory",
        data={**metadata(), "relative_paths": ["Synthetic.gdb/gdb"]},
        files=directory_files({"Synthetic.gdb/gdb": b"x", "Synthetic.gdb/a00000001.gdbtable": b"x"}),
    )

    assert response.status_code == 422
    assert not list((tmp_path / "01_raw" / "submissions").glob("*"))


def test_directory_upload_rejects_unsafe_roots_and_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    cases = [
        {"One.gdb/gdb": b"x", "Two.gdb/gdb": b"x"},
        {"NotGdb/gdb": b"x"},
        {"Synthetic.gdb/../evil": b"x"},
        {r"C:\Synthetic.gdb\gdb": b"x"},
        {r"\\server\share\Synthetic.gdb\gdb": b"x"},
        {"Synthetic.gdb/run.exe": b"x"},
    ]

    for entries in cases:
        response = client.post(
            "/api/intake/submissions/directory",
            data={**metadata(), "relative_paths": list(entries)},
            files=directory_files(entries),
        )
        assert response.status_code == 422


def test_directory_upload_hash_is_deterministic_and_detects_duplicates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UTILITY_DATA_ROOT", str(tmp_path))
    entries = {
        "Synthetic.gdb/gdb": b"gdb-system",
        "Synthetic.gdb/a00000001.gdbtable": b"table",
    }

    first = client.post("/api/intake/submissions/directory", data={**metadata(), "relative_paths": list(entries)}, files=directory_files(entries))
    second_entries = dict(reversed(list(entries.items())))
    second = client.post("/api/intake/submissions/directory", data={**metadata(), "relative_paths": list(second_entries)}, files=directory_files(second_entries))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["submissions"][0]["sha256_prefix"] == second.json()["submissions"][0]["sha256_prefix"]
    assert second.json()["submissions"][0]["current_status"] == "duplicate_detected"
