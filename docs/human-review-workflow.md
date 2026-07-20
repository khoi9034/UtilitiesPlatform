# Human Review Workflow

Human review separates workflow state from technical disposition.

Workflow statuses:

- `open`
- `assigned`
- `in_review`
- `decision_recorded`
- `resolved`
- `reopened`
- `deferred`

Dispositions:

- `unreviewed`
- `under_review`
- `confirmed_defect`
- `likely_defect`
- `false_positive`
- `source_data_limitation`
- `expected_condition`
- `missing_dependent_data`
- `needs_field_verification`
- `needs_engineering_review`
- `deferred`
- `resolved`

Review decisions update only local review metadata. They never edit raw files, staged GIS features, QA issue geometry, standardized data, or curated data.

Production deployment must add authentication and identity-based audit logging. The local SQLite review store is for controlled local review and calibration.
