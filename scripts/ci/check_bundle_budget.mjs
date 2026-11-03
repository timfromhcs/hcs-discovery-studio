#!/usr/bin/env node
/**
 * Bundle budget for the SPA.
 *
 * The size numbers are a promise to the user on a slow connection, not a vanity
 * metric: the JS payload is what delays first interaction. The budget is checked on
 * the built output, with gzip, because that is what the browser downloads.
 *
 * The RDKit WebAssembly module is excluded on purpose: it is a 2.4 MB gzip asset that
 * is only fetched when the browser-chemistry panel is opened, and bounding it would
 * force a worse trade-off (a smaller chemistry engine) instead of a smaller app.
 *
 * Usage: node scripts/ci/check_bundle_budget.mjs [--json]
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = resolve(import.meta.dirname, "..", "..");
const DIST = join(ROOT, "apps", "web", "dist");
const ASSETS = join(DIST, "assets");

// Budgets in bytes of gzip output. Current measured values (2026-11-03) are noted so
// a future change that doubles the bundle fails loudly instead of silently.
const BUDGET = {
  js: 210 * 1024, // measured ~167 kB
  css: 16 * 1024, // measured ~10.5 kB
  total: 235 * 1024, // js + css
};

function gzipSize(path) {
  return gzipSync(readFileSync(path), { level: 9 }).byteLength;
}

function listAssets(extension) {
  try {
    return readdirSync(ASSETS)
      .filter((name) => name.endsWith(extension))
      .map((name) => ({ name, path: join(ASSETS, name), raw: statSync(join(ASSETS, name)).size }));
  } catch {
    return [];
  }
}

const js = listAssets(".js");
const css = listAssets(".css");
if (js.length === 0) {
  console.error(`No built JS found under ${ASSETS}. Run "npm run build" in apps/web first.`);
  process.exit(1);
}
if (!statSync(join(DIST, "index.html")).isFile()) {
  console.error("dist/index.html is missing; the SPA was not built.");
  process.exit(1);
}

const jsGzip = js.reduce((sum, file) => sum + gzipSize(file.path), 0);
const cssGzip = css.reduce((sum, file) => sum + gzipSize(file.path), 0);
const total = jsGzip + cssGzip;

const rows = [
  { metric: "js (gzip)", value: jsGzip, budget: BUDGET.js, files: js.length },
  { metric: "css (gzip)", value: cssGzip, budget: BUDGET.css, files: css.length },
  { metric: "total (gzip)", value: total, budget: BUDGET.total, files: js.length + css.length },
];
const failures = rows.filter((row) => row.value > row.budget);

if (process.argv.includes("--json")) {
  console.log(JSON.stringify({ budgets: BUDGET, rows, failures }, null, 2));
} else {
  for (const row of rows) {
    const status = row.value > row.budget ? "FAIL" : "ok  ";
    console.log(
      `${status} ${row.metric.padEnd(14)} ${String(Math.round(row.value / 1024)).padStart(4)} kB ` +
        `(budget ${Math.round(row.budget / 1024)} kB, ${row.files} file(s))`,
    );
  }
}

if (failures.length > 0) {
  console.error(
    "\nBundle budget exceeded. Either shrink the bundle or raise the budget with a " +
      "measured reason in scripts/ci/check_bundle_budget.mjs.",
  );
  process.exit(1);
}
