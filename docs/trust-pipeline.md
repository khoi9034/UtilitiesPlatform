# Trust Pipeline

The platform lifecycle is:

Raw -> Inventoried -> Staged -> QA Evaluated -> Human Review -> Standardization Ready -> Standardized -> Curated -> Exported

A dataset cannot skip stages because each gate records a different trust requirement:

- Raw preserves the approved source unchanged.
- Inventory records what exists and how it is classified.
- Staging creates working GIS layers without claiming they are approved.
- QA evaluates candidates and limitations.
- Human review records decisions and evidence.
- Standardization readiness confirms mappings, units, dependencies, and approvals.
- Standardized data follows the approved schema.
- Curated data is approved for analysis and controlled outputs.
- Exported data is packaged only when authorized.

The pipeline applies to CAD, shapefiles, geodatabases, spreadsheets, PDFs, and service-based sources. Wastewater is the first implementation; telecom and other utilities can use the same gates.
