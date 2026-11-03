import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/**
 * Automated accessibility audit with axe-core.
 *
 * Scope: WCAG 2.0/2.1/2.2 A and AA rules. Serious and critical violations fail the
 * build; moderate and minor ones are printed so they are visible without pretending
 * they are release blockers. This runs against the real server, where pages have
 * data, not against the empty static shell.
 */

const ROUTES = ["/", "/lab", "/models", "/sources", "/settings", "/about", "/does-not-exist"];

for (const route of ROUTES) {
  test(`axe finds no serious or critical violations on ${route}`, async ({ page }) => {
    await page.goto(route);
    await page.locator("h1").first().waitFor({ timeout: 30_000 });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();

    const blocking = results.violations.filter(
      (violation) => violation.impact === "serious" || violation.impact === "critical",
    );
    const notes = results.violations.filter(
      (violation) => violation.impact !== "serious" && violation.impact !== "critical",
    );
    if (notes.length > 0) {
      console.log(
        `[a11y:${route}] non-blocking: ` +
          notes.map((violation) => `${violation.id} (${violation.impact})`).join(", "),
      );
    }
    expect(
      blocking.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        help: violation.help,
        nodes: violation.nodes.slice(0, 3).map((node) => node.target.join(" ")),
      })),
    ).toEqual([]);
  });
}
