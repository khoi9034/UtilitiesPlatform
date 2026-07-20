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

All initial responses are placeholders and state that no production utility database has been connected.

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
