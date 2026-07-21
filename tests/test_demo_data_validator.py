import json
from pathlib import Path

from scripts.demo.validate_demo_data import validate_demo_root


def write_demo(root: Path, extra: dict | None = None) -> None:
    root.mkdir(exist_ok=True)
    payload = {
        "mode": "portfolio_demo",
        "data_classification": "sanitized_and_synthetic",
        "live_system_connected": False,
        "writes_persisted": False,
        "generated_at": "2026-07-20T12:00:00-04:00",
        "disclaimer": "Sanitized portfolio snapshot. Geometry and identifiers are synthetic.",
    } | (extra or {})
    (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (root / "map.json").write_text(json.dumps(payload | {"pipes": [{} for _ in range(40)], "manholes": [{} for _ in range(35)], "issues": []}), encoding="utf-8")


def test_demo_validator_accepts_safe_fixture(tmp_path: Path) -> None:
    write_demo(tmp_path)
    assert validate_demo_root(tmp_path) == []


def test_demo_validator_blocks_local_paths(tmp_path: Path) -> None:
    write_demo(tmp_path, {"message": r"C:\UtilitiesPlatform_Data\05_qa\Wastewater_QA.gdb"})
    assert any("denied text pattern" in error for error in validate_demo_root(tmp_path))


def test_demo_validator_blocks_protected_extent(tmp_path: Path) -> None:
    write_demo(tmp_path, {"geometry": {"type": "point", "x": 10, "y": 10}})
    assert any("protected extent" in error for error in validate_demo_root(tmp_path, (0, 0, 20, 20)))
