# Staging Approval Workflow

Inspection creates a proposed staging plan, but every item defaults to not approved.

A layer may only stage when:

- inspection completed
- classification review is approved
- coordinate status is acceptable for source-preserving staging
- duplicate status is resolved
- sensitivity review is complete
- owner or jurisdiction uncertainty is resolved or documented
- target name is valid
- approved for staging is explicitly true
- reviewer and review timestamp exist

Staging is source-preserving. It must not project, repair geometry, rename source fields, translate domains, merge owners, merge utilities, combine duplicates, standardize, or curate records.
