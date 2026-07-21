# Demo Data Governance

`frontend/demo-data` is deliberately sanitized portfolio data. It is not copied from raw API outputs and must not contain exact utility geometry, county asset identifiers, local paths, credentials, source records, or internal database identifiers.

Permitted demo content:

- synthetic or shifted representative geometry
- generic IDs such as `GM-DEMO-001`
- sanitized source names
- aggregate metrics approved for public demonstration
- representative QA findings and workflow states
- explicit metadata marking the snapshot as `sanitized_and_synthetic`

Forbidden demo content:

- `C:\` paths
- `.gdb`, `.sde`, shapefile paths, or source geodatabase paths
- email addresses, tokens, secrets, connection strings, or credentials
- exact CAD content or private document names
- raw utility rows or exact protected coordinates

Validate before committing:

```powershell
python scripts\demo\validate_demo_data.py --demo-root frontend\demo-data
```

If a protected source extent is known, validate that synthetic coordinates avoid it:

```powershell
python scripts\demo\validate_demo_data.py --demo-root frontend\demo-data --protected-extent "minx,miny,maxx,maxy"
```

Demo review decisions use session storage only. `Reset Demo Session` clears them. Production review persistence remains in the local backend and requires authentication and identity-based audit logging before deployment.
