# Data Storage Architecture

Real utility data stays outside Git because utility infrastructure datasets can be sensitive, large, frequently changing, and unsuitable for source control. The local master storage root is:

```text
C:\UtilitiesPlatform_Data
```

## Storage Stages

- `01_raw`: untouched approved source copies. Raw files should never be edited.
- `02_staging`: temporary imported or converted data used for inspection and processing.
- `03_standardized`: schema-normalized working data with consistent fields, geometry, and coordinate systems.
- `04_curated`: approved analysis-ready utility layers.
- `05_qa`: QA reports, issue outputs, geometry checks, attribute checks, connectivity checks, and resolved issue records.
- `06_exports`: controlled output packages only.
- `07_samples`: sanitized or synthetic examples.
- `08_archive`: obsolete working outputs retained by year.
- `09_backups`: catalog, configuration, database, and processed-data backups.

## Dataset Registration

Register datasets without copying them:

```powershell
python scripts\data_storage\register_dataset.py --name "Wastewater Gravity Mains" --utility-type wastewater --asset-category gravity_main --source-format file_geodatabase --source-path "C:\UtilitiesPlatform_Data\01_raw\geodatabases\Example.gdb" --source-layer-name "GravityMain" --sensitivity-level restricted --current-stage raw
```

The catalog records metadata only. It should not expose credentials or unnecessary sensitive details.

## Export Packages

Create export package folders and manifests with:

```powershell
python scripts\data_storage\create_export_package.py --dataset-id DATASET_ID --export-name ExportName --export-format geopackage --destination "C:\UtilitiesPlatform_Data\06_exports\geopackages" --purpose "Internal review"
```

The script does not publish, upload, or copy restricted data automatically.

## Sensitivity And Approval Flags

- `approved_for_analysis`: the dataset can be used for internal analysis workflows.
- `approved_for_export`: the dataset can be included in controlled export packages.
- `approved_for_public_use`: the dataset can be used in public or portfolio contexts.
- `sanitized`: the export has been stripped or generalized as required.

Restricted utility infrastructure must not be copied into public export folders unless it is sanitized and approved for public use.

Production databases should never be used directly for experimentation. Export approved copies into raw storage first, preserve the original unchanged, and work forward through staging.
