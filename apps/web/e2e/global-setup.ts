import { rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const dataDir = fileURLToPath(new URL("../../.e2e-data", import.meta.url));

export default async function globalSetup() {
  await rm(dataDir, { recursive: true, force: true });
}
