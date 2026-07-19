from gis.cad.cad_layer_mapper import map_cad_layer
from gis.arcpy.classify_utility_layers import classify_layer
from gis.arcpy.inventory_geodatabase import discover_sources
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


def test_classifies_sewer_manholes_as_wastewater() -> None:
    result = classify_layer("Sewer_Manholes", ["OBJECTID", "FACILITYID"], "Point")

    assert result == {
        "utility_type": "wastewater",
        "asset_category": "manhole",
        "classification_confidence": "high",
    }


def test_classification_does_not_force_unknown_layer() -> None:
    result = classify_layer("misc_layer", ["OBJECTID"], "Polygon")

    assert result["utility_type"] == "unknown"


def test_source_discovery_ignores_shapefile_sidecars(tmp_path) -> None:
    shp = tmp_path / "raw" / "Layer.shp"
    shp.parent.mkdir()
    shp.write_text("placeholder", encoding="utf-8")
    (tmp_path / "raw" / "Layer.dbf").write_text("placeholder", encoding="utf-8")
    (tmp_path / "raw" / "Layer.shp.xml").write_text("placeholder", encoding="utf-8")

    sources = discover_sources(tmp_path / "raw")

    assert [source["source_name"] for source in sources] == ["Layer.shp"]
