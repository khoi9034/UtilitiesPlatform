# Intake Status Model

Submission status describes the package lifecycle:

- `queued`: selected in the browser, not yet sent in local mode.
- `uploading`: streaming to local temporary storage.
- `validating`: checksum and package validation are running.
- `duplicate_detected`: SHA-256 matched an existing Raw submission; no new Raw copy is created unless explicitly registered as a version.
- `registered_raw`: immutable Raw storage and manifest were created.
- `inventory_pending`: inventory has not been run.
- `inventory_running`: inventory is operating on inspection files only.
- `inventory_complete`: safe inventory report exists.
- `review_required`: classification or staging requires human decision.
- `failed`: processing stopped safely.

These statuses do not imply staging approval. `staging_status` remains `not_approved` until a future explicit review workflow approves staging.
