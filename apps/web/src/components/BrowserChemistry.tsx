import { useState } from "react";
import { type BrowserChemistryResult, runSelfTest, SELF_TEST_SMILES } from "../lib/rdkit";
import { Badge, Button, Card, CardHeader, InlineNotice, KeyValue } from "./ui";

function formatValue(value: number | null): string {
  return value === null ? "—" : value.toFixed(2);
}

/**
 * Browser-chemistry self-test. Parses a fixed SMILES and computes descriptors +
 * an SVG depiction entirely in the browser via RDKit WebAssembly (MinimalLib).
 * It is opt-in (a button), so the ~7 MB WASM module is only fetched on demand.
 */
export function BrowserChemistry() {
  const [state, setState] = useState<"idle" | "loading" | "done">("idle");
  const [result, setResult] = useState<BrowserChemistryResult | null>(null);

  const run = async () => {
    setState("loading");
    setResult(null);
    const next = await runSelfTest();
    setResult(next);
    setState("done");
  };

  const molecule = result?.molecule ?? null;

  return (
    <Card>
      <CardHeader
        title="Browser chemistry (WebAssembly)"
        subtitle="RDKit MinimalLib compiled to WebAssembly. Runs offline in this browser; nothing is sent to a server."
        icon="molecule"
        actions={
          <Button size="sm" variant="secondary" icon="play" onClick={() => void run()} loading={state === "loading"}>
            Run self-test
          </Button>
        }
      />

      {state === "idle" ? (
        <p className="muted small">
          Parse a fixed test molecule ({SELF_TEST_SMILES}) and compute canonical SMILES, descriptors and an SVG
          depiction with RDKit running as WebAssembly. A successful run means the browser can do real chemistry
          without the local backend.
        </p>
      ) : null}

      {state === "loading" ? <p className="muted small">Loading RDKit WebAssembly and computing…</p> : null}

      {state === "done" && result && !result.ok ? (
        <InlineNotice tone="danger" title="WebAssembly self-test failed">
          {result.error ?? "RDKit did not produce a result."} The local backend remains the dependable chemistry path.
        </InlineNotice>
      ) : null}

      {state === "done" && result?.ok && molecule ? (
        <>
          <div className="browser-chem">
            <div className="browser-chem-svg" dangerouslySetInnerHTML={{ __html: molecule.svg }} />
            <KeyValue
              items={[
                { label: "RDKit version", value: result.rdkit_version, mono: true },
                { label: "Canonical SMILES", value: molecule.canonical_smiles, mono: true },
                { label: "Molecular weight", value: `${formatValue(molecule.molecular_weight)} g/mol` },
                { label: "cLogP", value: formatValue(molecule.clogp) },
                { label: "TPSA", value: `${formatValue(molecule.tpsa)} Å²` },
                { label: "H-bond donors / acceptors", value: `${molecule.hbd ?? "—"} / ${molecule.hba ?? "—"}` },
                { label: "Rotatable bonds", value: molecule.rotatable_bonds === null ? "—" : String(molecule.rotatable_bonds) },
                { label: "Rings", value: molecule.rings === null ? "—" : String(molecule.rings) },
              ]}
            />
          </div>
          <div className="row-actions">
            <Badge tone="ok" dot>
              WebAssembly compute verified
            </Badge>
          </div>
        </>
      ) : null}
    </Card>
  );
}
