# Network Trace Calibration and Result Triage V1

## Purpose

Network Trace Calibration is a deterministic interpretation layer over an immutable Network Trace run. It answers whether the requested objective was reached, selects the first meaningful stopping condition, separates selected-path warnings from network background, distinguishes normal fan-out from true ambiguity, and records a safe next review action.

The original run, paths, steps, events, QA references, fingerprints, and receipt remain unchanged. A forced calibration creates a new immutable calibration run that supersedes the prior interpretation without overwriting it.

UtilitiesPlatform trace calibration interprets immutable vendor-neutral trace evidence for human review. It does not alter utility assets, repair connectivity, execute switching, allocate fiber capacity, predict outages, or reproduce proprietary utility-system traces.

## Deterministic Inputs

The calibration fingerprint covers:

- trace run and input fingerprints
- path, step, and event evidence
- referenced calibrated QA groups
- trace calibration version
- event-grouping version
- warning-relevance version
- branch-analysis version
- stopping-precedence version
- outcome-calibration version
- confidence-calibration version

An unchanged fingerprint reuses the existing result. `force_recalculate` creates a new run and immutable history while retaining deterministic result and event content.

The fixed allowlisted configuration is `config/network_trace/trace_calibration_v1.json`. APIs cannot upload configuration, executable mappings, SQL, Python, shell commands, filesystem paths, external URLs, credentials, or vendor schemas.

## Warning Scopes

`stopping_condition` directly stops all or part of the request. `path_specific` affects a selected returned path. `branch_specific` affects one returned branch. `start_asset_context` and `target_asset_context` identify endpoint eligibility or confidence evidence.

`network_background` is present in the loaded network without determining the selected path. `excluded_context` explains policy exclusions. `informational` records successful boundaries and useful context. `unrelated_to_selected_path` retains broad evidence with no material selected-path relationship.

Background and unrelated evidence remains inspectable but does not lower calibrated confidence by itself.

## Event Grouping

Repeated references to one calibrated QA issue group become one calibrated event. The event retains:

- all originating raw event IDs
- affected paths, assets, and relationships
- issue-group IDs
- repeated reference count
- first and last affected step
- strongest trace effect
- grouped recommended action

Independent defects are not merged solely because their text is similar. Non-QA events require a compatible category, cause, asset or relationship context, and action.

## Stopping Precedence

The versioned precedence starts with controlled execution failures, invalid starts, incompatible verticals, missing referenced endpoints, calibrated trace-stopping issues, open devices, endpoint failures, electrical or telecom compatibility conflicts, lifecycle exclusions, membership conflicts, ambiguity, missing relationships, traversal limits, and finally successful target, terminal, or source boundaries.

Precedence chooses the primary human-facing explanation only. Every raw stopping reason remains available. A successful requested path can coexist with a stopped secondary branch and remain `complete_with_warnings`.

## Branch Analysis

Normal branch fan-out is expected for feeder, transformer-service, cabinet, splitter, affected-network, and proposed-construction analyses. It does not create `ambiguous` by itself.

Ambiguity is reserved for trace types requiring one authoritative interpretation when evidence supports competing sources, routes, directions, terminations, memberships, or materially different provisional paths. The calibrated record stores normal and ambiguous counts, shared prefix, divergence step, competing paths, and supporting evidence.

## Outcomes And Confidence

Calibrated outcomes are `complete`, `complete_with_warnings`, `partial`, `blocked`, `no_path`, `ambiguous`, and `failed_safely`. The original outcome is always retained.

Confidence is based on selected-path evidence:

- `high`: objective reached on confirmed represented evidence with no material selected-path warning or ambiguity
- `medium`: objective reached with an advisory, provisional segment, optional evidence gap, or normal branching
- `low`: blocked, partial, or ambiguous evidence
- `indeterminate`: no meaningful path or controlled failure

Each result persists explanatory confidence and outcome factors instead of a hidden score.

## Persistence And APIs

The external application registry stores:

- `network_trace_calibration_runs`
- `network_trace_calibrated_results`
- `network_trace_calibrated_events`
- `network_trace_calibration_history`

Routes:

- `POST /api/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrate`
- `GET /api/network-trace/{utility_vertical}/calibration/status`
- `GET /api/network-trace/{utility_vertical}/calibration/runs`
- `GET /api/network-trace/{utility_vertical}/calibration/runs/{calibration_run_id}`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrated-result`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrated-events`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}/calibrated-safe-summary`

Calibrated-event filters are allowlisted for scope, category, priority, primary status, path, asset, relationship, and issue group.

## Proposed Edit Comparison Boundary

Calibration exposes stable comparison keys, path and branch signatures, objective state, reachable and unreachable asset sets, blocked path IDs, selected issue groups, confidence factors, and an allowlisted recommended edit category. These are read-only inputs for a future Proposed Edit Workspace. No edit workspace, temporary edit graph, change set, approval, or source-system write is implemented here.

## Vendor Adapter Boundary

Canonical trace categories, conceptual external mapping statuses, adapter-required flags, and general vendor-equivalent hints are metadata only. They do not import an SDK, call a vendor API, reproduce a proprietary schema, claim compatibility, or use production identifiers.

Vendor-equivalent hints describe general utility-network concepts only. Current traces are not direct ArcFM, Smallworld, Esri Utility Network, outage-management, or proprietary telecom traces.

## Demo

Static demo calibration runs entirely in the browser, persists synthetic runs in `sessionStorage`, generates receipts locally, and makes no backend request. Reset removes both raw trace and calibrated trace session keys.

All utility assets, relationships, QA findings, trace evidence, and calibrated trace results in this demo are synthetic and reset with the demo session.
