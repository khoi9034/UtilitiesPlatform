"""Placeholder proximity checks for staged utility assets."""

import logging

logger = logging.getLogger(__name__)


def check_asset_proximity(records: list[dict[str, object]] | None = None, distance_feet: float | None = None) -> dict[str, object]:
    if records is None or distance_feet is None:
        message = "Missing records or proximity distance; proximity check was not run."
        logger.warning(message)
        return {"status": "not_configured", "message": message, "warnings": []}
    return {"status": "not_implemented", "message": "Configure a spatial index before proximity checks.", "warnings": []}
