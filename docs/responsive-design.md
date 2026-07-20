# Responsive Design

The interface is desktop-first because map, table, and review workflows need space, but it remains functional at 1440, 1280, 1024, 768, and 390 pixel widths.

## Behavior

- The sidebar collapses on desktop and becomes a drawer below 1020px.
- Top-bar utility/status controls compress on smaller screens.
- KPI strips reduce from multi-column layouts to one or two columns.
- Map/table workspaces can switch between split, table-only, and map-only views.
- Tables keep controlled horizontal scrolling inside table containers.
- Issue details open in a right-side drawer, sized to the viewport on mobile.
- The page body is constrained with `overflow-x: hidden` and Playwright checks for body-level horizontal overflow.

## Practical Limits

ArcGIS map rendering depends on the browser loading the ArcGIS CDN. If that fails, the surrounding workspace and data tables still render through the safe API outputs.
