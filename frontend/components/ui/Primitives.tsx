import type { ReactNode } from "react";
import styles from "./workspace.module.css";
import { label } from "../../lib/formatters";
import { stageTone, severityTone } from "../../lib/statuses";

export function PageHeader({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle: string }) {
  return (
    <header className={styles.pageHeader}>
      <span className={styles.eyebrow}>{eyebrow}</span>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
  );
}

export function Panel({ title, description, children, action }: { title: string; description?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeader}>
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function MetricTile({ labelText, value, detail }: { labelText: string; value: string; detail: string }) {
  return (
    <article className={styles.metric}>
      <span>{labelText}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

export function StatusBadge({ value, tone }: { value: string; tone?: string }) {
  const className = tone === "danger" || tone === "warning" || tone === "success" || tone === "info" ? `${styles.badge} ${styles[tone]}` : styles.badge;
  return <span className={className}>{label(value)}</span>;
}

export function SeverityBadge({ value }: { value: string }) {
  return <StatusBadge value={value} tone={severityTone(value)} />;
}

export function StageBadge({ value }: { value: string }) {
  return <StatusBadge value={value} tone={stageTone(value)} />;
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className={styles.emptyState}>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}

export function OfflineState({ service }: { service: string }) {
  return <div className={styles.offlineState} role="status"><h3>{service} unavailable</h3><p>Keep the workspace open and retry after the FastAPI service is running. Real values are not replaced with zeros.</p></div>;
}

export function LoadingSkeleton() {
  return <div className={styles.skeleton} aria-label="Loading" />;
}

export { styles as workspaceStyles };
