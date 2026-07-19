from gis.cad.cad_layer_mapper import map_cad_layer
from gis.qa.check_duplicate_ids import check_duplicate_ids
from gis.qa.check_required_fields import check_required_fields


def test_cad_layer_mapper_matches_case_insensitively() -> None:
    result = map_cad_layer("wtr_main", {"water_main": ["WTR_MAIN"]})

    assert result["status"] == "matched"
    assert result["target"] == "water_main"


def test_duplicate_ids_ignore_missing_values() -> None:
    result = check_duplicate_ids(
        [{"asset_id": "A1"}, {"asset_id": ""}, {"asset_id": None}, {"asset_id": "A1"}],
        "asset_id",
    )

    assert result["duplicates"] == ["A1"]


def test_required_fields_allow_zero_values() -> None:
    result = check_required_fields([{"diameter": 0, "asset_id": ""}], ["diameter", "asset_id"])

    assert result["issues"] == [{"record_index": 0, "missing_fields": ["asset_id"]}]
