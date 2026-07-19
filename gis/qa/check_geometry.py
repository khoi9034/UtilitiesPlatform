"""Placeholder geometry validation for staged utility assets."""

import logging

logger = logging.getLogger(__name__)


def check_geometry(geometry_records: list[dict[str, object]] | None = None) -> dict[str, object]:
    # ArcPy or a GIS geometry engine must be configured before real geometry validation.
    if geometry_records is None:
        message = "Missing geometry records; geometry validation was not run."
        logger.warning(message)
        return {"status": "not_configured", "message": message, "issues": []}
    return {"status": "not_implemented", "message": "Configure a GIS geometry engine before validation.", "issues": []}
