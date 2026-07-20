# Wastewater Data Health V1

Wastewater Data Health V1 reviews the staged wastewater gravity mains and manholes in:

```text
C:\UtilitiesPlatform_Data\02_staging\Utility_Staging.gdb
```

Source layers:

- `wastewater_gravity_main`
- `wastewater_manhole`

The module reads staged data only. It does not edit raw shapefiles, staged feature classes, or source geometry.

## Outputs

Reports are written to:

```text
C:\UtilitiesPlatform_Data\05_qa\reports
```

Spatial issue outputs are written to:

```text
C:\UtilitiesPlatform_Data\05_qa\Wastewater_QA.gdb
```

Feature classes:

- `ww_pipe_issues`
- `ww_manhole_issues`
- `ww_network_issues`

## Field Mapping

Field mapping is inferred from staged schema metadata, field names, aliases, data types, null rates, distinct counts, domains, and safe aggregate value patterns. Full source records are not exposed in reports.

Current primary mappings:

- Pipe asset ID: `WSACC_ID`
- Pipe upstream node: `U_S_NODE`
- Pipe downstream node: `D_S_NODE`
- Pipe diameter: `SZ`
- Pipe material: `MA`
- Pipe type: `TYPE`
- Pipe status: `STATUS`
- Pipe upstream/downstream inverts: `INVERTIN`, `INVERTOUT`
- Manhole asset ID: `NEW_ID`
- Manhole facility ID: `WSACC_ID`
- Manhole rim elevation: `RIM_ELEV`
- Manhole status: `STATUS`

Unavailable fields are recorded as unavailable and rules requiring them are skipped.

## Limits

This is not an ArcGIS Utility Network. Connectivity is proximity-based and intended for onboarding QA. Geometry is not snapped or repaired automatically.
