# File Geodatabase Inspection

File geodatabase intake supports either a ZIP package containing exactly one `.gdb` directory or a direct `.gdb` folder selected through **Choose FileGDB Folder**. ZIP packages must contain no unrelated files. Direct folder uploads must have one top-level `.gdb` root and are copied into Raw submission storage as one immutable source package.

Raw registration and source inspection are separate lifecycle actions. A valid upload is registered first and receives its Raw receipt; optional inspection then runs through the source-inspection endpoint. An inspection failure leaves the immutable Raw registration intact and can be retried independently.

The immutable original remains in Raw storage; inspection reads the extracted or copied working copy under the submission inspection folder. Direct folder inspection does not require ZIP extraction and uses the same normalized child-layer inventory, classification, duplicate review, coordinate review, and submission-specific staging workflow as ZIP-based geodatabases.

When ArcPy is available, the adapter inventories feature datasets, feature classes, tables, fields, aliases, field types, domains, subtypes, indexes where ArcPy exposes them, attachments, editor tracking, GlobalIDs, spatial reference, extent, geometry type, Z/M flags, and record counts. Safe field profiles use aggregates such as null counts, distinct pattern counts, value-format patterns, and ranges. Full source rows are not returned.

When ArcPy is unavailable, the adapter records that full geodatabase schema inspection is blocked and reports the ArcGIS Pro Python requirement. It does not create fake geodatabase structures or infer unavailable feature classes from Esri internal storage files.

ArcGIS Pro Python command pattern:

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```
