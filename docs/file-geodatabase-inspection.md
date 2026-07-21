# File Geodatabase Inspection

File geodatabase ZIP packages must contain exactly one `.gdb` directory and no unrelated files. The immutable original remains in Raw storage; inspection reads the extracted working copy under the submission inspection folder.

When ArcPy is available, the adapter inventories feature datasets, feature classes, tables, fields, aliases, field types, domains, subtypes, indexes where ArcPy exposes them, attachments, editor tracking, GlobalIDs, spatial reference, extent, geometry type, Z/M flags, and record counts. Safe field profiles use aggregates such as null counts, distinct pattern counts, value-format patterns, and ranges. Full source rows are not returned.

When ArcPy is unavailable, the adapter records that full geodatabase schema inspection is blocked and reports the ArcGIS Pro Python requirement. It does not create fake geodatabase structures or infer unavailable feature classes from Esri internal storage files.

ArcGIS Pro Python command pattern:

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```
