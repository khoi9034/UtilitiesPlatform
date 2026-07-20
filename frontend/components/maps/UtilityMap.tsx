"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Issue, MapData, MapFeature } from "../../lib/api-types";
import { label } from "../../lib/formatters";
import styles from "./utility-map.module.css";

type ArcGisConstructor = new (properties?: Record<string, unknown>) => unknown;
type ArcGisLayer = { addMany: (items: unknown[]) => void };
type ArcGisView = {
  destroy: () => void;
  goTo: (target: unknown) => Promise<unknown>;
  on: (eventName: string, callback: (event: unknown) => void) => void;
  hitTest: (event: unknown) => Promise<{ results: { graphic?: { attributes?: Record<string, string> } }[] }>;
};
type ArcGisModules = {
  Map: ArcGisConstructor;
  MapView: ArcGisConstructor;
  GraphicsLayer: ArcGisConstructor;
  Graphic: ArcGisConstructor;
  Point: ArcGisConstructor;
  Polyline: ArcGisConstructor;
};

declare global {
  interface Window {
    require?: (modules: string[], callback: (...loaded: ArcGisConstructor[]) => void) => void;
  }
}

export function UtilityMap({
  mapData,
  selectedIssue,
  onIssueSelect,
  categories,
  height = 520,
  showOpenLink = true,
}: {
  mapData: MapData;
  selectedIssue?: Issue | null;
  onIssueSelect?: (issueId: string) => void;
  categories?: string[];
  height?: number;
  showOpenLink?: boolean;
}) {
  const mapNode = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<ArcGisView | null>(null);
  const [showPipes, setShowPipes] = useState(true);
  const [showManholes, setShowManholes] = useState(true);
  const [showIssues, setShowIssues] = useState(true);
  const [hiddenCategories, setHiddenCategories] = useState<string[]>([]);
  const detectedCategories = useMemo(() => categories ?? Array.from(new Set(mapData.issues.map((item) => item.category ?? "").filter(Boolean))).sort(), [categories, mapData.issues]);
  const visibleCategories = useMemo(() => detectedCategories.filter((category) => !hiddenCategories.includes(category)), [detectedCategories, hiddenCategories]);
  const issueCount = showIssues ? mapData.issues.filter((item) => visibleCategories.includes(item.category ?? "")).length : 0;
  const visibleIssues = useMemo(() => mapData.issues.filter((item) => visibleCategories.includes(item.category ?? "")), [mapData.issues, visibleCategories]);

  useEffect(() => {
    let cancelled = false;
    async function drawMap() {
      if (!mapNode.current) return;
      const { Map, MapView, GraphicsLayer, Graphic, Point, Polyline } = await loadArcGisSdk();
      if (cancelled || !mapNode.current) return;
      viewRef.current?.destroy();
      const map = new Map({ basemap: "streets-night-vector" });
      const layer = new GraphicsLayer() as ArcGisLayer;
      (map as { add: (item: unknown) => void }).add(layer);
      const graphics = [
        ...(showPipes ? mapData.pipes.map((item) => featureGraphic(Graphic, Polyline, Point, item, "pipe", selectedIssue)) : []),
        ...(showManholes ? mapData.manholes.map((item) => featureGraphic(Graphic, Polyline, Point, item, "manhole", selectedIssue)) : []),
        ...(showIssues ? visibleIssues.map((item) => featureGraphic(Graphic, Polyline, Point, item, "issue", selectedIssue)) : []),
      ].filter(Boolean);
      layer.addMany(graphics);
      const anchor = firstPoint(mapData) ?? { center: [-8968000, 4214000] as [number, number], wkid: 3857 };
      const view = new MapView({ container: mapNode.current, map, center: anchor.center, zoom: 12, spatialReference: { wkid: anchor.wkid } }) as ArcGisView;
      view.on("click", async (event) => {
        const hit = await view.hitTest(event);
        const issueId = hit.results.find((item) => item.graphic?.attributes?.issue_id)?.graphic?.attributes?.issue_id;
        if (issueId && onIssueSelect) onIssueSelect(issueId);
      });
      viewRef.current = view;
    }
    drawMap().catch(() => undefined);
    return () => {
      cancelled = true;
      viewRef.current?.destroy();
      viewRef.current = null;
    };
  }, [mapData, showPipes, showManholes, showIssues, visibleIssues, selectedIssue, onIssueSelect]);

  useEffect(() => {
    const geometry = selectedIssue?.safe_geometry;
    if (!geometry || !viewRef.current || !("x" in geometry)) return;
    viewRef.current.goTo({ center: [geometry.x, geometry.y], zoom: 16 }).catch(() => undefined);
  }, [selectedIssue]);

  return (
    <div className={styles.mapShell} style={{ "--map-height": `${height}px` } as React.CSSProperties}>
      <div className={styles.overlay}>
        <div className={styles.overlayHeader}>
          <div>
            <strong>Wastewater map</strong>
            <span> {issueCount} visible issue(s)</span>
          </div>
          {showOpenLink ? <Link className={styles.mapLink} href="/data-health">Open review</Link> : null}
        </div>
        <div className={styles.toggleGrid} aria-label="Map layer toggles">
          <label><input type="checkbox" checked={showPipes} onChange={(event) => setShowPipes(event.target.checked)} /> Pipes</label>
          <label><input type="checkbox" checked={showManholes} onChange={(event) => setShowManholes(event.target.checked)} /> Manholes</label>
          <label><input type="checkbox" checked={showIssues} onChange={(event) => setShowIssues(event.target.checked)} /> QA issues</label>
          {detectedCategories.map((category) => (
            <label key={category}>
              <input
                type="checkbox"
                checked={visibleCategories.includes(category)}
                onChange={(event) => setHiddenCategories((current) => event.target.checked ? current.filter((item) => item !== category) : [...current, category])}
              />
              {label(category)}
            </label>
          ))}
        </div>
        <div className={styles.legend} aria-label="Map legend">
          <span className={styles.legendItem}><i className={styles.lineSwatch} style={{ "--swatch": "#43d6ff" } as React.CSSProperties} /> Pipes</span>
          <span className={styles.legendItem}><i className={styles.swatch} style={{ "--swatch": "#43dfa9" } as React.CSSProperties} /> Manholes</span>
          <span className={styles.legendItem}><i className={styles.swatch} style={{ "--swatch": "#ff6f7f" } as React.CSSProperties} /> High</span>
          <span className={styles.legendItem}><i className={styles.swatch} style={{ "--swatch": "#ffc15e" } as React.CSSProperties} /> Medium</span>
        </div>
        {mapData.pipes.length + mapData.manholes.length + mapData.issues.length === 0 ? <p className={styles.empty}>No safe map geometry is available from the backend.</p> : null}
      </div>
      <div className={styles.mapCanvas} ref={mapNode} />
      <FallbackNetwork mapData={mapData} visibleIssues={visibleIssues} showPipes={showPipes} showManholes={showManholes} showIssues={showIssues} selectedIssue={selectedIssue} />
    </div>
  );
}

