# Connectivity QA Engine V1

## Purpose and Boundary

Connectivity QA Engine V1 evaluates canonical Electric Distribution and Telecom/Fiber assets before future tracing, editing, and vendor integration. It identifies review candidates from safe canonical attributes and explicit stored relationships.

It is not a network trace engine, ArcFM implementation, GE Smallworld implementation, Esri Utility Network, or telecom inventory system. It does not infer authoritative flow, snap or repair geometry, modify source or staged records, publish services, or call proprietary software.

## Shared Graph Model

One graph model supports both utility verticals. Canonical assets are graph nodes and `utility_asset_relationships` records are graph edges. Nodes retain safe identity, class, subtype, lifecycle, operational state, canonical attributes, and lineage references. Edges retain relationship type, direction, confidence, source, provisional state, and evidence.

Only explicit stored relationships enter the graph. A spatially inferred or rule-inferred relationship can participate when it has already been persisted, but its provisional and evidence fields remain visible. Crossings, coordinate proximity, and digitized line direction do not create hidden edges.

Run fingerprints hash the selected utility vertical, normalized canonical asset inputs, normalized relationship inputs, graph-model version, rule version, and profile name. An unchanged graph reuses its completed run unless the operator explicitly requests a forced rerun. Forced reruns create new immutable run records. Finding fingerprints remain stable for the same rule and evidence, allowing review decisions to follow recurring findings.

## Rule Profiles

Built-in profiles are:

- `electric_distribution_v1`
- `telecom_fiber_v1`

Both execute `SHARED-001` through `SHARED-008`. Electric executes `ELEC-001` through `ELEC-015`; telecom executes `TEL-001` through `TEL-016`.

Definitions are allowlisted Python structures with code, name, category, severity, blocking state, scope, description, action, limitation, and version. APIs do not accept executable rules, Python, SQL, shell commands, external URLs, or source-provided expressions.

Each rule runs independently. A rule error is stored as a blocked rule execution and produces no network finding. Other rules continue, and the run becomes `partially_failed`. Findings use `info`, `warning`, `error`, or `critical`; rule execution separately uses `passed`, `warning`, `failed`, `blocked`, or `skipped`.

## Persistence and Review

SQLite tables in the existing local application registry store:

- `connectivity_qa_runs`
- `connectivity_qa_rule_runs`
- `connectivity_qa_findings`
- `connectivity_qa_history`

Review states are `open`, `acknowledged`, `deferred`, `accepted_risk`, `resolved_externally`, `false_positive`, and `superseded`. A reviewer identity is required for every action. Defer, accepted-risk, and false-positive decisions require a rationale. Every transition creates immutable history and never changes an asset, relationship, source file, or staged geometry.

## APIs

Rule catalog:

- `GET /api/connectivity-qa/rules`
- `GET /api/connectivity-qa/rules/{utility_vertical}`

Runs and summaries:

- `POST /api/connectivity-qa/{utility_vertical}/runs`
- `GET /api/connectivity-qa/{utility_vertical}/status`
- `GET /api/connectivity-qa/{utility_vertical}/runs`
- `GET /api/connectivity-qa/{utility_vertical}/runs/{qa_run_id}`
- `GET /api/connectivity-qa/{utility_vertical}/summary`

Findings:

- `GET /api/connectivity-qa/{utility_vertical}/findings`
- `GET /api/connectivity-qa/{utility_vertical}/findings/{finding_id}`
- `POST /api/connectivity-qa/{utility_vertical}/findings/{finding_id}/acknowledge`
- `POST /api/connectivity-qa/{utility_vertical}/findings/{finding_id}/defer`
- `POST /api/connectivity-qa/{utility_vertical}/findings/{finding_id}/accept-risk`
- `POST /api/connectivity-qa/{utility_vertical}/findings/{finding_id}/mark-false-positive`
- `POST /api/connectivity-qa/{utility_vertical}/findings/{finding_id}/reopen`

Finding lists filter by severity, blocking status, review status, rule code, asset class, asset ID, and run ID. Responses contain safe canonical identifiers and logical graph context; they exclude local paths, connection strings, source records, raw geometry, customer data, and subscriber data.

## Local and Demo Operation

Local mode calls FastAPI and persists runs, findings, reviews, and history in the application registry outside Git. The pages are:

- `http://localhost:3001/utilities/electric/connectivity-qa`
- `http://localhost:3001/utilities/telecom/connectivity-qa`

Static demo mode uses deterministic synthetic assets and relationships. It derives findings in the browser, persists runs and review decisions in `sessionStorage`, supports refresh and safe JSON summary downloads, and makes no backend requests. It contains no real utility infrastructure or local metadata.

## Integration Boundaries

Future ArcFM, Smallworld, Esri Utility Network, and telecom inventory adapters should translate vendor records into the canonical asset and relationship model. They must preserve source evidence and vendor identifiers, label provisional relationships, and remain outside the shared rule engine. V1 does not include a proprietary client or copied vendor interface.

The next product phase is Network Trace Engine V1 for Electric Distribution and Telecom/Fiber. That future engine can consume only reviewed canonical relationships and must honor operational states such as normally open devices without turning QA candidates into automatic edits.
