# Portfolio Demo Deployment

Utilities Platform has two frontend runtime modes.

## Local full system

`NEXT_PUBLIC_APP_MODE=local` is the working research system. It uses FastAPI, `C:\UtilitiesPlatform_Data`, ArcPy workflows, file geodatabases, generated reports, local review persistence, and future PostgreSQL/PostGIS services.

Run it with:

```powershell
cd C:\Projects\UtilitiesPlatform\backend
$env:UTILITY_DATA_ROOT="C:\UtilitiesPlatform_Data"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001

cd C:\Projects\UtilitiesPlatform\frontend
$env:NEXT_PUBLIC_APP_MODE="local"
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8001"
npm run dev -- --port 3001
```

## Static recruiter demo

`NEXT_PUBLIC_APP_MODE=demo` loads committed sanitized JSON from `frontend/demo-data`. It does not require FastAPI, ArcPy, SQLite, PostgreSQL, object storage, secrets, or private utility files.

Build the static export:

```powershell
cd C:\Projects\UtilitiesPlatform\frontend
npm run build:demo
```

Serve the export locally:

```powershell
npm run serve:demo
```

Validate demo safety and route output:

```powershell
npm run test:demo
```

When `DEMO_EXPORT=true`, Next.js uses `output: "export"`, `trailingSlash: true`, static images, and the GitHub Pages base path `/UtilitiesPlatform`.

The GitHub Pages workflow is `.github/workflows/deploy-utilities-demo.yml`. It installs frontend dependencies, builds the demo export, validates demo data, uploads `frontend/out`, and deploys with official Pages actions. It needs no deployment secrets.

## Demo limitations

The demo is read-only except for temporary browser-session review decisions. It cannot upload, standardize, curate, export, repair geometry, or connect to live utility infrastructure.
