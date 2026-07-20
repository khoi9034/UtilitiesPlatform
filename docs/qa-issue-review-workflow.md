# QA Issue Review Workflow

QA issues are generated as review candidates. They are not automatic edits.

Allowed review statuses:

- `open`
- `under_review`
- `confirmed_issue`
- `false_positive`
- `needs_field_verification`
- `needs_engineering_review`
- `resolved`
- `deferred`

The API route:

```text
PATCH /api/data-health/wastewater/issues/{issue_id}
```

may update only:

- `review_status`
- `reviewer`
- `resolution_notes`

Review updates are stored in a separate review CSV under QA reports. Updating a QA issue does not edit raw data, staged feature classes, or QA geometry.

Production use requires authentication, authorization, and audit logging before review updates are accepted from multiple users.
