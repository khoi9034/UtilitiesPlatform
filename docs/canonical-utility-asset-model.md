# Canonical Utility Asset Model V1

## Purpose

Canonical Utility Asset Model V1 provides one vendor-neutral asset foundation for electric distribution and telecom/fiber. It models concepts used by enterprise utility GIS without copying ArcFM, GE Smallworld, or telecom inventory interfaces and without requiring their licenses.

This phase does not implement network tracing, source edits, staged edits, publishing, or proprietary adapters.

## Shared Core

Every asset carries a canonical identity, vertical and class taxonomy, geometry summary, separate lifecycle and operational states, owner status, source lineage, QA and review states, sensitivity, confidence, timestamps, notes, and JSON evidence.

Source attributes, canonical attributes, geometry summaries, and evidence remain separate. Evidence identifies whether a value is:

- source-provided
- normalized
- inferred
- human-confirmed

Canonicalization never overwrites source evidence.

Electric and telecom use the same `canonical_utility_assets`, `utility_asset_relationships`, plan, mapping, and immutable-history tables. Their extension attributes live in `canonical_attributes_json` under allowlisted profiles. The safe schema profile is `config/schemas/canonical_utility_asset_v1.json`.

## Relationships

Relationships are first-class records rather than overloaded asset columns. Each relationship stores direction, confidence, source, provisional state, evidence, and optional confirmation metadata.

Valid evidence sources are source-provided, spatially inferred, rule-inferred, and human-confirmed. Inferred relationships are never presented as authoritative.

## Canonicalization Workflow

1. Review the source layer.
2. Approve it separately for staging.
3. Select a utility vertical and canonical asset class.
4. Review deterministic field mappings.
5. Review safe record previews.
6. Resolve geometry, lifecycle, identifier, and attribute blockers.
7. Save the plan.
8. Record explicit human approval.
9. Run the separate create-assets action.

`approved_for_canonicalization` defaults to false. An approved staging plan does not imply canonicalization approval. Creation checks the stored source fingerprint, rejects changed metadata, uses deterministic asset IDs, prevents duplicates, and writes immutable history. It does not modify source or staged geometry and does not publish a service.

Only allowlisted transformations are accepted. SQL, Python, shell commands, executable expressions, external URLs, and source-provided rule files are rejected.

## Current Real Submission

The current reviewed submission is not eligible for canonicalization because human source-review and staging blockers remain unresolved. No plan or canonical asset is created automatically, and existing review decisions remain unchanged.

## Synthetic Electric Network

The local application registry and portfolio demo include a fully synthetic electric distribution network with:

- one substation, two feeders, and two feeder breakers
- switches, fuses, one recloser, and eight transformers
- twenty poles, overhead and underground conductors
- conduits, service points, junctions, attachments, structures, and a reference boundary

Intentional future-QA candidates include a disconnected conductor, missing transformer feeder ID, invalid phase combination, missing underground-conduit association, a normally open switch, a provisional relationship, and a retired asset related to active infrastructure.

No customer names, addresses, accounts, or personally identifiable information are present.

## Synthetic Telecom/Fiber Network

The synthetic telecom network includes a hub, two cabinets, three routes, four cables, poles, conduit, handholes, a manhole, splice closures, splitters, terminals, one proposed construction segment, structures, and a service-area boundary.

Intentional future-QA candidates include a missing cable endpoint, strand-range overlap, capacity inconsistency, provisional splice connection, proposed route gap, and a retired cable related to an active terminal.

No subscriber, customer, address, account, or service-order data are present.

## Demo Boundary

Static demo assets are generated from committed deterministic synthetic definitions. Plan approval and asset-creation simulations use `sessionStorage` only and reset with the demo session. Demo mode makes no backend requests.

## Future Adapters

Future ArcFM, Smallworld, and telecom inventory adapters should translate through canonical plans and relationship evidence. They must preserve source identifiers, enforce source fingerprints, and keep vendor-specific schemas outside the shared domain. Connectivity QA now evaluates explicit relationships as review candidates, but no relationship should be treated as authoritative topology. See `docs/connectivity-qa-engine.md`.

Connectivity QA Calibration adds vendor-neutral issue groups after technical finding generation. Canonical rule categories, conceptual external mapping statuses, and vendor-equivalent hints prepare an adapter boundary without importing proprietary libraries, schemas, object classes, rule IDs, versioning behavior, or interfaces.

UtilitiesPlatform currently uses its own vendor-neutral canonical asset and relationship model. Future licensed-system integrations will require organization-specific adapters and mappings. Current vendor-equivalent hints are conceptual only.
