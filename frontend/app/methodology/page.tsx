import { Panel, workspaceStyles as ws } from "../../components/ui/Primitives";
import styles from "../../components/readiness/module-readiness.module.css";

const docs = [
  ["Source inspection", "docs/source-inspection-architecture.md", "Mixed-package child-layer inspection and review architecture."],
  ["Layer classification rules", "docs/layer-classification-engine.md", "Deterministic taxonomy candidates, confidence, evidence, and limitations."],
  ["Layer taxonomy", "docs/layer-taxonomy.md", "Utility system, network group, category, subcategory, role, and lifecycle vocabulary."],
  ["Duplicate layer review", "docs/duplicate-layer-review.md", "Potential duplicate and alternate-layer review without automatic authority selection."],
  ["Coordinate review", "docs/coordinate-review.md", "Spatial-reference statuses and source-preserving inspection limits."],
  ["Staging approval", "docs/staging-approval-workflow.md", "Explicit child-layer approval gates before source-preserving staging."],
  ["QA methodology", "docs/qa-calibration.md", "Why QA findings are candidates until reviewed."],
  ["Network methodology", "docs/wastewater-network-methodology.md", "Proximity graph limits and component review."],
  ["Review workflow", "docs/human-review-workflow.md", "Disposition, workflow, history, and calibration."],
  ["Standardization readiness", "docs/wastewater-standardization-preview.md", "Preview schema and mapping approval rules."],
  ["Trust pipeline", "docs/trust-pipeline.md", "Lifecycle gates from raw source to export."],
  ["Data governance", "docs/data-governance.md", "Sensitive data handling and approvals."],
  ["Security", "docs/security-and-sensitive-data.md", "Repository and local data safety."],
];

export default function MethodologyPage() {
  return (
    <div className={ws.workspace}>
      <header className={ws.pageHeader}>
        <span className={ws.eyebrow}>Govern · Methodology</span>
        <h1>Methodology</h1>
        <p>Documentation hub for utility QA, network review, standardization readiness, trust pipeline, governance, and secure local data handling.</p>
      </header>
      <Panel title="Documentation Hub" description="Repository docs are linked as source references for the platform workflow.">
        <div className={styles.linkGrid}>
          {docs.map(([title, href, description]) => <a className={styles.docLink} href={`https://github.com/khoi9034/UtilitiesPlatform/blob/main/${href}`} key={href}><strong>{title}</strong><span>{description}</span></a>)}
        </div>
      </Panel>
    </div>
  );
}
