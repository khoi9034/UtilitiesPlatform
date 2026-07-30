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

The code repository and runtime data must remain on the local drive:

```text
Repository: C:\Projects\UtilitiesPlatform
Runtime data: C:\UtilitiesPlatform_Data
Public demo state: sessionStorage
```

Approved local utility data belongs in:

```text
C:\UtilitiesPlatform_Data
```

This directory is intentionally outside the Git repository. It is the local warehouse for raw approved source copies, staging work, standardized layers, curated analysis-ready data, QA reports, export packages, samples, archives, backups, and catalog files.

OneDrive, Documents, Desktop, and other synchronized folders are unsupported for the repository or runtime data. Recovery of uncertain cloud copies belongs under `C:\UtilitiesPlatform_Recovery\<timestamp>`, never under Raw, Staging, Standardized, Curated, or Git. Local paths are not returned by public APIs or included in the static demo.

Initialize it with:

```powershell
python scripts\data_storage\initialize_data_storage.py
python scripts\data_storage\validate_data_storage.py
python scripts\validate_local_storage.py
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
- `POST /api/intake/submissions/directory`
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

The upload page offers **Choose Package File** for ZIP/CAD/GeoPackage/spreadsheet/PDF packages and **Choose FileGDB Folder** for one complete unzipped `.gdb` directory. Direct folder upload uses the browser `webkitdirectory` picker, preserves relative paths, registers the folder as one Raw package, and computes a deterministic package SHA-256 from sorted `relative_path`, byte count, and per-file SHA-256 records.

Accepted V1 formats are shapefile ZIP, file-geodatabase ZIP, direct file-geodatabase folder, DWG, DXF, GeoPackage, CSV, XLSX, and PDF. The default upload limit is `1073741824` bytes and can be changed with `UTILITY_UPLOAD_MAX_BYTES`; direct folder upload also defaults to `50000` files and can be changed with `UTILITY_UPLOAD_MAX_FILES` / `NEXT_PUBLIC_UTILITY_UPLOAD_MAX_FILES`.

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

The demo runs with `NEXT_PUBLIC_APP_MODE=demo` and loads only committed sanitized JSON plus deterministic synthetic source definitions. No live utility system is connected, no exact utility geometry is published, no backend is required, and review decisions are temporary browser-session changes.

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

## Canonical Utility Asset Model V1

The platform has one shared canonical asset architecture for Electric Distribution, Telecom/Fiber, Water, and Wastewater. It includes vertical taxonomies, separate lifecycle and operational states, source lineage, provisional relationships, deterministic field mapping, human-approved canonicalization plans, immutable history, and synthetic asset explorers.

No real submission is eligible for canonicalization until source-review and staging blockers are resolved. Plan approval and asset creation are separate explicit actions. Neither action edits source or staged geometry or publishes a service.

Local routes:

- `http://localhost:3001/utility-assets`
- `http://localhost:3001/utility-assets/detail?asset_id=<asset_id>`

Start both local services:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\start-local-platform.ps1
```

The local workspace uses FastAPI and the external application registry. The public demo uses deterministic synthetic definitions and `sessionStorage` only; it makes no backend requests.

See `docs/canonical-utility-asset-model.md`.

## Multi-Utility Workspaces

UtilitiesPlatform uses one route-based workspace architecture for Electric Distribution, Telecom/Fiber, and the Water & Wastewater domain family:

- `http://localhost:3001/utilities` - choose a utility environment
- `http://localhost:3001/utilities/electric` - Electric Distribution overview
- `http://localhost:3001/utilities/electric/assets` - electric asset explorer
- `http://localhost:3001/utilities/telecom` - Telecom/Fiber overview
- `http://localhost:3001/utilities/telecom/assets` - telecom asset explorer
- `http://localhost:3001/utilities/water-wastewater` - Water & Wastewater overview
- `http://localhost:3001/utilities/water-wastewater/assets?system=water` - water asset explorer
- `http://localhost:3001/utilities/water-wastewater/assets?system=wastewater` - wastewater asset explorer
- `http://localhost:3001/command-center` - existing aggregate Command Center

Electric Distribution uses Pike-relevant concepts such as feeders, protective devices, transformers, poles, conductors, and conduit. Telecom/Fiber uses TDS-relevant concepts such as routes, cables, cabinets, splice closures, terminals, and capacity. These are vendor-neutral career-readiness workspaces; UtilitiesPlatform is not affiliated with Pike, TDS Telecom, Esri, Schneider Electric, or GE.

All workspaces use the same canonical asset core, source-governance registry, lineage model, approval controls, and audit principles. Future licensed-system integrations are adapter targets rather than copied interfaces. Utility selection is encoded in the URL, so direct links and refreshes retain context.

