# Layer Taxonomy

Universal source inspection uses a reusable hierarchy:

```text
utility_system
network_group
asset_category
asset_subcategory
```

Supported utility systems include `water`, `wastewater`, `stormwater`, `telecom`, `electric`, `gas`, `shared_reference`, `environmental_regulatory`, `planning_reference`, `unknown`, `review_required`, and `out_of_scope`.

Package-level intake may also use `mixed`. A mixed package means the source container spans multiple systems or business domains; each child layer still receives its own classification candidates.

Owner or jurisdiction is separate from taxonomy. Names such as Town, regional agency, or health agency are review signals, not authoritative ownership proof.

Lifecycle representation is also separate and may be `existing`, `proposed`, `final_as_built`, `planned`, `abandoned`, `retired`, or `unknown`.
