import type { Icon } from "@esri/calcite-components/components/calcite-icon/customElement";

export type UtilityVerticalId = "electric" | "telecom" | "water-wastewater";
export type CanonicalUtilityVertical = "electric_distribution" | "telecom_fiber" | "water" | "wastewater";
export type UtilityWorkspaceView =
  | "overview"
  | "assets"
  | "relationships"
  | "source-data"
  | "canonicalization"
  | "data-quality"
  | "connectivity-qa"
  | "network-trace"
  | "proposed-edits"
  | "work-orders"
  | "review-history";

export type UtilityVerticalConfig = {
  id: UtilityVerticalId;
  canonicalValue: CanonicalUtilityVertical;
  canonicalValues?: CanonicalUtilityVertical[];
  title: string;
  shortTitle: string;
  description: string;
  cardDescription: string;
  icon: Icon["icon"];
  routeBase: string;
  capabilities: string[];
  operationalFocus: string[];
  navigation: Array<{ view: UtilityWorkspaceView; label: string }>;
  futureModules: string[];
};

const sharedNavigation: UtilityVerticalConfig["navigation"] = [
  { view: "overview", label: "Overview" },
  { view: "assets", label: "Assets" },
  { view: "relationships", label: "Relationships" },
  { view: "source-data", label: "Source Data" },
  { view: "canonicalization", label: "Canonicalization" },
  { view: "data-quality", label: "Data Quality" },
  { view: "connectivity-qa", label: "Connectivity QA" },
  { view: "network-trace", label: "Network Trace" },
  { view: "proposed-edits", label: "Proposed Edits" },
  { view: "work-orders", label: "Work Orders" },
  { view: "review-history", label: "Review History" },
];

export const utilityVerticals: UtilityVerticalConfig[] = [
  {
    id: "electric",
    canonicalValue: "electric_distribution",
    title: "Electric Distribution",
    shortTitle: "Electric",
    description: "Distribution asset, feeder relationship, equipment status, and controlled electric GIS workflow readiness.",
    cardDescription: "Inspect distribution assets, feeder relationships, equipment status, network readiness, and proposed electric GIS workflows.",
    icon: "switch",
    routeBase: "/utilities/electric",
    capabilities: ["Feeders and circuits", "Devices and transformers", "Poles and conductors", "Connectivity readiness"],
    operationalFocus: ["Substations and feeders", "Protective devices", "Transformers", "Poles and conductors", "Conduit and service relationships"],
    navigation: sharedNavigation,
    futureModules: ["Implementation Verification enhancements", "Network Snapshots", "Vendor Integrations"],
  },
  {
    id: "telecom",
    canonicalValue: "telecom_fiber",
    title: "Telecom/Fiber",
    shortTitle: "Telecom",
    description: "Fiber asset, route, structure, capacity, splice relationship, and controlled construction workflow readiness.",
    cardDescription: "Inspect fiber assets, routes, structures, capacity, splice relationships, and proposed telecom GIS workflows.",
    icon: "nodesLink",
    routeBase: "/utilities/telecom",
    capabilities: ["Fiber routes and cables", "Cabinets and terminals", "Splices and structures", "Capacity readiness"],
    operationalFocus: ["Network hubs and cabinets", "Fiber routes and cables", "Poles and conduit", "Splice closures", "Splitters and terminals", "Capacity and construction status"],
    navigation: sharedNavigation,
    futureModules: ["Construction Workflow enhancements", "Network Snapshots", "Vendor Integrations"],
  },
  {
    id: "water-wastewater",
    canonicalValue: "water",
    canonicalValues: ["water", "wastewater"],
    title: "Water & Wastewater",
    shortTitle: "Water & Wastewater",
    description: "Vendor-neutral water distribution and wastewater collection asset readiness, QA, topology tracing, and controlled work planning.",
    cardDescription: "Review water and wastewater sources, network assets, topology evidence, proposed changes, and controlled job workflows.",
    icon: "utilityNetwork",
    routeBase: "/utilities/water-wastewater",
    capabilities: ["Water distribution", "Wastewater collection", "Topology QA", "Controlled work planning"],
    operationalFocus: ["Mains and services", "Valves and hydrants", "Gravity and force mains", "Manholes and lift stations", "Facilities and system context"],
    navigation: sharedNavigation,
    futureModules: ["Hydraulic model adapters", "Inspection integrations", "Vendor integrations"],
  },
];

export function getUtilityVertical(id: string) {
  return utilityVerticals.find((vertical) => vertical.id === id);
}

export function getUtilityVerticalByCanonical(vertical: CanonicalUtilityVertical) {
  return utilityVerticals.find((item) => item.canonicalValues?.includes(vertical) || item.canonicalValue === vertical);
}

export function utilityVerticalFromPath(pathname: string) {
  return utilityVerticals.find((vertical) => pathname === vertical.routeBase || pathname.startsWith(`${vertical.routeBase}/`));
}

export function utilityViewPath(
  vertical: UtilityVerticalConfig,
  view: UtilityWorkspaceView,
  params: Record<string, string> = {},
) {
  const path = view === "overview" ? vertical.routeBase : `${vertical.routeBase}/${view}`;
  const query = new URLSearchParams(params);
  if (vertical.id === "water-wastewater" && vertical.canonicalValue === "wastewater") query.set("system", "wastewater");
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}
