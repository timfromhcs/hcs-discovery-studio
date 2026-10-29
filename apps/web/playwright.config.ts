import { defineConfig } from "@playwright/test";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

// The web server starts before globalSetup, so a shared directory cannot be wiped
// safely once the server holds the database open. Give every invocation a fresh
// directory instead; workers inherit it through the environment.
process.env.HCS_E2E_DATA_DIR ??= join(repoRoot, ".e2e-data", `run-${Date.now()}`);

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8791",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  webServer: {
    command: "uv run hcs-discovery serve --port 8791",
    cwd: repoRoot,
    url: "http://127.0.0.1:8791/api/v1/health",
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      HCS_DATA_DIR: process.env.HCS_E2E_DATA_DIR,
      HCS_NETWORK_POLICY: "local",
    },
  },
});
