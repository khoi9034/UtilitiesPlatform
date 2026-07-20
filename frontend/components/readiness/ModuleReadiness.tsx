import Link from "next/link";
import { label } from "../../lib/formatters";
import { EmptyState, Panel, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./module-readiness.module.css";

export function ModuleReadiness({
  eyebrow,
  title,
  subtitle,
  status,
  purpose,
  dependencies,
  milestones,
  related,
  disabledAction,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  status: string;
  purpose: string[];
  dependencies: string[];
  milestones: string[];
  related: { label: string; href: string; description: string }[];
  disabledAction?: string;
}) {
  return (
    <div className={ws.workspace}>
      <header className={ws.pageHeader}>
        <span className={ws.eyebrow}>{eyebrow}</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
        <StatusBadge value={status} />
      </header>
      <section className={styles.layout}>
        <Panel title="Module Purpose" description="Honest readiness state with no fabricated operational records.">
          <ul className={styles.checklist}>
            {purpose.map((item) => <li key={item}>{item}</li>)}
          </ul>
          {disabledAction ? <button className={styles.disabledAction} disabled>{disabledAction}</button> : null}
        </Panel>
        <Panel title="Required Dependent Data" description="Data needed before this module can become operational.">
          {dependencies.length ? (
            <ul className={styles.checklist}>
              {dependencies.map((item) => <li key={item}><strong>{label(item)}</strong><span>Not onboarded or awaiting validation.</span></li>)}
            </ul>
          ) : <EmptyState title="No dependencies listed" message="This foundation page has no additional dependency catalog yet." />}
        </Panel>
      </section>
      <section className={styles.layout}>
        <Panel title="Next Implementation Milestones" description="Planned work, not current production capability.">
          <ul className={styles.checklist}>
            {milestones.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </Panel>
        <Panel title="Related Active Workspaces" description="Use the available modules for current wastewater review.">
          <div className={styles.linkGrid}>
            {related.map((item) => <Link className={styles.docLink} href={item.href} key={item.href}><strong>{item.label}</strong><span>{item.description}</span></Link>)}
          </div>
        </Panel>
      </section>
    </div>
  );
}
