import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

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
    const formText = await page.locator("main").innerText();
    expect(formText.indexOf("Source Information")).toBeLessThan(formText.indexOf("Select Source Package"));
    expect(formText.indexOf("Select Source Package")).toBeLessThan(formText.indexOf("Review Submission"));
    await expect(page.getByRole("button", { name: "Simulate Raw Registration" })).toBeDisabled();
    await page.getByRole("button", { name: "Load Synthetic Mixed FileGDB" }).click();
    await expect(page.getByText("Sample_Mixed_Utility_Source.gdb").first()).toBeVisible();
    await expect(page.getByText("NOT UPLOADED").first()).toBeVisible();
    await expect(page.getByText("Raw Registration Complete")).toHaveCount(0);
    await page.getByLabel("Submission name").fill("Synthetic Mixed Utility Source");
    await page.getByLabel("Source owner").fill("Synthetic Data Owner");
    await page.getByLabel("Submitted by").fill("Demo Reviewer");
    await page.getByLabel("Description").fill("Synthetic package for upload workflow testing.");
    await page.getByLabel(/authorized to store and analyze/i).check();
    await expect(page.getByRole("button", { name: "Simulate Raw Registration" })).toBeEnabled();
    await page.getByRole("button", { name: "Simulate Raw Registration" }).click();
    await expect(page.getByText("Raw Registration Complete").first()).toBeVisible();
    await expect(page.getByText("RAW REGISTERED").first()).toBeVisible();
    await expect(page.getByText("Demo mode does not upload or inspect your folder").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Run Source Inspection" }).first()).toBeVisible();
    await page.getByRole("link", { name: "View in Raw Stage" }).first().click();
    await expect(page.getByText("Synthetic Mixed Utility Source").first()).toBeVisible();
    await page.goto(`${basePath}/data-sources/upload`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Reset Demo Intake" }).click();
    await expect(page.getByText("Demo intake reset.")).toBeVisible();
  });

  test("treats a selected FileGDB folder as one package", async ({ page }, testInfo) => {
    const gdbRoot = testInfo.outputPath("Synthetic_Selected_Source.gdb");
    mkdirSync(gdbRoot, { recursive: true });
    writeFileSync(join(gdbRoot, "a00000001.gdbtable"), "table");
    writeFileSync(join(gdbRoot, "a00000001.gdbtablx"), "index");

    await page.goto(`${basePath}/data-sources/upload`, { waitUntil: "domcontentloaded" });
    await page.getByRole("radio", { name: "Choose FileGDB Folder" }).check();
    await page.locator("input[webkitdirectory]").setInputFiles(gdbRoot);

    await expect(page.getByText("Synthetic_Selected_Source.gdb").first()).toBeVisible();
    await expect(page.getByText(/2 of 50K allowed/).first()).toBeVisible();
    await expect(page.getByText("File geodatabase folder").first()).toBeVisible();
    await expect(page.getByText("Passed browser precheck").first()).toBeVisible();
    await page.getByText("View Package Contents").click();
    await expect(page.getByText("Synthetic_Selected_Source.gdb/a00000001.gdbtable").first()).toBeVisible();
  });

  test("rejects a non-GDB folder before upload", async ({ page }, testInfo) => {
    const folderRoot = testInfo.outputPath("LooseFolder");
    mkdirSync(folderRoot, { recursive: true });
    writeFileSync(join(folderRoot, "a00000001.gdbtable"), "table");

    await page.goto(`${basePath}/data-sources/upload`, { waitUntil: "domcontentloaded" });
    await page.getByRole("radio", { name: "Choose FileGDB Folder" }).check();
    await page.locator("input[webkitdirectory]").setInputFiles(folderRoot);

    await expect(page.getByText("Top-level folder must end in .gdb.").first()).toBeVisible();
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
