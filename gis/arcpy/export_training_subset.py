"""Export sanitized training subsets from approved utility data sources."""

from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def export_training_subset(source: str | Path | None = None, output: str | Path | None = None) -> dict[str, object]:
    # ArcPy scripts must run inside an ArcGIS Pro Python environment.
    if source is None or output is None:
        message = "Missing source or output path; no training subset was exported."
        logger.warning(message)
        return {"status": "not_configured", "message": message}
    return {"status": "not_implemented", "source": str(source), "output": str(output)}
