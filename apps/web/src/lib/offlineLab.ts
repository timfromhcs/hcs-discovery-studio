/**
 * Offline lab: the parts of the triage pipeline that can run in a browser tab.
 *
 * Semantics mirror the Python implementation deliberately, because a second
 * implementation that quietly disagrees is worse than no implementation:
 *
 * - filter operators and thresholds follow `filter.rules` / the triage template;
 * - the composite score follows `rank.pareto`: min-max normalisation per objective,
 *   direction-aware, 0.5 when every value is identical, then a weighted average over
 *   the total weight (missing values exclude the objective for that row);
 * - descriptors come from RDKit WebAssembly, not from a JavaScript approximation.
 *
 * What cannot match is stated in the UI: docking, force fields and the server's
 * cached provenance are not available here.
 */

export interface LabRow {
  name: string;
  smiles: string;
  mw: number | null;
  logp: number | null;
  tpsa: number | null;
  hbd: number | null;
  hba: number | null;
  rotb: number | null;
  rings: number | null;
  qed: number | null;
}

export interface TriageRule {
  id: string;
  label: string;
  test: (row: LabRow) => boolean;
}

export const TRIAGE_RULES: TriageRule[] = [
  { id: "mw", label: "MW 150-600 g/mol", test: (r) => r.mw !== null && r.mw >= 150 && r.mw <= 600 },
  { id: "logp", label: "cLogP -1..5.5", test: (r) => r.logp !== null && r.logp >= -1 && r.logp <= 5.5 },
  { id: "tpsa", label: "TPSA <= 160", test: (r) => r.tpsa !== null && r.tpsa <= 160 },
  { id: "hbd", label: "HBD <= 5", test: (r) => r.hbd !== null && r.hbd <= 5 },
  { id: "hba", label: "HBA <= 10", test: (r) => r.hba !== null && r.hba <= 10 },
  { id: "rotb", label: "Rotatable bonds <= 10", test: (r) => r.rotb !== null && r.rotb <= 10 },
];

/** Same weights and directions as the shipped triage template. */
export const OBJECTIVES = [
  { key: "qed" as const, direction: "higher" as const, weight: 1.5 },
  { key: "tpsa" as const, direction: "lower" as const, weight: 1.0 },
  { key: "logp" as const, direction: "lower" as const, weight: 1.0 },
  { key: "mw" as const, direction: "lower" as const, weight: 0.5 },
];

export function splitRecords(text: string, format: "csv" | "smi" | "sdf"): string[][] {
  if (format === "sdf") {
    return text
      .split("$$$$")
      .map((record) => record.trim())
      .filter(Boolean)
      .map((record) => [record]);
  }
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"))
    .map((line) => (format === "smi" ? line.split(/\s+/) : parseCsvLine(line)));
}

/** Minimal RFC-4180-ish CSV line parser: quotes, escaped quotes, no multiline fields. */
export function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index++) {
    const char = line[index];
    if (quoted) {
      if (char === '"' && line[index + 1] === '"') {
        current += '"';
        index++;
      } else if (char === '"') {
        quoted = false;
      } else {
        current += char;
      }
      continue;
    }
    if (char === '"') quoted = true;
    else if (char === ",") {
      out.push(current);
      current = "";
    } else current += char;
  }
  out.push(current);
  return out.map((value) => value.trim());
}

export function findSmilesColumn(header: string[]): number {
  const index = header.findIndex((name) => name.trim().toLowerCase() === "smiles");
  return index >= 0 ? index : 0;
}

export function findNameColumn(header: string[]): number {
  return header.findIndex((name) => ["name", "id", "identifier", "compound"].includes(name.trim().toLowerCase()));
}

export function triage(rows: LabRow[]): { passed: boolean[]; reasons: string[][] } {
  const passed: boolean[] = [];
  const reasons: string[][] = [];
  for (const row of rows) {
    const failed = TRIAGE_RULES.filter((rule) => !rule.test(row)).map((rule) => rule.label);
    passed.push(failed.length === 0);
    reasons.push(failed);
  }
  return { passed, reasons };
}

const isClose = (a: number, b: number) => Math.abs(a - b) <= 1e-12 * Math.max(1, Math.abs(a), Math.abs(b));

function normalise(values: Array<number | null>, direction: "higher" | "lower"): Array<number | null> {
  const present = values.filter((value): value is number => value !== null);
  if (present.length === 0) return values.map(() => null);
  const low = Math.min(...present);
  const high = Math.max(...present);
  const flat = isClose(high, low);
  return values.map((value) => {
    if (value === null) return null;
    if (flat) return 0.5;
    return direction === "higher" ? (value - low) / (high - low) : (high - value) / (high - low);
  });
}

/** Weighted composite score, `null` when a row has no scoring objective at all. */
export function compositeScores(rows: LabRow[]): Array<number | null> {
  const normalized = OBJECTIVES.map((objective) => ({
    objective,
    series: normalise(
      rows.map((row) => row[objective.key]),
      objective.direction,
    ),
  }));
  const totalWeight = OBJECTIVES.reduce((sum, objective) => sum + objective.weight, 0);
  return rows.map((_, index) => {
    let weighted = 0;
    let used = 0;
    for (const { objective, series } of normalized) {
      const value = series[index];
      if (value === null) continue;
      weighted += value * objective.weight;
      used += objective.weight;
    }
    if (used === 0 || totalWeight === 0) return null;
    return weighted / used;
  });
}

export interface RankedRow {
  row: LabRow;
  score: number | null;
  passed: boolean;
  reasons: string[];
  /** Position in the imported array: similarity scores are indexed by this, not by rank. */
  index: number;
}

export function rankByScore(rows: LabRow[]): RankedRow[] {
  const { passed, reasons } = triage(rows);
  const scores = compositeScores(rows);
  return rows
    .map((row, index) => ({ row, score: scores[index], passed: passed[index], reasons: reasons[index], index }))
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || a.row.name.localeCompare(b.row.name));
}

export interface LabState {
  version: 1;
  fileName: string;
  importedAt: string;
  rows: LabRow[];
  rejected: number;
}

const DB_NAME = "hcs-offline-lab";
const STORE = "state";
const KEY = "last";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveLabState(state: LabState): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(state, KEY);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function loadLabState(): Promise<LabState | null> {
  const db = await openDb();
  const state = await new Promise<LabState | null>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).get(KEY);
    request.onsuccess = () => resolve((request.result as LabState | undefined) ?? null);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return state && state.version === 1 ? state : null;
}

export async function clearLabState(): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(KEY);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export function toCsv(rows: LabRow[], scores: Array<number | null>, passed: boolean[]): string {
  const header = ["name", "smiles", "mw", "clogp", "tpsa", "hbd", "hba", "rotb", "rings", "qed", "passes_triage", "composite_score"];
  const escape = (value: string) => (/[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value);
  const lines = rows.map((row, index) =>
    [
      row.name,
      row.smiles,
      row.mw,
      row.logp,
      row.tpsa,
      row.hbd,
      row.hba,
      row.rotb,
      row.rings,
      row.qed,
      passed[index] ? "yes" : "no",
      scores[index] === null ? "" : scores[index]!.toFixed(4),
    ]
      .map((value) => (value === null ? "" : escape(String(value))))
      .join(","),
  );
  return [header.join(","), ...lines].join("\n");
}
