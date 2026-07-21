from __future__ import annotations

from app.services.source_inspection.cad_inspector import metadata_container
from app.services.source_inspection.base import InspectionContext
from app.services.source_inspection.models import SourceLayer
from app.services.source_inspection.normalization import stable_id


class GeoPackageInspector:
    def supports(self, source_format: str) -> bool:
        return source_format == "geopackage"

    def capabilities(self) -> dict[str, object]:
        return {"source_format": "geopackage", "schema_support": "container metadata only in V1"}

    def inspect(self, context: InspectionContext):
        name = str(context.submission.get("original_filename", "geopackage_source"))
        container_id = f"container-{stable_id(context.submission['submission_id'], name)}"
        layer = SourceLayer(
            layer_id=f"layer-{stable_id(context.submission['submission_id'], name, 'geopackage_container')}",
            submission_id=str(context.submission["submission_id"]),
            container_id=container_id,
            source_layer_name=name.rsplit(".", 1)[0],
            source_layer_alias=name.rsplit(".", 1)[0],
            object_type="geopackage_container",
            geometry_type="unknown",
            spatial_reference_name="unknown",
            coordinate_status="unknown_spatial_reference",
            created_at=context.inspected_at,
            updated_at=context.inspected_at,
        )
        return metadata_container(context, container_id, name, "geopackage"), [layer]
