# Data Governance

Utility infrastructure data may be sensitive and must be handled as controlled operational information.

Rules:

- Do not commit county production data.
- Do not commit utility infrastructure data unless explicitly approved.
- Do not commit CAD files, PDFs, spreadsheets, database exports, or local environment files.
- Use sanitized JSON or GeoJSON only for public demonstrations.
- Keep raw incoming files separate from staged and processed outputs.
- Keep production data outside Git.
- Document source owner, access level, refresh method, and sensitivity before loading data.
