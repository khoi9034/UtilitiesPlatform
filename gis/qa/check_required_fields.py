"""Check staged records for missing required attribute values."""

import logging

logger = logging.getLogger(__name__)


def check_required_fields(
    records: list[dict[str, object]] | None = None,
    required_fields: list[str] | None = None,
) -> dict[str, object]:
    if records is None or not required_fields:
        message = "Missing records or required field list; required-field check was not run."
        logger.warning(message)
        return {"status": "not_configured", "message": message, "issues": []}

    issues = [
        {"record_index": index, "missing_fields": [field for field in required_fields if record.get(field) in (None, "")]}
        for index, record in enumerate(records)
        if any(record.get(field) in (None, "") for field in required_fields)
    ]
    return {"status": "checked", "issues": issues}
