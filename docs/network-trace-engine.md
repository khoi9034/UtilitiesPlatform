# Network Trace Engine V1

## Proposed Overlay Reuse

Proposed Edit Workspace V1 calls the same read-only trace and trace-calibration functions against a fixed baseline and a sparse temporary overlay. Comparison uses calibrated outcome, confidence, objective status, comparison key, path signature, branch signature, reachable assets, and path-specific blockers.

Proposal trace runs are isolated analytical evidence. They do not mutate immutable active trace runs, operate devices, allocate capacity, or claim authoritative topology.

Work Order and Job Package V1 invokes the same trace engine against a recorded implementation overlay and compares baseline, approved-plan, and recorded outcomes, confidence, objectives, path signatures, and branch signatures. Work-order traces are stored separately and cannot rewrite original or proposal trace evidence.

## Boundary

UtilitiesPlatform Network Trace V1 performs read-only analytical traversal of the platform's vendor-neutral canonical asset and relationship model. It is not an operational ArcFM, Smallworld, Esri Utility Network, outage-management, engineering, or telecom-provisioning trace.

Network Trace Calibration and Result Triage V1 now derives a separate concise interpretation from each immutable run. It groups repeated QA references, scopes warnings to selected paths or background context, distinguishes normal branches from competing authoritative alternatives, and preserves both original and calibrated outcomes and confidence. See `network-trace-calibration.md`.

The engine does not switch equipment, allocate fiber, infer customer outages, repair topology, edit source or staged geometry, publish a service, or call a proprietary utility system. It has no official affiliation with Pike, TDS Telecom, ArcFM, Schneider Electric, GE, Smallworld, Esri, or a telecom-system vendor.

## Shared Architecture

One engine serves Electric Distribution and Telecom/Fiber:

1. Validate an allowlisted request.
2. Read canonical assets and explicit relationships.
3. load the latest applicable Connectivity QA and calibration evidence.
4. Fingerprint the graph, QA state, calibration state, profile, and options.
5. Reuse an unchanged result unless recalculation is explicitly forced.
6. Apply the vertical trace profile.
7. Traverse with stable relationship and path ordering.
8. Record exclusions, warnings, blockers, paths, steps, events, confidence, and history.

The engine reuses `canonical-connectivity-graph-v1` from Connectivity QA. It does not maintain a second topology. V1 uses bounded in-process traversal because the current synthetic graph is small; a larger registry should add indexed graph storage only when measured scale requires it.

Local evidence is stored in the existing external application registry:

- `network_trace_runs`
- `network_trace_paths`
- `network_trace_steps`
- `network_trace_events`
- `network_trace_history`

Historical rows are appended, not rewritten. A forced run creates a new run. An unchanged non-forced request reopens the existing result.

## Relationship Semantics

Relationship types are classified before traversal:

| Category | Examples | V1 behavior |
|---|---|---|
| Operational flow | `feeds`, `upstream_of`, `downstream_of`, `served_by` | Traversable when allowed by the vertical profile |
| Operational connection | `connects_to`, `spliced_to`, `terminates_at`, `protected_by` | Traversable when allowed by the profile |
| Membership context | `belongs_to_feeder`, `belongs_to_circuit`, `belongs_to_route` | Used only by a compatible membership analysis |
| Containment context | `contained_in`, `routed_through` | Reported as context; never converted into power or signal flow |
| Support context | `mounted_on` | Not operational continuity |
| Historical context | `replaces`, `retires` | Not active continuity |
| Reference context | `reference_for`, work-order associations | Not operational continuity |
| Prohibited cross-vertical | Electric-to-telecom operational links | Stopped and reported |

A pole does not conduct power because equipment is mounted on it. Conduit does not establish electrical or fiber continuity. A service-area polygon is not a network node. Handholes and manholes can appear on a represented route, but they do not establish a splice without explicit evidence.

## Electric Profiles

Electric V1 includes:

- `ELEC-TRACE-001`: feeder downstream
- `ELEC-TRACE-002`: asset upstream
- `ELEC-TRACE-003`: nearest upstream protective-device candidate
- `ELEC-TRACE-004`: analytical isolation
- `ELEC-TRACE-005`: transformer service
- `ELEC-TRACE-006`: feeder membership
- `ELEC-TRACE-007`: trace to source

Operational classes include substations, feeders, breakers, conductors, switches, fuses, reclosers, transformers, junctions, secondary conductors, and service points. Poles, conduit, attachments, and reference boundaries are excluded from energized flow.

Open and normally open devices stop downstream traversal under `respect_state`. Closed devices permit represented traversal. Unknown state lowers confidence. Active-only mode excludes retired, removed, and inactive assets. Phase transitions require compatible represented phase evidence. Unexplained voltage changes stop or warn according to policy; a represented transformer can carry a voltage transition. This is not protection coordination, load flow, switching analysis, or an outage prediction.

## Telecom Profiles

Telecom/Fiber V1 includes:

