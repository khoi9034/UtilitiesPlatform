import styles from "./page.module.css";

const navigation = [
  "Overview",
  "Asset Inventory",
  "Data Quality",
  "CAD Intake",
  "Network Intelligence",
  "Projects",
  "Maintenance",
  "Data Sources",
  "Methodology",
];

const metrics = [
  "Total Assets",
  "Network Mileage",
  "Open QA Issues",
  "Pending CAD Submissions",
  "Active Projects",
  "Assets Requiring Review",
];

export default function Home() {
  return (
    <main className={styles.shell}>
      <aside className={styles.sidebar} aria-label="Application sections">
        <div className={styles.brand}>
          <span className={styles.brandMark}>UP</span>
          <span>Utilities Platform</span>
        </div>
        <nav className={styles.nav}>
          {navigation.map((item) => (
            <a key={item} href="#overview">
              {item}
            </a>
          ))}
        </nav>
      </aside>

      <section className={styles.workspace} id="overview">
        <header className={styles.header}>
          <p className={styles.kicker}>Foundation dashboard</p>
          <h1>Utilities Intelligence Platform</h1>
          <p>
            Asset, network, construction, and data-quality intelligence for
            modern utility operations.
          </p>
        </header>

        <section className={styles.metrics} aria-label="Platform metrics">
          {metrics.map((metric) => (
            <article className={styles.metric} key={metric}>
              <span>{metric}</span>
              <strong>Not connected</strong>
              <p>Demo placeholder. No production utility data is loaded.</p>
            </article>
          ))}
        </section>

        <section className={styles.panels}>
          <div className={styles.mapPanel}>
            <div>
              <span>GIS map panel</span>
              <p>Utility map will appear after GIS data is configured.</p>
            </div>
          </div>

          <div className={styles.statusPanel}>
            <h2>Platform Status</h2>
            <dl>
              <div>
                <dt>Database</dt>
                <dd>PostGIS connection pending</dd>
              </div>
              <div>
                <dt>GIS intake</dt>
                <dd>Schema and mapping templates ready</dd>
              </div>
              <div>
                <dt>Production data</dt>
                <dd>Not included</dd>
              </div>
            </dl>
          </div>
        </section>
      </section>
    </main>
  );
}
