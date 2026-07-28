"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import { label } from "../../lib/formatters";
import type { ConnectivityFinding, ConnectivityIssueGroup } from "../../lib/connectivity-qa";
import type { AssetRelationship, CanonicalMapping, CanonicalizationPlan, UtilityAsset } from "../../lib/utility-assets";
import { getUtilityVertical, utilityViewPath, type UtilityVerticalConfig, type UtilityWorkspaceView } from "../../lib/utility-verticals";
import { EmptyState, LoadingSkeleton, MetricTile, OfflineState, PageHeader, Panel, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./utility-assets.module.css";

type AssetResponse = {
  items: UtilityAsset[];
  summary: {
    total_assets: number;
    electric_assets: number;
    telecom_assets: number;
    assets_needing_review: number;
    provisional_relationships: number;
    active_plans: number;
    approved_plans: number;
    blocked_plans: number;
    lifecycle_distribution: Record<string, number>;
    qa_status_distribution: Record<string, number>;
    data_scope: string;
  };
};
type Taxonomy = {
  utility_verticals: Array<{ id: string; label: string; asset_classes: string[] }>;
  lifecycle_states: string[];
  qa_states: string[];
  review_states: string[];
  relationship_types: string[];
  transformation_types: string[];
};
type AssetFiltersState = {
  vertical: string; assetClass: string; assetSubtype: string; lifecycle: string; operational: string;
  qa: string; review: string; owner: string; feederCircuit: string; telecomRoute: string;
  sourceLayer: string; search: string; provisional: boolean;
};
type AssetTraceReadiness = {
  eligible_trace_types: Array<{ trace_type: string; name: string; default_direction: string }>;
  trace_ready: boolean;
  blockers: Array<Record<string, string>>;
  warnings: Array<Record<string, string>>;
  provisional_relationships: number;
  trace_count: number;
  recent_traces: Array<Record<string, string>>;
  relationship_trace_usage: Record<string, { traces_used: number; traces_stopped: number }>;
};

const tabs = ["Overview", "Electric Distribution", "Telecom/Fiber", "Asset Explorer", "Relationships", "Canonicalization Plans", "Data Quality Preview"] as const;
type WorkspaceTab = (typeof tabs)[number];

export function UtilityAssetsWorkspace({
  detailAssetId = "",
  initialVertical = "",
  routeBase = "/utility-assets",
  vertical = "",
  view = "overview",
}: {
  detailAssetId?: string;
  initialVertical?: string;
  routeBase?: string;
  vertical?: UtilityAsset["utility_vertical"] | "";
  view?: UtilityWorkspaceView;
}) {
  const provider = getDataProvider();
  const [data, setData] = useState<AssetResponse | null>(null);
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [plans, setPlans] = useState<CanonicalizationPlan[]>([]);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(
    initialVertical === "electric_distribution" ? "Electric Distribution"
      : initialVertical === "telecom_fiber" ? "Telecom/Fiber"
        : "Overview",
  );
  const [selectedAsset, setSelectedAsset] = useState<UtilityAsset | null>(null);
  const [relationships, setRelationships] = useState<AssetRelationship[]>([]);
  const [lineage, setLineage] = useState<Record<string, unknown> | null>(null);
  const [assetFindings, setAssetFindings] = useState<ConnectivityFinding[]>([]);
  const [assetIssueGroups, setAssetIssueGroups] = useState<ConnectivityIssueGroup[]>([]);
  const [traceReadiness, setTraceReadiness] = useState<AssetTraceReadiness | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [filters, setFilters] = useState<AssetFiltersState>({
    vertical: "", assetClass: "", assetSubtype: "", lifecycle: "", operational: "", qa: "",
    review: "", owner: "", feederCircuit: "", telecomRoute: "", sourceLayer: "", search: "", provisional: false,
  });
  const selectedAssetId = selectedAsset?.asset_id ?? "";
  const currentTab = vertical ? tabForView(view) : activeTab;
  const verticalConfig = vertical ? getUtilityVertical(vertical === "electric_distribution" ? "electric" : "telecom") : undefined;

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      provider.get<AssetResponse>("/api/utility-assets?limit=500", controller.signal),
      provider.get<Taxonomy>("/api/utility-assets/taxonomy", controller.signal),
      provider.get<{ items: CanonicalizationPlan[] }>("/api/utility-assets/canonicalization-plans", controller.signal),
    ]).then(([assetData, taxonomyData, planData]) => {
      setData(assetData);
      setTaxonomy(taxonomyData);
      setPlans(planData.items);
      if (detailAssetId) {
        const asset = assetData.items.find((item) => item.asset_id === detailAssetId);
        if (asset) setSelectedAsset(asset);
      }
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Utility asset service unavailable."));
    return () => controller.abort();
  }, [detailAssetId, provider]);

  useEffect(() => {
    if (!selectedAssetId) return;
    const controller = new AbortController();
    Promise.all([
      provider.get<UtilityAsset>(`/api/utility-assets/${encodeURIComponent(selectedAssetId)}`, controller.signal),
      provider.get<{ items: AssetRelationship[] }>(`/api/utility-assets/${encodeURIComponent(selectedAssetId)}/relationships`, controller.signal),
      provider.get<Record<string, unknown>>(`/api/utility-assets/${encodeURIComponent(selectedAssetId)}/lineage`, controller.signal),
      provider.get<AssetTraceReadiness>(`/api/network-trace/assets/${encodeURIComponent(selectedAssetId)}/readiness`, controller.signal),
    ]).then(([asset, relationData, lineageData, traceData]) => {
      setSelectedAsset(asset);
      setRelationships(relationData.items);
      setLineage(lineageData);
      setTraceReadiness(traceData);
      return Promise.all([
        provider.get<{ items: ConnectivityFinding[] }>(`/api/connectivity-qa/${asset.utility_vertical}/findings?asset_id=${encodeURIComponent(asset.asset_id)}&limit=500`, controller.signal),
        provider.get<{ items: ConnectivityIssueGroup[] }>(`/api/connectivity-qa/${asset.utility_vertical}/issue-groups?asset_id=${encodeURIComponent(asset.asset_id)}&limit=500`, controller.signal),
      ]);
    }).then(([findingData, groupData]) => {
      setAssetFindings(findingData.items);
      setAssetIssueGroups(groupData.items);
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Asset detail unavailable."));
    return () => controller.abort();
  }, [provider, selectedAssetId]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const selectedVertical = vertical || (currentTab === "Electric Distribution" ? "electric_distribution" : currentTab === "Telecom/Fiber" ? "telecom_fiber" : filters.vertical);
    const needle = filters.search.toLowerCase();
    return data.items.filter((asset) =>
      (!selectedVertical || asset.utility_vertical === selectedVertical)
      && (!filters.assetClass || asset.asset_class === filters.assetClass)
      && (!filters.assetSubtype || asset.asset_subtype === filters.assetSubtype)
      && (!filters.lifecycle || asset.lifecycle_status === filters.lifecycle)
      && (!filters.operational || asset.operational_status === filters.operational)
      && (!filters.qa || asset.qa_status === filters.qa)
      && (!filters.review || asset.review_status === filters.review)
      && (!filters.owner || asset.owner_status === filters.owner)
      && (!filters.feederCircuit || [asset.canonical_attributes_json?.feeder_id, asset.canonical_attributes_json?.circuit_id].includes(filters.feederCircuit))
      && (!filters.telecomRoute || asset.canonical_attributes_json?.route_id === filters.telecomRoute)
      && (!filters.sourceLayer || asset.source_layer_id === filters.sourceLayer)
      && (!filters.provisional || asset.has_provisional_relationships)
      && (!needle || `${asset.asset_id} ${asset.canonical_name} ${asset.asset_class}`.toLowerCase().includes(needle)),
    );
  }, [currentTab, data, filters, vertical]);

  if (error && !data) return <div className={ws.workspace}><PageHeader eyebrow="Utility Assets" title="Canonical Utility Asset Model" subtitle="Shared electric and telecom asset foundation." /><OfflineState service="Canonical utility asset service" /></div>;
  if (!data || !taxonomy) return <div className={ws.workspace}><LoadingSkeleton /><LoadingSkeleton /></div>;
  if (detailAssetId) return <AssetDetail asset={selectedAsset} relationships={relationships} lineage={lineage} findings={assetFindings} issueGroups={assetIssueGroups} traceReadiness={traceReadiness} backHref={verticalConfig ? utilityViewPath(verticalConfig, "assets") : routeBase} />;

  async function planAction(plan: CanonicalizationPlan, action: "approve" | "create-assets" | "defer") {
    setMessage("");
    try {
      const path = `/api/intake/submissions/${encodeURIComponent(plan.submission_id)}/layers/${encodeURIComponent(plan.layer_id)}/canonicalization-plan/${action}`;
      const result = await provider.post<CanonicalizationPlan | { created_count: number; existing_count: number }>(path, action === "approve" ? { approved_by: "Demo Reviewer", reason: "Mappings reviewed." } : action === "defer" ? { actor: "Demo Reviewer", reason: "Deferred for source confirmation." } : { actor: "Demo Reviewer" });
      setMessage(action === "create-assets" ? `Creation simulation complete: ${"created_count" in result ? result.created_count : 0} assets created.` : `Plan ${action === "approve" ? "approved" : "deferred"}.`);
      const refreshed = await provider.get<{ items: CanonicalizationPlan[] }>("/api/utility-assets/canonicalization-plans");
      setPlans(refreshed.items);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Plan action failed safely.");
    }
  }

  async function saveMappings(plan: CanonicalizationPlan, mappings: CanonicalMapping[]) {
    try {
      const path = `/api/intake/submissions/${encodeURIComponent(plan.submission_id)}/layers/${encodeURIComponent(plan.layer_id)}/canonicalization-plan/field-mappings`;
      const updated = await provider.put<CanonicalizationPlan>(path, { mappings, actor: "Demo Reviewer", reason: "Field mapping review." });
      setPlans((items) => items.map((item) => item.plan_id === updated.plan_id ? updated : item));
      setMessage("Field mappings saved. Human approval is still required.");
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Mapping update failed safely.");
    }
  }

  return (
    <div className={ws.workspace}>
      {!vertical ? <PageHeader eyebrow={isDemoMode ? "PORTFOLIO DEMO" : "Operational Asset Model"} title="Utility Assets" subtitle="A shared canonical asset foundation for electric distribution and telecom/fiber operations." /> : null}
      {isDemoMode && !vertical ? <div className={styles.demoNotice} role="status">All utility assets, relationships, and canonicalization results in this demo are synthetic and reset with the demo session.</div> : null}
      {!vertical ? <div className={styles.tabs} role="tablist" aria-label="Utility asset workspace">
        {tabs.map((tab) => <button key={tab} type="button" role="tab" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)}>{tab}</button>)}
      </div> : null}
      {message ? <div className={styles.notice} role="status">{message}</div> : null}

      {currentTab === "Overview" && (!vertical || view === "overview") ? verticalConfig
        ? <VerticalOverview config={verticalConfig} items={data.items.filter((item) => item.utility_vertical === vertical)} plans={plans.filter((plan) => plan.utility_vertical === vertical)} />
        : <Overview data={data} /> : null}
      {["Electric Distribution", "Telecom/Fiber", "Asset Explorer"].includes(currentTab) ? (
        <>
          <AssetFilters
            taxonomy={taxonomy}
            filters={filters}
            setFilters={setFilters}
            vertical={vertical}
            verticalLocked={Boolean(vertical) || currentTab !== "Asset Explorer"}
            items={vertical ? data.items.filter((item) => item.utility_vertical === vertical) : currentTab === "Electric Distribution" ? data.items.filter((item) => item.utility_vertical === "electric_distribution") : currentTab === "Telecom/Fiber" ? data.items.filter((item) => item.utility_vertical === "telecom_fiber") : data.items}
          />
          <AssetTable items={filtered} routeBase={routeBase} />
        </>
      ) : null}
      {currentTab === "Relationships" ? <RelationshipOverview items={vertical ? data.items.filter((item) => item.utility_vertical === vertical) : data.items} routeBase={routeBase} /> : null}
      {currentTab === "Canonicalization Plans" ? (
        <>
          {!isDemoMode ? <div className={styles.warning}><strong>Current reviewed submission: Not eligible for canonicalization</strong><span>Human source-review and staging blockers remain unresolved. Staging readiness does not imply canonicalization approval.</span></div> : null}
          <PlanWorkspace plans={vertical ? plans.filter((plan) => plan.utility_vertical === vertical) : plans} onAction={planAction} onSaveMappings={saveMappings} />
        </>
      ) : null}
      {currentTab === "Data Quality Preview" ? <QualityPreview items={vertical ? data.items.filter((item) => item.utility_vertical === vertical) : data.items} routeBase={routeBase} /> : null}
      {view === "source-data" && verticalConfig ? <SourceDataContext config={verticalConfig} /> : null}
      {view === "review-history" && verticalConfig ? <ReviewHistory plans={plans.filter((plan) => plan.utility_vertical === vertical)} /> : null}
    </div>
  );
}

