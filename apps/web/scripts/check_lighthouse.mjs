#!/usr/bin/env node
/**
 * Lighthouse budget check for the static SPA.
 *
 *   node scripts/check_lighthouse.mjs --base-url http://127.0.0.1:8792
 *   npm run lighthouse
 *
 * Runs Lighthouse against the workspace shell and the offline lab, checks a small set
 * of budgets, writes build/lighthouse.json and docs/validation/lighthouse.md.
 *
 * The budgets are regression bands, not promises: they are set well above the
 * measured local values (perf 0.95/0.99, LCP 2.4/0.8 s, TBT 170/120 ms) so a slower
 * shared CI runner does not fail for noise, while a real regression (a doubled LCP,
 * a layout shift, a runaway bundle) does. The workspace shell measured 0.81 on the
 * Ubuntu runner because the static preview has no API and the page sits in its error
 * states; the score budget is 0.75 for that reason, while LCP/CLS/TBT stay absolute.
 *
 * Chrome: Chrome Launcher finds it automatically on CI. Locally set CHROME_PATH to a
 * Chromium/Chrome executable if the default lookup fails.
 */

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = join(webRoot, "..", "..");
const args = process.argv.slice(2);
const argValue = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
};
const baseURL = argValue("--base-url", process.env.HCS_BASE_URL ?? "http://127.0.0.1:8792");
const outDir = argValue("--out", join(repoRoot, "build"));
const reportPath = join(repoRoot, "docs", "validation", "lighthouse.md");

const PAGES = [
  { name: "Workspace shell", path: "/" },
  { name: "Offline lab", path: "/lab" },
];

// Hard budgets: deterministic signals plus a catastrophic floor. Paint timings on a
// shared host vary by more than 3× between runs (0.96 / 104 ms TBT idle vs 0.74 /
// 1058 ms under load on the same machine), so a tight hard budget would be flaky and
// would train people to ignore the gate. The advisory targets are still recorded and
// reported; the bundle budget and the axe gate remain the hard checks for size and
// accessibility.
const BUDGETS = {
  accessibility: 1,
  "cumulative-layout-shift": 0.1,
  performance: 0.5,
  "largest-contentful-paint": 5000,
  "total-blocking-time": 2000,
  "first-contentful-paint": 4000,
};

//: Reported against, but not failed: host load moves these too much.
const ADVISORY = {
  performance: 0.85,
  "largest-contentful-paint": 2500,
  "total-blocking-time": 600,
  "first-contentful-paint": 2500,
};

async function measure(lighthouse, chromeLauncher, page) {
  const url = new URL(page.path, baseURL).toString();
  const chrome = await chromeLauncher.launch({ chromeFlags: ["--headless=new", "--no-sandbox"] });
  try {
    const result = await lighthouse(url, {
      port: chrome.port,
      output: "json",
      logLevel: "error",
      onlyCategories: ["performance", "accessibility"],
    });
    const report = JSON.parse(result.report);
    const metrics = {
      performance: report.categories.performance.score,
      accessibility: report.categories.accessibility.score,
      "first-contentful-paint": report.audits["first-contentful-paint"].numericValue,
      "largest-contentful-paint": report.audits["largest-contentful-paint"].numericValue,
      "cumulative-layout-shift": report.audits["cumulative-layout-shift"].numericValue,
      "total-blocking-time": report.audits["total-blocking-time"].numericValue,
    };
    return { ...page, url, metrics };
  } finally {
    await chrome.kill();
  }
}

const { default: lighthouse } = await import("lighthouse");
const chromeLauncher = await import("chrome-launcher");

const results = [];
const failures = [];
for (const page of PAGES) {
  console.log(`Lighthouse: ${page.name} (${page.path})`);
  const measured = await measure(lighthouse, chromeLauncher, page);
  results.push(measured);
  for (const [key, limit] of Object.entries(BUDGETS)) {
    const value = measured.metrics[key];
    const ok = key === "performance" || key === "accessibility" ? value >= limit : value <= limit;
    if (!ok) failures.push(`${page.name}: ${key} = ${value} (budget ${limit})`);
  }
}

await mkdir(outDir, { recursive: true });
const generatedAt = new Date().toISOString();
await writeFile(
  join(outDir, "lighthouse.json"),
  JSON.stringify({ schema: "hcs.lighthouse.v1", generatedAt, baseURL, budgets: BUDGETS, results }, null, 2) + "\n",
);

const fmt = (value, digits = 0) => (value === null || value === undefined ? "n/a" : value.toFixed(digits));
const rows = results
  .map(
    (result) =>
      `| ${result.name} | ${fmt(result.metrics.performance * 100)} | ${fmt(result.metrics.accessibility * 100)} | ${fmt(result.metrics["first-contentful-paint"])} ms | ${fmt(result.metrics["largest-contentful-paint"])} ms | ${fmt(result.metrics["cumulative-layout-shift"], 3)} | ${fmt(result.metrics["total-blocking-time"])} ms |`,
  )
  .join("\n");

const markdown = `# Lighthouse budgets

Generated by \`node scripts/check_lighthouse.mjs\`. Do not edit by hand.

| Item | Value |
|---|---|
| Base URL | \`${baseURL}\` |
| Lighthouse | 13.6.0 |
| Generated | ${generatedAt} |
| Result | **${failures.length === 0 ? "pass" : "FAIL"}** |

| Page | Performance | Accessibility | FCP | LCP | CLS | TBT |
|---|---|---|---|---|---|---|
${rows}

## Budgets (hard)

| Metric | Budget | Direction |
|---|---|---|
| Accessibility score | = ${BUDGETS.accessibility} | no violations |
| CLS | <= ${BUDGETS["cumulative-layout-shift"]} | lower is better |
| Performance score | >= ${BUDGETS.performance} | catastrophic floor |
| FCP | <= ${BUDGETS["first-contentful-paint"]} ms | catastrophic floor |
| LCP | <= ${BUDGETS["largest-contentful-paint"]} ms | catastrophic floor |
| TBT | <= ${BUDGETS["total-blocking-time"]} ms | catastrophic floor |

## Advisory targets (recorded, not failed)

| Metric | Target |
|---|---|
| Performance score | >= ${ADVISORY.performance} |
| FCP | <= ${ADVISORY["first-contentful-paint"]} ms |
| LCP | <= ${ADVISORY["largest-contentful-paint"]} ms |
| TBT | <= ${ADVISORY["total-blocking-time"]} ms |

## What this measures, and what it does not

- The run is against the **static build** (\`vite preview\`), so the API calls fail and
  the pages render their shell and error states. It measures the application bundle,
  layout and script cost, not a populated run monitor.
- One run per page. Paint timings on a shared host vary by more than 3× between runs
  (0.96 / 104 ms TBT idle vs 0.74 / 1058 ms under load on the same machine), which is
  why only the deterministic signals (accessibility, CLS) and a catastrophic floor are
  hard budgets. The advisory targets are the numbers to watch in the trend.
- The accessibility score is Lighthouse's automated subset; the Playwright axe gate is
  the stronger check. Neither proves conformance.
- No third-party network is involved: the SPA and its assets are served locally.
`;

await mkdir(dirname(reportPath), { recursive: true });
await writeFile(reportPath, markdown);

if (failures.length > 0) {
  console.error("\nBudget failures:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}
console.log(`\nLighthouse budgets passed. Report: ${reportPath}`);
