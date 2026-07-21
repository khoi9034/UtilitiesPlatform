import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(here, "..");
const repoRoot = join(frontendRoot, "..");
const env = { ...process.env, NEXT_PUBLIC_APP_MODE: "demo", DEMO_EXPORT: "true" };
const result = spawnSync(process.execPath, [join(frontendRoot, "node_modules", "next", "dist", "bin", "next"), "build"], {
  cwd: frontendRoot,
  env,
  stdio: "inherit",
});
if (result.status) process.exit(result.status);
const parity = spawnSync("python", [join(repoRoot, "scripts", "demo", "check_feature_parity.py"), "--frontend-root", frontendRoot], {
  cwd: repoRoot,
  env,
  stdio: "inherit",
});
process.exit(parity.status ?? 1);