function tabForView(view: UtilityWorkspaceView): WorkspaceTab {
  if (view === "assets") return "Asset Explorer";
  if (view === "relationships") return "Relationships";
  if (view === "canonicalization") return "Canonicalization Plans";
  if (view === "data-quality") return "Data Quality Preview";
  return "Overview";
}

function VerticalOverview({ config, items, plans }: { config: UtilityVerticalConfig; items: UtilityAsset[]; plans: CanonicalizationPlan[] }) {
  const active = items.filter((item) => item.lifecycle_status === "active").length;
  const needsReview = items.filter((item) => item.review_status === "needs_review").length;
  const provisional = items.filter((item) => item.has_provisional_relationships).length;
  const warnings = items.filter((item) => item.qa_status === "warning").length;
  const approvedPlans = plans.filter((plan) => plan.approved_for_canonicalization).length;
  const tools = [
    { view: "assets" as const, label: "Asset Explorer", description: `Inspect canonical ${config.shortTitle.toLowerCase()} assets and safe lineage.` },
    { view: "relationships" as const, label: `${config.shortTitle} Relationships`, description: "Review confirmed and provisional network relationships." },
    { view: "source-data" as const, label: "Source Data", description: "Open the shared source-governance workflow in this utility context." },
    { view: "canonicalization" as const, label: "Canonicalization Plans", description: "Review mappings, approvals, and explicit asset creation." },
    { view: "data-quality" as const, label: `${config.shortTitle} Data Quality`, description: "Inspect stored asset-quality candidates." },
    { view: "connectivity-qa" as const, label: "Connectivity QA", description: "Run versioned relationship checks and review network findings." },
    { view: "network-trace" as const, label: "Network Trace", description: "Run read-only analytical traversal over canonical relationships and calibrated QA evidence." },
    { view: "review-history" as const, label: "Review History", description: "Read immutable canonicalization plan events." },
  ];
  return (
    <>
      <section className={ws.grid12} aria-label={`${config.title} overview metrics`}>
        <div className={ws.span4}><MetricTile labelText="Canonical assets" value={String(items.length)} detail={`${config.shortTitle} assets in the current registry.`} /></div>
        <div className={ws.span4}><MetricTile labelText="Active assets" value={String(active)} detail="Lifecycle state is active." /></div>
        <div className={ws.span4}><MetricTile labelText="Needs review" value={String(needsReview)} detail="Candidates, not confirmed defects." /></div>
        <div className={ws.span4}><MetricTile labelText="Provisional relationships" value={String(provisional)} detail="Human confirmation remains required." /></div>
        <div className={ws.span4}><MetricTile labelText="QA candidates" value={String(warnings)} detail="Stored warnings for future rule evaluation." /></div>
        <div className={ws.span4}><MetricTile labelText="Canonicalization plans" value={`${approvedPlans}/${plans.length}`} detail="Approved plans / total plans." /></div>
      </section>
      <Panel title={`${config.shortTitle} tools`} description="Shared platform capabilities, filtered to the active utility context.">
        <div className={styles.toolGrid}>
          {tools.map((tool) => <Link className={styles.toolLink} href={utilityViewPath(config, tool.view)} key={tool.view}><strong>{tool.label}</strong><span>{tool.description}</span><calcite-icon icon="arrowRight" scale="s" aria-hidden="true" /></Link>)}
        </div>
      </Panel>
      <div className={ws.grid12}>
        <div className={ws.span6}><Panel title={`${config.shortTitle} operational focus`}><ul className={styles.focusList}>{config.operationalFocus.map((item) => <li key={item}>{item}</li>)}</ul></Panel></div>
        <div className={ws.span6}><Panel title="Coming next" description="Future modules are visible for product direction and are not yet available."><div className={styles.plannedList}>{config.futureModules.map((item) => <span key={item}><strong>{item}</strong><em>Planned</em></span>)}</div></Panel></div>
      </div>
    </>
  );
}

