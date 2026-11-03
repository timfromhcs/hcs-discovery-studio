import { spawn, type ChildProcess } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

/**
 * Offline after the first visit.
 *
 * Playwright's `context.setOffline()` does not reliably stop a service worker's own
 * network access, so this spec takes a static preview server up, uses the lab, kills
 * the server and reloads. A connection-refused reload is the real thing: if the
 * shell, the bundle and the RDKit WebAssembly module were not cached, the page is
 * empty and the test fails.
 */
const webRoot = fileURLToPath(new URL("..", import.meta.url));
const PORT = 8793;
const ORIGIN = `http://127.0.0.1:${PORT}`;

let server: ChildProcess | null = null;

async function waitForServer(url: string, timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`preview server did not start at ${url}`);
}

test.beforeAll(async () => {
  server = spawn(
    process.execPath,
    [join(webRoot, "node_modules", "vite", "bin", "vite.js"), "preview", "--port", String(PORT), "--strictPort", "--host", "127.0.0.1"],
    { cwd: webRoot, stdio: "ignore" },
  );
  await waitForServer(`${ORIGIN}/`);
});

test.afterAll(() => {
  server?.kill();
  server = null;
});

test("the lab opens and scores after the server is gone", async ({ page, request }) => {
  // Static assets first: the manifest is installable metadata, and the worker must
  // never cache the API.
  const manifest = await request.get(`${ORIGIN}/manifest.webmanifest`);
  expect(manifest.status()).toBe(200);
  expect((await manifest.json()).name).toBe("HCS Discovery Studio");
  const worker = await request.get(`${ORIGIN}/sw.js`);
  expect(worker.status()).toBe(200);
  expect(await worker.text()).toContain("/api/");

  await page.goto(`${ORIGIN}/lab`);
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller), null, { timeout: 30_000 });

  // Use the lab once so the RDKit WebAssembly module goes through the worker.
  await page.getByLabel("Library file").setInputFiles({
    name: "library.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("name,smiles\nBenzene,c1ccccc1\nAspirin,CC(=O)Oc1ccccc1C(=O)O\nEthanol,CCO\n", "utf-8"),
  });
  await expect(page.getByText("3 structures imported in this browser")).toBeVisible({ timeout: 90_000 });
  await page.getByRole("button", { name: "Score library" }).click();
  await expect(page.getByText("Parity")).toBeVisible({ timeout: 90_000 });

  // Pull the plug: the origin is gone, not merely "emulated offline".
  server?.kill();
  server = null;
  await new Promise((resolve) => setTimeout(resolve, 1000));
  await expect
    .poll(async () => {
      try {
        await fetch(`${ORIGIN}/`);
        return "reachable";
      } catch {
        return "gone";
      }
    }, { timeout: 15_000 })
    .toBe("gone");

  await page.reload();
  await expect(page.getByRole("heading", { name: "Offline lab" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Restored from this device")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Score library" }).click();
  await expect(page.getByText("Parity")).toBeVisible({ timeout: 120_000 });
  await expect(page.locator("table").last().locator("tbody tr").first()).toContainText("Benzene");
});
