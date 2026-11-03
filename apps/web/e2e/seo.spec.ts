import { expect, test } from "@playwright/test";

/**
 * SEO and metadata are part of the product surface: a single-page app serves one
 * document, so the tags have to be right after navigation, not only at load.
 */
test.use({ baseURL: "http://127.0.0.1:8792" });

test("per-route titles, descriptions and canonical URLs are set", async ({ page }) => {
  await page.goto("/lab");
  await expect(page).toHaveTitle(/Offline lab/);
  const description = await page.locator('meta[name="description"]').getAttribute("content");
  expect(description ?? "").toContain("browser");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/lab$/);
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", /Offline lab/);

  await page.goto("/models");
  await expect(page).toHaveTitle(/Model registry/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/models$/);
});

test("the document ships structured data and a sitemap", async ({ page, request }) => {
  await page.goto("/");
  const jsonLd = await page.locator('script[type="application/ld+json"]').first().textContent();
  const data = JSON.parse(jsonLd ?? "{}");
  expect(data["@type"]).toBe("SoftwareApplication");
  expect(data.name).toBe("HCS Discovery Studio");

  const robots = await request.get("/robots.txt");
  expect(robots.status()).toBe(200);
  expect(await robots.text()).toContain("Sitemap:");

  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.status()).toBe(200);
  const xml = await sitemap.text();
  expect(xml).toContain("<urlset");
  expect(xml).toContain("/lab");
});

test("an unknown route is a real 404 page, not a blank shell", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page.getByRole("heading", { name: /does not exist/i })).toBeVisible();
  await expect(page).toHaveTitle(/not found/i);
});
