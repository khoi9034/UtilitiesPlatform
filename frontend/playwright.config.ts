import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PORT ?? 3001);
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    channel: "chrome",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `cmd /c "set \"NEXT_PUBLIC_API_URL=${process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001"}\" && set \"PORT=${port}\" && npm run dev -- --hostname 127.0.0.1 --port ${port}"`,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
