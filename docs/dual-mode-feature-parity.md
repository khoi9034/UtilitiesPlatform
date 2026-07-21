# Dual-Mode Feature Parity

Utilities Platform has two runtime modes:

- Local full system: FastAPI, ArcPy, approved local utility data, external storage, geodatabases, local review persistence, and future PostGIS.
- Recruiter demo: the same React pages and reusable components, backed by sanitized or synthetic fixtures with no backend calls and no persistent writes.

## Expectations

Every user-visible local workflow needs a demo representation. The demo may simulate writes in memory or `sessionStorage`, but it must clearly label those actions as temporary and must never imply a production change occurred.

Planned local modules can stay planned in demo mode when the real workflow is not ready, but they need an honest readiness page instead of disappearing.

## Fixture Requirements

Demo fixtures must be sanitized or synthetic. Do not include real utility geometry, private identifiers, local storage roots, source filenames, credentials, account emails, or backend URLs.

## Provider Checklist

- Update `PlatformDataProvider`.
- Implement `ApiDataProvider`.
- Implement `DemoDataProvider`.
- Add fixture files to `frontend/demo-data/manifest.json`.
- Keep pages routed through the provider instead of direct FastAPI calls.
- For source-inspection workflows, mirror layer reviews, duplicate decisions, and staging simulation with `sessionStorage`.

## Testing Checklist

- Run `python scripts/demo/validate_demo_data.py --demo-root frontend/demo-data`.
- Run `npm run build:demo`.
- Run `npm run test:parity`.
- Run `npm run test:demo`.
- Confirm demo mode makes no `/api/` network requests.

## Release Checklist

- Static export succeeds.
- Vercel and GitHub Pages deployment checks include parity validation.
- No real data, `.vercel` metadata, generated output, logs, or secrets are committed.
