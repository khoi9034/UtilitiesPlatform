"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { isDemoMode } from "../../lib/data-provider/provider";
import { getUtilityVertical, utilityVerticals, utilityViewPath, type UtilityVerticalConfig, type UtilityVerticalId, type UtilityWorkspaceView } from "../../lib/utility-verticals";
import { UtilityAssetsWorkspace } from "../utility-assets/UtilityAssetsWorkspace";
import { ConnectivityQAWorkspace } from "../connectivity-qa/ConnectivityQAWorkspace";
import { NetworkTraceWorkspace } from "../network-trace/NetworkTraceWorkspace";
import styles from "./utility-workspaces.module.css";

export function UtilitiesLanding() {
  return (
    <div className={styles.landing}>
      <header className={styles.landingHeader}>
        <span>UtilitiesPlatform</span>
        <h1>Utilities Operations Platform</h1>
        <p>Choose a utility network to inspect assets, review data quality, manage source lineage, and prepare controlled GIS workflows.</p>
      </header>
      <div className={styles.selectionGrid} aria-label="Utility workspaces">
        {utilityVerticals.map((vertical) => <VerticalCard key={vertical.id} vertical={vertical} />)}
      </div>
      <p className={styles.sharedNote}>One vendor-neutral canonical core. Separate operational context for each utility network.</p>
      {isDemoMode ? <DemoNotice /> : null}
    </div>
  );
}

function VerticalCard({ vertical }: { vertical: UtilityVerticalConfig }) {
  return (
    <Link
      className={`${styles.selectionCard} ${styles[vertical.id]}`}
      data-utility={vertical.id}
      href={vertical.routeBase}
      aria-label={`Open ${vertical.title} workspace`}
    >
      <span className={styles.cardIcon} aria-hidden="true"><calcite-icon icon={vertical.icon} scale="l" /></span>
      <div className={styles.cardCopy}>
        <span className={styles.cardLabel}>Utility workspace</span>
        <h2>{vertical.title}</h2>
        <p>{vertical.cardDescription}</p>
      </div>
      <ul className={styles.capabilities}>
        {vertical.capabilities.map((capability) => <li key={capability}>{capability}</li>)}
      </ul>
      <strong className={styles.cardAction}>Open {vertical.shortTitle} Workspace <calcite-icon icon="arrowRight" scale="s" aria-hidden="true" /></strong>
    </Link>
  );
}

export function UtilityVerticalWorkspace({ verticalId, view }: { verticalId: UtilityVerticalId; view: UtilityWorkspaceView }) {
  const searchParams = useSearchParams();
  const vertical = getUtilityVertical(verticalId)!;
  const assetId = searchParams.get("asset_id") ?? "";

  return (
    <div className={`${styles.workspace} ${styles[vertical.id]}`} data-utility={vertical.id}>
      <header className={styles.workspaceHeader}>
        <div className={styles.workspaceIdentity}>
          <span className={styles.workspaceIcon} aria-hidden="true"><calcite-icon icon={vertical.icon} scale="m" /></span>
          <div>
            <span>{isDemoMode ? "PORTFOLIO DEMO" : "LOCAL FASTAPI WORKSPACE"}</span>
            <h1>{vertical.title}</h1>
            <p>{vertical.description}</p>
          </div>
        </div>
        <nav className={styles.switcher} aria-label="Switch utility workspace">
          <Link href="/utilities">All utilities</Link>
          {utilityVerticals.map((item) => (
            <Link key={item.id} href={item.routeBase} aria-current={item.id === vertical.id ? "page" : undefined}>
              {item.shortTitle}
            </Link>
          ))}
        </nav>
      </header>
      {isDemoMode ? <DemoNotice /> : null}
      <nav className={styles.workspaceNav} aria-label={`${vertical.title} workspace`}>
        {vertical.navigation.map((item) => (
          <Link
            key={item.view}
            href={utilityViewPath(vertical, item.view)}
            aria-current={item.view === view ? "page" : undefined}
          >
            {item.view === "assets" ? `${vertical.shortTitle} Assets` : item.view === "relationships" ? `${vertical.shortTitle} Relationships` : item.label}
          </Link>
        ))}
      </nav>
      {view === "connectivity-qa" ? (
        <ConnectivityQAWorkspace config={vertical} />
      ) : view === "network-trace" ? (
        <NetworkTraceWorkspace config={vertical} />
      ) : (
        <UtilityAssetsWorkspace
          detailAssetId={assetId}
          routeBase={vertical.routeBase}
          vertical={vertical.canonicalValue}
          view={view}
        />
      )}
    </div>
  );
}

function DemoNotice() {
  return (
    <div className={styles.demoNotice} role="status">
      All utility assets, relationships, QA findings, trace evidence, and calibrated trace results in this demo are synthetic and reset with the demo session.
    </div>
  );
}
