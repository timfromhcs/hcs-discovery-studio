import { chromium } from "@playwright/test";

const base = process.env.BASE_URL ?? "http://127.0.0.1:4173";

const browser = await chromium.launch();
const page = await browser.newPage();
const consoleErrors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

await page.goto(`${base}/settings`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: /Run self-test/i }).click();

// The self-test loads the WASM and computes; wait for the verified badge.
await page.getByText("WebAssembly compute verified").waitFor({ timeout: 30000 });

const rdkitVersion = await page.getByText("RDKit version").locator("..").locator("dd").textContent();
const mw = await page.getByText("Molecular weight").locator("..").locator("dd").textContent();
const smiles = await page.getByText("Canonical SMILES").locator("..").locator("dd").textContent();
const svgPresent = (await page.locator(".browser-chem-svg svg").count()) === 1;

console.log(JSON.stringify({ rdkitVersion, mw, smiles, svgPresent, consoleErrors }, null, 2));

await browser.close();
