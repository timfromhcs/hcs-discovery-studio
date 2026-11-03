import { expect, test } from "@playwright/test";

/**
 * The offline lab is the one part of the product that has to work with no backend at
 * all. This spec runs against `vite preview` (a static file server), so a regression
 * that silently starts depending on the API fails here.
 */
test.use({ baseURL: "http://127.0.0.1:8792" });

const LIBRARY = [
  "name,smiles",
  "Benzene,c1ccccc1",
  "Aspirin,CC(=O)Oc1ccccc1C(=O)O",
  "Ethanol,CCO",
  "Broken,not-a-smiles",
  "",
].join("\n");

test("offline lab imports, triages, scores and persists without a backend", async ({ page }) => {
  const errors: string[] = [];
  const labApiCalls: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const url = request.url();
    if (/\/api\/v1\/(datasets|similarity|runs)/.test(url)) labApiCalls.push(url);
  });

  await page.goto("/lab");
  await expect(page.getByRole("heading", { name: "Offline lab" })).toBeVisible();

  await page.getByLabel("Library file").setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(LIBRARY, "utf-8"),
  });

  // Three structures parse; the fourth is rejected and counted, not silently dropped.
  await expect(page.getByText("3 structures imported in this browser")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("Rejected rows")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Broken" })).toHaveCount(0);

  // WCAG: the result is announced and receives focus, so keyboard and screen-reader
  // users land on the outcome instead of guessing that something happened.
  const importRegion = page.getByTestId("lab-import-result");
  await expect(importRegion).toHaveAttribute("aria-live", "polite");
  await expect(importRegion).toBeFocused();

  // Triage and ranking run on RDKit WebAssembly output.
  await expect(page.getByText(/of 3 pass every rule/)).toBeVisible();
  await expect(page.getByRole("cell", { name: "3", exact: true })).toBeVisible();

  // Similarity runs through the shared kernel or its CPU reference.
  await page.getByRole("button", { name: "Score library" }).click();
  await expect(page.getByText("Parity")).toBeVisible({ timeout: 90_000 });
  // The top hit must be the query molecule itself, not whichever row ranks highest
  // by composite score: similarity scores are indexed by import order.
  const topSimilarityRow = page.locator("table").last().locator("tbody tr").first();
  await expect(topSimilarityRow).toContainText("Benzene");
  await expect(topSimilarityRow).toContainText("1.0000");

  // The stored copy survives a reload: IndexedDB, not a server session.
  await page.reload();
  await expect(page.getByText("Restored from this device")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("3 structures imported in this browser")).toHaveCount(0);

  expect(labApiCalls).toEqual([]);
  expect(errors).toEqual([]);
});

test("offline lab fits a 360 px phone without horizontal scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/lab");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  const choose = page.getByRole("button", { name: "Choose file" });
  await expect(choose).toBeVisible();
  // WCAG 2.2 target size and focus visibility under a sticky header.
  const box = await choose.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(43.5);
  const scrollPadding = await page.evaluate(() => getComputedStyle(document.documentElement).scrollPaddingTop);
  expect(parseFloat(scrollPadding)).toBeGreaterThan(0);
});

test("offline lab deletes its stored copy", async ({ page }) => {
  await page.goto("/lab");
  await page.getByLabel("Library file").setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(LIBRARY, "utf-8"),
  });
  await expect(page.getByText("3 structures imported in this browser")).toBeVisible({ timeout: 90_000 });
  await page.getByRole("button", { name: "Delete stored copy" }).click();
  await expect(page.getByText("Nothing imported yet", { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Restored from this device")).toHaveCount(0);
});
