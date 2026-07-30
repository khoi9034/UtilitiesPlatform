import { notFound } from "next/navigation";
import { Suspense } from "react";
import { UtilityVerticalWorkspace } from "../../../../components/utility-workspaces/UtilityWorkspaces";
import { getUtilityVertical, utilityVerticals, type UtilityVerticalId, type UtilityWorkspaceView } from "../../../../lib/utility-verticals";

export function generateStaticParams() {
  return utilityVerticals.flatMap(({ id: vertical, navigation }) => [
    { vertical, view: [] },
    ...navigation.filter(({ view }) => view !== "overview").map(({ view }) => ({ vertical, view: [view] })),
  ]);
}

export const dynamicParams = false;

export default async function UtilityWorkspacePage({ params }: { params: Promise<{ vertical: string; view?: string[] }> }) {
  const route = await params;
  const vertical = getUtilityVertical(route.vertical);
  const view = route.view?.[0] ?? "overview";
  if (!vertical || route.view?.length && route.view.length > 1 || !vertical.navigation.some((item) => item.view === view)) notFound();
  return (
    <Suspense fallback={null}>
      <UtilityVerticalWorkspace verticalId={vertical.id as UtilityVerticalId} view={view as UtilityWorkspaceView} />
    </Suspense>
  );
}
