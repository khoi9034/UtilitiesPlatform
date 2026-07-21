import type { Issue } from "../api-types";

const key = "utilities-platform-demo-reviews";

type ReviewPatch = Partial<Issue>;
type ReviewMap = Record<string, ReviewPatch>;

function read(): ReviewMap {
  if (typeof sessionStorage === "undefined") return {};
  try {
    return JSON.parse(sessionStorage.getItem(key) ?? "{}") as ReviewMap;
  } catch {
    return {};
  }
}

function write(reviews: ReviewMap) {
  if (typeof sessionStorage !== "undefined") sessionStorage.setItem(key, JSON.stringify(reviews));
}

export function applyDemoReview(issue: Issue): Issue {
  const patch = read()[issue.issue_id];
  return patch ? { ...issue, ...patch, review_status: patch.workflow_status ?? patch.review_status ?? issue.review_status } : issue;
}

export function updateDemoIssue(issue: Issue, update: ReviewPatch): Issue {
  const reviews = read();
  reviews[issue.issue_id] = { ...reviews[issue.issue_id], ...update };
  write(reviews);
  return applyDemoReview(issue);
}

export function batchUpdateDemoIssues(issues: Issue[], issueIds: string[], update: ReviewPatch) {
  const byId = new Set(issueIds);
  const reviews = read();
  const updated = issues.filter((issue) => byId.has(issue.issue_id)).map((issue) => issue.issue_id);
  for (const issueId of updated) reviews[issueId] = { ...reviews[issueId], ...update };
  write(reviews);
  return { updated_count: updated.length, updated_issue_ids: updated, missing_issue_ids: issueIds.filter((issueId) => !updated.includes(issueId)) };
}

export function resetDemoSession() {
  if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(key);
}
