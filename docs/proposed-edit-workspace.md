# Proposed Edit Workspace V1

UtilitiesPlatform Proposed Edit Workspace V1 creates isolated vendor-neutral change plans and evaluates them against temporary network overlays. Approval confirms the plan for future implementation review; it does not modify an operational utility GIS, execute switching, allocate telecom capacity, or apply changes to ArcFM, Smallworld, Esri Utility Network, or another proprietary system.

## Scope

The shared proposal engine supports Electric Distribution and Telecom/Fiber. It stores proposal metadata and operations once, then applies vertical-specific field, lifecycle, operational-state, relationship, phase, voltage, strand, capacity, and containment validation.

The workspace does not edit canonical, source, staged, QA, or trace records; edit geometry; create GIS feature classes; execute switching or provisioning; publish a service; invoke a vendor SDK; or create an executable implementation payload.

## Lifecycle And Versions

The primary lifecycle is:

`draft -> ready_for_analysis -> analysis_complete -> submitted_for_review -> under_review -> approved`

Failure and preservation states include `validation_failed`, `needs_revision`, `rejected`, `deferred`, `withdrawn`, `superseded`, `implementation_ready`, `implementation_exported`, and `archived`.

Proposal lifecycle, operation validation, analysis, review, approval, and implementation readiness are separate fields. `approved` means the plan was approved; it never means implemented.

Submitted and approved versions are locked. Changes require a new immutable version or clone. Earlier operations, comparisons, reviews, and history remain available.

## Operations

Operations use a fixed allowlist for asset additions, safe attribute overrides, lifecycle and operational-state proposals, relationship changes, provisional confirmation, feeder or route assignment, containment, structure association, explicit retirement, replacement, notes, and manual investigation.

The API rejects arbitrary fields, transformations, scripts, expressions, SQL, shell commands, paths, URLs, vendor commands, and credentials.

Proposed additions receive deterministic proposal-local identifiers. They remain noncanonical and nonoperational after approval. Replacement plans require explicit relationship changes and an explicit retirement operation; relationships are not transferred automatically.

## Fixed Baseline

Each proposal captures fingerprints for canonical assets, canonical relationships, Connectivity QA, QA calibration, trace profiles, and trace calibration. Validation compares that baseline with the current registry.

A changed graph or rule baseline produces `stale_baseline` and analysis stops. Users can clone or version a proposal against the current baseline without overwriting original evidence.

## Isolated Overlay

The overlay is sparse. Unchanged records remain baseline references; assets are copied only in memory when overridden; temporary assets exist only in proposal analysis; and relationship changes are represented in the effective state. Changes are labeled `modified`, `added`, `removed`, `replaced`, `provisional`, or `confirmed_in_proposal`.

The deterministic overlay fingerprint covers the effective changes. No GIS or canonical write occurs.

## QA And Trace Comparison

The existing pure Connectivity QA and calibration functions run against baseline and overlay graphs. Comparison reports resolved, unchanged, new, improved, and worsened issue groups plus blocker and warning deltas. Original QA evidence is unchanged.

The existing Network Trace and trace-calibration functions run against both states for the selected trace scenario. Comparison reports outcome, objective, confidence, reachable assets, blockers, path signature, branch signature, and an `improved`, `unchanged`, `worsened`, `mixed`, or `incomparable` result. Original trace evidence is unchanged.

## Review And Approval

Review roles are `proposal_author`, `technical_reviewer`, `data_steward`, `final_approver`, and `system`. The local application records safe reviewer metadata but does not replace production authentication.

Approval requires passed validation, completed analysis, a current baseline, a nonempty operation list, QA evidence, required trace comparisons, reviewer identity, and explicit acknowledgement of new blockers. The author is not automatically the final approver outside the labeled synthetic demo.

Every operation, workflow action, review, version change, analysis, and package creation appends immutable history.

## Safe Implementation Package

An approved plan can generate vendor-neutral JSON containing proposal and version identifiers, fingerprints, approval metadata, ordered safe operations, QA and trace summaries, readiness, mapping states, and required adapter capabilities.

The package excludes geometry, paths, credentials, connection strings, restricted source attributes, customer or subscriber information, proprietary objects, executable scripts, SQL, and vendor transactions. `executable` is always `false`.

A future adapter needs licensed-system access, organization-specific schema mapping, permissions, approvals, and utility validation. No ArcFM, Smallworld, Esri Utility Network, or telecom platform client is present.

## Runtime

Frontend routes:

- `/utilities/electric/proposed-edits`
- `/utilities/telecom/proposed-edits`

Catalog and workflow APIs begin at `/api/proposed-edits`. Local mode uses FastAPI and the external application registry. Demo mode uses synthetic `sessionStorage` state and makes no backend request.

## Work Order Boundary

Work Order and Job Package V1 can reference an approved locked proposal and convert its operations into a separate versioned job checklist. A work order cannot mutate proposal operations. Changed field evidence requires an exception plus a revised or superseding proposal.

Approval remains plan approval; release remains synthetic workflow release; recorded implementation remains an isolated overlay. See `work-order-job-package.md`.