function FallbackNetwork({ mapData, visibleIssues, showPipes, showManholes, showIssues, selectedIssue }: { mapData: MapData; visibleIssues: MapFeature[]; showPipes: boolean; showManholes: boolean; showIssues: boolean; selectedIssue?: Issue | null }) {
  const points = collectPoints(mapData);
  if (points.length < 2) return null;
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const padX = Math.max((maxX - minX) * 0.08, 1);
  const padY = Math.max((maxY - minY) * 0.08, 1);
  const viewBox = `${minX - padX} ${-(maxY + padY)} ${(maxX - minX) + padX * 2} ${(maxY - minY) + padY * 2}`;
  return (
    <svg className={styles.fallbackSvg} viewBox={viewBox} aria-hidden="true" preserveAspectRatio="xMidYMid meet">
      {showPipes ? mapData.pipes.slice(0, 650).map((pipe, index) => "paths" in pipe.geometry ? <polyline key={`p-${index}`} points={pipe.geometry.paths[0].map(([x, y]) => `${x},${-y}`).join(" ")} fill="none" stroke="#43d6ff" strokeOpacity="0.55" strokeWidth="18" vectorEffect="non-scaling-stroke" /> : null) : null}
      {showManholes ? mapData.manholes.slice(0, 650).map((manhole, index) => "x" in manhole.geometry ? <circle key={`m-${index}`} cx={manhole.geometry.x} cy={-manhole.geometry.y} r="28" fill="#43dfa9" fillOpacity="0.78" vectorEffect="non-scaling-stroke" /> : null) : null}
      {showIssues ? visibleIssues.slice(0, 900).map((issue, index) => "x" in issue.geometry ? <circle key={`i-${index}`} cx={issue.geometry.x} cy={-issue.geometry.y} r={selectedIssue?.issue_id === issue.issue_id ? "58" : "38"} fill={issue.severity === "high" ? "#ff6f7f" : issue.severity === "medium" ? "#ffc15e" : "#79aaff"} fillOpacity="0.82" stroke="#071019" strokeWidth="12" vectorEffect="non-scaling-stroke" /> : null) : null}
    </svg>
  );
}

