# Utilities Platform

Utilities Platform is an asset- and network-centered utility intelligence system designed to connect GIS assets, CAD and as-built submissions, data-quality controls, construction projects, inspections, maintenance records, and network analysis.

## Current Status

This repository is an initial professional foundation. It includes a Next.js dashboard shell, a FastAPI backend with safe placeholder endpoints, initial SQLAlchemy/PostGIS models, Alembic migration support, GIS script placeholders, data-governance rules, and documentation templates.

No county production utility data is included.

## Architecture

- `frontend/`: Next.js, TypeScript, App Router, ESLint, CSS modules, and ArcGIS Maps SDK dependency.
- `backend/`: FastAPI application with Pydantic responses, SQLAlchemy models, GeoAlchemy2 geometry fields, Alembic, and PostgreSQL/PostGIS support.
- `database/`: configuration examples for QA rules and future database setup.
- `gis/`: ArcPy, CAD, QA, schema, notebook, and toolbox workspace.
- `data/`: guarded intake, staging, processed, sample, schema, and mapping folders.
- `docs/`: architecture, governance, CAD intake, QA, roadmap, and security documentation.

## Technology Stack

- Next.js, React, TypeScript, ESLint
- ArcGIS Maps SDK for JavaScript
- Python, FastAPI, Pydantic, Uvicorn
- SQLAlchemy, GeoAlchemy2, Alembic
- PostgreSQL with PostGIS
- Docker Compose

## Local Setup

```powershell
cd C:\Projects\UtilitiesPlatform
Copy-Item .env.example .env
docker compose up --build
```

Frontend in a separate terminal:

```powershell
cd C:\Projects\UtilitiesPlatform\frontend
npm install
npm run dev
```

Backend without Docker:

```powershell
cd C:\Projects\UtilitiesPlatform\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Data Governance Warning

Never commit county production data, utility infrastructure datasets, CAD files, PDFs, spreadsheets, database exports, credentials, or local environment files. Use sanitized JSON or GeoJSON samples only when explicitly approved for demonstration.

## Local Master Data Storage

Approved local utility data belongs in:

```text
C:\UtilitiesPlatform_Data
```

This directory is intentionally outside the Git repository. It is the local warehouse for raw approved source copies, staging work, standardized layers, curated analysis-ready data, QA reports, export packages, samples, archives, backups, and catalog files.

Initialize it with:

```powershell
python scripts\data_storage\initialize_data_storage.py
python scripts\data_storage\validate_data_storage.py
python scripts\data_storage\build_stage_manifest.py
```

File geodatabases are created only when the script runs inside an ArcGIS Pro Python environment with ArcPy available.

## Initial API Endpoints

- `GET /health`
- `GET /api/platform/status`
- `GET /api/data-sources`
- `GET /api/assets/summary`
- `GET /api/qa/summary`
- `GET /api/storage/status`
- `GET /api/storage/catalog`
- `GET /api/storage/catalog/summary`
- `GET /api/intake/capabilities`
- `POST /api/intake/submissions`
- `GET /api/intake/submissions`
- `POST /api/intake/submissions/{submission_id}/inspect`
- `GET /api/intake/submissions/{submission_id}/inspection-status`
- `GET /api/intake/submissions/{submission_id}/layers`
- `GET /api/intake/submissions/{submission_id}/duplicate-groups`
- `GET /api/intake/submissions/{submission_id}/staging-plan`
- `GET /api/data-sources/stages`
- `GET /api/data-sources/items`

Production database endpoints still state when no live production utility database has been connected. Storage, intake, inventory, QA, and stage-browser endpoints return safe local or demo metadata when available.

## Utility Data Intake And Stage Browser

Utility Data Intake V1 adds local website upload for approved source packages. Local mode streams files to FastAPI, validates them, calculates SHA-256, preserves the original under `C:\UtilitiesPlatform_Data\01_raw\submissions\<submission_id>\original`, creates `submission_manifest.json`, registers a pending-inventory catalog row, and rebuilds `C:\UtilitiesPlatform_Data\00_admin\data_stage_manifest.json`.

Upload page:

```text
http://localhost:3001/data-sources/upload
```

Submission detail:

```text
http://localhost:3001/data-sources/submission?id=<submission_id>
```

Stage browser:

```text
http://localhost:3001/data-sources?stage=raw
http://localhost:3001/data-sources?stage=staging
http://localhost:3001/data-sources?stage=standardized
http://localhost:3001/data-sources?stage=curated
http://localhost:3001/data-sources?stage=export
```

Accepted V1 formats are shapefile ZIP, file-geodatabase ZIP, DWG, DXF, GeoPackage, CSV, XLSX, and PDF. The default upload limit is `1073741824` bytes and can be changed with `UTILITY_UPLOAD_MAX_BYTES`.

Intake does not stage, standardize, curate, repair, publish, overwrite, or export data automatically. Demo mode provides the same visible workflow with sanitized fixtures and session-only simulated submissions; it does not upload files or call the backend.

## Universal Source Inspection V1

Universal Source Inspection V1 adds child-layer inspection, taxonomy candidate generation, duplicate-candidate routing, coordinate review, and staging-plan approval for uploaded source packages. Package-level `utility_system` now supports `mixed`; child layers are classified independently.

Rule configuration:

```text
config\taxonomy\utility_layer_rules_v1.json
```

Inspect a local submission:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8001/api/intake/submissions/<submission_id>/inspect
```

