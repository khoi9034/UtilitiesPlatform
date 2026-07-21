import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(here, "..");
const repoRoot = join(frontendRoot, "..");
const demoDeployTarget = process.env.DEMO_DEPLOY_TARGET ?? "github-pages";
const demoBasePath = demoDeployTarget === "vercel" ? "" : "/UtilitiesPlatform";
const routes = ["index.html", "asset-inventory/index.html", "data-health/index.html", "network-intelligence/index.html", "cad-intake/index.html", "trust-pipeline/index.html", "data-sources/index.html", "data-sources/inventory/index.html", "projects/index.html", "maintenance/index.html", "methodology/index.html"];

run(process.execPath, [join(here, "build-demo.mjs")], frontendRoot);
run("python", [join(repoRoot, "scripts", "demo", "validate_demo_data.py"), "--demo-root", join(frontendRoot, "demo-data")], repoRoot);

const missing = routes.filter((route) => !existsSync(join(frontendRoot, "out", route)));
if (missing.length) {
  console.error(`Missing static route(s): ${missing.join(", ")}`);
  process.exit(1);
}
console.log("Demo static export routes validated.");
run(process.execPath, [join(frontendRoot, "node_modules", "@playwright", "test", "cli.js"), "test", "--config", "playwright.demo.config.ts"], frontendRoot, { PORT: "3004", PLAYWRIGHT_BASE_URL: "http://127.0.0.1:3004", DEMO_BASE_PATH: demoBasePath });

function run(command, args, cwd, env = {}) {
  const result = spawnSync(command, args, { cwd, env: { ...process.env, ...env }, stdio: "inherit" });
  if (result.status) process.exit(result.status);
}
