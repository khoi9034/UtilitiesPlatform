import { notFound } from "next/navigation";
import { Suspense } from "react";
import { UtilityVerticalWorkspace } from "../../../../components/utility-workspaces/UtilityWorkspaces";
import { getUtilityVertical, type UtilityVerticalId, type UtilityWorkspaceView } from "../../../../lib/utility-verticals";

const views: UtilityWorkspaceView[] = ["overview", "assets", "relationships", "source-data", "canonicalization", "data-quality", "connectivity-qa", "network-trace", "proposed-edits", "review-history"];

export function generateStaticParams() {
  return ["electric", "telecom"].flatMap((vertical) => [
    { vertical, view: [] },
    ...views.filter((view) => view !== "overview").map((view) => ({ vertical, view: [view] })),
  ]);
}

export const dynamicParams = false;

export default async function UtilityWorkspacePage({ params }: { params: Promise<{ vertical: string; view?: string[] }> }) {
  const route = await params;
  const vertical = getUtilityVertical(route.vertical);
  const view = route.view?.[0] ?? "overview";
  if (!vertical || route.view?.length && route.view.length > 1 || !views.includes(view as UtilityWorkspaceView)) notFound();
  return (
    <Suspense fallback={null}>
      <UtilityVerticalWorkspace verticalId={vertical.id as UtilityVerticalId} view={view as UtilityWorkspaceView} />
    </Suspense>
  );
}
