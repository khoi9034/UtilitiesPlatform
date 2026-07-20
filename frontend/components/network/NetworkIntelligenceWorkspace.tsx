"use client";

import { useEffect, useState } from "react";
import type { CommandCenterResponse, ComponentRow, NetworkResponse } from "../../lib/api-types";
import { fetchJson } from "../../lib/api-client";
import { compactNumber, label, percent, safeText } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, Panel, StageBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./network-intelligence.module.css";

export function NetworkIntelligenceWorkspace() {
  const [command, setCommand] = useState<CommandCenterResponse | null>(null);
  const [network, setNetwork] = useState<NetworkResponse | null>(null);
  const [components, setComponents] = useState<ComponentRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchJson<CommandCenterResponse>("/api/platform/command-center?utility_system=wastewater", controller.signal),
      fetchJson<NetworkResponse>("/api/data-health/wastewater/network", controller.signal),
      fetchJson<{ items: ComponentRow[] }>("/api/data-health/wastewater/components?limit=100", controller.signal),
    ])
      .then(([commandData, networkData, componentData]) => {
        setCommand(commandData);
        setNetwork(networkData);
        setComponents(componentData.items ?? []);
      })
      .catch(() => setError("Network Intelligence API is unavailable."));
    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <OfflineState service="Network Intelligence API" />
      </div>
    );
  }

  if (!command || !network) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <div className={ws.workspace}>
      <PageIntro />
      <section className={ws.grid12}>
        <div className={ws.span3}><MetricTile labelText="Endpoint match" value={percent(command.network.endpoint_match_rate)} detail={`${compactNumber(command.network.unmatched_endpoints)} unmatched endpoint(s).`} /></div>
        <div className={ws.span3}><MetricTile labelText="Components" value={compactNumber(command.network.connected_components)} detail="Proximity graph groups." /></div>
        <div className={ws.span3}><MetricTile labelText="Isolated pipes" value={compactNumber(command.network.isolated_pipes)} detail="Candidate isolated segments." /></div>
        <div className={ws.span3}><MetricTile labelText="Isolated manholes" value={compactNumber(command.network.isolated_manholes)} detail="Candidate isolated structures." /></div>
      </section>
      <section className={styles.componentLayout}>
        <Panel title="Component Analysis" description="Component rows are review candidates and may reflect source coverage or missing dependent layers.">
          {components.length ? (
            <div className={ws.tableWrap}>
              <table className={ws.table}>
                <thead><tr><th>ID</th><th>Assets</th><th>Pipes</th><th>Manholes</th><th>Length</th><th>Unmatched</th><th>Nearest</th><th>Likely classification</th><th>Review status</th></tr></thead>
                <tbody>{components.map((component) => <tr key={component.component_id}><td className="technical">{component.component_id}</td><td>{component.total_asset_count}</td><td>{component.pipe_count}</td><td>{component.manhole_count}</td><td>{compactNumber(component.approximate_network_length)}</td><td>{component.unmatched_endpoints}</td><td>{safeText(component.nearest_other_component_distance)}</td><td>{label(component.likely_classification)}</td><td><StageBadge value={component.review_classification || component.review_status} /></td></tr>)}</tbody>
              </table>
            </div>
          ) : <EmptyState title="No components" message="No component report is available from the safe API." />}
        </Panel>
        <Panel title="Methodology Limits" description="This module is a topology proxy for onboarding review.">
          <ul className={styles.limitations}>
            {(network.limitations.length ? network.limitations : [
              "Proximity-based connectivity only.",
              "Not authoritative topology or an ArcGIS Utility Network.",
              "Crossings do not automatically mean connectivity.",
            ]).map((item) => <li key={item}>{item}</li>)}
            <li>Force mains, lift stations, services, and private/external networks are not yet onboarded.</li>
          </ul>
        </Panel>
      </section>
    </div>
  );
}

function PageIntro() {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>Utilities · Wastewater</span>
      <h1>Network Intelligence</h1>
      <p>Proximity-based connectivity analysis for staged wastewater mains and manholes. It is a review aid, not authoritative utility topology.</p>
    </header>
  );
}
