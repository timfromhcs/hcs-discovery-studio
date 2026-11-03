import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, Card, CardHeader, Field, InlineNotice, Input, KeyValue, PageHeader, useToast } from "../components/ui";
import { scoreLibrary, type LibraryScoreResult } from "../lib/gpuTanimoto";
import {
  clearLabState,
  findNameColumn,
  findSmilesColumn,
  loadLabState,
  rankByScore,
  saveLabState,
  splitRecords,
  toCsv,
  type LabRow,
} from "../lib/offlineLab";
import { loadRDKit } from "../lib/rdkit";
import { downloadText } from "../lib/format";

type Format = "csv" | "smi" | "sdf";

function detectFormat(name: string): Format {
  const lower = name.toLowerCase();
  if (lower.endsWith(".sdf") || lower.endsWith(".mol")) return "sdf";
  if (lower.endsWith(".smi") || lower.endsWith(".smiles")) return "smi";
  return "csv";
}

function numberOrNull(descriptors: Record<string, number>, key: string): number | null {
  const value = descriptors[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Offline lab: import, describe, triage, rank and score similarity without a server.
 *
 * Everything here runs in the tab: RDKit WebAssembly for chemistry, the shared WGSL
 * kernel (or the CPU reference) for Tanimoto, IndexedDB for the stored copy. The page
 * says what it does not do — no docking, no force fields, no server-side provenance —
 * instead of showing a plausible number it cannot back up.
 */
export function LabPage() {
  const { notify } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<LabRow[]>([]);
  const [rejected, setRejected] = useState(0);
  const [fileName, setFileName] = useState("");
  const [importedAt, setImportedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);
  const [query, setQuery] = useState("c1ccccc1");
  const [similarity, setSimilarity] = useState<LibraryScoreResult | null>(null);
  const [simBusy, setSimBusy] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);
  const importResultRef = useRef<HTMLDivElement>(null);
  const similarityResultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (rows.length > 0) importResultRef.current?.focus();
  }, [rows.length, importedAt]);

  useEffect(() => {
    if (similarity) similarityResultRef.current?.focus();
  }, [similarity]);

  useEffect(() => {
    let cancelled = false;
    loadLabState()
      .then((state) => {
        if (cancelled || !state) return;
        setRows(state.rows);
        setRejected(state.rejected);
        setFileName(state.fileName);
        setImportedAt(state.importedAt);
        setRestored(true);
      })
      .catch(() => {
        /* no storage: the lab still works, it just forgets */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ranked = useMemo(() => rankByScore(rows), [rows]);
  const passed = useMemo(() => ranked.filter((entry) => entry.passed).length, [ranked]);

  const importFile = useCallback(
    async (file: File) => {
      setBusy(true);
      setError(null);
      setSimilarity(null);
      setRestored(false);
      try {
        const format = detectFormat(file.name);
        const text = await file.text();
        const rdkit = await loadRDKit();
        const records = splitRecords(text, format);
        let header: string[] = [];
        let smilesIndex = 0;
        let nameIndex = -1;
        if (format === "csv") {
          header = records[0] ?? [];
          smilesIndex = findSmilesColumn(header);
          nameIndex = findNameColumn(header);
        }
        const data = format === "csv" ? records.slice(1) : records;
        const parsed: LabRow[] = [];
        let bad = 0;
        for (let index = 0; index < data.length; index++) {
          const record = data[index];
          const smiles = format === "sdf" ? record[0] : (record[smilesIndex] ?? "");
          const name =
            format === "smi"
              ? (record[1] ?? "")
              : nameIndex >= 0
                ? (record[nameIndex] ?? "")
                : (record[0] ?? "");
          if (!smiles) {
            bad++;
            continue;
          }
          const mol = rdkit.get_mol(smiles);
          if (!mol) {
            bad++;
            continue;
          }
          try {
            const descriptors = JSON.parse(mol.get_descriptors()) as Record<string, number>;
            parsed.push({
              name: name || mol.get_smiles(),
              smiles: mol.get_smiles(),
              mw: numberOrNull(descriptors, "amw"),
              logp: numberOrNull(descriptors, "CrippenClogP"),
              tpsa: numberOrNull(descriptors, "tpsa"),
              hbd: numberOrNull(descriptors, "NumHBD"),
              hba: numberOrNull(descriptors, "NumHBA"),
              rotb: numberOrNull(descriptors, "NumRotatableBonds"),
              rings: numberOrNull(descriptors, "RingCount"),
              qed: numberOrNull(descriptors, "qed"),
            });
          } finally {
            mol.delete();
          }
          if (index % 150 === 0) {
            setProgress(`${index + 1} / ${data.length}`);
            await new Promise((resolve) => setTimeout(resolve, 0));
          }
        }
        setProgress(null);
        if (parsed.length === 0) {
          setError("No structure in this file could be parsed by RDKit. Nothing was stored.");
          return;
        }
        setRows(parsed);
        setRejected(bad);
        setFileName(file.name);
        const stamp = new Date().toISOString();
        setImportedAt(stamp);
        await saveLabState({ version: 1, fileName: file.name, importedAt: stamp, rows: parsed, rejected: bad });
        notify(`${parsed.length} structures imported in this browser`, "ok");
      } catch (problem) {
        setError(problem instanceof Error ? problem.message : "The file could not be read.");
      } finally {
        setBusy(false);
        setProgress(null);
        if (fileInput.current) fileInput.current.value = "";
      }
    },
    [notify],
  );

  const runSimilarity = useCallback(async () => {
    if (rows.length === 0) return;
    setSimBusy(true);
    setSimError(null);
    setSimilarity(null);
    try {
      const result = await scoreLibrary(
        rows.map((row) => row.smiles),
        query,
      );
      setSimilarity(result);
    } catch (problem) {
      setSimError(problem instanceof Error ? problem.message : "Similarity scoring failed.");
    } finally {
      setSimBusy(false);
    }
  }, [rows, query]);

  const exportCsv = () => {
    const scores = ranked.map((entry) => entry.score);
    const ordered = ranked.map((entry) => entry.row);
    const passFlags = ranked.map((entry) => entry.passed);
    downloadText("offline-lab-triage.csv", toCsv(ordered, scores, passFlags), "text/csv");
  };

  const clear = async () => {
    await clearLabState();
    setRows([]);
    setRejected(0);
    setFileName("");
    setImportedAt(null);
    setSimilarity(null);
    setRestored(false);
    notify("The stored copy in this browser was deleted", "ok");
  };

  const topHits = similarity
    ? ranked
        .filter((entry) => similarity.valid[entry.index])
        .sort((a, b) => similarity.scores[b.index] - similarity.scores[a.index])
        .slice(0, 10)
    : [];

  return (
    <div className="stack">
      <PageHeader
        title="Offline lab"
        description="Import, describe, triage and rank a library in this browser. No server, no upload, no account."
        actions={
          rows.length > 0 ? (
            <Button variant="secondary" icon="download" onClick={exportCsv}>
              Export CSV
            </Button>
          ) : null
        }
      />

      <InlineNotice tone="info" title="What runs where">
        RDKit WebAssembly computes the descriptors, the same WGSL Tanimoto kernel as the native engine (or its CPU
        reference) scores similarity, and the stored copy lives in this browser's IndexedDB. Docking, force fields and
        the server's provenance manifest are not available here, and the page says so instead of imitating them.
      </InlineNotice>

      {restored ? (
        <InlineNotice tone="ok" title="Restored from this device">
          {rows.length} structures from {fileName} were loaded from local storage. Nothing was sent anywhere.
        </InlineNotice>
      ) : null}

      <Card>
        <CardHeader
          title="1 · Import"
          subtitle="CSV with a SMILES column, .smi (SMILES name) or .sdf. Row-level failures are counted, not hidden."
          icon="upload"
          actions={
            <Button
              variant="primary"
              icon="upload"
              loading={busy}
              onClick={() => fileInput.current?.click()}
            >
              Choose file
            </Button>
          }
        />
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.smi,.smiles,.sdf,.mol,text/csv,text/plain"
          className="visually-hidden"
          aria-label="Library file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void importFile(file);
          }}
        />
        {busy ? <p className="muted small">Parsing and describing {progress ?? "…"}</p> : null}
        {error ? (
          <InlineNotice tone="danger" title="Import failed">
            {error}
          </InlineNotice>
        ) : null}
        {rows.length > 0 ? (
          <div
            ref={importResultRef}
            tabIndex={-1}
            aria-live="polite"
            className="lab-result"
            data-testid="lab-import-result"
          >
            <KeyValue
              items={[
                { label: "File", value: fileName, mono: true },
                { label: "Imported", value: importedAt ? new Date(importedAt).toLocaleString() : "—" },
                { label: "Structures", value: rows.length.toLocaleString() },
                { label: "Rejected rows", value: rejected.toLocaleString() },
              ]}
            />
            <div className="row-actions">
              <Button variant="quiet" size="sm" icon="trash" onClick={() => void clear()}>
                Delete stored copy
              </Button>
            </div>
          </div>
        ) : (
          <p className="muted small">Nothing imported yet. A 17-row example lives in examples/datasets/demo_library.csv.</p>
        )}
      </Card>

      {rows.length > 0 ? (
        <Card>
          <CardHeader
            title="2 · Triage and ranking"
            subtitle={`${passed} of ${rows.length} pass every rule. The score is a weighted, dataset-relative composite — not a drug-likeness law.`}
            icon="filter"
          />
          <div className="table-wrap tall">
            <table>
              <caption className="table-note">
                Rules and weights mirror the server's triage template. Values are RDKit WebAssembly output; a different
                RDKit version can shift the last digit.
              </caption>
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Name</th>
                  <th scope="col">SMILES</th>
                  <th scope="col">MW</th>
                  <th scope="col">cLogP</th>
                  <th scope="col">TPSA</th>
                  <th scope="col">QED</th>
                  <th scope="col">Score</th>
                  <th scope="col">Triage</th>
                </tr>
              </thead>
              <tbody>
                {ranked.slice(0, 200).map((entry, index) => (
                  <tr key={`${entry.row.smiles}-${index}`}>
                    <td>{index + 1}</td>
                    <td>{entry.row.name}</td>
                    <td className="mono small">{entry.row.smiles}</td>
                    <td>{entry.row.mw === null ? "—" : entry.row.mw.toFixed(1)}</td>
                    <td>{entry.row.logp === null ? "—" : entry.row.logp.toFixed(2)}</td>
                    <td>{entry.row.tpsa === null ? "—" : entry.row.tpsa.toFixed(1)}</td>
                    <td>{entry.row.qed === null ? "—" : entry.row.qed.toFixed(3)}</td>
                    <td>{entry.score === null ? "—" : entry.score.toFixed(3)}</td>
                    <td>
                      {entry.passed ? (
                        <Badge tone="ok" dot>
                          pass
                        </Badge>
                      ) : (
                        <Badge tone="warn">{entry.reasons[0] ?? "flag"}</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {ranked.length > 200 ? (
            <p className="table-note">Showing the top 200 of {ranked.length}. The CSV export is complete.</p>
          ) : null}
        </Card>
      ) : null}

      {rows.length > 0 ? (
        <Card>
          <CardHeader
            title="3 · Similarity"
            subtitle="Query against the imported library. GPU counts must match the CPU reference exactly or no score is shown."
            icon="run"
            actions={
              <Button
                variant="secondary"
                icon="play"
                loading={simBusy}
                onClick={() => void runSimilarity()}
              >
                Score library
              </Button>
            }
          />
          <div className="form-stack">
            <Field label="Query SMILES" hint="Morgan/ECFP radius 2, 2048 bits, Tanimoto.">
              <Input value={query} onChange={(event) => setQuery(event.target.value)} spellCheck={false} />
            </Field>
          </div>
          {simError ? (
            <InlineNotice tone="danger" title="Similarity failed">
              {simError}
            </InlineNotice>
          ) : null}
          {similarity ? (
            <div
              ref={similarityResultRef}
              tabIndex={-1}
              aria-live="polite"
              className="lab-result"
              data-testid="lab-similarity-result"
            >
              <KeyValue
                items={[
                  {
                    label: "Engine",
                    value:
                      similarity.engine === "gpu"
                        ? `WebGPU · ${similarity.adapter ?? "adapter"}`
                        : "CPU reference (no hardware adapter)",
                    mono: similarity.engine === "gpu",
                  },
                  { label: "Library", value: similarity.n.toLocaleString() },
                  { label: "Wall time", value: `${similarity.ms.toFixed(1)} ms` },
                  { label: "Parity", value: similarity.parityExact === null ? "CPU reference" : "bit-exact" },
                ]}
              />
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Name</th>
                      <th scope="col">Tanimoto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topHits.map((entry, rank) => (
                      <tr key={`${entry.row.smiles}-sim-${entry.index}`}>
                        <td>{rank + 1}</td>
                        <td>{entry.row.name}</td>
                        <td>{similarity.scores[entry.index].toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="muted small">No score computed yet. The first run loads the kernel and fingerprints the library.</p>
          )}
        </Card>
      ) : null}
    </div>
  );
}

