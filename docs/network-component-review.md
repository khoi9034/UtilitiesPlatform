# Network Component Review

Wastewater V1 created a proximity graph from staged gravity mains, staged manholes, and endpoint-to-manhole matches. It is not authoritative utility topology and is not an ArcGIS Utility Network.

Phase 2 adds a component review workspace for all 77 current components. Each component includes:

- component ID
- pipe count
- manhole count
- total asset count
- approximate network length
- bounding extent
- nearest other component distance
- unmatched endpoints
- isolated status
- likely classification
- review status and notes

Valid classifications include `primary_network`, `legitimate_secondary_network`, `likely_missing_connection`, `missing_dependent_layer`, `incomplete_source_coverage`, `private_or_external_network`, `isolated_asset_group`, and `unknown`.

Small components are not automatically defects.
