import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(here, "..");
const env = { ...process.env, NEXT_PUBLIC_APP_MODE: "demo", DEMO_EXPORT: "true" };
const result = spawnSync(process.execPath, [join(frontendRoot, "node_modules", "next", "dist", "bin", "next"), "build"], {
  cwd: frontendRoot,
  env,
  stdio: "inherit",
});
process.exit(result.status ?? 1);
