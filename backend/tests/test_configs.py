import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_cad_mapping_configuration_parses() -> None:
    mapping_path = ROOT / "data" / "mappings" / "example_cad_layer_mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    assert "water_main" in mapping["layer_mappings"]
    assert "WATER_MAIN" in mapping["layer_mappings"]["water_main"]


def test_qa_rule_configuration_parses() -> None:
    rules_path = ROOT / "database" / "config" / "example_qa_rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))

    assert rules["rules"][0]["rule_code"] == "REQUIRED_ASSET_ID"
    assert rules["rules"][0]["is_active"] is True