The static portfolio demo follows the same routes using synthetic assets and `sessionStorage` only. It does not call the local FastAPI backend or include real utility infrastructure.

Water & Wastewater V1 adds conservative source classification, 18 Water QA rules, 20 Wastewater QA rules, six Water topology traces, seven Wastewater topology traces, proposed-edit and work-order catalogs, and a fully synthetic offline demo. These are topology/connectivity workflows, not hydraulic simulation. See `docs/water-wastewater-domain-v1.md`.

## Connectivity QA Engine V1

All four utility verticals share one versioned connectivity-readiness engine over canonical assets and explicit stored relationships. Profiles run 8 shared rules plus 15 Electric, 16 Telecom, 18 Water, or 20 Wastewater rules. Runs preserve deterministic fingerprints, isolate rule failures, support human review with immutable history, and export safe summaries.

- `http://localhost:3001/utilities/electric/connectivity-qa`
- `http://localhost:3001/utilities/telecom/connectivity-qa`
- `http://localhost:3001/utilities/water-wastewater/connectivity-qa?system=water`
- `http://localhost:3001/utilities/water-wastewater/connectivity-qa?system=wastewater`

Start both services, open either route, and select **Run Connectivity QA**:

```powershell
cd C:\Projects\UtilitiesPlatform
powershell -ExecutionPolicy Bypass -File scripts\local\start-local-platform.ps1
```

Local mode persists QA records in the existing external application registry. Static demo mode derives the same synthetic scenarios in the browser, uses `sessionStorage` for run and review state, and makes no backend requests.

This engine does not trace networks, infer authoritative electrical flow, repair topology, alter source or staged geometry, publish services, or implement ArcFM, GE Smallworld, Esri Utility Network, or a telecom inventory product. See `docs/connectivity-qa-engine.md`.

### Connectivity QA Calibration and Root-Cause Triage V1

The QA workspace now separates immutable technical evidence from actionable issue groups. Deterministic calibration groups findings that share explicit asset or relationship evidence and an allowlisted dependency, while preserving every original finding.

The default **Actionable Issues** view prioritizes probable root causes, trace impact, affected assets, and the next corrective action. **All Technical Findings** retains the complete raw result set. Technical severity and blocking are never silently downgraded; workflow priority and trace impact are stored separately.

Run QA and calibration through the interface, or call:

```powershell
Invoke-RestMethod -Method Post `
  -ContentType "application/json" `
  -Body '{"force_recalculate":false,"preserve_review_decisions":true}' `
  http://127.0.0.1:8001/api/connectivity-qa/electric_distribution/runs/<qa_run_id>/calibrate
```

The public demo performs the same synthetic grouping in `sessionStorage`, supports group review and safe summary export, and makes no backend requests. The expectation manifest is `config/qa_rules/connectivity_synthetic_expectations_v1.json`.

Electric QA rule V2 limits feeder and circuit membership checks to active operational network assets and connectivity or membership edges. This changes the deterministic Electric fixture from 172 to 113 raw findings (`ELEC-009`: 63 to 34; `ELEC-010`: 65 to 35) without changing any other rule, technical severity, or blocking setting. The V1 run remains immutable.

UtilitiesPlatform currently uses its own vendor-neutral canonical asset and relationship model. Future licensed-system integrations will require organization-specific adapters and mappings. Current vendor-equivalent hints are conceptual only.

## Network Trace Engine V1

Electric Distribution, Telecom/Fiber, Water, and Wastewater share one read-only analytical trace engine over the canonical graph and calibrated Connectivity QA evidence.

- `http://localhost:3001/utilities/electric/network-trace`
- `http://localhost:3001/utilities/telecom/network-trace`
- `http://localhost:3001/utilities/water-wastewater/network-trace?system=water`
- `http://localhost:3001/utilities/water-wastewater/network-trace?system=wastewater`
- FastAPI: `http://127.0.0.1:8001/docs`

Start the local frontend and backend:

```powershell
cd C:\Projects\UtilitiesPlatform
powershell -ExecutionPolicy Bypass -File scripts\local\start-local-platform.ps1
```

Example local trace:

```powershell
$body = @{
  trace_type = "ELEC-TRACE-001"
  start_asset_id = "<canonical-asset-id>"
  lifecycle_mode = "active_only"
  provisional_relationship_policy = "include_with_warning"
  qa_policy = "conservative"
  requested_by = "Local Operator"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -ContentType "application/json" `
  -Body $body `
  http://127.0.0.1:8001/api/network-trace/electric_distribution/runs
```