Review workspace:

```text
http://localhost:3001/data-sources/submission?id=<submission_id>
```

File geodatabase ZIP inspection uses ArcPy for full schema inventory when FastAPI is run from ArcGIS Pro Python. Without ArcPy, real geodatabase schema inspection is reported as blocked rather than faked.

See `docs/source-inspection-architecture.md`, `docs/layer-classification-engine.md`, and `docs/staging-approval-workflow.md`.

## Wastewater Data Health V1

Wastewater Data Health V1 reviews the staged wastewater gravity mains and manholes in `C:\UtilitiesPlatform_Data\02_staging\Utility_Staging.gdb`. It generates transparent schema, identity, attribute, geometry, flow, and proximity-connectivity QA outputs without editing raw or staged data.

Dry run:

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" gis\qa\wastewater\run_wastewater_qa.py --dry-run
```

Execute:

```powershell
& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" gis\qa\wastewater\run_wastewater_qa.py --execute --replace-output
```

Backend:

```powershell
cd C:\Projects\UtilitiesPlatform\backend
$env:UTILITY_DATA_ROOT="C:\UtilitiesPlatform_Data"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Frontend:

```powershell
cd C:\Projects\UtilitiesPlatform\frontend
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8001"
npm run dev -- --port 3001
```

View:

```text
http://localhost:3001/data-health
```

Wastewater Data Health V1 is proximity-based QA. It is not an ArcGIS Utility Network and does not claim authoritative topology.

## QA Calibration And Review Phase 2

Phase 2 adds deterministic issue fingerprints, local review persistence, immutable review history, rule calibration summaries, dependency-aware explanations, review sampling, component review, and standardization-readiness previews.

Generate Phase 2 artifacts after a Wastewater Data Health V1 run:

```powershell
python gis\qa\wastewater\review_phase2.py --data-root C:\UtilitiesPlatform_Data
```

Start the backend:

