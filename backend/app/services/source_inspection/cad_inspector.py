from __future__ import annotations

from app.services.source_inspection.base import InspectionContext
from app.services.source_inspection.models import SourceContainer, SourceLayer
from app.services.source_inspection.normalization import stable_id


class CadInspector:
    def supports(self, source_format: str) -> bool:
        return source_format == "cad"

    def capabilities(self) -> dict[str, object]:
        return {"source_format": "cad", "schema_support": "container metadata only in V1"}

    def inspect(self, context: InspectionContext) -> tuple[SourceContainer, list[SourceLayer]]:
        name = str(context.submission.get("original_filename", "cad_source"))
        container_id = f"container-{stable_id(context.submission['submission_id'], name)}"
        layer = SourceLayer(
            layer_id=f"layer-{stable_id(context.submission['submission_id'], name, 'cad_container')}",
            submission_id=str(context.submission["submission_id"]),
            container_id=container_id,
            source_layer_name=name.rsplit(".", 1)[0],
            source_layer_alias=name.rsplit(".", 1)[0],
            object_type="cad_container",
            geometry_type="mixed_cad",
            spatial_reference_name="unknown",
            coordinate_status="unknown_spatial_reference",
            routing_state="unsupported",
            created_at=context.inspected_at,
            updated_at=context.inspected_at,
        )
        return metadata_container(context, container_id, name, "cad"), [layer]


def metadata_container(context: InspectionContext, container_id: str, name: str, source_format: str) -> SourceContainer:
    return SourceContainer(
        submission_id=str(context.submission["submission_id"]),
        container_id=container_id,
        container_name=name,
        source_format=source_format,
        source_type=str(context.submission.get("source_type", "")),
        package_utility_system=str(context.submission.get("utility_system", "")),
        source_owner=str(context.submission.get("source_owner", "")),
        project_id=str(context.submission.get("project_id", "")),
        sensitivity_level=str(context.submission.get("sensitivity_level", "")),
        inspection_status="limited",
        child_layer_count=1,
        inspection_run_id=context.run_id,
        inspected_at=context.inspected_at,
        warnings=[f"{source_format} adapter is normalized but metadata-only in V1."],
    )
