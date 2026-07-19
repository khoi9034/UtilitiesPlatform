"""Inspect CAD files after an approved source path is configured."""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def inspect_cad_file(cad_path: str | Path | None = None) -> dict[str, object]:
    if cad_path is None:
        message = "Missing CAD path; no file inspection was performed."
        logger.warning(message)
        return {"status": "not_configured", "message": message, "layers": []}
    return {"status": "not_implemented", "cad_path": str(cad_path), "layers": []}
