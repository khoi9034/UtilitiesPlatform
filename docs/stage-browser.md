# Stage Browser

The Data Sources workspace groups primary utility data by stage:

- Raw: immutable approved source packages and web-uploaded submissions.
- Staging: temporary imported or converted working layers and staging candidates.
- Standardized: schema-normalized working data after approved mapping.
- Curated: approved analysis-ready utility layers.
- Export: controlled output packages from the export registry.

Derived artifacts such as inventory reports, QA runs, issue outputs, review stores, mapping previews, and processing runs are shown as trust metadata, not counted as primary utility datasets.

The stage manifest at `C:\UtilitiesPlatform_Data\00_admin\data_stage_manifest.json` is built from safe catalog rows, intake registry metadata, inventory reports, staging allowlist metadata, processing history, and export registry rows. It strips local paths before API responses.
