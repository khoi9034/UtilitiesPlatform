"""Inventory a utility geodatabase when an approved workspace is configured."""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def inventory_geodatabase(workspace: str | Path | None = None) -> dict[str, object]:
    # ArcPy scripts must run inside an ArcGIS Pro Python environment.
    if workspace is None:
        message = "Missing geodatabase workspace; no inventory was performed."
        logger.warning(message)
        return {"status": "not_configured", "message": message, "layers": []}
    return {"status": "not_implemented", "workspace": str(workspace), "layers": []}
