import initRDKitModule, { type MainModule, type Mol } from "@rdkit/rdkit";
import wasmUrl from "@rdkit/rdkit/RDKit_minimal.wasm?url";

/**
 * Lazily-initialised RDKit WebAssembly (MinimalLib).
 *
 * The module is only fetched and compiled on first use, so a page that never
 * opens the browser-chemistry panel pays no WASM cost. The returned handle is
 * cached and shared for the lifetime of the page.
 *
 * This is real, offline chemistry in the browser — the same RDKit version that
 * ships in the local backend (2026.9.1), compiled to WebAssembly. Numeric values
 * come from RDKit itself; nothing is approximated in JavaScript.
 */

let modulePromise: Promise<MainModule> | null = null;

export function loadRDKit(): Promise<MainModule> {
  if (!modulePromise) {
    modulePromise = initRDKitModule({ locateFile: () => wasmUrl });
  }
  return modulePromise;
}

export interface BrowserMolecule {
  canonical_smiles: string;
  molecular_weight: number | null;
  clogp: number | null;
  tpsa: number | null;
  hbd: number | null;
  hba: number | null;
  rotatable_bonds: number | null;
  rings: number | null;
  svg: string;
}

export interface BrowserChemistryResult {
  ok: boolean;
  rdkit_version: string;
  error: string | null;
  molecule: BrowserMolecule | null;
}

const SELF_TEST_SMILES = "CC(=O)Oc1ccccc1C(=O)O"; // aspirin

function descriptorNumber(descriptors: Record<string, number>, key: string): number | null {
  const value = descriptors[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function toMolecule(mol: Mol): BrowserMolecule {
  const descriptors = JSON.parse(mol.get_descriptors()) as Record<string, number>;
  return {
    canonical_smiles: mol.get_smiles(),
    molecular_weight: descriptorNumber(descriptors, "amw"),
    clogp: descriptorNumber(descriptors, "CrippenClogP"),
    tpsa: descriptorNumber(descriptors, "tpsa"),
    hbd: descriptorNumber(descriptors, "NumHBD"),
    hba: descriptorNumber(descriptors, "NumHBA"),
    rotatable_bonds: descriptorNumber(descriptors, "NumRotatableBonds"),
    rings: descriptorNumber(descriptors, "RingCount"),
    svg: mol.get_svg(320, 200),
  };
}

/**
 * Parse ``smiles`` and compute descriptors + an SVG depiction, entirely in the
 * browser via RDKit WebAssembly. Returns a structured result (never throws); a
 * parse failure or a failed WASM load is reported as ``ok: false``.
 */
export async function computeMolecule(smiles: string): Promise<BrowserChemistryResult> {
  let rdkit: MainModule;
  try {
    rdkit = await loadRDKit();
  } catch (error) {
    return {
      ok: false,
      rdkit_version: "",
      error: error instanceof Error ? error.message : "RDKit WebAssembly failed to load",
      molecule: null,
    };
  }
  const mol = rdkit.get_mol(smiles);
  if (!mol) {
    return { ok: false, rdkit_version: rdkit.version(), error: "RDKit could not parse the SMILES", molecule: null };
  }
  try {
    return { ok: true, rdkit_version: rdkit.version(), error: null, molecule: toMolecule(mol) };
  } catch (error) {
    return {
      ok: false,
      rdkit_version: rdkit.version(),
      error: error instanceof Error ? error.message : "Descriptor calculation failed",
      molecule: null,
    };
  } finally {
    mol.delete();
  }
}

/** Run the built-in self-test molecule (aspirin) through the browser engine. */
export function runSelfTest(): Promise<BrowserChemistryResult> {
  return computeMolecule(SELF_TEST_SMILES);
}

export { SELF_TEST_SMILES };
