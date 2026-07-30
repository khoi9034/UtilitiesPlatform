# Water & Wastewater Source-to-Canonical Mapping Review V1

Water & Wastewater Source-to-Canonical Mapping Review V1 prepares reviewed mapping plans and preview records. It does not create canonical assets, approve staging, alter source geometry, infer unsupported flow or elevation values, or publish utility data.

## Workflow

```text
Stored source-inspection evidence
-> domain and source-role review
-> canonical class review
-> field mapping
-> value mapping
-> geometry and coordinate review
-> owner, jurisdiction, sensitivity, and duplicate gates
-> safe preview
-> human mapping-plan approval
-> blocked pending final staging approval
```

Plans are created only by an explicit request. Recommendation generation does not approve a plan, approve staging, create an asset, create a relationship, change source data, or change staged data.

## Persistence

The existing external application registry contains five additive tables:

- `source_canonical_mapping_plans`: versioned domain, role, target class, fingerprints, gate states, warnings, blockers, and approval metadata.
- `source_canonical_field_mappings`: deterministic source-to-canonical field transformations.
- `source_canonical_value_mappings`: reviewed safe coded-value normalization.
- `source_canonical_preview_runs`: aggregate-only preview receipts and counts.
- `source_canonical_mapping_history`: append-only plan, mapping, version, and review events.

The source fingerprint covers stored submission and layer evidence. A changed fingerprint marks the plan `stale_source` and blocks approval or future creation. New versions supersede the prior plan without deleting its history.

## Plan States

The workflow supports:

- `draft`
- `recommendations_ready`
- `needs_domain_review`
- `needs_taxonomy_review`
- `needs_field_mapping`
- `needs_value_mapping`
- `needs_owner_confirmation`
- `needs_jurisdiction_confirmation`
- `needs_coordinate_review`
- `needs_sensitivity_review`
- `duplicate_review_required`
- `staging_blocked`
- `review_ready`
- `under_review`
- `approved_plan`
- `deferred`
- `rejected`
- `superseded`
- `stale_source`
- `archived`

`approved_plan` means a human reviewed the mapping. It does not authorize staging or asset creation.

## Source Roles

Allowlisted roles are:

- `operational_inventory`
- `reference_inventory`
- `facility_inventory`
- `network_context`
- `service_area`
- `boundary`
- `planning_context`
- `historical`
- `deprecated`
- `unknown`

Only operational inventory and reviewed facility inventory can be candidates for a future operational asset-creation phase. Reference, boundary, planning, historical, deprecated, and unknown roles remain blocked.

## Recommendations

Recommendations combine stored safe evidence when available:

- normalized source name and alias
- geometry type
- field names and aliases
- domain and subtype summaries
- automated-review decisions
- taxonomy candidates
- lifecycle, material, diameter, and elevation signals
- related-layer context

Results contain the recommended domain, alternative domains, class candidates, confidence, evidence categories, contradictions, geometry compatibility, source role, and reviewer requirement. Ambiguous Water/Wastewater and multi-utility layers are not automatically classified.

Wastewater polylines are conservative. Geometry alone cannot distinguish gravity main, force main, pressure sewer, service lateral, or an unknown wastewater line. Flow direction, invert values, rim elevations, slope, gravity status, and pressure status are never invented.

## Field Mapping

Shared canonical targets include identity, names, class and subtype, lifecycle and operational state, owner and jurisdiction, source identifiers, dates, sensitivity, notes, source attributes, canonical attributes, geometry summary, and evidence.

Water targets include system, main, service, valve, hydrant, meter, facility, pressure-zone, diameter, material, placement, facility type, owner, and jurisdiction fields.

Wastewater targets include system, basin, gravity-main, force-main, lateral, manhole, lift-station, facility, outfall, node, diameter, material, elevation, slope, flow, status, owner, and jurisdiction fields.

Each value remains labeled as source-provided, normalized, inferred, human-confirmed, or unmapped. Source values are preserved.

Allowed transformations are:

