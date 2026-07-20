import { ModuleReadiness } from "../../components/readiness/ModuleReadiness";

export default function MaintenancePage() {
  return (
    <ModuleReadiness
      eyebrow="Manage · Maintenance"
      title="Maintenance"
      subtitle="Maintenance and inspection intelligence will be added after approved work orders, inspections, and repair records are available."
      status="Planned"
      purpose={["Prepare asset-health context for reviewed utility features.", "Relate inspections and repairs to standardized assets.", "Surface operational gaps without exposing raw source records."]}
      dependencies={["inspection_records", "repair_records", "work_orders", "standardized_assets"]}
      milestones={["Define inspection and work-order intake schemas.", "Create safe maintenance summary APIs.", "Link maintenance history to curated assets after approval."]}
      related={[{ label: "Asset Inventory", href: "/asset-inventory", description: "Current safe asset list." }, { label: "Network Intelligence", href: "/network-intelligence", description: "Connectivity review context." }]}
    />
  );
}
