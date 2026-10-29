import { readdir, rm } from "node:fs/promises";
import { basename, dirname, join } from "node:path";

// Remove data from earlier invocations. The current run's directory (set in
// playwright.config.ts) is already in use by the web server and is left alone.
export default async function globalSetup() {
  const current = process.env.HCS_E2E_DATA_DIR;
  if (!current) throw new Error("HCS_E2E_DATA_DIR is not set; check playwright.config.ts");
  const dataRoot = dirname(current);
  const entries = await readdir(dataRoot).catch((error: NodeJS.ErrnoException) => {
    if (error.code === "ENOENT") return [] as string[];
    throw error;
  });
  for (const entry of entries) {
    if (entry === basename(current)) continue;
    await rm(join(dataRoot, entry), { recursive: true, force: true });
  }
}
