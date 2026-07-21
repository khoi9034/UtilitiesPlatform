import { expect, test } from "@playwright/test";

const routes = ["/", "/asset-inventory", "/data-health", "/network-intelligence", "/cad-intake", "/trust-pipeline", "/data-sources", "/data-sources/inventory", "/data-sources/upload", "/data-sources/submission", "/projects", "/maintenance", "/methodology"];
const basePath = process.env.DEMO_BASE_PATH ?? "";

test.describe("portfolio demo mode", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/**", (route) => route.abort("failed"));
    await page.route("https://js.arcgis.com/**", (route) => route.abort("blockedbyclient"));
  });

  test("loads every route without backend API requests", async ({ page }) => {
    for (const route of routes) {
      await page.goto(`${basePath}${route}`, { waitUntil: "domcontentloaded" });
      await expect(page.getByText("PORTFOLIO DEMO", { exact: true }).first()).toBeVisible();
      await expect(page.locator("body")).not.toContainText("C:\\");
      await expect(page.locator("body")).not.toContainText("UtilitiesPlatform_Data");
      await expect(page.locator("body")).not.toContainText("Backend API is unavailable");
    }
  });

  test("shows sanitized data-source stages", async ({ page }) => {
    await page.goto(`${basePath}/data-sources`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Sanitized source package A", { exact: true }).first()).toBeVisible();
    await page.getByRole("tab", { name: /Staging/i }).click();
    await expect(page.getByText("demo_gravity_main", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Standardized").first()).toBeVisible();
    await page.getByRole("tab", { name: /Standardized/i }).click();
    await expect(page.getByText("Awaiting data-owner confirmation and approved standardization mappings.").first()).toBeVisible();
  });

  test("simulates intake without backend requests", async ({ page }) => {
    await page.goto(`${basePath}/data-sources/upload`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("PORTFOLIO DEMO INTAKE", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Load Synthetic Sample" }).click();
    await expect(page.getByText("Sample_Mixed_Utility_Source.gdb").first()).toBeVisible();
    await expect(page.getByText("Demo mode does not upload or inspect your file").first()).toBeVisible();
    await page.getByRole("link", { name: "View in Raw Stage" }).first().click();
    await expect(page.getByText("Synthetic Mixed Utility Source").first()).toBeVisible();
    await page.goto(`${basePath}/data-sources/upload`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Reset Demo Intake" }).click();
    await expect(page.getByText("Demo intake reset.")).toBeVisible();
  });

  test("reviews synthetic mixed-package child layers", async ({ page }) => {
    await page.goto(`${basePath}/data-sources/submission`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Synthetic Mixed Utility Source").first()).toBeVisible();
    await page.getByRole("tab", { name: "Layers" }).click();
    await expect(page.getByText("Town_A_ForceMains").first()).toBeVisible();
    await page.getByText("WaterLine").first().click();
    await expect(page.getByText("Classification Recommendation").first()).toBeVisible();
    await page.getByRole("tab", { name: "Duplicate Candidates" }).click();
    await expect(page.getByText("Town_B_Sewer").first()).toBeVisible();
    await page.getByRole("button", { name: "Retain Both" }).first().click();
    await expect(page.getByText("Duplicate review decision recorded.")).toBeVisible();
    await page.getByRole("tab", { name: "Coordinate Review" }).click();
    await expect(page.getByText("WaterLine").first()).toBeVisible();
    await page.getByRole("tab", { name: "Staging Plan" }).click();
    await page.getByRole("button", { name: "Approve" }).first().click();
    await expect(page.getByText("Demo staging approval recorded in sessionStorage.")).toBeVisible();
    await page.getByRole("button", { name: "Simulate Approved Staging" }).click();
    await expect(page.getByText("Demo staging was simulated in sessionStorage.")).toBeVisible();
  });

  test("loads demo findings and keeps review decisions temporary", async ({ page }) => {
    await page.goto(`${basePath}/data-health`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Representative sanitized network sample").first()).toBeVisible();
    await page.getByText("GM-DEMO-004").first().click();
    await expect(page.getByText("Review Decision")).toBeVisible();
    await page.getByLabel("Disposition", { exact: true }).first().selectOption("false_positive");
    await page.getByRole("button", { name: "Save temporary review" }).click();
    await expect(page.getByLabel("Disposition", { exact: true }).first()).toHaveValue("false_positive");
    await page.getByRole("button", { name: "Close" }).click();
    await page.getByRole("button", { name: "Reset Demo Session" }).click();
    await expect(page.getByText("PORTFOLIO DEMO", { exact: true }).first()).toBeVisible();
  });
});
