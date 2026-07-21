# Submission-Specific Staging

Approved child layers are staged into an isolated workspace:

```text
C:\UtilitiesPlatform_Data\02_staging\submissions\<submission_id>\<submission_id>_Staging.gdb
```

The submission-specific geodatabase is created with ArcPy. Layers are copied only after explicit approval and retain source geometry, source fields, and source spatial reference.

The global `Utility_Staging.gdb` is not the first destination for newly approved mixed-package layers. Submission isolation preserves lineage and prevents accidental mixing of owners, utilities, duplicate candidates, or unreviewed schemas.

After staging, the stage manifest can show the staged child item while preserving the parent Raw submission and source-layer lineage.
