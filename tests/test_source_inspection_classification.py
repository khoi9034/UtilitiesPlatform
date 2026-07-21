from app.services.source_inspection.models import SourceLayer
from app.services.source_inspection.normalization import classify_layer, create_plan_items, detect_duplicate_groups


def layer(name: str, geometry: str = "polyline") -> SourceLayer:
    return SourceLayer(
        layer_id=f"layer-{name.lower()}",
        submission_id="TEST",
        container_id="container",
        source_layer_name=name,
        source_layer_alias=name,
        geometry_type=geometry,
        spatial_reference_name="Demo State Plane",
    )


def test_force_main_name_maps_to_wastewater_pressurized_pipe() -> None:
    candidate = classify_layer(layer("Town_A_ForceMains"), {"source_owner": "Town A"})[0]

    assert candidate.utility_system == "wastewater"
    assert candidate.network_group == "pressurized_network"
    assert candidate.asset_subcategory == "force_main"
    assert candidate.confidence == "high"


def test_waterline_keeps_ambiguous_candidates() -> None:
    candidates = classify_layer(layer("WaterLine"), {"source_owner": "Synthetic Owner"})

    systems = {(candidate.utility_system, candidate.asset_category, candidate.asset_subcategory) for candidate in candidates}
    assert ("water", "pipe", "water_main") in systems
    assert ("shared_reference", "hydrography_line", "stream") in systems
    assert any("confirmation" in " ".join(candidate.warnings).lower() for candidate in candidates)


def test_duplicate_detection_does_not_select_authoritative_layer() -> None:
    groups = detect_duplicate_groups("TEST", [layer("Town_B_Sewer"), layer("TownBSewer"), layer("Town_A_ForceMains")])

    assert len(groups) == 1
    assert groups[0].status == "potential_duplicate"
    assert groups[0].authoritative_layer_id == ""


def test_staging_plan_defaults_to_not_approved() -> None:
    source = layer("Town_A_ForceMains")
    candidates = {source.layer_id: classify_layer(source, {"source_owner": "Town A"})}

    item = create_plan_items("TEST", [source], candidates)[0]

    assert item.proposed_target_name.startswith("ww_force_main")
    assert item.approved_for_staging is False
