# Connectivity QA Engine V1

## Proposed Overlay Reuse

Proposed Edit Workspace V1 calls the same pure graph builder, rule evaluator, and deterministic issue-group calibration against baseline and proposal-overlay state. Proposal QA findings and comparisons are stored in proposal-specific tables. Active QA runs and technical findings are never overwritten, reviewed, or downgraded by proposal analysis.

Resolved counts are candidates for human review. A lower total does not offset a newly introduced critical blocker.

## Purpose and Boundary

Connectivity QA Engine V1 evaluates canonical Electric Distribution and Telecom/Fiber assets before future tracing, editing, and vendor integration. It identifies review candidates from safe canonical attributes and explicit stored relationships.

Network Trace Calibration consumes exact issue groups referenced by the immutable trace run. It may classify a group as path-specific, branch-specific, background, excluded, or unrelated for that one trace objective. This does not alter the QA finding, issue group, technical severity, blocking state, trace impact, or review history.

It does not itself traverse a requested path, implement ArcFM, GE Smallworld, Esri Utility Network, or a telecom inventory system. It does not infer authoritative flow, snap or repair geometry, modify source or staged records, publish services, or call proprietary software. Network Trace V1 consumes its immutable findings and calibrated trace-impact groups through the shared canonical graph; QA remains a separate evidence-producing stage.

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

## Calibration and Root-Cause Triage

Connectivity QA Calibration V1 preserves every raw technical finding and creates a separate human-facing issue-group layer. A group has one primary root-cause candidate plus contributing, consequence, corroborating, informational, or independent members. Every member remains available with its original rule, severity, blocking state, evidence, and review history.

Grouping is deterministic. It uses the QA run, stable finding fingerprints, exact affected assets and relationships, allowlisted rule dependencies, corrective-action families, and root-cause precedence. It never groups by title similarity, invokes an external model, or accepts executable rules.

Technical severity and technical blocking remain unchanged. Separate fields describe:

- workflow priority: `immediate`, `high`, `normal`, `low`, or `informational`
- future trace impact: `stops_trace`, `limits_trace`, `introduces_ambiguity`, `advisory`, `no_trace_effect`, or `not_evaluated`
- effective group blocking, derived without downgrading member findings

A normally open device therefore remains an informational technical condition with no independent trace defect. A missing endpoint remains a technical blocker and can become the primary issue above a disconnected-network consequence.

Calibration fingerprints include the QA run ID, technical finding fingerprints, dependency-map version, grouping version, priority version, and trace-impact version. Unchanged inputs reuse a completed calibration. Forced recalculation creates immutable run history, preserves compatible group review decisions, and marks obsolete memberships superseded.

Calibration records use:

- `connectivity_qa_calibration_runs`
- `connectivity_qa_issue_groups`
- `connectivity_qa_group_members`
- `connectivity_qa_calibration_history`

Group review actions identify and update only listed member review states, append both member and group history, and never modify technical evidence. A later member-level review recomputes the derived group state, including `mixed`, while preserving member history. Forced recalibration supersedes the prior active group row, retains it as immutable history, and leaves one active row per stable issue-group ID. The deterministic scenario manifest is `config/qa_rules/connectivity_synthetic_expectations_v1.json`; it validates intentional synthetic conditions but does not drive rule execution.

### Electric rule-scope calibration

`connectivity-qa-rules-v2` narrows `ELEC-009` and `ELEC-010` to active operational electric assets joined by connectivity or membership relationships. Poles, conduit, attachments, reference boundaries, retired contexts, containment edges, and reference edges no longer participate in feeder or circuit consistency checks. This preserves the original V1 run as immutable evidence while removing findings caused by evaluating non-energized context as network membership.

On the deterministic Electric fixture, no other rule changed:

| Rule | V1 findings | V2 findings | Reason |
|---|---:|---:|---|
| `ELEC-009` | 63 | 34 | Excluded non-operational classes, non-membership edges, and retired contexts |
| `ELEC-010` | 65 | 35 | Excluded non-operational classes, non-membership edges, and retired contexts |
| All other rules | 44 | 44 | Detection behavior unchanged |
| Total | 172 | 113 | Rule-scope correction only |

The V2 result retains 54 errors, 58 warnings, and 1 informational condition. Severity and blocking settings were not changed to obtain this reduction.

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

Calibration and issue groups:

- `POST /api/connectivity-qa/{utility_vertical}/runs/{qa_run_id}/calibrate`
- `GET /api/connectivity-qa/{utility_vertical}/calibration/status`
- `GET /api/connectivity-qa/{utility_vertical}/calibration/runs`
- `GET /api/connectivity-qa/{utility_vertical}/calibration/runs/{calibration_run_id}`
- `GET /api/connectivity-qa/{utility_vertical}/issue-groups`
- `GET /api/connectivity-qa/{utility_vertical}/issue-groups/{issue_group_id}`
- `POST /api/connectivity-qa/{utility_vertical}/issue-groups/{issue_group_id}/{review_action}`
- `GET /api/connectivity-qa/{utility_vertical}/calibrated-summary`

Finding lists filter by severity, blocking status, review status, rule code, asset class, asset ID, and run ID. Responses contain safe canonical identifiers and logical graph context; they exclude local paths, connection strings, source records, raw geometry, customer data, and subscriber data.

## Local and Demo Operation

Local mode calls FastAPI and persists runs, findings, reviews, and history in the application registry outside Git. The pages are:

- `http://localhost:3001/utilities/electric/connectivity-qa`
- `http://localhost:3001/utilities/telecom/connectivity-qa`

Static demo mode uses deterministic synthetic assets and relationships. It derives findings in the browser, persists runs and review decisions in `sessionStorage`, supports refresh and safe JSON summary downloads, and makes no backend requests. It contains no real utility infrastructure or local metadata.

The default QA view is **Actionable Issues**. **All Technical Findings** preserves transparent access to raw rule results. Safe calibrated summary downloads contain run IDs, versions, counts, distributions, safe canonical asset IDs, review states, and recommended actions; they exclude paths, geometry, restricted source attributes, customer or subscriber data, credentials, and connection strings.

## Integration Boundaries

Future ArcFM, Smallworld, Esri Utility Network, and telecom inventory adapters should translate vendor records into the canonical asset and relationship model. They must preserve source evidence and vendor identifiers, label provisional relationships, and remain outside the shared rule engine. V1 does not include a proprietary client or copied vendor interface.

The adapter boundary is:

`Vendor object or network record -> adapter mapping -> canonical asset or relationship -> technical QA finding -> calibrated issue group -> human review -> future trace or proposed edit`

Vendor-equivalent hints describe general utility GIS concepts only. They do not represent direct ArcFM, Smallworld, Esri Utility Network, or proprietary telecom-system integration.

UtilitiesPlatform currently uses its own vendor-neutral canonical asset and relationship model. Future licensed-system integrations will require organization-specific adapters and mappings. Current vendor-equivalent hints are conceptual only.

Network Trace Engine V1 is documented in `network-trace-engine.md`. It consumes explicit canonical relationships and calibrated issue groups, honors operational states such as normally open devices, and never turns a QA candidate into an automatic edit.
