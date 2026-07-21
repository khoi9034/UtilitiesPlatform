# Utility Data Intake

Utility Data Intake V1 registers approved source packages into immutable local Raw storage under `C:\UtilitiesPlatform_Data\01_raw\submissions`.

The workflow is intentionally gated:

1. Select one approved logical package.
2. Enter source metadata and authorization confirmation.
3. Run browser prechecks.
4. Stream upload to local FastAPI.
5. Validate package and checksum.
6. Move the untouched original into Raw submission storage.
7. Write a safe submission manifest.
8. Register a pending-inventory catalog row.
9. Optionally run safe inventory on the inspection copy.

Intake never stages, standardizes, curates, repairs, publishes, overwrites, or exports data automatically.

Accepted V1 packages are shapefile ZIPs, file-geodatabase ZIPs, DWG, DXF, GeoPackage, CSV, XLSX, and PDF. PDFs are metadata-only in V1.