function Overview({ data }: { data: AssetResponse }) {
  const summary = data.summary;
  return (
    <>
      <div className={ws.grid12}>
        <div className={ws.span3}><MetricTile labelText="Canonical assets" value={String(summary.total_assets)} detail={`${label(summary.data_scope)} application registry`} /></div>
        <div className={ws.span3}><MetricTile labelText="Electric distribution" value={String(summary.electric_assets)} detail="Shared-core electric assets" /></div>
        <div className={ws.span3}><MetricTile labelText="Telecom/Fiber" value={String(summary.telecom_assets)} detail="Shared-core telecom assets" /></div>
        <div className={ws.span3}><MetricTile labelText="Needs review" value={String(summary.assets_needing_review)} detail="Candidates, not confirmed defects" /></div>
      </div>
      <div className={ws.grid12}>
        <div className={ws.span6}><Distribution title="Lifecycle distribution" values={summary.lifecycle_distribution} /></div>
        <div className={ws.span6}><Distribution title="QA status distribution" values={summary.qa_status_distribution} /></div>
      </div>
      <Panel title="Governed creation" description="Canonicalization remains separate from source review and staging approval.">
        <div className={styles.flow}><span>Reviewed source layer</span><span>Select vertical and class</span><span>Review mappings</span><span>Human approval</span><span>Explicit asset creation</span></div>
      </Panel>
    </>
  );
}

