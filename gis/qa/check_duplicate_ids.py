"""Check staged asset records for duplicate source identifiers."""

import logging

logger = logging.getLogger(__name__)


def check_duplicate_ids(records: list[dict[str, object]] | None = None, id_field: str | None = None) -> dict[str, object]:
    if records is None or not id_field:
        message = "Missing records or ID field; duplicate check was not run."
        logger.warning(message)
        return {"status": "not_configured", "message": message, "duplicates": []}

    seen: set[object] = set()
    duplicates = []
    for record in records:
        value = record.get(id_field)
        if value in (None, ""):
            continue
        if value in seen:
            duplicates.append(value)
        seen.add(value)
    return {"status": "checked", "duplicates": duplicates}
