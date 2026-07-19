# Architecture

Utilities Platform uses a monorepo with a frontend, backend, database layer, GIS processing workspace, guarded data folders, and documentation.

## Frontend

The frontend is a Next.js TypeScript application using the App Router, ESLint, CSS modules, and the ArcGIS Maps SDK for JavaScript. The initial UI is a non-production dashboard shell with demo placeholders only.

## Backend

The backend is a FastAPI application exposing health, platform status, data source, asset summary, and QA summary endpoints. Responses are Pydantic models and do not fabricate production data.

## PostGIS

PostgreSQL with PostGIS is the planned spatial database for staged utility systems, layers, assets, QA issues, CAD submissions, projects, and edit history.

## GIS Processing Layer

The `gis/` workspace separates ArcPy scripts, CAD inspection, QA checks, schemas, notebooks, and toolbox assets from web application code.

## ArcPy Tools

ArcPy modules are placeholders until run inside an ArcGIS Pro Python environment with approved paths and configuration.

## CAD Intake

CAD intake will validate submitted files, inventory layers, review coordinate systems, map source layers to target layers, and stage results for review.

## Data Staging

Incoming data stays separate from staging and processed outputs. Production utility data must remain outside Git.

## QA Engine

The planned QA engine will run checks for identifiers, required attributes, geometry, domains, proximity, connectivity, and source mapping issues.

## Review And Approval Workflow

Future production updates should move from staging to reviewer approval to update package generation. Production loading is not implemented yet.
