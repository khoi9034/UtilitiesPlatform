import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const routes = ["/", "/utilities", "/utilities/electric", "/utilities/electric/assets", "/utilities/electric/connectivity-qa", "/utilities/electric/network-trace", "/utilities/electric/proposed-edits", "/utilities/electric/work-orders", "/utilities/telecom", "/utilities/telecom/assets", "/utilities/telecom/connectivity-qa", "/utilities/telecom/network-trace", "/utilities/telecom/proposed-edits", "/utilities/telecom/work-orders", "/utilities/water-wastewater", "/utilities/water-wastewater/assets", "/utilities/water-wastewater/mapping-plans", "/utilities/water-wastewater/connectivity-qa", "/utilities/water-wastewater/network-trace", "/utilities/water-wastewater/proposed-edits", "/utilities/water-wastewater/work-orders", "/command-center", "/asset-inventory", "/utility-assets", "/utility-assets/detail?asset_id=demo-electric_distribution-substation-1", "/data-health", "/network-intelligence", "/cad-intake", "/trust-pipeline", "/data-sources", "/data-sources/inventory", "/data-sources/upload", "/data-sources/submission", "/projects", "/maintenance", "/methodology"];
const basePath = process.env.DEMO_BASE_PATH ?? "";

test.setTimeout(120_000);

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

  test("runs synthetic connectivity QA and persists review decisions in sessionStorage", async ({ page }) => {
    await page.goto(`${basePath}/utilities/electric/connectivity-qa`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("All utility assets, QA findings, issue groups, and review decisions in this demo are synthetic and reset with the demo session.")).toBeVisible();
    await expect(page.getByRole("button", { name: /ELEC-001/ }).first()).toBeVisible();
    await page.getByRole("button", { name: /ELEC-001/ }).first().click();
    await expect(page.getByText("Consequence", { exact: true }).first()).toBeVisible();
    await page.getByLabel("Rationale").fill("Expected synthetic training condition.");
    await page.getByRole("button", { name: "Accept risk" }).click();
    await expect(page.getByText(/Group review updated/)).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-connectivity-qa-v1"))).toContain("accepted_risk");

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /ELEC-001/ }).first().click();
    await expect(page.getByText("Accepted Risk", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "All Technical Findings" }).click();
    await page.getByLabel("QA rule").selectOption("ELEC-001");
    await expect(page.getByRole("button", { name: /ELEC-001/ }).first()).toBeVisible();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Download safe summary" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("electric-connectivity-qa-summary.json");

    await page.goto(`${basePath}/utilities/telecom/connectivity-qa`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: /SHARED-004/ }).first()).toBeVisible();
    await page.getByRole("button", { name: "All Technical Findings" }).click();
    await page.getByLabel("QA rule").selectOption("TEL-001");
    await expect(page.getByRole("button", { name: /TEL-001/ }).first()).toBeVisible();
    await page.getByRole("button", { name: "Reset Demo Session" }).click();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-connectivity-qa-v1"))).toBeNull();
  });

  test("runs and restores a browser-only synthetic network trace", async ({ page }) => {
    await page.goto(`${basePath}/utilities/electric/network-trace`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/All utility assets, proposed changes, work orders, assignments/)).toBeVisible();
    await page.getByLabel("QA policy").selectOption("diagnostic");
    await page.getByRole("button", { name: "Run Trace" }).click();
    await expect(page.getByText("Calibrated interpretation", { exact: true })).toBeVisible();
    await expect(page.getByText("Why this result", { exact: true })).toBeVisible();
    await expect(page.getByText("Original trace result", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-network-trace-v1"))).toContain("ELEC-TRACE-001");
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-network-trace-calibration-v1"))).toContain("network-trace-calibration-v1");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Download Calibrated Receipt" }).click(),
    ]);
    expect(download.suggestedFilename()).toContain("calibrated-safe-trace-receipt.json");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByText("Calibrated interpretation", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Ordered Paths" }).click();
    await expect(page.getByText("Ordered path", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Primary Issues" }).click();
    await expect(page.getByText("Primary issues and selected-path conditions", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Background Conditions" }).click();
    await expect(page.getByText("Background Network Conditions", { exact: true })).toBeVisible();

    await page.goto(`${basePath}/utilities/telecom/network-trace`, { waitUntil: "domcontentloaded" });
    await expect(page.getByLabel("Trace type")).toHaveValue("TEL-TRACE-001");
    await page.getByLabel("QA policy").selectOption("diagnostic");
    await page.getByRole("button", { name: "Run Trace" }).click();
    await expect(page.getByText("Calibrated interpretation", { exact: true })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("C:\\");
    await page.getByRole("button", { name: "Reset Demo Session" }).click();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-network-trace-v1"))).toBeNull();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-network-trace-calibration-v1"))).toBeNull();
  });

  test("uses synthetic water and wastewater assets with no backend", async ({ page }) => {
    await page.goto(`${basePath}/utilities/water-wastewater/assets`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("WATER-TREATMENT-FACILITY-001", { exact: true })).toBeVisible();
    await page.getByRole("navigation", { name: "Water and wastewater system" }).getByRole("link", { name: "Wastewater" }).click();
    await expect(page).toHaveURL(/system=wastewater/);
    await expect(page.getByText("WW-MANHOLE-001", { exact: true })).toBeVisible();

    await page.goto(`${basePath}/utilities/water-wastewater/connectivity-qa`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: /WATER-002/ }).first()).toBeVisible();
    await page.goto(`${basePath}/utilities/water-wastewater/network-trace?system=wastewater`, { waitUntil: "domcontentloaded" });
    await expect(page.getByLabel("Trace type")).toHaveValue("WW-TRACE-001");
    await page.getByLabel("QA policy").selectOption("diagnostic");
    await page.getByRole("button", { name: "Run Trace" }).click();
    await expect(page.getByText("Calibrated interpretation", { exact: true })).toBeVisible();
    await expect(page.getByText(/not a hydraulic simulation/i).first()).toBeVisible();

    await page.goto(`${basePath}/utilities/water-wastewater/proposed-edits?system=wastewater`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: /WW-EDIT-001/ })).toBeVisible();
    await page.goto(`${basePath}/utilities/water-wastewater/work-orders?system=wastewater`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("button", { name: /WW-WO-001/ })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("C:\\");
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
    await Promise.all([
      page.waitForURL("**/data-sources?stage=raw"),
      page.getByRole("link", { name: "View in Raw Stage" }).first().click(),
    ]);
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
    writeFileSync(join(gdbRoot, "_gdb.1234.sr.lock"), "lock");

    await page.goto(`${basePath}/data-sources/upload`, { waitUntil: "domcontentloaded" });
    await page.getByRole("radio", { name: "Choose FileGDB Folder" }).check();
    await page.locator("input[webkitdirectory]").setInputFiles(gdbRoot);

    await expect(page.getByText("Synthetic_Selected_Source.gdb").first()).toBeVisible();
    await expect(page.getByText(/2 of 50K allowed/).first()).toBeVisible();
    await expect(page.getByText("File geodatabase folder").first()).toBeVisible();
    await expect(page.getByText("Passed browser precheck").first()).toBeVisible();
    await expect(page.getByText(/Recognized transient files will be omitted/).first()).toBeVisible();
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

  test("runs synthetic automated review without backend requests", async ({ page }) => {
    await page.goto(`${basePath}/data-sources/submission`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Run Automated Review" }).click();
    await expect(page.getByText("Automation Receipt")).toBeVisible();
    await expect(page.getByText("Validate Inspection")).toBeVisible();
    await expect(page.getByText("Automation results are synthetic and reset with the demo session.")).toBeVisible();
    await expect(page.getByText("Source Review Automation V1", { exact: false })).toHaveCount(0);
    await expect(page.getByText("0 created by automation")).toBeVisible();
    await page.getByRole("button", { name: "View Approved Classifications" }).click();
    await expect(page.getByRole("tab", { name: "Approved Classifications" })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Automation" }).click();
    await page.getByRole("button", { name: /Review Exceptions/ }).click();
    await expect(page.getByRole("heading", { name: "Owner Uncertainty" }).first()).toBeVisible();
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

  test("explores synthetic assets and simulates governed creation", async ({ page }) => {
    await page.goto(`${basePath}/utility-assets`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("All utility assets, relationships, and canonicalization results in this demo are synthetic and reset with the demo session.")).toBeVisible();
    await page.getByRole("tab", { name: "Electric Distribution" }).click();
    await expect(page.getByText("ELEC-SUBSTATION-001", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Telecom/Fiber" }).click();
    await expect(page.getByText("FIBER-NETWORK-HUB-001", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Canonicalization Plans" }).click();
    await expect(page.getByText("Electric Distribution to Transformer")).toBeVisible();
    await page.getByRole("button", { name: "Create canonical assets" }).first().click();
    await expect(page.getByText(/Creation simulation complete: 3 assets created/)).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-canonical-assets-v1"))).toContain("DEMO-ELECTRIC-PLAN");
  });

  test("reviews synthetic Water and Wastewater mappings without backend requests", async ({ page }) => {
    await page.goto(`${basePath}/utilities/water-wastewater/mapping-plans`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText("DEMO-WATER-MAIN-PLAN")).toBeVisible();
    await expect(page.getByText("DEMO-WW-GRAVITY-PLAN")).toBeVisible();
    await page.getByRole("button", { name: "Review" }).first().click();
    await page.getByRole("button", { name: /Field Mapping/ }).click();
    await page.getByLabel("Canonical field for SOURCE_ID").fill("display_name");
    await page.getByRole("button", { name: "Save field mappings" }).click();
    await page.getByRole("button", { name: /Value Mapping/ }).click();
    await page.getByLabel("Target value for MATERIAL PVC").fill("ductile_iron");
    await page.getByRole("button", { name: "Save value mappings" }).click();
    await page.getByRole("navigation", { name: "Mapping review steps" }).getByRole("button", { name: /Preview/ }).click();
    await page.getByRole("button", { name: "Generate safe preview" }).click();
    await expect(page.getByText("Preview only - no canonical asset has been created.").first()).toBeVisible();
    await page.getByRole("navigation", { name: "Mapping review steps" }).getByRole("button", { name: /Review/ }).click();
    await page.getByRole("button", { name: "Approve Mapping Plan" }).click();
    await expect(page.getByText(/canonical asset creation remains disabled/i).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Canonical Assets" })).toBeDisabled();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-mapping-review-v1"))).toContain("approved_plan");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByText("Approved Plan")).toBeVisible();
    await page.getByRole("button", { name: "Reset Demo Session" }).click();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-mapping-review-v1"))).toBeNull();
  });

  test("selects synthetic vertical workspaces without API requests", async ({ page }) => {
    await page.goto(`${basePath}/utilities`, { waitUntil: "domcontentloaded" });
    await page.getByRole("link", { name: "Open Electric Distribution workspace" }).click();
    await expect(page).toHaveURL(new RegExp(`${basePath}/utilities/electric/?$`));
    await expect(page.getByText("71", { exact: true }).first()).toBeVisible();
    await page.getByRole("navigation", { name: "Electric Distribution workspace" }).getByRole("link", { name: "Electric Assets", exact: true }).click();
    await expect(page.getByText("ELEC-SUBSTATION-001", { exact: true })).toBeVisible();
    await expect(page.getByText("FIBER-NETWORK-HUB-001", { exact: true })).toHaveCount(0);
    await page.getByRole("navigation", { name: "Switch utility workspace" }).getByRole("link", { name: "Telecom" }).click();
    await expect(page).toHaveURL(new RegExp(`${basePath}/utilities/telecom/?$`));
    await expect(page.getByRole("heading", { name: "Telecom/Fiber", level: 1 })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("C:\\");
  });

  test("shows synthetic asset detail and relationship evidence", async ({ page }) => {
    await page.goto(`${basePath}/utility-assets/detail?asset_id=demo-telecom_fiber-splice_closure-1`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "FIBER-SPLICE-CLOSURE-001" })).toBeVisible();
    await expect(page.getByText("Source lineage")).toBeVisible();
    await expect(page.getByText("Provisional / Rule Inferred")).toBeVisible();
    await expect(page.locator("body")).not.toContainText("C:\\");
  });

  test("reviews and approves a synthetic proposed change without API requests", async ({ page }) => {
    await page.goto(`${basePath}/utilities/electric/proposed-edits`, { waitUntil: "domcontentloaded" });
    await expect(page.getByText(/All utility assets, proposed changes, work orders, assignments/)).toBeVisible();
    await page.getByRole("button", { name: /E-EDIT-001/ }).click();
    await page.getByRole("button", { name: "Compare" }).click();
    await expect(page.getByText("Connectivity QA comparison")).toBeVisible();
    await expect(page.getByText("Network Trace comparison")).toBeVisible();
    await page.getByRole("button", { name: "Review" }).click();
    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.getByRole("button", { name: "Start Review" }).click();
    await page.getByRole("button", { name: "Approval" }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Approve Change Plan" }).click();
    await expect(page.getByText("Approved plan - not implemented in any operational utility system.")).toBeVisible();
    await page.getByRole("button", { name: "Package" }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Generate safe package" }).click();
    await expect(page.getByText(/"executable": false/)).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-proposed-edits-v1"))).toContain('"approval_status":"approved"');
  });

  test("runs a synthetic work order through release and three-state validation without API requests", async ({ page }) => {
    await page.goto(`${basePath}/utilities/electric/work-orders`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Electric Work Orders" })).toBeVisible();
    await expect(page.getByText(/All utility assets, proposed changes, work orders, assignments/)).toBeVisible();
    await page.getByRole("button", { name: /E-WO-001/ }).click();
    await page.getByRole("button", { name: "Release" }).click();
    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.getByRole("button", { name: "Start Review" }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Approve for Release" }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Release Work" }).click();
    await page.getByRole("button", { name: "Implementation" }).click();
    await page.getByRole("button", { name: "Start Work" }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Record Implementation" }).click();
    await expect(page.getByText("Recorded implementation is synthetic and has not changed the canonical or source network.")).toBeVisible();
    await page.getByRole("button", { name: "Validate" }).click();
    await page.getByRole("button", { name: "Run Conformance" }).click();
    await page.getByRole("button", { name: "Run Post-Work QA" }).click();
    await page.getByRole("button", { name: "Run Post-Work Traces" }).click();
    await expect(page.getByText("Baseline / approved plan / recorded implementation")).toBeVisible();
    expect(await page.evaluate(() => sessionStorage.getItem("utilities-platform-demo-work-orders-v1"))).toContain('"status":"simulated_overlay_only"');

    await page.goto(`${basePath}/utilities/telecom/work-orders`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /T-WO-001/ }).click();
    await page.getByRole("button", { name: "Closeout" }).click();
    await page.getByRole("button", { name: "View Completion Receipt" }).click();
    await expect(page.getByText(/"receipt_version": "work-order-completion-receipt-v1"/)).toBeVisible();
  });
});
