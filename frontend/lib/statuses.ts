export const workflowStatuses = ["open", "assigned", "in_review", "decision_recorded", "resolved", "reopened", "deferred"];

export const dispositions = [
  "unreviewed",
  "under_review",
  "confirmed_defect",
  "likely_defect",
  "false_positive",
  "source_data_limitation",
  "expected_condition",
  "missing_dependent_data",
  "needs_field_verification",
  "needs_engineering_review",
  "deferred",
  "resolved",
];

export function severityTone(value = "") {
  if (value === "high") return "danger";
  if (value === "medium") return "warning";
  if (value === "low") return "success";
  return "info";
}

export function stageTone(value = "") {
  if (value === "complete") return "success";
  if (value === "in_progress" || value === "active") return "info";
  if (value === "blocked") return "danger";
  if (value === "pending") return "warning";
  return "neutral";
}
