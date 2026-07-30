# Work Order and Job Package V1

UtilitiesPlatform Work Order and Job Package V1 converts approved vendor-neutral proposed changes into structured synthetic job workflows. It records planning, review, evidence, validation, and closeout without modifying an operational utility GIS or executing work in ArcFM, Smallworld, Esri Utility Network, telecom inventory, field-service, outage-management, or work-management systems.

## Shared Model

Electric Distribution, Telecom/Fiber, Water, and Wastewater use one work-order model with vertical-specific work types and inspections. A work order stores independent overall, design, field-work, GIS-implementation, inspection, QA, trace, review, and closeout states. This prevents field completion from being mistaken for GIS recording, validation, or approved closeout.

The external application registry persists versioned work orders, role assignments, phases, ordered job steps, prerequisites, inspections, metadata-only evidence, implementation records, conformance runs, post-work QA, post-work traces, immutable history, safe packages, and completion receipts.

## Proposal Boundary

Operational jobs require an approved, nonstale Proposed Edit version. Proposed operations become ordered job steps but remain immutable. Excluding or changing an approved operation requires an exception and a revised or superseding Proposed Edit; the work order cannot rewrite the approved plan.

`manual_investigation` is the only work-order type that can start without a proposal. It carries no network-changing operations.

## Release Gates

Release requires:

- approved and current proposal evidence
- required technical reviewer and final approver assignments
- satisfied or explicitly waived prerequisites
- a defined operation checklist
- available QA and trace requirements
- explicit **Approve for Release**, followed by separate **Release Work**

The system rejects blocked replacement proposals and deliberately incomplete scenarios. `emergency_record_review` means urgent data review, not dispatch, switching, outage response, or field authority.

## Implementation Overlay

V1 records `simulated_overlay_only`. It reuses the Proposed Edit overlay engine to represent completed, skipped, and exception operations as a recorded implementation state separate from both the approved plan and the canonical network.

The comparison states are:

1. Baseline canonical state
2. Approved Proposed Edit overlay
3. Recorded implementation overlay

No source, staged, canonical, or GIS geometry is changed.

## Validation and Closeout

Conformance compares approved and recorded operation identities. The existing Connectivity QA and Network Trace engines run against the recorded implementation overlay and preserve separate work-order evidence. Closeout remains blocked when required steps or inspections are incomplete, implementation is nonconformant, QA or traces fail, or final approval is missing.

Approved closeout generates an immutable completion receipt. The receipt records the UtilitiesPlatform review workflow; it does not prove that a real operational utility system was updated without separate authorized external verification.

## Safe Evidence and Packages

Evidence accepts notes, confirmations, receipt references, checksums, and safe attachment metadata. It rejects local paths, URLs, executable attachments, scripts, commands, credentials, customer or subscriber data, and raw location metadata. Binary uploads are not implemented.

Job packages are structured JSON with `executable: false`. They contain proposal and work-order fingerprints, assignments, prerequisites, phases, ordered steps, inspections, QA and trace requirements, release approval, affected canonical identifiers, and required future adapter capabilities. They contain no geometry, scripts, SQL, connection strings, proprietary commands, or transactions.

## Runtime

- `/utilities/electric/work-orders`
- `/utilities/telecom/work-orders`
- `/utilities/water-wastewater/work-orders?system=water`
- `/utilities/water-wastewater/work-orders?system=wastewater`
- `/api/work-orders/types`
- `/api/work-orders/{utility_vertical}`

Local mode uses FastAPI and the external application registry. Static demo mode uses synthetic `sessionStorage` state, supports direct route refresh and reset, and makes no backend request.

Production deployment requires authentication, identity-based audit logging, approved vendor adapters, organization-specific schemas, and authorized external verification. No proprietary integration is implemented or implied.
