# Frontend Architecture

The frontend keeps the existing Next.js, React, TypeScript, CSS Modules, and ArcGIS Maps SDK foundations.

## Shared Shell

`frontend/components/app-shell/AppShell.tsx` provides the persistent sidebar, top bar, utility selector, command palette, theme toggle, route status, and local research badge. Public URLs did not change.

## Shared Libraries

- `frontend/lib/api-client.ts`: API URL handling and fetch helpers.
- `frontend/lib/api-types.ts`: safe API response types.
- `frontend/lib/formatters.ts`: labels, dates, percentages, and compact numbers.
- `frontend/lib/navigation.ts`: route definitions, groups, statuses, and Calcite icon names.
- `frontend/lib/statuses.ts`: workflow/disposition lists and status tones.
- `frontend/lib/utility-systems.ts`: reusable utility-system configuration.

## Reusable Workspaces

- Command Center: aggregate operations view using `/api/platform/command-center`.
- Data Health: tabbed issue, network, rules, calibration, and standardization review workspace.
- Data Sources: catalog, inventory, storage, and processing-history workspace.
- Trust Pipeline: interactive lifecycle stage rail.
- Asset Inventory and Network Intelligence: safe live summaries using existing wastewater API outputs.
- Module Readiness: honest planned-state pages for CAD intake, projects, and maintenance.

## Map Strategy

`frontend/components/maps/UtilityMap.tsx` centralizes ArcGIS SDK loading from the official CDN and consumes only safe backend map JSON. It does not expose local paths or source records.
