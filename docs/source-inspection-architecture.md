# Source Inspection Architecture

Universal Source Inspection V1 treats one uploaded package as one immutable Raw submission, then inspects each child layer independently. A mixed package can contain water, wastewater, reference, environmental, planning, ambiguous, duplicate-looking, and out-of-scope layers without forcing one package-level classification onto every child.

The backend keeps inspection metadata in the local intake SQLite registry under `C:\UtilitiesPlatform_Data`. API responses expose safe names, counts, aggregate metadata, classification candidates, review states, and staging-plan status only. They do not expose local paths, source records, credentials, or connection strings.

Flow:

1. Upload registers an immutable Raw package.
2. Inspection reads only the working inspection copy.
3. Adapters normalize source-container and child-layer metadata.
4. Deterministic rules create ranked classification candidates.
5. Duplicate and coordinate candidates are routed to review.
6. A staging plan is proposed but not approved.
7. Human review may approve, defer, exclude, or request confirmation.

Adapters are registered behind one provider-facing workflow. File geodatabase ZIP is ArcPy-capable; shapefile, CAD, GeoPackage, spreadsheet, and PDF adapters normalize existing lightweight inspection behavior for V1.
