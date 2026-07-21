import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PORT ?? 3004);
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${port}`;
const basePath = process.env.DEMO_BASE_PATH ?? "/UtilitiesPlatform";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "demo.spec.ts",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    channel: "chrome",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "node scripts/serve-demo.mjs",
    url: `${baseURL}${basePath}/`,
    reuseExistingServer: true,
    timeout: 30_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
