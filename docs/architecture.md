# Architecture

Utilities Platform uses a monorepo with a frontend, backend, database layer, GIS processing workspace, guarded data folders, and documentation.

## Proposed Change Boundary

`Connectivity QA -> QA calibration -> Network Trace -> trace calibration -> Proposed Edit Workspace -> Work Order and Job Package -> future network snapshot and licensed-system adapter`

Proposed Edit Workspace V1 stores versioned vendor-neutral plans and ordered allowlisted operations in the application registry. It builds sparse temporary overlays in memory and invokes the existing pure QA, calibration, trace, and trace-calibration functions for before-and-after evidence. Canonical assets, canonical relationships, source and staged geometry, and immutable QA and trace evidence remain unchanged.

An approved proposal is an approved plan only. Safe implementation packages are descriptive JSON with `executable: false`; no proprietary SDK, schema, command, credential, service publication, or operational transaction is included.

Work Order and Job Package V1 references locked approved proposal versions and converts their operations into roles, prerequisites, phases, checklists, inspections, metadata-only evidence, a recorded implementation overlay, conformance, post-work QA and trace verification, closeout, and an immutable receipt. Baseline, approved-plan, and recorded-implementation states remain separate. Work-order release and closeout do not modify the canonical graph or prove external implementation.

## Frontend

The frontend is a Next.js TypeScript application using the App Router, ESLint, CSS modules, and the ArcGIS Maps SDK for JavaScript. The initial UI is a non-production dashboard shell with demo placeholders only.

## Backend

The backend is a FastAPI application exposing intake, source-to-canonical mapping review, canonical asset, Connectivity QA, QA calibration, read-only Network Trace, trace-calibration, Proposed Edit, and Work Order APIs. Mapping plans, field and value mappings, safe preview receipts, immutable mapping history, the canonical asset registry, QA evidence, issue groups, immutable trace records, proposal evidence, work-order records, and separate interpretations share one external application database while real GIS data remains outside Git.

Network Trace reuses the canonical connectivity graph instead of maintaining a second topology. Vertical profiles provide Electric, Telecom, Water, and Wastewater semantics over one deterministic traversal engine. A separate calibration layer groups and scopes immutable trace evidence without rewriting it. Water and Wastewater traces remain topology/connectivity analysis, not hydraulic simulation. See `network-trace-engine.md`, `network-trace-calibration.md`, and `water-wastewater-domain-v1.md`.

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
