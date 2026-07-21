from __future__ import annotations

from pathlib import Path

from app.services.source_inspection.base import InspectionContext
from app.services.source_inspection.file_gdb_inspector import fallback_geometry
from app.services.source_inspection.models import SourceContainer, SourceLayer
from app.services.source_inspection.normalization import stable_id


class ShapefileInspector:
    def supports(self, source_format: str) -> bool:
        return source_format == "shapefile"

    def capabilities(self) -> dict[str, object]:
        return {"source_format": "shapefile", "schema_support": "sidecar inventory; ArcPy feature counts can be added later"}

    def inspect(self, context: InspectionContext) -> tuple[SourceContainer, list[SourceLayer]]:
        shapefiles = sorted(context.inspection_dir.rglob("*.shp"))
        container = SourceContainer(
            submission_id=str(context.submission["submission_id"]),
            container_id=f"container-{stable_id(context.submission['submission_id'], 'shapefile')}",
            container_name=str(context.submission.get("original_filename", "")),
            source_format="shapefile",
            source_type=str(context.submission.get("source_type", "")),
            package_utility_system=str(context.submission.get("utility_system", "")),
            source_owner=str(context.submission.get("source_owner", "")),
            project_id=str(context.submission.get("project_id", "")),
            sensitivity_level=str(context.submission.get("sensitivity_level", "")),
            inspection_status="complete" if shapefiles else "blocked",
            child_layer_count=len(shapefiles),
            inspection_run_id=context.run_id,
            inspected_at=context.inspected_at,
            blockers=[] if shapefiles else ["No shapefile was found in the inspection copy."],
        )
        layers = [
            SourceLayer(
                layer_id=f"layer-{stable_id(context.submission['submission_id'], path.stem)}",
                submission_id=str(context.submission["submission_id"]),
                container_id=container.container_id,
                source_layer_name=path.stem,
                source_layer_alias=path.stem,
                object_type="feature_class",
                geometry_type=fallback_geometry(path.stem),
                spatial_reference_name="provided" if path.with_suffix(".prj").exists() else "unknown",
                coordinate_status="coordinate_ready" if path.with_suffix(".prj").exists() else "unknown_spatial_reference",
                created_at=context.inspected_at,
                updated_at=context.inspected_at,
            )
            for path in shapefiles
        ]
        return container, layers