The workspace provides readiness preview, bounded branching, logical and ordered path views, calibrated blockers, immutable history, asset and relationship trace context, and safe receipt download. Static demo mode runs the same synthetic workflow in `sessionStorage` with no backend request.

UtilitiesPlatform Network Trace V1 performs read-only analytical traversal of the platform's vendor-neutral canonical asset and relationship model. It is not an operational ArcFM, Smallworld, Esri Utility Network, outage-management, engineering, or telecom-provisioning trace.

See `docs/network-trace-engine.md`.

### Network Trace Calibration and Result Triage V1

Every Electric and Telecom trace can now produce a separate deterministic calibrated interpretation. The default result view shows objective status, primary stopping condition, selected-path warnings, background network conditions, normal branches, genuine ambiguity, calibrated confidence reasons, and a safe human review action. The original outcome, confidence, paths, steps, raw warning and blocker counts, and every raw event remain available under **All Trace Evidence**.

Run calibration for an existing immutable trace:

```powershell
Invoke-RestMethod -Method Post -ContentType "application/json" `
  -Body '{"force_recalculate":false}' `
  http://127.0.0.1:8001/api/network-trace/electric_distribution/runs/<trace_run_id>/calibrate
```

The fixed allowlisted rule contract is `config/network_trace/trace_calibration_v1.json`; the 20 deterministic scenario expectations are in `config/network_trace_synthetic_expectations.json`. Static demo calibration and safe receipt generation run in the browser and persist synthetic state in `sessionStorage` only.

UtilitiesPlatform trace calibration interprets immutable vendor-neutral trace evidence for human review. It does not alter utility assets, repair connectivity, execute switching, allocate fiber capacity, predict outages, or reproduce proprietary utility-system traces.

See `docs/network-trace-calibration.md`.

## Proposed Edit Workspace V1

Electric Distribution, Telecom/Fiber, Water, and Wastewater share one vendor-neutral proposed-change workflow:

- `http://localhost:3001/utilities/electric/proposed-edits`
- `http://localhost:3001/utilities/telecom/proposed-edits`
- `http://localhost:3001/utilities/water-wastewater/proposed-edits?system=water`
- `http://localhost:3001/utilities/water-wastewater/proposed-edits?system=wastewater`
- `http://127.0.0.1:8001/api/proposed-edits/types`

Start both local services:

```powershell
cd <repository-root>
powershell -ExecutionPolicy Bypass -File scripts\local\start-local-platform.ps1
```

The workspace creates ordered allowlisted operations, validates a fixed baseline, applies a sparse in-memory overlay, reuses Connectivity QA and Network Trace analysis, compares before and after evidence, locks submitted versions, records human review, and generates descriptive nonexecutable JSON packages. Static demo mode provides the same synthetic workflow in `sessionStorage` with no backend requests.

UtilitiesPlatform Proposed Edit Workspace V1 creates isolated vendor-neutral change plans and evaluates them against temporary network overlays. Approval confirms the plan for future implementation review; it does not modify an operational utility GIS, execute switching, allocate telecom capacity, or apply changes to ArcFM, Smallworld, Esri Utility Network, or another proprietary system.

See `docs/proposed-edit-workspace.md`.

## Work Order and Job Package V1

Approved synthetic Proposed Edits can become structured Electric, Telecom, Water, or Wastewater job packages:

- `http://localhost:3001/utilities/electric/work-orders`
- `http://localhost:3001/utilities/telecom/work-orders`
- `http://localhost:3001/utilities/water-wastewater/work-orders?system=water`
- `http://localhost:3001/utilities/water-wastewater/work-orders?system=wastewater`
- `http://127.0.0.1:8001/api/work-orders/types`

The shared workflow stores independent design, field, GIS implementation, inspection, QA, trace, review, and closeout states. It manages roles, prerequisites, ordered job steps, inspections, safe evidence metadata, synthetic implementation overlays, approved-versus-recorded conformance, reused post-work Connectivity QA and Network Trace evidence, release gates, closeout gates, immutable versions, descriptive job packages, and completion receipts.

All V1 implementation records use `simulated_overlay_only`. Job packages contain `"executable": false`; no source, staged, canonical, or operational GIS data is edited. The public demo stores only deterministic synthetic work orders in `sessionStorage` and makes no backend requests.

UtilitiesPlatform Work Order and Job Package V1 converts approved vendor-neutral proposed changes into structured synthetic job workflows. It records planning, review, evidence, validation, and closeout without modifying an operational utility GIS or executing work in ArcFM, Smallworld, Esri Utility Network, telecom inventory, field-service, outage-management, or work-management systems.

See `docs/work-order-job-package.md`. The exact next product action is Network Snapshot, Version Control, and Implementation Verification V1; it is not started in this phase.

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
