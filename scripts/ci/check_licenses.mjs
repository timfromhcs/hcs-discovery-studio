#!/usr/bin/env node
/**
 * Check licenses of production npm packages using the committed lockfile.
 *
 * This runs without installing node_modules, so CI can audit the exact locked
 * graph. Development-only packages are excluded because they are not shipped in
 * the built single-page application.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const lockfile = JSON.parse(readFileSync(join(repoRoot, "apps", "web", "package-lock.json"), "utf8"));

const allowed = new Set([
  "0BSD",
  "Apache-2.0",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "CC0-1.0",
  "ISC",
  "MIT",
  "MPL-2.0",
  "Unlicense",
]);

function identifiers(expression) {
  if (typeof expression !== "string") return [];
  return expression
    .replace(/[()]/g, " ")
    .split(/\s+/)
    .filter((token) => token && !["AND", "OR", "WITH"].includes(token));
}

const failures = [];
const rows = [];
for (const [path, entry] of Object.entries(lockfile.packages ?? {})) {
  if (!path || entry.dev || !entry.version) continue;
  const name = path.replace(/^.*node_modules\//, "");
  const license = entry.license ?? "UNKNOWN";
  const tokens = identifiers(license);
  const ok = tokens.length > 0 && tokens.every((token) => allowed.has(token));
  rows.push({ name, version: entry.version, license, ok });
  if (!ok) failures.push(`${name} ${entry.version}: ${license}`);
}

for (const row of rows.sort((a, b) => a.name.localeCompare(b.name))) {
  console.log(`${row.ok ? "ok  " : "FAIL"}  ${row.name.padEnd(28)} ${row.version.padEnd(12)} ${row.license}`);
}
console.log(`\n${rows.length} production packages checked; ${failures.length} outside policy.`);

if (failures.length > 0) {
  console.error("\nLicense policy failures:");
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}
