#!/usr/bin/env node
/**
 * Capture the documentation screenshots from a running local installation.
 *
 * Start the application first, then run from the repository root:
 *
 *   uv run hcs-discovery serve --port 8787
 *   node apps/web/scripts/capture_screenshots.mjs
 *
 * The script discovers the first project, its latest successful run and a
 * compound through the public API. It never fabricates UI state: every image is
 * a Playwright capture of the real application.
 */

import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const baseURL = process.env.HCS_BASE_URL ?? "http://127.0.0.1:8787";
const outputDir = join(repoRoot, "docs", "screenshots");

async function getJson(path) {
  const response = await fetch(new URL(path, baseURL));
  if (!response.ok) throw new Error(`GET ${path} failed with ${response.status}`);
  return response.json();
}

async function discover() {
  const projects = await getJson("/api/v1/projects?limit=1");
  const project = projects.items?.[0];
  if (!project) throw new Error("No project found. Run the demo import before capturing screenshots.");

  const runs = await getJson(`/api/v1/runs?project_id=${encodeURIComponent(project.id)}&limit=50`);
  const run = runs.items?.find((item) => item.status === "succeeded") ?? runs.items?.[0];
  if (!run) throw new Error("No run found. Execute the demo workflow before capturing screenshots.");

  const compounds = await getJson(`/api/v1/projects/${project.id}/compounds?limit=100`);
  const compound =
    compounds.items?.find((item) => item.name === "Naproxen") ?? compounds.items?.[0];
  if (!compound) throw new Error("No compound found. Import a library before capturing screenshots.");

  return { project, run, compound };
}

async function main() {
  const { project, run, compound } = await discover();
  console.log(`project=${project.id} run=${run.id} compound=${compound.id}`);

  const projectPath = `/projects/${project.id}`;
  const captures = [
    { name: "workspace-dark", path: "/", theme: "dark" },
    { name: "workspace-narrow", path: "/", theme: "light", narrow: true },
    { name: "project-light", path: projectPath, theme: "light" },
    { name: "project-dark", path: projectPath, theme: "dark" },
    { name: "project-narrow", path: projectPath, theme: "light", narrow: true },
    { name: "library-light", path: `${projectPath}/library`, theme: "light" },
    { name: "library-dark", path: `${projectPath}/library`, theme: "dark" },
    { name: "library-narrow", path: `${projectPath}/library`, theme: "light", narrow: true },
    { name: "workflows-light", path: `${projectPath}/workflows`, theme: "light" },
    { name: "workflows-dark", path: `${projectPath}/workflows`, theme: "dark" },
    {
      name: "editor-light",
      path: `${projectPath}/workflows/new?template=triage-basic`,
      theme: "light",
    },
    {
      name: "workflow-editor-dark",
      path: `${projectPath}/workflows/new?template=triage-basic`,
      theme: "dark",
    },
    {
      name: "workflow-editor-narrow",
      path: `${projectPath}/workflows/new?template=triage-basic`,
      theme: "light",
      narrow: true,
    },
    { name: "runs-light", path: `${projectPath}/runs`, theme: "light" },
    { name: "run-monitor-light", path: `/runs/${run.id}`, theme: "light" },
    { name: "run-monitor-narrow", path: `/runs/${run.id}`, theme: "light", narrow: true },
    { name: "results-fixed-light", path: `/runs/${run.id}/results`, theme: "light" },
    { name: "results-dark", path: `/runs/${run.id}/results`, theme: "dark" },
    { name: "results-narrow", path: `/runs/${run.id}/results`, theme: "light", narrow: true },
    { name: "compound-light", path: `/compounds/${compound.id}`, theme: "light" },
    { name: "compound-dark", path: `/compounds/${compound.id}`, theme: "dark" },
    { name: "models-light", path: "/models", theme: "light" },
    { name: "models-narrow", path: "/models", theme: "light", narrow: true },
    { name: "sources-light", path: "/sources", theme: "light" },
    { name: "settings-light", path: "/settings", theme: "light" },
    { name: "settings-narrow", path: "/settings", theme: "light", narrow: true },
    { name: "about-light", path: "/about", theme: "light" },
    { name: "notfound-light", path: "/missing-page", theme: "light" },
  ];

  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch();
  const problems = [];

  for (const capture of captures) {
    const context = await browser.newContext({
      viewport: capture.narrow ? { width: 390, height: 844 } : { width: 1440, height: 900 },
      deviceScaleFactor: 1,
      colorScheme: capture.theme,
    });
    await context.addInitScript((theme) => {
      window.localStorage.setItem("hcs.theme", theme);
    }, capture.theme);
    const page = await context.newPage();
    page.on("console", (message) => {
      if (message.type() === "error") problems.push(`${capture.name}: ${message.text()}`);
    });
    await page.goto(new URL(capture.path, baseURL).toString(), { waitUntil: "domcontentloaded" });
    await page.waitForSelector("main", { timeout: 15_000 });
    await page
      .waitForFunction(() => !document.querySelector(".skeleton"), null, { timeout: 15_000 })
      .catch(() => {});
    await page.waitForTimeout(1_200);
    const file = join(outputDir, `${capture.name}.png`);
    await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
    console.log(`captured ${capture.name}`);
    await context.close();
  }

  await browser.close();

  if (problems.length > 0) {
    console.error("\nConsole errors observed:");
    for (const problem of problems) console.error(`  - ${problem}`);
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
