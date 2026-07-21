"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { PropsWithChildren, useEffect, useMemo, useState } from "react";
import { fetchJson } from "../../lib/api-client";
import { isDemoMode } from "../../lib/data-provider/provider";
import { resetDemoSession } from "../../lib/data-provider/demo-review-store";
import { activeNavigationItem, navigationItems } from "../../lib/navigation";
import { utilitySystems } from "../../lib/utility-systems";
import { label, shortDate } from "../../lib/formatters";
import styles from "./app-shell.module.css";

type ThemeChoice = "dark" | "light" | "system";
type StorageStatus = { configured?: boolean; master_root_available?: boolean };
type RunResponse = { runs?: { completed_at?: string; status?: string }[] };

const groups = ["OPERATE", "INTEGRATE", "MANAGE", "GOVERN"] as const;

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const router = useRouter();
  const active = activeNavigationItem(pathname);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<ThemeChoice>("dark");
  const [commandOpen, setCommandOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [lastRun, setLastRun] = useState("");

  useEffect(() => {
    import("@esri/calcite-components/components/calcite-icon/customElement").catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setCollapsed(localStorage.getItem("up-sidebar-collapsed") === "true");
      const savedTheme = (localStorage.getItem("up-theme") as ThemeChoice | null) ?? "dark";
      setTheme(savedTheme);
      applyTheme(savedTheme);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    localStorage.setItem("up-sidebar-collapsed", String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([
      fetchJson<StorageStatus>("/api/storage/status", controller.signal),
      fetchJson<RunResponse>("/api/data-health/wastewater/runs", controller.signal),
    ]).then(([storageResult, runResult]) => {
      if (storageResult.status === "fulfilled") setStorage(storageResult.value);
      if (runResult.status === "fulfilled") setLastRun(runResult.value.runs?.[0]?.completed_at ?? "");
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
        setMobileOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const commands = useMemo(
    () => [
      ...navigationItems.map((item) => ({ label: `Open ${item.label}`, detail: item.description, action: () => router.push(item.href) })),
      { label: "Upload Data", detail: "Register approved source packages into Raw storage.", action: () => router.push("/data-sources/upload") },
      ...utilitySystems.map((system) => ({ label: `Use ${system.label}`, detail: system.enabled ? system.status : "Not onboarded", action: () => undefined })),
      { label: "Toggle theme", detail: "Cycle dark, light, and system preference.", action: () => setThemeChoice(nextTheme(theme), setTheme) },
      ...(isDemoMode ? [{ label: "Reset demo session", detail: "Clear temporary review decisions.", action: resetAndReload }] : []),
      { label: collapsed ? "Expand navigation" : "Collapse navigation", detail: "Persist sidebar width.", action: () => setCollapsed((value) => !value) },
    ],
    [collapsed, router, theme],
  );
  const visibleCommands = commands.filter((command) => `${command.label} ${command.detail}`.toLowerCase().includes(query.toLowerCase())).slice(0, 8);

  function setThemeChoice(choice: ThemeChoice, setter = setTheme) {
    setter(choice);
    localStorage.setItem("up-theme", choice);
    applyTheme(choice);
  }

  function resetAndReload() {
    resetDemoSession();
    window.location.reload();
  }

  return (
    <div className={`${styles.shell} ${collapsed ? styles.collapsed : ""}`}>
      <a href="#main-content" className="skip-link">Skip to content</a>
      <aside className={`${styles.sidebar} ${mobileOpen ? styles.sidebarOpen : ""}`} aria-label="Primary navigation">
        <div className={styles.brand}>
          <BrandMark />
          <div className={styles.brandText}>
            <strong>Utilities Platform</strong>
            <span>Trust operations</span>
          </div>
        </div>
        <nav className={styles.nav} aria-label="Primary navigation">
          {groups.map((group) => (
            <div className={styles.navGroup} key={group}>
              <span className={styles.navGroupLabel}>{group}</span>
              {navigationItems.filter((item) => item.group === group).map((item) => (
                <Link
                  className={`${styles.navItem} ${active.href === item.href ? styles.active : ""}`}
                  href={item.href}
                  key={item.href}
                  onClick={() => setMobileOpen(false)}
                  aria-current={active.href === item.href ? "page" : undefined}
                >
                  <calcite-icon icon={item.icon} scale="s" />
                  <span>{item.label}</span>
                  <em>{item.status}</em>
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className={styles.sidebarStatus}>
          <span className={isDemoMode || storage?.master_root_available ? styles.onlineDot : styles.warnDot} aria-hidden="true" />
          <span>{isDemoMode ? "Demo snapshot loaded" : storage?.master_root_available ? "Local storage online" : "Storage unavailable"}</span>
        </div>
      </aside>

      <div className={styles.contentShell}>
        <header className={styles.topbar}>
          <button className={styles.iconButton} onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <calcite-icon icon="hamburger" scale="s" />
          </button>
          <button className={styles.iconButton} onClick={() => setCollapsed((value) => !value)} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}>
            <calcite-icon icon={collapsed ? "arrowRight" : "arrowLeft"} scale="s" />
          </button>
          <div className={styles.pageTitle}>
            <span>{active.group}</span>
            <strong>{active.label}</strong>
          </div>
          <label className={styles.utilitySelector}>
            <span>Utility</span>
            <select defaultValue="wastewater" aria-label="Utility system selector">
              {utilitySystems.map((system) => (
                <option key={system.id} value={system.id} disabled={!system.enabled}>
                  {system.label} - {system.status}
                </option>
              ))}
            </select>
          </label>
          <button className={styles.commandButton} onClick={() => setCommandOpen(true)} aria-label="Open command palette">
            <calcite-icon icon="search" scale="s" />
            <span>Command</span>
            <kbd>Ctrl K</kbd>
          </button>
          <span className={styles.researchBadge}>{isDemoMode ? "PORTFOLIO DEMO" : "LOCAL RESEARCH"}</span>
          <span className={styles.runStamp}>Last run {shortDate(lastRun)}</span>
          {isDemoMode ? <button className={styles.demoReset} onClick={resetAndReload}>Reset Demo Session</button> : null}
          <ThemeToggle theme={theme} setTheme={setThemeChoice} />
        </header>
        {isDemoMode ? (
          <div className={styles.demoBanner} role="status">
            Sanitized static snapshot. No live utility infrastructure or production system is connected. Demo decisions are temporary and are not sent to a server.
          </div>
        ) : null}
        <main id="main-content" className={styles.main}>
          {children}
        </main>
      </div>

      {mobileOpen ? <button className={styles.scrim} aria-label="Close navigation" onClick={() => setMobileOpen(false)} /> : null}
      {commandOpen ? (
        <div className={styles.commandOverlay} role="dialog" aria-modal="true" aria-label="Command palette">
          <div className={styles.commandPalette}>
            <div className={styles.commandInput}>
              <calcite-icon icon="search" scale="s" />
              <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search routes and actions" />
              <button onClick={() => setCommandOpen(false)} aria-label="Close command palette"><calcite-icon icon="x" scale="s" /></button>
            </div>
            <div className={styles.commandList}>
              {visibleCommands.map((command) => (
                <button
                  key={command.label}
                  onClick={() => {
                    command.action();
                    setCommandOpen(false);
                    setQuery("");
                  }}
                >
                  <strong>{command.label}</strong>
                  <span>{command.detail}</span>
                </button>
              ))}
              {visibleCommands.length === 0 ? <p>No matching commands.</p> : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ThemeToggle({ theme, setTheme }: { theme: ThemeChoice; setTheme: (theme: ThemeChoice) => void }) {
  return (
    <button className={styles.themeButton} onClick={() => setTheme(nextTheme(theme))}>
      <calcite-icon icon="moon" scale="s" />
      {label(theme)}
    </button>
  );
}

function nextTheme(theme: ThemeChoice): ThemeChoice {
  if (theme === "dark") return "light";
  if (theme === "light") return "system";
  return "dark";
}

function applyTheme(theme: ThemeChoice) {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const resolved = theme === "system" ? (prefersDark ? "dark" : "light") : theme;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.classList.remove("calcite-mode-dark", "calcite-mode-light");
  document.documentElement.classList.add(`calcite-mode-${resolved}`);
}

function BrandMark() {
  return (
    <svg className={styles.brandMark} viewBox="0 0 44 44" aria-hidden="true">
      <path d="M9 31V14l13-7 13 7v17l-13 7-13-7Z" />
      <circle cx="14" cy="16" r="3" />
      <circle cx="30" cy="17" r="3" />
      <circle cx="20" cy="29" r="3" />
      <path d="M16.5 17.5 27.5 17.2M28 19.5 21.8 27M15.4 18.5 19 27" />
    </svg>
  );
}
