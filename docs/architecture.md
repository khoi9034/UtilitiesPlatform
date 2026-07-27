# Architecture

Utilities Platform uses a monorepo with a frontend, backend, database layer, GIS processing workspace, guarded data folders, and documentation.

## Frontend

The frontend is a Next.js TypeScript application using the App Router, ESLint, CSS modules, and the ArcGIS Maps SDK for JavaScript. The initial UI is a non-production dashboard shell with demo placeholders only.

## Backend

The backend is a FastAPI application exposing intake, canonical asset, Connectivity QA, calibration, and read-only Network Trace APIs. The canonical asset registry, QA evidence, issue groups, and immutable trace records share one external application database while real GIS data remains outside Git.

Network Trace reuses the canonical connectivity graph instead of maintaining a second topology. Vertical profiles provide Electric and Telecom semantics over one deterministic traversal engine. See `network-trace-engine.md`.

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

## QA And Trace

Connectivity QA records immutable technical candidates and calibration groups likely root causes without downgrading technical evidence. Network Trace consumes those calibrated trace impacts, honors lifecycle and operational state, and records bounded analytical paths. Neither engine repairs geometry or edits source, staged, standardized, or curated data.

## Review And Approval Workflow

Future production updates should move from staging to reviewer approval to update package generation. Production loading is not implemented yet.
