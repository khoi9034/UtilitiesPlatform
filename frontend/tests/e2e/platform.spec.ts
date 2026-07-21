import { expect, test } from "@playwright/test";

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

  for (const viewport of viewports) {
    test(`no body horizontal overflow at ${viewport.width}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto("/data-health");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      expect(overflow).toBe(false);
    });
  }
});