function Distribution({ title, values }: { title: string; values: Record<string, number> }) {
  return <Panel title={title}><div className={styles.distribution}>{Object.entries(values).map(([key, value]) => <div key={key}><span>{label(key)}</span><strong>{value}</strong></div>)}</div></Panel>;
}

function AssetFilters({ taxonomy, filters, setFilters, vertical, verticalLocked, items }: { taxonomy: Taxonomy; filters: AssetFiltersState; setFilters: (value: AssetFiltersState) => void; vertical: UtilityAsset["utility_vertical"] | ""; verticalLocked: boolean; items: UtilityAsset[] }) {
  const classes = [...new Set(items.filter((item) => !filters.vertical || item.utility_vertical === filters.vertical).map((item) => item.asset_class))].sort();
  const subtypes = [...new Set(items.map((item) => item.asset_subtype))].sort();
  const operationalStates = [...new Set(items.map((item) => item.operational_status))].sort();
  const owners = [...new Set(items.map((item) => item.owner_status))].sort();
  const feederCircuits = [...new Set(items.flatMap((item) => [item.canonical_attributes_json?.feeder_id, item.canonical_attributes_json?.circuit_id]).filter(Boolean).map(String))].sort();
  const routes = [...new Set(items.map((item) => item.canonical_attributes_json?.route_id).filter(Boolean).map(String))].sort();
  const sourceLayers = [...new Set(items.map((item) => item.source_layer_id))].sort();
  return (
    <Panel title="Asset Explorer" description="Filter the shared canonical registry without exposing source paths.">
      <div className={styles.filters}>
        {!verticalLocked ? <label>Utility vertical<select value={String(filters.vertical)} onChange={(event) => setFilters({ ...filters, vertical: event.target.value, assetClass: "" })}><option value="">All verticals</option>{taxonomy.utility_verticals.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label> : null}
        <label>Asset class<select value={String(filters.assetClass)} onChange={(event) => setFilters({ ...filters, assetClass: event.target.value })}><option value="">All classes</option>{classes.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
        <label>Asset subtype<select value={filters.assetSubtype} onChange={(event) => setFilters({ ...filters, assetSubtype: event.target.value })}><option value="">All subtypes</option>{subtypes.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Lifecycle<select value={String(filters.lifecycle)} onChange={(event) => setFilters({ ...filters, lifecycle: event.target.value })}><option value="">All states</option>{taxonomy.lifecycle_states.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Operational status<select value={filters.operational} onChange={(event) => setFilters({ ...filters, operational: event.target.value })}><option value="">All states</option>{operationalStates.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>QA status<select value={String(filters.qa)} onChange={(event) => setFilters({ ...filters, qa: event.target.value })}><option value="">All states</option>{taxonomy.qa_states.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Review status<select value={String(filters.review)} onChange={(event) => setFilters({ ...filters, review: event.target.value })}><option value="">All states</option>{taxonomy.review_states.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Owner status<select value={filters.owner} onChange={(event) => setFilters({ ...filters, owner: event.target.value })}><option value="">All states</option>{owners.map((item) => <option key={item}>{item}</option>)}</select></label>
        {vertical !== "telecom_fiber" ? <label>Feeder or circuit<select value={filters.feederCircuit} onChange={(event) => setFilters({ ...filters, feederCircuit: event.target.value })}><option value="">All IDs</option>{feederCircuits.map((item) => <option key={item}>{item}</option>)}</select></label> : null}
        {vertical !== "electric_distribution" ? <label>Telecom route<select value={filters.telecomRoute} onChange={(event) => setFilters({ ...filters, telecomRoute: event.target.value })}><option value="">All routes</option>{routes.map((item) => <option key={item}>{item}</option>)}</select></label> : null}
        <label>Source layer<select value={filters.sourceLayer} onChange={(event) => setFilters({ ...filters, sourceLayer: event.target.value })}><option value="">All layers</option>{sourceLayers.map((item) => <option key={item}>{label(item)}</option>)}</select></label>
        <label>Search<input value={String(filters.search)} onChange={(event) => setFilters({ ...filters, search: event.target.value })} placeholder="ID, name, or class" /></label>
        <label className={styles.check}><input type="checkbox" checked={Boolean(filters.provisional)} onChange={(event) => setFilters({ ...filters, provisional: event.target.checked })} />Provisional relationships</label>
      </div>
    </Panel>
  );
}

function AssetTable({ items, routeBase = "/utility-assets", title = "Canonical assets", description = `${items.length} assets visible` }: { items: UtilityAsset[]; routeBase?: string; title?: string; description?: string }) {
  if (!items.length) return <EmptyState title="No assets matched" message="Adjust the filters to inspect another part of the canonical registry." />;
  return (
    <Panel title={title} description={description}>
      <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Asset</th><th>Vertical</th><th>Class</th><th>Lifecycle</th><th>Operational</th><th>QA</th><th>Review</th><th>Source</th><th>Relations</th></tr></thead>
        <tbody>{items.map((asset) => <tr key={asset.asset_id}>
          <td><Link href={`${routeBase}${routeBase === "/utility-assets" ? "/detail" : "/assets"}?asset_id=${encodeURIComponent(asset.asset_id)}`}>{asset.canonical_name}</Link><small className={styles.assetId}>{asset.asset_id}</small></td>
          <td>{label(asset.utility_vertical)}</td><td>{label(asset.asset_class)}</td><td><StatusBadge value={asset.lifecycle_status} /></td>
          <td>{label(asset.operational_status)}</td><td><StatusBadge value={asset.qa_status} tone={asset.qa_status === "passed" ? "success" : "warning"} /></td>
          <td>{label(asset.review_status)}</td><td>{label(asset.source_system)}</td><td>{asset.relationship_count}{asset.has_provisional_relationships ? " provisional" : ""}</td>
        </tr>)}</tbody></table></div>
    </Panel>
  );
}

function RelationshipOverview({ items, routeBase }: { items: UtilityAsset[]; routeBase: string }) {
  const provisional = items.filter((item) => item.has_provisional_relationships);
  return <AssetTable title="Relationship review" description="Inferred relationships remain provisional until human confirmation." items={provisional} routeBase={routeBase} />;
}

function QualityPreview({ items, routeBase }: { items: UtilityAsset[]; routeBase: string }) {
  return <AssetTable title="Data Quality Preview" description="Stored signals for future connectivity QA. These are intentional synthetic candidates, not automatic truth." items={items.filter((item) => item.qa_status !== "passed")} routeBase={routeBase} />;
}

function SourceDataContext({ config }: { config: UtilityVerticalConfig }) {
  return (
    <Panel title={`${config.title} source context`} description="Data Sources remains one shared intake and governance registry. Utility context is applied through review and taxonomy filters.">
      <div className={styles.contextActions}>
        <Link className={ws.button} href={`/data-sources?utility_vertical=${config.canonicalValue}`}>View eligible source layers</Link>
        <Link className={ws.button} href={`/data-sources/submission?utility_vertical=${config.canonicalValue}`}>Review taxonomy approvals</Link>
        <Link className={ws.button} href={utilityViewPath(config, "canonicalization")}>Open canonicalization plans</Link>
      </div>
      <p className={styles.inlineWarning}>The existing reviewed submission remains ineligible for canonicalization while source-review and staging blockers are unresolved.</p>
    </Panel>
  );
}

function ReviewHistory({ plans }: { plans: CanonicalizationPlan[] }) {
  const events = plans.flatMap((plan) => plan.history.map((event): Record<string, unknown> => ({ ...event, plan_id: plan.plan_id })));
  return (
    <Panel title="Immutable review history" description="Canonicalization decisions are preserved separately from source and staged geometry.">
      {events.length ? <ol className={styles.history}>{events.map((event, index) => <li key={`${event.plan_id}-${event.action}-${index}`}><strong>{label(String(event.action ?? "event"))}</strong><span>{String(event.created_at ?? "")} / {String(event.actor ?? event.actor_type ?? "system")} / {String(event.plan_id)}</span></li>)}</ol> : <EmptyState title="No review events" message="No canonicalization history is available for this utility workspace." />}
    </Panel>
  );
}

function PlanWorkspace({ plans, onAction, onSaveMappings }: { plans: CanonicalizationPlan[]; onAction: (plan: CanonicalizationPlan, action: "approve" | "create-assets" | "defer") => void; onSaveMappings: (plan: CanonicalizationPlan, mappings: CanonicalMapping[]) => void }) {
  return <div className={styles.planGrid}>{plans.map((plan) => <Plan key={`${plan.plan_id}:${plan.status}:${plan.mapped_field_count}:${plan.unmapped_field_count}`} plan={plan} onAction={onAction} onSaveMappings={onSaveMappings} />)}</div>;
}

function Plan({ plan, onAction, onSaveMappings }: { plan: CanonicalizationPlan; onAction: (plan: CanonicalizationPlan, action: "approve" | "create-assets" | "defer") => void; onSaveMappings: (plan: CanonicalizationPlan, mappings: CanonicalMapping[]) => void }) {
  const [mappings, setMappings] = useState(plan.mappings);
  return (
    <Panel title={`${label(plan.utility_vertical)} to ${label(plan.target_asset_class)}`} description={`${plan.source_record_count} source records; ${plan.preview_record_count} safe previews`}>
      <div className={styles.planStatus}><StatusBadge value={plan.status} tone={plan.approved_for_canonicalization ? "success" : "warning"} /><span>Rule {plan.rule_version}</span><span>{plan.mapped_field_count} mapped / {plan.unmapped_field_count} unmapped</span></div>
      <dl className={styles.planReadiness}>
        <div><dt>Lifecycle mapping</dt><dd>{plan.mappings.some((item) => item.transformation_type === "lifecycle_mapping") ? "Mapped; code confirmation retained" : "Unavailable"}</dd></div>
        <div><dt>Geometry compatibility</dt><dd>Safe geometry summary compatible; source geometry remains unchanged</dd></div>
        <div><dt>Relationship candidates</dt><dd>Provisional only; human confirmation required</dd></div>
        <div><dt>Preview records</dt><dd>{plan.preview_records.map((item) => item.source_asset_identifier).join(", ") || "No approved preview adapter"}</dd></div>
      </dl>
      <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Source field</th><th>Canonical field</th><th>Transformation</th><th>Confidence</th></tr></thead>
        <tbody>{mappings.map((mapping, index) => <tr key={mapping.mapping_id}><td>{mapping.source_alias}<small className={styles.assetId}>{mapping.source_field}</small></td><td>
          <select aria-label={`Canonical field for ${mapping.source_field}`} value={mapping.canonical_field} onChange={(event) => setMappings(mappings.map((item, itemIndex) => itemIndex === index ? { ...item, canonical_field: event.target.value, transformation_type: event.target.value ? item.transformation_type === "unmapped" ? "renamed" : item.transformation_type : "unmapped" } : item))}>
            <option value="">Unmapped</option><option value="source_asset_identifier">Source asset identifier</option><option value="lifecycle_status">Lifecycle status</option><option value="asset_subtype">Asset subtype</option><option value="operational_status">Operational status</option>
          </select>
        </td><td>{label(mapping.transformation_type)}</td><td>{label(mapping.confidence)}</td></tr>)}</tbody></table></div>
      {plan.warnings.map((warning) => <p className={styles.inlineWarning} key={warning}>{warning}</p>)}
      <div className={ws.buttonRow}>
        <button className={ws.button} type="button" onClick={() => onSaveMappings(plan, mappings)}>Accept mapping</button>
        {!plan.approved_for_canonicalization ? <button className={`${ws.button} ${ws.buttonPrimary}`} type="button" disabled={plan.blockers.length > 0} onClick={() => onAction(plan, "approve")}>Approve plan</button> : null}
        <button className={ws.button} type="button" onClick={() => onAction(plan, "defer")}>Defer plan</button>
        <button className={`${ws.button} ${ws.buttonPrimary}`} type="button" disabled={!plan.approved_for_canonicalization} onClick={() => onAction(plan, "create-assets")}>Create canonical assets</button>
      </div>
      <p className={styles.inlineWarning}>Approval never creates assets automatically. Creation is a separate explicit action and does not alter source or staged geometry.</p>
    </Panel>
  );
}

function AssetDetail({ asset, relationships, lineage, findings, issueGroups, traceReadiness, backHref }: { asset: UtilityAsset | null; relationships: AssetRelationship[]; lineage: Record<string, unknown> | null; findings: ConnectivityFinding[]; issueGroups: ConnectivityIssueGroup[]; traceReadiness: AssetTraceReadiness | null; backHref: string }) {
  if (!asset) return <div className={ws.workspace}><LoadingSkeleton /></div>;
  const source = (lineage?.source ?? {}) as Record<string, unknown>;
  const history = (lineage?.history ?? []) as Array<Record<string, unknown>>;
  const verticalConfig = getUtilityVertical(asset.utility_vertical === "electric_distribution" ? "electric" : "telecom")!;
  const severityRank: Record<string, number> = { critical: 4, error: 3, warning: 2, info: 1 };
  const highestSeverity = findings.reduce((highest, finding) => severityRank[finding.severity] > severityRank[highest] ? finding.severity : highest, "none");
  const blocking = findings.filter((finding) => finding.blocking).length;
  const highestPriority = ["immediate", "high", "normal", "low", "informational"].find((priority) => issueGroups.some((group) => group.display_priority === priority)) ?? "none";
  const highestTraceImpact = ["stops_trace", "limits_trace", "introduces_ambiguity", "advisory", "no_trace_effect"].find((impact) => issueGroups.some((group) => group.trace_impact === impact)) ?? "not_evaluated";
  return (
    <div className={ws.workspace}>
      <PageHeader eyebrow={isDemoMode ? "PORTFOLIO DEMO ASSET" : "Canonical Asset"} title={asset.canonical_name} subtitle={`${label(asset.utility_vertical)} / ${label(asset.asset_class)} / ${label(asset.asset_subtype)}`} />
      <Link href={backHref} className={styles.backLink}>Back to {asset.utility_vertical === "electric_distribution" ? "Electric Assets" : "Telecom Assets"}</Link>
      {isDemoMode ? <div className={styles.demoNotice}>All utility assets, relationships, QA findings, trace evidence, and calibrated trace results in this demo are synthetic and reset with the demo session.</div> : null}
      <div className={ws.grid12}>
        <div className={ws.span6}><KeyValues title="Identity" values={{ "Asset ID": asset.asset_id, "Canonical name": asset.canonical_name, "Vertical": label(asset.utility_vertical), "Class": label(asset.asset_class), "Subtype": label(asset.asset_subtype), "Lifecycle": label(asset.lifecycle_status), "Operational": label(asset.operational_status) }} /></div>
        <div className={ws.span6}><KeyValues title="QA and review" values={{ "Asset QA status": label(asset.qa_status), "Asset review status": label(asset.review_status), "Actionable issue groups": issueGroups.length, "Technical findings": findings.length, "Highest severity": label(highestSeverity), "Highest priority": label(highestPriority), "Trace impact": label(highestTraceImpact), "Blocking findings": blocking, "Latest connectivity run": findings[0]?.qa_run_id || "Not evaluated" }} /></div>
      </div>
      <Panel title="Connectivity QA" description="Findings are candidates from explicit canonical relationships; no source geometry is changed.">
        <div className={styles.contextActions}>
          <Link className={ws.button} href={utilityViewPath(verticalConfig, "connectivity-qa")}>Open Connectivity QA</Link>
          {issueGroups.slice(0, 3).map((group) => <span key={group.issue_group_id}><strong>{group.primary_rule_code}</strong> {label(group.display_priority)} / {label(group.trace_impact)} / {group.technical_finding_count} finding{group.technical_finding_count === 1 ? "" : "s"}</span>)}
          {findings.slice(0, 4).map((finding) => <span key={finding.finding_id}><strong>{finding.rule_code}</strong> {label(finding.severity)} / {label(finding.review_status)}</span>)}
        </div>
      </Panel>
      <Panel title="Network Trace" description="Read-only analytical traversal readiness; no device state, relationship, or source evidence is changed.">
        <div className={styles.contextActions}>
          <Link className={ws.button} href={`${utilityViewPath(verticalConfig, "network-trace")}?start_asset_id=${encodeURIComponent(asset.asset_id)}`}>Start trace from this asset</Link>
          <span><strong>Eligible trace types</strong> {traceReadiness?.eligible_trace_types.map((item) => item.name).join(", ") || "None"}</span>
          <span><strong>Trace eligibility</strong> {traceReadiness?.trace_ready ? "Eligible" : "Not eligible"}</span>
          <span><strong>Historical trace count</strong> {traceReadiness?.trace_count ?? 0}</span>
          <span><strong>Highest trace warning</strong> {traceReadiness?.blockers[0]?.group_title || traceReadiness?.warnings[0]?.group_title || "None recorded"}</span>
          <span><strong>Blocking issue groups</strong> {traceReadiness?.blockers.length ?? 0}</span>
          <span><strong>Provisional relationships</strong> {traceReadiness?.provisional_relationships ?? 0}</span>
        </div>
      </Panel>
      <Panel title="Source lineage" description="Safe identifiers only; filesystem paths are never returned."><KeyGrid values={{ "Source system": source.source_system, "Source submission": source.source_submission_id, "Source layer": source.source_layer_id, "Source record": source.source_record_id, "Source fingerprint": source.source_fingerprint, "Canonicalization plan": lineage?.canonicalization_plan_id || "Synthetic seed", "Mapping rule": lineage?.mapping_rule_version || "synthetic-assets-v1" }} /></Panel>
      <div className={ws.grid12}>
        <div className={ws.span6}><JsonPanel title="Canonical attributes" value={asset.canonical_attributes_json ?? {}} provenance="Normalized or inferred values are labeled in evidence." /></div>
        <div className={ws.span6}><JsonPanel title="Source attributes" value={asset.source_attributes_json ?? {}} provenance="Original safe source evidence is preserved separately." /></div>
      </div>
      <Panel title="Relationships" description="Provisional and inferred connections are not authoritative.">
        {relationships.length ? <div className={ws.tableWrap}><table className={ws.table}><thead><tr><th>Type</th><th>Connected asset</th><th>Direction</th><th>Confidence</th><th>Evidence</th><th>QA</th><th>Trace use</th></tr></thead><tbody>{relationships.map((item) => {
          const relationshipFindings = findings.filter((finding) => finding.relationship_id === item.relationship_id);
          const relationshipGroups = issueGroups.filter((group) => group.affected_relationship_ids.includes(item.relationship_id));
          const usage = traceReadiness?.relationship_trace_usage[item.relationship_id];
          const traversable = ["feeds", "connects_to", "upstream_of", "downstream_of", "served_by", "protected_by", "spliced_to", "terminates_at"].includes(item.relationship_type);
          return <tr key={item.relationship_id}><td>{label(item.relationship_type)}<small className={styles.assetId}>{traversable ? `${verticalConfig.shortTitle} operational profile` : "Context only"}</small></td><td>{item.connected_asset_name}<small className={styles.assetId}>{label(item.connected_asset_class)}</small></td><td>{label(item.direction)}</td><td>{label(item.confidence)}</td><td>{item.provisional ? "Provisional" : "Source relationship"} / {label(item.source)}</td><td>{relationshipGroups.length ? `${relationshipGroups.length} group${relationshipGroups.length === 1 ? "" : "s"} / ${label(relationshipGroups[0].trace_impact)} / ${relationshipGroups[0].primary_rule_code}` : relationshipFindings.length ? `${relationshipFindings.length} technical finding${relationshipFindings.length === 1 ? "" : "s"}` : "No active findings"}</td><td>{usage ? `${usage.traces_used} used / ${usage.traces_stopped} stopped` : "No trace use"}</td></tr>;
        })}</tbody></table></div> : <EmptyState title="No relationships" message="No safe canonical relationship is registered for this asset." />}
      </Panel>
      <Panel title="Immutable history">{history.length ? <ol className={styles.history}>{history.map((item, index) => <li key={`${item.action}-${index}`}><strong>{label(String(item.action ?? "event"))}</strong><span>{String(item.created_at ?? "")} / {String(item.actor ?? item.actor_type ?? "system")}</span></li>)}</ol> : <EmptyState title="No history events" message="No canonical history event is available." />}</Panel>
    </div>
  );
}

function KeyValues({ title, values }: { title: string; values: Record<string, unknown> }) {
  return <Panel title={title}><KeyGrid values={values} /></Panel>;
}

function KeyGrid({ values }: { values: Record<string, unknown> }) {
  return <dl className={styles.keyGrid}>{Object.entries(values).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value ?? "Unavailable")}</dd></div>)}</dl>;
}

function JsonPanel({ title, value, provenance }: { title: string; value: Record<string, unknown>; provenance: string }) {
  return <Panel title={title} description={provenance}><KeyGrid values={Object.keys(value).length ? value : { Status: "No safe attributes available" }} /></Panel>;
}
