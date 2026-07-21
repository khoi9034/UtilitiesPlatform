import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(here, "..");
const port = process.env.PORT ?? "3001";
const env = { ...process.env, NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001", PORT: port };
const result = spawnSync(process.execPath, [join(frontendRoot, "node_modules", "next", "dist", "bin", "next"), "dev", "--hostname", "127.0.0.1", "--port", port], {
  cwd: frontendRoot,
  env,
  stdio: "inherit",
});
process.exit(result.status ?? 1);
