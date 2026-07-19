# Exporting Data

Use controlled export packages for any data shared outside the working storage folders.

Supported export targets:

- File geodatabase
- GeoPackage
- Shapefile
- CSV
- GeoJSON
- PDF report

Warnings:

- Shapefile field names may be truncated.
- CSV cannot preserve geometry directly unless coordinates or WKT fields are included.
- GeoJSON should only contain approved, sanitized features.
- Restricted utility infrastructure should never be exported for public portfolio use without approval.

Create package metadata first:

```powershell
python scripts\data_storage\create_export_package.py --dataset-id DATASET_ID --export-name ExportName --export-format geojson --destination "C:\UtilitiesPlatform_Data\06_exports\geojson" --sanitized --approved-for-public-use --purpose "Approved portfolio sample"
```

The script creates a folder, manifest, README, and registry entry. It does not publish or upload files.
