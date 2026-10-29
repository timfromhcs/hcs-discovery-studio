#!/usr/bin/env node
/**
 * Visual and accessibility QA sweep against a running local installation.
 *
 * Opens every route at 320, 390, 768, 1280 and 1440 px in light and dark themes,
 * saves a full-page screenshot of each and checks automatically for:
 *   - horizontal page overflow and elements extending past the viewport
 *     (content inside an element that scrolls horizontally on purpose is allowed)
 *   - console errors, uncaught page errors and failed same-origin requests
 *   - buttons, links and form controls without an accessible name
 *   - images without alt text
 *
 * Start the app with synthetic data first, then run from the repository root:
 *
 *   HCS_BASE_URL=http://127.0.0.1:8787 node apps/web/scripts/visual_qa.mjs [outputDir]
 *
 * Screenshots and qa-report.json go to outputDir (default
 * apps/web/test-results/visual-qa, which is git-ignored). The exit code is
 * non-zero when any automatic check fails. Screenshots still need to be looked at:
 * these checks do not judge layout quality.
 */

import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const baseURL = process.env.HCS_BASE_URL ?? "http://127.0.0.1:8787";
const outputDir = process.argv[2] ?? join(webRoot, "test-results", "visual-qa");
const WIDTHS = [320, 390, 768, 1280, 1440];
const THEMES = ["light", "dark"];

async function getJson(path) {
  const response = await fetch(new URL(path, baseURL));
  if (!response.ok) throw new Error(`GET ${path} failed with ${response.status}`);
  return response.json();
}

async function routes() {
  const projects = (await getJson("/api/v1/projects?limit=50")).items ?? [];
  const project = projects.find((p) => p.compound_count > 0) ?? projects[0];
  if (!project) throw new Error("No project found. Create synthetic QA data first.");
  const empty = projects.find((p) => p.id !== project.id);
  const runs = (await getJson(`/api/v1/runs?project_id=${encodeURIComponent(project.id)}&limit=50`)).items ?? [];
  const run = runs.find((r) => r.status === "succeeded") ?? runs[0];
  const compound = ((await getJson(`/api/v1/projects/${project.id}/compounds?limit=5`)).items ?? [])[0];
  const workflows = ((await getJson(`/api/v1/projects/${project.id}/workflows`)).items ?? []);
  const p = `/projects/${project.id}`;
  const list = [
    ["workspace", "/"],
    ["project", p],
    ["library", `${p}/library`],
    ["workflows", `${p}/workflows`],
    ["editor-template", `${p}/workflows/new?template=triage-basic`],
    ["runs", `${p}/runs`],
    ["models", "/models"],
    ["sources", "/sources"],
    ["settings", "/settings"],
    ["about", "/about"],
    ["not-found", "/missing-page"],
    ["unknown-run", "/runs/run_does_not_exist"],
  ];
  if (empty) list.push(["project-empty", `/projects/${empty.id}`]);
  if (workflows[0]) list.push(["editor-saved", `${p}/workflows/${workflows[0].id}`]);
  if (run) list.push(["run-monitor", `/runs/${run.id}`], ["results", `/runs/${run.id}/results`]);
  if (compound) list.push(["compound", `/compounds/${compound.id}`]);
  return list;
}

