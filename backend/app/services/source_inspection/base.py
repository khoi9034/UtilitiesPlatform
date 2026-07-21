from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.services.source_inspection.models import SourceContainer, SourceLayer


@dataclass(frozen=True)
class InspectionContext:
    submission: dict[str, object]
    inspection_dir: Path
    reports_dir: Path
    run_id: str
    inspected_at: str


class SourceInspector(Protocol):
    def supports(self, source_format: str) -> bool:
        ...

    def inspect(self, context: InspectionContext) -> tuple[SourceContainer, list[SourceLayer]]:
        ...

    def capabilities(self) -> dict[str, object]:
        ...
