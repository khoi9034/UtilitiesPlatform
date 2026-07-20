import { ModuleReadiness } from "../../components/readiness/ModuleReadiness";

export default function CadIntakePage() {
  return (
    <ModuleReadiness
      eyebrow="Integrate · CAD & As-Built Intake"
      title="CAD & As-Built Intake"
      subtitle="Controlled intake architecture for CAD, as-builts, PDFs, and project records. Upload processing is not enabled until a backend intake endpoint exists."
      status="Planned"
      purpose={["Receive approved CAD/as-built packages into external storage.", "Inventory drawing layers, coordinate context, and source lineage.", "Route accepted features into staging only after review."]}
      dependencies={["cad_storage_area", "drawing_layer_mapping", "project_records", "data_owner_approval"]}
      milestones={["Create a safe package manifest endpoint.", "Add CAD layer preview and schema mapping.", "Connect accepted packages to the Trust Pipeline."]}
      related={[{ label: "Trust Pipeline", href: "/trust-pipeline", description: "Review lifecycle gates." }, { label: "Data Sources", href: "/data-sources", description: "Storage and catalog state." }]}
      disabledAction="Upload unavailable"
    />
  );
}
