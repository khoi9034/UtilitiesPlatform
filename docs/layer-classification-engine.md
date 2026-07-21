# Layer Classification Engine

Layer classification is deterministic candidate generation, not an authoritative classifier. Rules live in `config/taxonomy/utility_layer_rules_v1.json`.

Evidence may include layer name, alias, feature dataset, schema prefix, fields, field aliases, domains, subtypes, geometry type, spatial reference, source owner, and package metadata. The engine emits ranked candidates with utility system, network group, asset category, asset subcategory, operational role, lifecycle representation, owner or jurisdiction signal, confidence, score, evidence, warnings, and limitations.

Confidence states:

- `high`: ready for classification review, still not approved for staging.
- `medium`: needs taxonomy review.
- `low`: needs source-owner or data-owner confirmation.
- `unavailable`: no configured rule matched safely.

Ambiguous names such as `WaterLine` can produce both water-main and hydrography candidates. The reviewer must use field evidence and data-owner confirmation before staging.
