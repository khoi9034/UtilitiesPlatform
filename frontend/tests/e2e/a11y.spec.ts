import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.setTimeout(120_000);

for (const route of ["/", "/utilities", "/utilities/electric", "/utilities/electric/assets", "/utilities/telecom", "/utilities/telecom/assets", "/data-health", "/trust-pipeline", "/data-sources/inventory", "/data-sources/upload", "/utility-assets", "/utility-assets/detail?asset_id=demo-electric_distribution-substation-1"]) {
  test(`axe critical checks on ${route}`, async ({ page }) => {
    await page.goto(route);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(results.violations.filter((violation) => violation.impact === "critical")).toEqual([]);
  });
}
