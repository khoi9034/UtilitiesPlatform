# Utility Health Module Architecture

The Data Health module is designed to be reusable across utility systems.

Core concepts:

- `utility_system`
- `network_group`
- `asset_category`
- `asset_subcategory`
- QA category
- issue status
- source layer

Wastewater V1 supplies wastewater-specific rules and labels, but the frontend structure uses reusable sections:

- `UtilityHealthSummary`
- `IssueExplorer`
- `UtilityMap`
- `RuleCatalog`
- `NetworkMetrics`
- `UtilityContextBreadcrumb`

The same pattern can support water, stormwater, telecom, electric, gas, and shared reference data by adding system-specific rules, field mappings, generated reports, and safe API services.

Generated reports stay outside Git in `C:\UtilitiesPlatform_Data`. Source code, tests, safe configuration, and documentation stay in the repository.
