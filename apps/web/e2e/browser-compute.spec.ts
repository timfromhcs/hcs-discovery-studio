import { test, expect } from "@playwright/test";

/**
 * The browser-chemistry panel is the reason the local Content-Security-Policy has to
 * allow WebAssembly and Emscripten embind's generated bindings. This test runs the
 * panel against the *served* app, so a CSP regression (for example dropping
 * 'wasm-unsafe-eval' or 'unsafe-eval') fails here instead of only in a manual check.
 */
test("RDKit WebAssembly self-test runs under the application CSP", async ({ page }) => {
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.goto("/settings");
  await page.getByRole("button", { name: "Run self-test" }).click();
  await expect(page.getByText("WebAssembly compute verified")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("CC(=O)Oc1ccccc1C(=O)O", { exact: false })).toBeVisible();
  await expect(page.getByText("WebAssembly self-test failed")).toHaveCount(0);
  expect(failures).toEqual([]);
});
