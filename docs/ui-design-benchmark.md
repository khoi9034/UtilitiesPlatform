# UI Design Benchmark

Utilities Platform was redesigned after reviewing these official references as design guidance, not as templates to copy:

- Esri Calcite Design System: https://developers.arcgis.com/calcite-design-system/
- Calcite Shell: https://developers.arcgis.com/calcite-design-system/components/shell/
- Calcite Navigation: https://developers.arcgis.com/calcite-design-system/components/navigation/
- Calcite Action Bar: https://developers.arcgis.com/calcite-design-system/components/action-bar/
- Calcite Colors: https://developers.arcgis.com/calcite-design-system/foundations/colors/
- Calcite Frameworks: https://developers.arcgis.com/calcite-design-system/resources/frameworks/
- Grafana Saga: https://grafana.com/developers/saga
- Grafana dashboard best practices: https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/
- IBM data visualization basics: https://www.ibm.com/design/language/data-visualization/design/basics/
- Microsoft Fluent Nav: https://fluent2.microsoft.design/components/web/react/core/nav/usage
- Palantir Foundry ontology applications: https://www.palantir.com/docs/foundry/ontology/applications

## Useful Patterns

- Use one persistent application shell with grouped navigation, active route state, utility context, and operational status.
- Treat maps as primary work surfaces, with overlays for layer controls and review context.
- Keep dashboards hierarchical: current state first, evidence and detail next, workflow/action context last.
- Use tables for review work, with sticky headers, compact rows, filters, and side-panel details.
- Use sparse color: one actionable accent, state colors only for severity/status, and labels so color is never the only signal.
- Frame data as utility objects and workflows: assets, findings, components, dependencies, mappings, stages.

## Patterns Rejected

- Generic admin templates, Tailwind dashboard kits, fake notification/user chrome, vanity health scores, crypto-like neon styling, and fabricated metrics.
- Full proprietary interface mimicry. The final interface borrows principles only: shell discipline, operational density, restrained palette, map-first flow, and workflow/object framing.

## Accessibility And Utility Workflow Fit

The redesign uses semantic landmarks, a skip link, visible focus states, keyboard navigation, reduced-motion handling, table headers, real empty/offline states, and human-readable status badges. It supports utility workflows by keeping raw data hidden, surfacing QA candidates, separating review decisions from technical findings, and keeping planned modules honest about readiness.
