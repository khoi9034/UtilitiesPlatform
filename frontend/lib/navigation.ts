import type { Icon } from "@esri/calcite-components/components/calcite-icon/customElement";

type CalciteIconName = Icon["icon"];

export type ModuleStatus = "Active" | "Foundation ready" | "Not onboarded" | "Planned";

export type NavigationItem = {
  label: string;
  href: string;
  icon: CalciteIconName;
  group: "OPERATE" | "INTEGRATE" | "MANAGE" | "GOVERN";
  status: ModuleStatus;
  description: string;
};

export const navigationItems: NavigationItem[] = [
  { label: "Command Center", href: "/", icon: "dashboard", group: "OPERATE", status: "Active", description: "Aggregate operating picture." },
  { label: "Asset Inventory", href: "/asset-inventory", icon: "layers", group: "OPERATE", status: "Foundation ready", description: "Safe utility asset inventory." },
  { label: "Data Health", href: "/data-health", icon: "checkShield", group: "OPERATE", status: "Active", description: "QA review and calibration." },
  { label: "Network Intelligence", href: "/network-intelligence", icon: "utilityNetworkTrace", group: "OPERATE", status: "Foundation ready", description: "Proximity connectivity analysis." },
  { label: "CAD & As-Built Intake", href: "/cad-intake", icon: "fileData", group: "INTEGRATE", status: "Planned", description: "Controlled CAD intake workflow." },
  { label: "Trust Pipeline", href: "/trust-pipeline", icon: "dataClockChart", group: "INTEGRATE", status: "Active", description: "Lifecycle gates and readiness." },
  { label: "Data Sources", href: "/data-sources", icon: "dataFolder", group: "INTEGRATE", status: "Active", description: "Catalog, storage, and inventory." },
  { label: "Projects", href: "/projects", icon: "folderOpen", group: "MANAGE", status: "Planned", description: "Project and delivery context." },
  { label: "Maintenance", href: "/maintenance", icon: "wrench", group: "MANAGE", status: "Planned", description: "Maintenance and inspection readiness." },
  { label: "Methodology", href: "/methodology", icon: "book", group: "GOVERN", status: "Foundation ready", description: "Methodology and governance docs." },
];

export function activeNavigationItem(pathname: string) {
  return navigationItems
    .filter((item) => item.href === "/" ? pathname === "/" : pathname.startsWith(item.href))
    .sort((a, b) => b.href.length - a.href.length)[0] ?? navigationItems[0];
}
