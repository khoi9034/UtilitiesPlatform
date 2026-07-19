# Data Workspace

Never commit county production data.

Never commit utility infrastructure data unless explicitly approved.

Never commit database exports containing sensitive information.

Use sanitized samples for portfolio demonstrations.

Keep raw incoming files separate from processed outputs.

Use staging before loading anything into a database.

Production data must remain outside Git.

Folder purpose:

- `incoming/`: raw files received from approved sources.
- `staging/`: temporary normalized files before database loading.
- `processed/`: generated outputs that still may be sensitive.
- `samples/`: sanitized JSON or GeoJSON examples only.
- `schemas/`: data inventory and validation schemas.
- `mappings/`: source-to-target mapping examples.