function collectPoints(mapData: MapData): [number, number][] {
  const points: [number, number][] = [];
  for (const feature of [...mapData.pipes.slice(0, 650), ...mapData.manholes.slice(0, 650), ...mapData.issues.slice(0, 900)]) {
    const geometry = feature.geometry;
    if ("x" in geometry) points.push([geometry.x, geometry.y]);
    if ("paths" in geometry) geometry.paths[0]?.forEach(([x, y]) => points.push([x, y]));
  }
  return points;
}

function firstPoint(mapData: MapData): { center: [number, number]; wkid: number } | null {
  for (const feature of [...mapData.manholes, ...mapData.issues, ...mapData.pipes]) {
    const geometry = feature.geometry;
    if ("x" in geometry && typeof geometry.x === "number" && typeof geometry.y === "number") return { center: [geometry.x, geometry.y], wkid: geometry.spatial_reference_wkid ?? 3857 };
    if ("paths" in geometry && geometry.paths[0]?.[0]) return { center: geometry.paths[0][0] as [number, number], wkid: geometry.spatial_reference_wkid ?? 3857 };
  }
  return null;
}

function loadArcGisSdk(): Promise<ArcGisModules> {
  return new Promise((resolve, reject) => {
    const finish = () => {
      const arcgisRequire = Reflect.get(window, "require") as Window["require"] | undefined;
      if (typeof arcgisRequire !== "function") {
        reject(new Error("ArcGIS loader unavailable."));
        return;
      }
      arcgisRequire(
        ["esri/Map", "esri/views/MapView", "esri/layers/GraphicsLayer", "esri/Graphic", "esri/geometry/Point", "esri/geometry/Polyline"],
        (Map, MapView, GraphicsLayer, Graphic, Point, Polyline) => resolve({ Map, MapView, GraphicsLayer, Graphic, Point, Polyline }),
      );
    };
    if (typeof Reflect.get(window, "require") === "function") {
      finish();
      return;
    }
    if (!document.getElementById("arcgis-css")) {
      const link = document.createElement("link");
      link.id = "arcgis-css";
      link.rel = "stylesheet";
      link.href = "https://js.arcgis.com/4.31/esri/themes/dark/main.css";
      document.head.appendChild(link);
    }
    const existing = document.getElementById("arcgis-js") as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", finish, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.id = "arcgis-js";
    script.src = "https://js.arcgis.com/4.31/";
    script.async = true;
    script.onload = finish;
    script.onerror = () => reject(new Error("ArcGIS SDK failed to load."));
    document.body.appendChild(script);
  });
}

function featureGraphic(Graphic: ArcGisConstructor, Polyline: ArcGisConstructor, Point: ArcGisConstructor, item: MapFeature, kind: string, selectedIssue?: Issue | null) {
  const geometry = item.geometry;
  const isSelected = selectedIssue?.issue_id && item.issue_id === selectedIssue.issue_id;
  if ("paths" in geometry) {
    return new Graphic({
      geometry: new Polyline({ paths: geometry.paths, spatialReference: { wkid: geometry.spatial_reference_wkid ?? 3857 } }),
      attributes: item,
      symbol: { type: "simple-line", color: kind === "issue" ? [255, 111, 127, 0.95] : [67, 214, 255, 0.7], width: isSelected ? 4 : 1.7 },
    });
  }
  if ("x" in geometry) {
    const issueColor = item.severity === "high" ? [255, 111, 127, 0.95] : item.severity === "medium" ? [255, 193, 94, 0.95] : [121, 170, 255, 0.9];
    return new Graphic({
      geometry: new Point({ x: geometry.x, y: geometry.y, spatialReference: { wkid: geometry.spatial_reference_wkid ?? 3857 } }),
      attributes: item,
      symbol: { type: "simple-marker", color: kind === "issue" ? issueColor : [67, 223, 169, 0.8], outline: { color: [6, 16, 25, 0.95], width: 1 }, size: isSelected ? 13 : kind === "issue" ? 9 : 5 },
    });
  }
  return null;
}
