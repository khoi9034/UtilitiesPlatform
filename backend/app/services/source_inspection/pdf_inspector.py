from __future__ import annotations

from app.services.source_inspection.cad_inspector import metadata_container
from app.services.source_inspection.base import InspectionContext
from app.services.source_inspection.models import SourceLayer
from app.services.source_inspection.normalization import stable_id


class PdfInspector:
    def supports(self, source_format: str) -> bool:
        return source_format == "pdf"

    def capabilities(self) -> dict[str, object]:
        return {"source_format": "pdf", "schema_support": "metadata only in V1"}

    def inspect(self, context: InspectionContext):
        name = str(context.submission.get("original_filename", "pdf_source"))
        container_id = f"container-{stable_id(context.submission['submission_id'], name)}"
        layer = SourceLayer(
            layer_id=f"layer-{stable_id(context.submission['submission_id'], name, 'pdf_document')}",
            submission_id=str(context.submission["submission_id"]),
            container_id=container_id,
            source_layer_name=name.rsplit(".", 1)[0],
            source_layer_alias=name.rsplit(".", 1)[0],
            object_type="document",
            geometry_type="not_applicable",
            spatial_reference_name="not_applicable",
            coordinate_status="coordinate_ready",
            routing_state="needs_source_owner_confirmation",
            created_at=context.inspected_at,
            updated_at=context.inspected_at,
        )
        return metadata_container(context, container_id, name, "pdf"), [layer]
