from __future__ import annotations

import csv

from app.services.source_inspection.base import InspectionContext
from app.services.source_inspection.models import SourceContainer, SourceLayer
from app.services.source_inspection.normalization import stable_id


class SpreadsheetInspector:
    def supports(self, source_format: str) -> bool:
        return source_format == "spreadsheet"

    def capabilities(self) -> dict[str, object]:
        return {"source_format": "spreadsheet", "schema_support": "CSV header and row-count summary; XLSX metadata-only in V1"}

    def inspect(self, context: InspectionContext) -> tuple[SourceContainer, list[SourceLayer]]:
        files = sorted(path for path in context.inspection_dir.iterdir() if path.suffix.lower() in {".csv", ".xlsx"})
        container = SourceContainer(
            submission_id=str(context.submission["submission_id"]),
            container_id=f"container-{stable_id(context.submission['submission_id'], 'spreadsheet')}",
            container_name=str(context.submission.get("original_filename", "")),
            source_format="spreadsheet",
            source_type=str(context.submission.get("source_type", "")),
            package_utility_system=str(context.submission.get("utility_system", "")),
            source_owner=str(context.submission.get("source_owner", "")),
            project_id=str(context.submission.get("project_id", "")),
            sensitivity_level=str(context.submission.get("sensitivity_level", "")),
            inspection_status="complete" if files else "blocked",
            table_count=len(files),
            inspection_run_id=context.run_id,
            inspected_at=context.inspected_at,
            blockers=[] if files else ["No spreadsheet file was found in the inspection copy."],
        )
        layers = [table_layer(path, context, container.container_id) for path in files]
        return container, layers


def table_layer(path, context: InspectionContext, container_id: str) -> SourceLayer:
    fields: list[dict[str, object]] = []
    row_count: int | None = None
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            row_count = sum(1 for _ in reader)
        fields = [{"name": column[:64], "alias": column[:64], "type": "String", "nullable": True, "required": False, "domain": ""} for column in header[:100]]
    return SourceLayer(
        layer_id=f"layer-{stable_id(context.submission['submission_id'], path.stem)}",
        submission_id=str(context.submission["submission_id"]),
        container_id=container_id,
        source_layer_name=path.stem,
        source_layer_alias=path.stem,
        object_type="table",
        geometry_type="table",
        record_count=row_count,
        field_profile=fields,
        field_count=len(fields),
        spatial_reference_name="not_applicable",
        coordinate_status="coordinate_ready",
        created_at=context.inspected_at,
        updated_at=context.inspected_at,
    )
