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

The upload page supports two package selectors:

- **Choose Package File** for ZIPs, CAD files, GeoPackages, spreadsheets, and PDFs.
- **Choose FileGDB Folder** for one complete unzipped `.gdb` directory selected with the browser folder picker.

Accepted V1 packages are shapefile ZIPs, file-geodatabase ZIPs, direct file-geodatabase folders, DWG, DXF, GeoPackage, CSV, XLSX, and PDF. PDFs are metadata-only in V1.

Direct FileGDB folder upload preserves the browser-provided `webkitRelativePath` hierarchy and registers the folder as one logical Raw package. Local mode streams the internal files to FastAPI, reconstructs the folder under temporary storage, calculates per-file hashes, calculates one deterministic folder-package hash, then moves the reconstructed `.gdb` into the submission `original` folder. The user's selected source folder is not edited.
