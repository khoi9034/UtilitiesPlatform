import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const routes = ["/", "/utilities", "/utilities/electric", "/utilities/electric/assets", "/utilities/electric/connectivity-qa", "/utilities/electric/network-trace", "/utilities/electric/proposed-edits", "/utilities/electric/work-orders", "/utilities/telecom", "/utilities/telecom/assets", "/utilities/telecom/connectivity-qa", "/utilities/telecom/network-trace", "/utilities/telecom/proposed-edits", "/utilities/telecom/work-orders", "/utilities/water-wastewater", "/utilities/water-wastewater/assets", "/utilities/water-wastewater/connectivity-qa", "/utilities/water-wastewater/network-trace", "/utilities/water-wastewater/proposed-edits", "/utilities/water-wastewater/work-orders", "/command-center", "/data-health", "/trust-pipeline", "/data-sources", "/data-sources/inventory", "/data-sources/upload", "/data-sources/submission", "/asset-inventory", "/utility-assets", "/utility-assets/detail?asset_id=demo-electric_distribution-substation-1", "/network-intelligence", "/cad-intake", "/projects", "/maintenance", "/methodology"];
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
    await page.waitForLoadState("networkidle");
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

  test("explores canonical electric and telecom assets", async ({ page }) => {
    await page.goto("/utility-assets");
    await expect(page.getByRole("heading", { name: "Utility Assets" })).toBeVisible();
    await page.getByRole("tab", { name: "Electric Distribution" }).click();
    await expect(page.getByText("ELEC-SUBSTATION-001", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Telecom/Fiber" }).click();
    await expect(page.getByText("FIBER-NETWORK-HUB-001", { exact: true })).toBeVisible();
  });

  test("selects a route-based utility workspace", async ({ page }) => {
    await page.goto("/utilities");
    const electric = page.getByRole("link", { name: "Open Electric Distribution workspace" });
    const telecom = page.getByRole("link", { name: "Open Telecom/Fiber workspace" });
    await expect(electric).toHaveAttribute("href", "/utilities/electric");
    await expect(telecom).toHaveAttribute("href", "/utilities/telecom");
    await electric.focus();
    await expect(electric).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/utilities\/electric$/);
    await expect(page.getByRole("heading", { name: "Electric Distribution" })).toBeVisible();
    await expect(page.getByText("71", { exact: true }).first()).toBeVisible();
  });

  test("keeps electric explorer and detail in electric context", async ({ page }) => {
    await page.goto("/utilities/electric/assets");
    await expect(page.getByText("ELEC-SUBSTATION-001", { exact: true })).toBeVisible();
    await expect(page.getByText("FIBER-NETWORK-HUB-001", { exact: true })).toHaveCount(0);
    await page.getByRole("link", { name: "ELEC-SUBSTATION-001" }).click();
    await expect(page).toHaveURL(/\/utilities\/electric\/assets\?asset_id=/);
    await expect(page.getByRole("link", { name: "Back to Electric Assets" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Electric Distribution workspace" })).toBeVisible();
  });

  test("keeps telecom explorer filtered and switches utilities", async ({ page }) => {
    await page.goto("/utilities/telecom/assets");
    await expect(page.getByText("FIBER-NETWORK-HUB-001", { exact: true })).toBeVisible();
    await expect(page.getByText("ELEC-SUBSTATION-001", { exact: true })).toHaveCount(0);
    await page.getByRole("navigation", { name: "Switch utility workspace" }).getByRole("link", { name: "Electric" }).click();
    await expect(page).toHaveURL(/\/utilities\/electric$/);
    await page.getByRole("navigation", { name: "Switch utility workspace" }).getByRole("link", { name: "All utilities" }).click();
    await expect(page).toHaveURL(/\/utilities$/);
  });

  test("runs and inspects electric connectivity QA through FastAPI", async ({ page }) => {
    await page.goto("/utilities/electric/connectivity-qa");
    await expect(page.getByRole("heading", { name: "Electric Connectivity QA" })).toBeVisible();
    await page.getByRole("button", { name: "Run Connectivity QA" }).click();
    await expect(page.getByText(/Connectivity QA completed|Unchanged graph detected/)).toBeVisible();
    await expect(page.getByRole("button", { name: /ELEC-001/ }).first()).toBeVisible();
    await page.getByRole("button", { name: /ELEC-001/ }).first().click();
    await expect(page.getByRole("heading", { name: "Root problem" })).toBeVisible();
    await expect(page.getByText("Stops Trace", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "All Technical Findings" }).click();
    await page.getByLabel("QA rule").selectOption("ELEC-001");
    const finding = page.getByRole("button", { name: /ELEC-001/ }).first();
    await expect(finding).toBeVisible();
    await finding.click();
    await expect(page.getByText("Logical graph context")).toBeVisible();
    await expect(page.getByLabel("Comment or rationale")).toBeVisible();
    await expect(page.getByRole("button", { name: "Accept risk" })).toBeVisible();
  });

  test("runs a read-only electric trace through FastAPI", async ({ page }) => {
    await page.goto("/utilities/electric/network-trace");
    await expect(page.getByText("Electric Network Trace", { exact: true })).toBeVisible();
    await page.getByLabel("QA policy").selectOption("diagnostic");
    await page.getByRole("button", { name: "Run Trace" }).click();
    await expect(page.getByText("Calibrated interpretation", { exact: true })).toBeVisible();
    await expect(page.getByText("Original trace result", { exact: true })).toBeVisible();
    await expect(page).toHaveURL(/trace_run_id=/);
    await page.getByRole("tab", { name: "Ordered Paths" }).click();
    await expect(page.getByText("Ordered path", { exact: true })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("C:\\");
  });

  test("compatibility explorer accepts vertical query filters", async ({ page }) => {
    await page.goto("/utility-assets?vertical=telecom_fiber");
    await expect(page.getByRole("tab", { name: "Telecom/Fiber" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText("FIBER-NETWORK-HUB-001", { exact: true })).toBeVisible();
  });

  test("utility cards stack on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/utilities");
    const columns = await page.getByLabel("Utility workspaces").evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(" ").length);
    expect(columns).toBe(1);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });

  test("network trace has no mobile horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/utilities/telecom/network-trace");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });

  test("loads electric and telecom Proposed Edit workspaces through FastAPI", async ({ page }) => {
    await page.goto("/utilities/electric/proposed-edits");
    await expect(page.getByRole("heading", { name: "Electric Proposed Edits" })).toBeVisible();
    await expect(page.getByRole("button", { name: /E-EDIT-001 Connect missing conductor endpoint/ })).toBeVisible();
    await expect(page.getByText("This is a proposed data change, not a switching instruction.")).toBeVisible();
    await page.goto("/utilities/telecom/proposed-edits");
    await expect(page.getByRole("heading", { name: "Telecom Proposed Edits" })).toBeVisible();
    await expect(page.getByRole("button", { name: /T-EDIT-001/ })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("C:\\");
  });

  test("loads electric and telecom Work Order workspaces through FastAPI", async ({ page }) => {
    await page.goto("/utilities/electric/work-orders");
    await expect(page.getByRole("heading", { name: "Electric Work Orders" })).toBeVisible();
    await expect(page.getByRole("button", { name: /E-WO-001/ })).toBeVisible();
    await expect(page.getByText("Device-state review is data verification, not a switching instruction or outage response.")).toBeVisible();
    await page.goto("/utilities/telecom/work-orders");
    await expect(page.getByRole("heading", { name: "Telecom Work Orders" })).toBeVisible();
    await expect(page.getByRole("button", { name: /T-WO-001/ })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("C:\\");
  });

  test("upload workflow keeps metadata before local package selection", async ({ page }) => {
    await page.goto("/data-sources/upload");
    const body = await page.locator("main").innerText();
    expect(body.indexOf("Source Information")).toBeLessThan(body.indexOf("Select Source Package"));
    expect(body.indexOf("Select Source Package")).toBeLessThan(body.indexOf("Review Submission"));
    await expect(page.getByText("NOT UPLOADED").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Complete required information" })).toBeDisabled();
  });

  test("Raw browser separates packages, layers, duplicate attempts, and test records", async ({ page }) => {
    await page.goto("/data-sources?stage=raw");
    await expect(page.getByText("Raw registered sources")).toBeVisible();
    await expect(page.getByRole("cell", { name: "103106 spatial records; 0 table rows" })).toBeVisible();
    await expect(page.getByText("Synthetic Upload Workflow Check")).toHaveCount(0);

    await page.getByRole("button", { name: "Registered Layers" }).click();
    await page.getByRole("button", { name: "WSACC_Manholes26" }).click();
    await expect(page.getByRole("definition").filter({ hasText: "WSACC_Manholes26" })).toBeVisible();

    await page.getByRole("button", { name: "Duplicates" }).click();
    await expect(page.getByText("Duplicate Detected", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "View Prior Submission" })).toHaveCount(2);

    await page.getByRole("button", { name: "All Raw" }).click();
    await page.getByLabel("Show Test Records").check();
    await expect(page.getByText("Synthetic Upload Workflow Check")).toBeVisible();
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

    test(`Utility Assets has no body horizontal overflow at ${viewport.width}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/utility-assets");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      expect(overflow).toBe(false);
    });

    test(`Utility workspaces have no body horizontal overflow at ${viewport.width}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/utilities/electric/assets");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      expect(overflow).toBe(false);
    });

    test(`Connectivity QA has no body horizontal overflow at ${viewport.width}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/utilities/telecom/connectivity-qa");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      expect(overflow).toBe(false);
    });
  }
});
