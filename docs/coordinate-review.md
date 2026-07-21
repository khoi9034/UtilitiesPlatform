# Coordinate Review

Coordinate review compares inspected spatial-reference metadata with layer-name signals and other layers in the package.

Statuses include:

- `coordinate_ready`
- `mixed_source_spatial_references`
- `unknown_spatial_reference`
- `suspicious_extent`
- `name_and_metadata_conflict`
- `transformation_review_required`

Inspection does not project data, define missing projections, snap geometry, or repair source features. Source-preserving staging may allow mixed coordinate systems because approved layers remain standalone child outputs.
