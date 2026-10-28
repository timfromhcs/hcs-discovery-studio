import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCreateRun } from "../api/queries";
import type { DatasetSummary, WorkflowDefinition, WorkflowSummary } from "../api/types";
import { Button, Field, InlineNotice, Input, Modal, Select, useToast } from "./ui";

interface Preset {
  definition: WorkflowDefinition;
  workflowId?: string;
  name?: string;
}

export function StartRunModal({
  open,
  onClose,
  projectId,
  datasets,
  workflows,
  templates,
  preset,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string;
  datasets: DatasetSummary[];
  workflows: WorkflowSummary[];
  templates: WorkflowDefinition[];
  preset?: Preset | null;
}) {
  const navigate = useNavigate();
  const createRun = useCreateRun();
  const { notify } = useToast();
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const [source, setSource] = useState<string>(preset ? "editor" : workflows[0] ? `workflow:${workflows[0].id}` : templates[0] ? `template:${templates[0].id}` : "");
  const [seed, setSeed] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDatasetId((current) => current || datasets[0]?.id || "");
    setSource(preset ? "editor" : workflows[0] ? `workflow:${workflows[0].id}` : templates[0] ? `template:${templates[0].id}` : "");
    setSeed("");
    setError(null);
  }, [open, datasets, workflows, templates, preset]);

  const chosen = useMemo(() => {
    if (source === "editor" && preset) return preset.definition;
    if (source.startsWith("workflow:")) {
      const id = source.slice("workflow:".length);
      return workflows.find((workflow) => workflow.id === id)?.definition ?? null;
    }
    if (source.startsWith("template:")) {
      const id = source.slice("template:".length);
      return templates.find((template) => template.id === id) ?? null;
    }
    return null;
  }, [source, preset, workflows, templates]);

  const submit = async () => {
    setError(null);
    if (!datasetId) {
      setError("Choose a dataset that contains imported compounds.");
      return;
    }
    if (!chosen) {
      setError("Choose a saved workflow or a template.");
      return;
    }
    try {
      const payload =
        source === "editor" && preset?.workflowId
          ? {
              project_id: projectId,
              dataset_id: datasetId,
              workflow_id: preset.workflowId,
              seed: seed ? Number(seed) : null,
            }
          : {
              project_id: projectId,
              dataset_id: datasetId,
              workflow: chosen,
              seed: seed ? Number(seed) : null,
            };
      const run = await createRun.mutateAsync(payload);
      notify(`Run ${run.id} queued`, "ok");
      onClose();
      navigate(`/runs/${run.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The run could not be queued.");
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Start a reproducible run"
      description="The workflow snapshot, dataset checksum and engine versions are captured in the run manifest."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={createRun.isPending}>
            Cancel
          </Button>
          <Button variant="primary" icon="play" onClick={submit} loading={createRun.isPending} disabled={!datasets.length}>
            Queue run
          </Button>
        </>
      }
    >
      <div className="form-stack">
        {!datasets.length ? (
          <InlineNotice tone="warn" title="No dataset yet">
            Import a CSV, SDF or SMILES file into this project before running a workflow.
          </InlineNotice>
        ) : null}
        <Field label="Input dataset" htmlFor="run-dataset" required error={error}>
          <Select id="run-dataset" value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name} · {dataset.imported_count} compounds
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Workflow source" htmlFor="run-source" required>
          <Select id="run-source" value={source} onChange={(event) => setSource(event.target.value)}>
            {preset ? <option value="editor">Current editor definition (unsaved)</option> : null}
            {workflows.length ? (
              <optgroup label="Saved workflows">
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={`workflow:${workflow.id}`}>
                    {workflow.name}
                  </option>
                ))}
              </optgroup>
            ) : null}
            {templates.length ? (
              <optgroup label="Built-in templates">
                {templates.map((template) => (
                  <option key={template.id} value={`template:${template.id}`}>
                    {template.name}
                  </option>
                ))}
              </optgroup>
            ) : null}
          </Select>
        </Field>
        <Field label="Seed" htmlFor="run-seed" hint="Optional integer recorded in the manifest. Current nodes are deterministic.">
          <Input
            id="run-seed"
            inputMode="numeric"
            placeholder="e.g. 42"
            value={seed}
            onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ""))}
          />
        </Field>
        {chosen ? (
          <div className="run-preview">
            <div className="meta-label">Run preview</div>
            <strong>{chosen.name}</strong>
            <p className="muted small">{chosen.description || "No description."}</p>
            <div className="run-preview-nodes">
              {chosen.nodes.map((node) => (
                <span key={node.id} className="chip mono">
                  {node.type}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
