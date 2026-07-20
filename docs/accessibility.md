# Accessibility

The redesigned interface targets WCAG 2.2 AA where practical for a local research application.

## Implemented

- Skip-to-content link.
- Semantic main, header, navigation, table, and dialog regions.
- Visible keyboard focus.
- Keyboard-accessible sidebar links, command palette, theme control, tabs, filters, and review drawer.
- Escape closes the command palette and mobile navigation.
- Badges include text labels so status is not color-only.
- Tables include headers.
- Empty and offline states explain what is missing and what to do next.
- `prefers-reduced-motion` reduces transitions and animations.
- Playwright + axe critical accessibility checks are configured.

## Production Notes

Production deployment still needs authentication, identity-based audit logging, formal focus trapping for all modal workflows, and a full accessibility audit with real users and assistive technologies.