```powershell
cd C:\Projects\UtilitiesPlatform\backend
$env:UTILITY_DATA_ROOT="C:\UtilitiesPlatform_Data"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Start the frontend:

```powershell
cd C:\Projects\UtilitiesPlatform\frontend
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8001"
npm run dev -- --port 3001
```

Review pages:

```text
http://localhost:3001/data-health
http://localhost:3001/trust-pipeline
```

Phase 2 does not repair source data, alter QA thresholds, write standardized records, or create curated records. All standardization mappings default to not approved.

## Enterprise Interface

The frontend now uses a shared enterprise application shell for every platform route. It includes grouped navigation, active route state, persisted sidebar collapse, dark/light/system theme control, a keyboard command palette (`Ctrl+K` or `Cmd+K`), a utility-system selector, backend/storage status, last run context, and a restrained `LOCAL RESEARCH` indicator.

Routes:

- `http://localhost:3001/` - Command Center
- `http://localhost:3001/asset-inventory`
- `http://localhost:3001/data-health`
- `http://localhost:3001/network-intelligence`
- `http://localhost:3001/cad-intake`
- `http://localhost:3001/trust-pipeline`
- `http://localhost:3001/data-sources`
- `http://localhost:3001/data-sources/inventory`
- `http://localhost:3001/data-sources/upload`
- `http://localhost:3001/data-sources/submission?id=<submission_id>`
- `http://localhost:3001/projects`
- `http://localhost:3001/maintenance`
- `http://localhost:3001/methodology`

Frontend startup:

```powershell
cd C:\Projects\UtilitiesPlatform\frontend
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8001"
npm install
npm run dev -- --port 3001
```

Frontend checks:

```powershell
npm run lint
npm run build
npm run test:e2e
npm run test:a11y
npm audit --audit-level=moderate
```

The interface uses Calcite components/assets selectively, CSS Modules, semantic design tokens, and the existing ArcGIS Maps SDK workflow. Screenshot review artifacts belong outside Git under `C:\UtilitiesPlatform_Data\logs\ui-review`.

## Portfolio Demo

The frontend supports a static recruiter demo:

```powershell
cd C:\Projects\UtilitiesPlatform\frontend
npm run build:demo
npm run serve:demo
npm run test:demo
```

The demo runs with `NEXT_PUBLIC_APP_MODE=demo` and loads only committed sanitized JSON from `frontend/demo-data`. No live utility system is connected, no exact utility geometry is published, no backend is required, and review decisions are temporary browser-session changes.

The local full-system processing architecture is intentionally not deployed to the public demo. FastAPI, ArcPy, file geodatabases, SQLite review persistence, and `C:\UtilitiesPlatform_Data` remain local research/runtime infrastructure.

GitHub Pages deployment is defined in `.github/workflows/deploy-utilities-demo.yml` and uses the `/UtilitiesPlatform` base path.

Demo governance:

```powershell
python scripts\demo\validate_demo_data.py --demo-root frontend\demo-data
```

See `docs/demo-deployment.md` and `docs/demo-data-governance.md`.

## Dual-Mode Feature Development

Every user-visible local feature must have a recruiter-demo equivalent through the shared `PlatformDataProvider`. Local mode owns real processing; demo mode mirrors the workflow with sanitized or synthetic fixtures and temporary browser-session writes.

Checks:

```powershell
cd C:\Projects\UtilitiesPlatform\frontend
npm run build:demo
npm run test:parity
npm run test:demo
```

See `AGENTS.md` and `docs/dual-mode-feature-parity.md`.

## Repository Structure

```text
UtilitiesPlatform/
  frontend/
  backend/
  database/
  gis/
  data/
  docs/
  scripts/
  tests/
  .github/
  .env.example
  .gitignore
  README.md
  docker-compose.yml
```

## Development Roadmap

Phase 1:

- Repository and platform foundation
- Utility data inventory
- Safe staging architecture
- Initial database schema

Phase 2:

- Utility geodatabase inventory automation
- Data-health and QA reporting
- Training data ingestion

Phase 3:

- CAD intake and validation
- CAD layer mapping
- Source-to-target conversion
- Change detection

Phase 4:

- Asset intelligence dashboard
- Map-based QA review
- Project and work-order tracking

Phase 5:

- Connectivity analysis
- Trace-style workflows
- Maintenance and risk intelligence
- ArcGIS Utility Network integration research
