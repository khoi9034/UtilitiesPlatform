# Utilities Platform Agent Instructions

## Dual-Mode Feature Parity

For every new user-visible module, route, workflow, table, map, filter, detail panel, status, or action:

1. Update the shared `PlatformDataProvider` interface.
2. Implement local behavior in `ApiDataProvider`.
3. Implement demo behavior in `DemoDataProvider`.
4. Add or update sanitized demo fixtures.
5. Add local-mode tests.
6. Add demo-mode tests.
7. Run the demo safety validator.
8. Verify the static export.
9. Ensure demo mode makes no backend requests.
10. Document any intentionally unavailable demo operation.

Rules:

- Local mode is the canonical processing implementation.
- Demo mode mirrors the user experience with fake, synthetic, or sanitized data.
- No real utility geometry or identifiers may enter demo fixtures.
- Demo write actions use `sessionStorage` or React state only.
- Demo intake actions must never upload, read file contents, or persist beyond `sessionStorage`.
- No local-only user-visible route may be added without a demo equivalent.
- Planned local modules may remain planned in demo mode, but must have an honest readiness page.
- Business logic should be shared where practical.
- Pages must consume `PlatformDataProvider` rather than calling FastAPI directly.
- Any exception must be documented with a reason.

## Source Inspection Rules

- Mixed Raw packages remain one submission; child layers get independent taxonomy candidates.
- Source inspection reads the inspection copy only.
- Staging approval is explicit and layer-level.
- Demo source-inspection reviews and staging simulation stay in `sessionStorage`.
- File geodatabase schema inspection requires ArcPy for real `.gdb` contents.
