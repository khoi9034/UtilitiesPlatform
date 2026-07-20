# Visual Language

Utilities Platform uses a restrained operational visual system for critical-infrastructure data review.

## Tokens

Global CSS tokens define canvas backgrounds, elevated surfaces, hover and selected states, subtle and emphasized borders, primary/secondary/tertiary text, inverse text, accent, success, warning, danger, information, map overlay background, shadows, radii, spacing, motion, and z-index layers.

Dark mode is the default. Light mode is available through the top-bar theme control. The selected mode is persisted in `localStorage`, while the initial document script avoids a wrong-theme flash.

## Color

The system uses cyan as the single primary action/accent color. Severity and status colors are reserved for actual meaning:

- Danger: high severity or blocked state.
- Warning: medium severity or pending state.
- Success: complete/available state.
- Info: active/in-progress state.

No state is communicated by color alone; labels and badges accompany color.

## Typography And Density

Geist Sans is used for interface text. Geist Mono is used for asset IDs, rule codes, run IDs, technical values, and timestamps. KPI cards use short labels and contextual descriptions instead of oversized decorative numbers.

## Interaction

Motion is limited to orientation changes such as drawers, sidebar collapse, loading skeletons, and selected states. `prefers-reduced-motion` is respected globally.
