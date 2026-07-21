from __future__ import annotations

from app.services.source_inspection.base import SourceInspector
from app.services.source_inspection.cad_inspector import CadInspector
from app.services.source_inspection.file_gdb_inspector import FileGdbInspector
from app.services.source_inspection.geopackage_inspector import GeoPackageInspector
from app.services.source_inspection.pdf_inspector import PdfInspector
from app.services.source_inspection.shapefile_inspector import ShapefileInspector
from app.services.source_inspection.spreadsheet_inspector import SpreadsheetInspector


def inspectors() -> list[SourceInspector]:
    return [
        FileGdbInspector(),
        ShapefileInspector(),
        CadInspector(),
        GeoPackageInspector(),
        SpreadsheetInspector(),
        PdfInspector(),
    ]


def inspector_for(source_format: str) -> SourceInspector | None:
    return next((inspector for inspector in inspectors() if inspector.supports(source_format)), None)


def capabilities() -> list[dict[str, object]]:
    return [dict(inspector.capabilities()) for inspector in inspectors()]