- `TEL-TRACE-001`: hub to terminal
- `TEL-TRACE-002`: terminal upstream
- `TEL-TRACE-003`: cable route
- `TEL-TRACE-004`: splice sequence
- `TEL-TRACE-005`: cabinet downstream
- `TEL-TRACE-006`: affected network
- `TEL-TRACE-007`: capacity path
- `TEL-TRACE-008`: proposed construction continuity

Operational classes include network hubs, cabinets, routes, cables, represented structures, splice closures, splitters, terminals, and proposed segments when requested. Poles and conduit remain support or containment context. Retired cables are excluded in active-only mode. Proposed segments require `include_proposed`. Missing cable endpoints stop the affected represented direction. Capacity and strand values are reported and checked; the engine never reserves capacity, allocates strands, or predicts subscriber impact.

## QA And Calibration

Trace V1 consumes immutable technical findings from `connectivity-qa-rules-v2` and the latest active calibration groups:

- `stops_trace`: stops strict and conservative traversal unless the group was accepted as risk; diagnostic mode continues with a warning.
- `limits_trace`: stops strict traversal and warns or limits conservative traversal.
- `introduces_ambiguity`: evaluates bounded alternatives and reports ambiguity only when evidence cannot select a defensible path.
- `advisory`: continues with a warning.
- `no_trace_effect`: records no interruption.
- `not_evaluated`: continues only on explicit evidence and lowers confidence.

Tracing never changes QA findings, issue groups, or review decisions. A false-positive or superseded group does not block. Accepted risk remains visible as warning context.

## Policies And Outcomes

Requests allow only documented values for direction, lifecycle mode, operational mode, provisional policy, and QA policy. They reject paths, URLs, SQL, Python, shell commands, expressions, and external rule files. Maximum depth and visited-asset limits prevent runaway traversal. Cycle candidates are recorded and skipped. Results use:

- `complete`
- `complete_with_warnings`
- `partial`
- `blocked`
- `no_path`
- `ambiguous`
- `failed_safely`

Confidence is separate from completeness: `high`, `medium`, `low`, or `indeterminate`. It describes canonical evidence quality, not engineering certainty.

Provisional policy is explicit:

- `exclude`: do not use provisional edges.
- `include_with_warning`: use and label them.
- `require_when_only_path`: use a provisional edge only when no confirmed candidate exists.

## Fingerprints

The input fingerprint covers the utility vertical, asset and relationship checksums, canonical graph version, Connectivity QA version and run, calibration version and groups, trace profile version, lifecycle policy, provisional policy, and QA policy.

The request fingerprint separately covers start, optional target, trace type, direction, selected options, and safe limits. Stable ordering makes reruns and path ranking deterministic. A changed graph, QA run, calibration, profile, or option creates new immutable evidence.

## APIs

- `GET /api/network-trace/types`
- `GET /api/network-trace/types/{utility_vertical}`
- `POST /api/network-trace/{utility_vertical}/runs`
- `GET /api/network-trace/{utility_vertical}/status`
- `GET /api/network-trace/{utility_vertical}/runs`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}/paths`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}/steps`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}/events`
- `GET /api/network-trace/{utility_vertical}/runs/{trace_run_id}/safe-summary`
- `GET /api/network-trace/assets/{asset_id}/readiness`

Responses expose safe canonical identifiers, represented operational state, allowlisted context, issue-group references, and analytical decisions. They exclude filesystem paths, raw geometry, restricted source attributes, credentials, customer or subscriber data, and proprietary records.

## Synthetic Demo

The public demo runs entirely in the browser. It uses committed synthetic asset definitions, deterministic synthetic relationships, calibrated synthetic QA candidates, and `sessionStorage` trace history. It makes no FastAPI request. Refresh restores a result by URL and session state; resetting the demo session removes it.

Eight same-membership explicit synthetic relationships were added for trace coverage without removing intentional defects or changing the calibrated QA baseline. They create represented operational paths around support-only nodes while preserving the disconnected conductor, open switch, missing feeder, missing conduit, missing cable endpoint, provisional splice, capacity conflict, strand overlap, proposed gap, and retired-to-active candidates. The expectation manifest is `config/network_trace_synthetic_expectations.json`.

## Future Adapter Boundary

A future licensed-system adapter may translate approved vendor objects and network records into canonical assets and relationships, invoke the same read-only trace request, and translate safe results back to an approved integration contract. It must remain outside the engine, preserve vendor identifiers and source evidence, and never make inferred relationships authoritative.

`Vendor record -> approved adapter mapping -> canonical asset/relationship -> Connectivity QA -> calibration -> Network Trace -> human interpretation`

The current flow extends through a separate read-only trace interpretation:

`Network Trace immutable evidence -> trace calibration -> human triage -> future proposed-edit comparison`

Calibration never updates the canonical graph or the evidence tables documented above.

No proprietary connector, dependency, logo, interface copy, or vendor service call is included in V1.
