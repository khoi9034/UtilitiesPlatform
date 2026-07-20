import { ModuleReadiness } from "../../components/readiness/ModuleReadiness";

export default function ProjectsPage() {
  return (
    <ModuleReadiness
      eyebrow="Manage · Projects"
      title="Projects"
      subtitle="Project context will connect design packages, work orders, source documents, and accepted utility changes after those records are onboarded."
      status="Planned"
      purpose={["Track source project lineage for utility changes.", "Connect as-built packages to affected assets.", "Support review handoffs from QA to project owners."]}
      dependencies={["project_records", "work_orders", "as_built_packages", "source_document_ids"]}
      milestones={["Define safe project catalog schema.", "Add project-to-asset relationship review.", "Connect project history to standardized assets after approval."]}
      related={[{ label: "CAD & As-Built Intake", href: "/cad-intake", description: "Future project package intake." }, { label: "Data Health", href: "/data-health", description: "Current wastewater QA review." }]}
    />
  );
}
