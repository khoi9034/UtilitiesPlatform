import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const routes = ["/", "/data-health", "/trust-pipeline", "/data-sources", "/data-sources/inventory", "/data-sources/upload", "/data-sources/submission", "/asset-inventory", "/network-intelligence", "/cad-intake", "/projects", "/maintenance", "/methodology"];
const viewports = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 390, height: 844 },
];

test.describe("enterprise shell", () => {
  for (const route of routes) {
    test(`renders shared shell on ${route}`, async ({ page }) => {
      await page.goto(route);
      await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
      await expect(page.getByText("Utilities Platform").first()).toBeVisible();
      await expect(page.locator("body")).not.toContainText("C:\\UtilitiesPlatform_Data");
      await expect(page.locator("body")).not.toContainText(".gdb");
    });
  }

  test("command palette and theme controls persist", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
    await page.getByRole("button", { name: "Close command palette" }).click();
    await page.getByRole("button", { name: /Dark|Light|System/ }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", /dark|light/);
  });

  test("Data Health tabs and filters are usable", async ({ page }) => {
    await page.goto("/data-health");
    await page.getByRole("tab", { name: "Network" }).click();
    await expect(page.getByText("Component Explorer")).toBeVisible();
    await page.getByRole("tab", { name: "Issues" }).click();
    await page.getByLabel("Severity").selectOption({ index: 1 });
    await expect(page.getByText(/results/i).first()).toBeVisible();
  });

  test("upload workflow keeps metadata before local package selection", async ({ page }) => {
    await page.goto("/data-sources/upload");
    const body = await page.locator("main").innerText();
    expect(body.indexOf("Source Information")).toBeLessThan(body.indexOf("Select Source Package"));
    expect(body.indexOf("Select Source Package")).toBeLessThan(body.indexOf("Review Submission"));
    await expect(page.getByText("NOT UPLOADED").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Complete required information" })).toBeDisabled();
  });

  test("upload failure displays structured backend detail", async ({ page, context }, testInfo) => {
    const gdbRoot = testInfo.outputPath("Synthetic_Error_Source.gdb");
    mkdirSync(gdbRoot, { recursive: true });
    writeFileSync(join(gdbRoot, "gdb"), "system");
    writeFileSync(join(gdbRoot, "a00000001.gdbtable"), "table");
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.route("**/api/intake/submissions/directory", (route) => route.fulfill({
      status: 422,
      contentType: "application/json",
      headers: { "X-Request-ID": "safe-request-123" },
      body: JSON.stringify({ detail: { code: "file_gdb_structure_invalid", message: "Selected folder does not contain recognizable FileGDB system files.", retryable: true, safe_context: { raw_source_created: false }, request_id: "safe-request-123" } }),
    }));

    await page.goto("/data-sources/upload");
    await page.getByLabel("Submission name").fill("Synthetic failure check");
    await page.getByLabel("Source owner").fill("Synthetic Owner");
    await page.getByLabel("Submitted by").fill("Tester");
    await page.getByLabel("Description").fill("Synthetic directory error response check.");
    await page.getByLabel(/authorized to store and analyze/i).check();
    await page.getByRole("radio", { name: "Choose FileGDB Folder" }).check();
    await page.locator("input[webkitdirectory]").setInputFiles(gdbRoot);
    await page.getByRole("button", { name: "Upload to Local Raw" }).click();

    await expect(page.getByText("Registration Failed", { exact: true })).toBeVisible();
    await expect(page.getByText("file_gdb_structure_invalid", { exact: true })).toBeVisible();
    await expect(page.getByText("Selected folder does not contain recognizable FileGDB system files.", { exact: true })).toBeVisible();
    await expect(page.getByText("No", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Copy Diagnostic Summary" }).click();
    await expect(page.getByText("Diagnostic summary copied.")).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("safe-request-123");
  });

  for (const viewport of viewports) {
    test(`no body horizontal overflow at ${viewport.width}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/data-health");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      expect(overflow).toBe(false);
    });
  }
});
