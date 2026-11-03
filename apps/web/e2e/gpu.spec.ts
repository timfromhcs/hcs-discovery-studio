import { test, expect } from "@playwright/test";

// With HCS_E2E_WEBGPU=1 the test demands a real adapter and bit-exact parity (local release gate).
// Without it (CI runners have no GPU) it accepts the honest "unavailable" state, never a fake pass.
const requireGpu = process.env.HCS_E2E_WEBGPU === "1";

// Playwright's bundled headless Chromium exposes no hardware adapter; the system Chrome does.
test.use(
  requireGpu
    ? { channel: "chrome", launchOptions: { args: ["--enable-unsafe-webgpu", "--ignore-gpu-blocklist"] } }
    : {},
);

test("WebGPU Tanimoto benchmark reports parity before speed", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => console.log("[browser]", m.type(), m.text().slice(0, 300)));
  await page.goto("/settings");
  await page.getByRole("button", { name: "Run benchmark" }).click();
  const passed = page.getByText("Parity: bit-exact");
  const unavailable = page.getByText("WebGPU hardware not available");
  await expect(passed.or(unavailable)).toBeVisible({ timeout: 30_000 });
  if (requireGpu) {
    await expect(passed).toBeVisible();
    await expect(page.getByText("Speed-up (measured)")).toBeVisible();
  } else {
    await expect(page.getByText("Parity check failed")).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});