/** Runs in the page: layout and accessibility checks. */
function inspectPage() {
  const width = document.documentElement.clientWidth;
  const issues = [];
  const scrollWidth = document.scrollingElement.scrollWidth;
  if (scrollWidth > width + 1) issues.push(`page scrolls horizontally: ${scrollWidth}px > ${width}px`);

  const scrollsX = (el) => {
    for (let node = el.parentElement; node && node !== document.body; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (["auto", "scroll"].includes(style.overflowX) && node.scrollWidth > node.clientWidth) return true;
    }
    return false;
  };
  const describe = (el) =>
    `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${el.className && typeof el.className === "string" ? `.${el.className.trim().split(/\s+/).slice(0, 2).join(".")}` : ""}`;

  const overflowing = [];
  for (const el of document.body.querySelectorAll("*")) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    const style = getComputedStyle(el);
    if (style.visibility === "hidden" || style.position === "fixed") continue;
    if (rect.right > width + 1 && !scrollsX(el)) overflowing.push(`${describe(el)} right=${Math.round(rect.right)}`);
  }
  if (overflowing.length) issues.push(`elements past viewport: ${overflowing.slice(0, 5).join(", ")}${overflowing.length > 5 ? ` (+${overflowing.length - 5})` : ""}`);

  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== "hidden";
  };
  const name = (el) => {
    const labelledby = el.getAttribute("aria-labelledby");
    const fromIds = labelledby
      ? labelledby.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? "").join(" ")
      : "";
    const labels = el.labels ? [...el.labels].map((l) => l.textContent).join(" ") : "";
    return (el.getAttribute("aria-label") || fromIds || labels || el.getAttribute("title") || el.textContent || el.getAttribute("alt") || el.getAttribute("placeholder") || "")
      .trim();
  };
  const unnamed = [];
  for (const el of document.querySelectorAll("button, a[href], input:not([type=hidden]), select, textarea, [role=button]")) {
    if (!visible(el)) continue;
    const imgAlt = [...el.querySelectorAll("img[alt], svg[aria-label]")].map((i) => i.getAttribute("alt") || i.getAttribute("aria-label")).join("");
    if (!name(el) && !imgAlt) unnamed.push(describe(el));
  }
  if (unnamed.length) issues.push(`controls without accessible name: ${unnamed.slice(0, 5).join(", ")}`);
  const noAlt = [...document.querySelectorAll("img")].filter((img) => visible(img) && !img.hasAttribute("alt"));
  if (noAlt.length) issues.push(`images without alt: ${noAlt.length}`);
  return issues;
}

async function main() {
  const targets = await routes();
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch();
  const report = [];
  let failures = 0;

  for (const [routeName, path] of targets) {
    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const context = await browser.newContext({
          viewport: { width, height: 900 },
          deviceScaleFactor: 1,
          colorScheme: theme,
          reducedMotion: "reduce",
        });
        await context.addInitScript((value) => window.localStorage.setItem("hcs.theme", value), theme);
        const page = await context.newPage();
        const problems = [];
        page.on("console", (m) => {
          // The unknown-run route deliberately triggers a 404 from the API.
          if (m.type() === "error" && !(routeName === "unknown-run" && m.text().includes("404"))) {
            problems.push(`console: ${m.text().slice(0, 200)}`);
          }
        });
        page.on("pageerror", (e) => problems.push(`pageerror: ${e.message.slice(0, 200)}`));
        page.on("requestfailed", (r) => {
          if (r.url().startsWith(baseURL)) problems.push(`requestfailed: ${r.url()} ${r.failure()?.errorText ?? ""}`);
        });
        await page.goto(new URL(path, baseURL).toString(), { waitUntil: "networkidle" });
        await page.waitForSelector("main", { timeout: 15_000 });
        await page.waitForFunction(() => !document.querySelector(".skeleton"), null, { timeout: 15_000 }).catch(() => {});
        problems.push(...(await page.evaluate(inspectPage)));
        const file = `${routeName}-${theme}-${width}.png`;
        await page.screenshot({ path: join(outputDir, file), fullPage: true, animations: "disabled" });
        report.push({ route: routeName, path, theme, width, screenshot: file, problems });
        if (problems.length) {
          failures += 1;
          console.log(`FAIL ${routeName} ${theme} ${width}: ${problems.join(" | ")}`);
        }
        await context.close();
      }
    }
  }
  await browser.close();
  await writeFile(join(outputDir, "qa-report.json"), `${JSON.stringify({ baseURL, report }, null, 2)}\n`);
  console.log(`${report.length} captures, ${failures} with automatic findings. Report: ${join(outputDir, "qa-report.json")}`);
  if (failures) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