- `direct`
- `renamed`
- `normalized_identifier`
- `normalized_text`
- `numeric_parse`
- `unit_conversion`
- `boolean_mapping`
- `lifecycle_mapping`
- `operational_status_mapping`
- `domain_mapping`
- `subtype_mapping`
- `date_parse`
- `null_normalization`
- `safe_constant`
- `inferred_with_review`
- `unmapped`

Python, SQL, shell commands, executable expressions, arbitrary formulas, external URLs, and source-provided scripts are rejected.

## Value Normalization

Material normalization uses a fixed allowlist including cast iron, ductile iron, PVC, HDPE, concrete, reinforced concrete, clay, steel, copper, asbestos cement, other, and unknown. Original text remains evidence.

Diameter parsing records the source value, parsed number, source unit, target unit, conversion, confidence, warning, and review state. Missing unit evidence remains `unknown`; the service does not assume inches or millimeters.

Lifecycle and operational mappings remain separate. Unknown or conflicting coded values require review instead of being forced into a canonical state.

## Geometry And Coordinates

Compatibility compares stored source geometry metadata with the selected canonical class. This review cannot define a projection, project geometry, repair geometry, snap endpoints, reverse lines, or write any geometry.

Coordinate, sensitivity, duplicate, owner, and jurisdiction decisions are independent gates. Provisional owner or jurisdiction candidates are never presented as authoritative.

## Preview And Eligibility

Restricted local sources use aggregate-only preview. The service reads no source records for that preview and returns no paths, raw coordinates, unrestricted attributes, or geometry. Synthetic demo plans may show three synthetic preview rows.

Every preview states:

```text
Preview only - no canonical asset has been created.
```

Eligibility reports independent gates for domain, taxonomy, source role, field mapping, value mapping, geometry, coordinates, sensitivity, duplicate review, owner, jurisdiction, staging, and source freshness.

Real Water/Wastewater creation requires every gate, an approved current mapping plan, final staging approval, and a separate explicit human creation action. Mapping Review V1 intentionally provides no such action. The existing generic endpoint rejects real Water/Wastewater creation even after plan review.

## APIs

Global safe discovery:

- `GET /api/utility-assets/water-wastewater/mapping-candidates`
- `GET /api/utility-assets/mapping-plans`

Submission and layer review:

- `GET /api/intake/submissions/{submission_id}/water-wastewater/mapping-candidates`
- `GET /api/intake/submissions/{submission_id}/layers/{layer_id}/mapping-recommendations`
- `POST|GET /api/intake/submissions/{submission_id}/layers/{layer_id}/mapping-plan`
- `POST .../mapping-plan/new-version`
- `POST .../mapping-plan/recalculate`
- `GET|PUT .../mapping-plan/fields`
- `GET|PUT .../mapping-plan/values`
- `POST|GET .../mapping-plan/preview`
- `POST .../mapping-plan/submit`
- `POST .../mapping-plan/start-review`
- `POST .../mapping-plan/approve`
- `POST .../mapping-plan/request-revision`
- `POST .../mapping-plan/defer`
- `POST .../mapping-plan/reject`
- `GET .../canonicalization-eligibility`
- `GET .../mapping-plan/safe-summary`

Responses omit filesystem paths, credentials, connection strings, raw records, and raw coordinates.

## Frontend And Demo

The workspace is:

```text
http://localhost:3001/utilities/water-wastewater/mapping-plans
```

It provides candidate filters, the eleven-step persisted review workflow, field and value edits, geometry and ownership review, safe preview, eligibility gates, workflow actions, and immutable history. Canonical creation is visible only as a disabled command with the missing gate.

The public demo contains eight deterministic synthetic plans: four Water and four Wastewater. It includes owner, coordinate, unmapped endpoint, invert-unit, gravity-versus-force-main, and jurisdiction review examples. All edits and approvals use `sessionStorage`, reset with the demo session, and make no backend requests.

## Next Phase

The next development phase is Controlled Staging Approval and Canonical Asset Creation V1. It must require explicit final staging approval, deterministic IDs, preserved lineage, duplicate prevention, explicit relationship evidence, immediate Water/Wastewater QA, supported topology traces, and rollback-safe immutable history. It is not implemented here.
