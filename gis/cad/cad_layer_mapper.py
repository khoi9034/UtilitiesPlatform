"""Map CAD layer names to configured utility layer targets."""

import logging

logger = logging.getLogger(__name__)


def map_cad_layer(layer_name: str | None = None, mapping: dict[str, list[str]] | None = None) -> dict[str, object]:
    if not layer_name or not mapping:
        message = "Missing CAD layer name or mapping configuration."
        logger.warning(message)
        return {"status": "not_configured", "message": message, "target": None}

    normalized = layer_name.upper()
    for target, source_layers in mapping.items():
        if normalized in {source.upper() for source in source_layers}:
            return {"status": "matched", "source": layer_name, "target": target}
    return {"status": "unmapped", "source": layer_name, "target": None}
