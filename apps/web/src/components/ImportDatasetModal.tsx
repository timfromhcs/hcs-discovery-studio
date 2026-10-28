import { useRef, useState } from "react";
import { useImportDataset } from "../api/queries";
import type { DatasetSummary, ImportOptions } from "../api/types";
import { formatBytes } from "../lib/format";
import { Button, Checkbox, Field, InlineNotice, Input, Modal, Select, useToast } from "./ui";

const defaultOptions: ImportOptions = {
  format: "auto",
  license: "unknown",
  strip_salts: true,
  neutralize: false,
  canonical_tautomer: false,
};

export function ImportDatasetModal({
  projectId,
  open,
  onClose,
  onImported,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onImported?: (dataset: DatasetSummary) => void;
}) {
  const importDataset = useImportDataset(projectId);
  const { notify } = useToast();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [options, setOptions] = useState<ImportOptions>(defaultOptions);
  const [name, setName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [smilesColumn, setSmilesColumn] = useState("");
  const [nameColumn, setNameColumn] = useState("");
  const [idColumn, setIdColumn] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DatasetSummary | null>(null);

  const reset = () => {
    setFile(null);
    setOptions(defaultOptions);
    setName("");
    setSourceUrl("");
    setSmilesColumn("");
    setNameColumn("");
    setIdColumn("");
    setError(null);
    setResult(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  const close = () => {
    reset();
    onClose();
  };

  const submit = async () => {
    setError(null);
    if (!file) {
      setError("Choose a CSV, SDF or SMILES file to import.");
      return;
    }
    try {
      const dataset = await importDataset.mutateAsync({
        file,
        options: {
          ...options,
          name: name.trim() || undefined,
          source_url: sourceUrl.trim() || undefined,
          smiles_column: smilesColumn.trim() || undefined,
          name_column: nameColumn.trim() || undefined,
          id_column: idColumn.trim() || undefined,
        },
      });
      setResult(dataset);
      notify(`Imported ${dataset.imported_count} of ${dataset.record_count} records`, dataset.error_count ? "info" : "ok");
      onImported?.(dataset);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The import failed.");
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={result ? "Import complete" : "Import a compound dataset"}
      description={
        result
          ? "Every source row is preserved, including malformed rows. Duplicates stay visible for audit."
          : "Files are parsed locally. Structures are standardised with RDKit; the original record is retained."
      }
      width="lg"
      footer={
        result ? (
          <Button variant="primary" onClick={close}>
            Done
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={close} disabled={importDataset.isPending}>
              Cancel
            </Button>
            <Button variant="primary" icon="upload" onClick={submit} loading={importDataset.isPending}>
              Import dataset
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="form-stack">
          <div className="import-result-grid">
            <div>
              <span className="meta-label">Records</span>
              <strong className="tabular">{result.record_count}</strong>
            </div>
            <div>
              <span className="meta-label">Imported</span>
              <strong className="tabular success-text">{result.imported_count}</strong>
            </div>
            <div>
              <span className="meta-label">Errors</span>
              <strong className="tabular error-text">{result.error_count}</strong>
            </div>
            <div>
              <span className="meta-label">Duplicates</span>
              <strong className="tabular">{result.duplicate_count}</strong>
            </div>
          </div>
          <InlineNotice tone={result.error_count ? "warn" : "ok"} title={result.error_count ? "Some rows need attention" : "Row-level validation passed"}>
            {result.error_count
              ? "Open the dataset in the project to inspect each row error. No rejected row was silently dropped."
              : "All parsed records were imported or retained as duplicates with a linked compound."}
          </InlineNotice>
          <dl className="key-value compact">
            <div>
              <dt>Dataset</dt>
              <dd>{result.name}</dd>
            </div>
            <div>
              <dt>Detected format</dt>
              <dd>{result.source_format}</dd>
            </div>
            <div>
              <dt>SHA-256</dt>
              <dd className="mono break-all">{result.sha256}</dd>
            </div>
          </dl>
        </div>
      ) : (
        <div className="form-stack">
          <Field label="Structure file" htmlFor="dataset-file" required error={error}>
            <div className="file-drop">
              <input
                ref={fileInput}
                id="dataset-file"
                type="file"
                accept=".csv,.tsv,.sdf,.mol,.smi,.txt"
                onChange={(event) => {
                  const chosen = event.target.files?.[0] ?? null;
                  setFile(chosen);
                  if (chosen && !name) setName(chosen.name.replace(/\.[^.]+$/, ""));
                }}
              />
              <Button size="sm" variant="secondary" icon="upload" onClick={() => fileInput.current?.click()}>
                Choose file
              </Button>
              <span className="file-name">
                {file ? (
                  <>
                    <strong>{file.name}</strong> <span className="muted">{formatBytes(file.size)}</span>
                  </>
                ) : (
                  "CSV, SDF, MOL or SMILES · parsed on this machine"
                )}
              </span>
            </div>
          </Field>

          <div className="grid-2">
            <Field label="Display name" htmlFor="dataset-name" hint="Defaults to the filename.">
              <Input id="dataset-name" value={name} maxLength={200} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field label="Format" htmlFor="dataset-format">
              <Select
                id="dataset-format"
                value={options.format}
                onChange={(event) => setOptions({ ...options, format: event.target.value })}
              >
                <option value="auto">Auto-detect</option>
                <option value="csv">CSV</option>
                <option value="sdf">SDF</option>
                <option value="smi">SMILES (.smi)</option>
              </Select>
            </Field>
          </div>

          <div className="grid-2">
            <Field label="SMILES column" htmlFor="smiles-column" hint="CSV only. Auto-detected when blank.">
              <Input
                id="smiles-column"
                placeholder="smiles"
                value={smilesColumn}
                onChange={(event) => setSmilesColumn(event.target.value)}
              />
            </Field>
            <Field label="Name column" htmlFor="name-column" hint="Optional.">
              <Input id="name-column" placeholder="name" value={nameColumn} onChange={(event) => setNameColumn(event.target.value)} />
            </Field>
          </div>

          <div className="grid-2">
            <Field label="Source ID column" htmlFor="id-column" hint="Optional; preserved per compound.">
              <Input id="id-column" placeholder="id" value={idColumn} onChange={(event) => setIdColumn(event.target.value)} />
            </Field>
            <Field label="License" htmlFor="dataset-license" hint="Recorded with every compound from this source.">
              <Input
                id="dataset-license"
                value={options.license}
                placeholder="unknown"
                onChange={(event) => setOptions({ ...options, license: event.target.value })}
              />
            </Field>
          </div>

          <Field label="Source URL" htmlFor="source-url" hint="Optional provenance link.">
            <Input
              id="source-url"
              type="url"
              placeholder="https://…"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
            />
          </Field>

          <fieldset className="fieldset">
            <legend>Standardisation policy</legend>
            <Checkbox
              label="Strip counter-ions (keep largest fragment)"
              description="The original SMILES is preserved alongside the normalised structure."
              checked={options.strip_salts}
              onChange={(event) => setOptions({ ...options, strip_salts: event.target.checked })}
            />
            <Checkbox
              label="Neutralise formal charges"
              description="Transformation is recorded in the dataset log."
              checked={options.neutralize}
              onChange={(event) => setOptions({ ...options, neutralize: event.target.checked })}
            />
            <Checkbox
              label="Canonicalise tautomers"
              description="Can change the represented tautomer; source structure remains available."
              checked={options.canonical_tautomer}
              onChange={(event) => setOptions({ ...options, canonical_tautomer: event.target.checked })}
            />
          </fieldset>
        </div>
      )}
    </Modal>
  );
}
