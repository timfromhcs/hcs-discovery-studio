import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import {
  useDatasets,
  useProject,
  useProjectWorkflows,
  useWorkflow,
  useWorkflowCatalog,
} from "../api/queries";
import { Icon } from "../components/Icon";
import { StartRunModal } from "../components/StartRunModal";
import { WorkflowGraph } from "../components/WorkflowGraph";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Checkbox,
  CopyButton,
  EmptyState,
  ErrorState,
  Field,
  Input,
  InlineNotice,
  PageHeader,
  Select,
  Skeleton,
  Textarea,
  useToast,
} from "../components/ui";
import { downloadText } from "../lib/format";
import type { NodeCatalogItem, WorkflowDefinition, WorkflowNode } from "../api/types";

const DESCRIPTORS = [
  ["mw", "Molecular weight", "g/mol"],
  ["logp", "cLogP", "log10"],
  ["tpsa", "TPSA", "Å²"],
  ["hbd", "H-bond donors", "count"],
  ["hba", "H-bond acceptors", "count"],
  ["rotb", "Rotatable bonds", "count"],
  ["rings", "Ring count", "count"],
  ["aromatic_rings", "Aromatic rings", "count"],
  ["heavy_atoms", "Heavy atoms", "count"],
  ["fsp3", "Fraction sp³", "0-1"],
  ["qed", "QED", "0-1"],
  ["formal_charge", "Formal charge", "charge"],
  ["mr", "Molar refractivity", "cm³/mol"],
];

function emptyDefinition(): WorkflowDefinition {
  return {
    schema_version: 1,
    id: `workflow_${Date.now().toString(36)}`,
    name: "Untitled workflow",
    description: "",
    nodes: [],
    edges: [],
  };
}

function defaultConfig(item: NodeCatalogItem): Record<string, unknown> {
  switch (item.type) {
    case "chem.descriptors":
      return { descriptors: ["mw", "logp", "tpsa", "hbd", "hba", "rotb", "qed"] };
    case "chem.similarity":
      return { query_smiles: "CCO", radius: 2, bits: 2048, metric: "tanimoto", column: "similarity_query" };
    case "filter.rules":
      return {
        mode: "flag",
        rules: [{ column: "mw", op: "between", value: 150, value2: 600, label: "MW 150–600 g/mol" }],
      };
    case "rank.pareto":
      return { objectives: [{ column: "qed", direction: "higher", weight: 1.0 }], pareto_front_limit: 10 };
    case "report.summary":
      return { title: "Run summary", top_n: 10 };
    default:
      return {};
  }
}

function uniqueNodeId(type: string, nodes: WorkflowNode[]): string {
  const base = type.split(".").pop()?.replace(/[^a-z0-9_]/g, "_") || "node";
  const safeBase = /^[a-z]/.test(base) ? base : `n_${base}`;
  const used = new Set(nodes.map((node) => node.id));
  if (!used.has(safeBase)) return safeBase;
  let index = 2;
  while (used.has(`${safeBase}_${index}`)) index += 1;
  return `${safeBase}_${index}`;
}

export function WorkflowEditorPage() {
  const { projectId = "", workflowId } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const isNew = !workflowId || workflowId === "new";
  const project = useProject(projectId);
  const catalog = useWorkflowCatalog();
  const saved = useWorkflow(isNew ? "" : workflowId ?? "");
  const datasets = useDatasets(projectId);
  const workflows = useProjectWorkflows(projectId);
  const validate = useMutation({ mutationFn: api.workflows.validate });
  const { notify } = useToast();

  const [definition, setDefinition] = useState<WorkflowDefinition | null>(null);
  const [savedId, setSavedId] = useState(isNew ? "" : workflowId ?? "");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showRun, setShowRun] = useState(false);
  const [paletteSearch, setPaletteSearch] = useState("");
  const [edgeSource, setEdgeSource] = useState("");
  const [edgeTarget, setEdgeTarget] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const initialised = useRef(false);

  useEffect(() => {
    if (initialised.current) return;
    if (!isNew) {
      if (saved.data?.definition) {
        setDefinition(structuredClone(saved.data.definition));
        setSelectedId(saved.data.definition.nodes[0]?.id ?? null);
        initialised.current = true;
      }
      return;
    }
    if (!catalog.data) return;
    const templateId = params.get("template");
    const template = catalog.data.templates.find((item) => item.id === templateId);
    const base = template ? structuredClone(template) : emptyDefinition();
    base.id = base.id || `workflow_${Date.now().toString(36)}`;
    setDefinition(base);
    setSelectedId(base.nodes[0]?.id ?? null);
    initialised.current = true;
  }, [catalog.data, saved.data, isNew, params]);

  useEffect(() => {
    if (!definition || !initialised.current) return;
    const handle = window.setTimeout(() => validate.mutate(definition), 500);
    return () => window.clearTimeout(handle);
  }, [definition]);

  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const selectedNode = definition?.nodes.find((node) => node.id === selectedId) ?? null;
  const selectedCatalog = catalog.data?.items.find((item) => item.type === selectedNode?.type);

  const update = (updater: (current: WorkflowDefinition) => WorkflowDefinition) => {
    setDefinition((current) => (current ? updater(current) : current));
    setDirty(true);
  };

  const updateNode = (nodeId: string, patch: Partial<WorkflowNode>) => {
    update((current) => ({
      ...current,
      nodes: current.nodes.map((node) => (node.id === nodeId ? { ...node, ...patch } : node)),
    }));
  };

  const addNode = (item: NodeCatalogItem) => {
    const id = uniqueNodeId(item.type, definition?.nodes ?? []);
    update((current) => ({
      ...current,
      nodes: [...current.nodes, { id, type: item.type, title: item.title, config: defaultConfig(item) }],
    }));
    setSelectedId(id);
  };

  const removeNode = (nodeId: string) => {
    update((current) => ({
      ...current,
      nodes: current.nodes.filter((node) => node.id !== nodeId),
      edges: current.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
    }));
    if (selectedId === nodeId) setSelectedId(null);
  };

  const addEdge = () => {
    if (!edgeSource || !edgeTarget || edgeSource === edgeTarget) return;
    update((current) => {
      if (current.edges.some((edge) => edge.source === edgeSource && edge.target === edgeTarget)) return current;
      return {
        ...current,
        edges: [...current.edges.filter((edge) => edge.target !== edgeTarget), { source: edgeSource, target: edgeTarget }],
      };
    });
    setEdgeSource("");
    setEdgeTarget("");
  };

  const removeEdge = (source: string, target: string) => {
    update((current) => ({
      ...current,
      edges: current.edges.filter((edge) => !(edge.source === source && edge.target === target)),
    }));
  };

  const issues = useMemo(() => {
    const error = validate.error;
    if (!error) return [];
    if (error instanceof ApiError && error.details && typeof error.details === "object") {
      const details = error.details as { issues?: Array<Record<string, unknown>> };
      if (Array.isArray(details.issues)) {
        return details.issues.map((issue) => {
          const node = issue.node ? `[${String(issue.node)}] ` : "";
          return `${node}${String(issue.message ?? issue.code ?? "Validation issue")}`;
        });
      }
    }
    return [error instanceof Error ? error.message : "Validation failed."];
  }, [validate.error]);

  const save = async () => {
    if (!definition) return;
    setSaveError(null);
    setSaving(true);
    try {
      await api.workflows.validate(definition);
      const result = await api.workflows.save(projectId, definition, savedId || undefined);
      setSavedId(result.id);
      setDirty(false);
      notify(`Workflow “${result.name}” saved`, "ok");
      if (isNew) navigate(`/projects/${projectId}/workflows/${result.id}`, { replace: true });
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Could not save the workflow.");
    } finally {
      setSaving(false);
    }
  };

  const exportJson = () => {
    if (!definition) return;
    downloadText(`${definition.name.replace(/[^a-z0-9-_]+/gi, "-").toLowerCase()}.json`, JSON.stringify(definition, null, 2));
    notify("Workflow definition downloaded", "ok");
  };

  const importJson = async (file: File) => {
    setImportError(null);
    try {
      const parsed = JSON.parse(await file.text()) as WorkflowDefinition;
      if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
        throw new Error("File must contain a workflow object with nodes and edges arrays.");
      }
      setDefinition(parsed);
      setSelectedId(parsed.nodes[0]?.id ?? null);
      setDirty(true);
      notify("Workflow definition imported into the editor", "ok");
    } catch (error) {
      setImportError(error instanceof Error ? error.message : "Could not parse this file.");
    }
  };

  if (!isNew && saved.isLoading) {
    return (
      <div className="page">
        <Skeleton className="skeleton-hero" />
        <Skeleton className="skeleton-block tall-skeleton" />
      </div>
    );
  }

  if (!isNew && saved.error) {
    return (
      <div className="page">
        <ErrorState error={saved.error} onRetry={() => void saved.refetch()} />
        <Link className="text-link" to={`/projects/${projectId}/workflows`}>
          Back to workflows
        </Link>
      </div>
    );
  }

  if (isNew && catalog.error) {
    return (
      <div className="page">
        <ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} />
        <Link className="text-link" to={`/projects/${projectId}/workflows`}>
          Back to workflows
        </Link>
      </div>
    );
  }

  if (!definition) {
    return (
      <div className="page">
        <Skeleton className="skeleton-hero" />
        <Skeleton className="skeleton-block tall-skeleton" />
      </div>
    );
  }

  const catalogItems = catalog.data?.items ?? [];
  const filteredPalette = catalogItems.filter((item) =>
    `${item.title} ${item.type} ${item.category}`.toLowerCase().includes(paletteSearch.toLowerCase()),
  );
  const valid = validate.isSuccess && !validate.isPending;
  const invalid = Boolean(validate.error);

  return (
    <div className="page editor-page">
      <PageHeader
        eyebrow={
          <>
            <Link to={`/projects/${projectId}`}>{project.data?.project.name ?? "Project"}</Link>
            <Icon name="chevronRight" size={12} />
            <Link to={`/projects/${projectId}/workflows`}>Workflows</Link>
            <Icon name="chevronRight" size={12} />
            {savedId ? <span className="mono">{savedId}</span> : "New"}
          </>
        }
        title={
          <span className="title-input-wrap">
            <input
              className="title-input"
              aria-label="Workflow name"
              value={definition.name}
              maxLength={200}
              onChange={(event) => update((current) => ({ ...current, name: event.target.value }))}
            />
          </span>
        }
        description="Single-input DAG. The graph, configuration, engine versions and dataset checksum are frozen into each run."
        actions={
          <>
            <input
              ref={importRef}
              type="file"
              accept=".json,application/json"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void importJson(file);
                event.target.value = "";
              }}
            />
            <Button variant="quiet" icon="upload" onClick={() => importRef.current?.click()}>
              Import
            </Button>
            <Button variant="quiet" icon="download" onClick={exportJson}>
              Export
            </Button>
            <Button variant="secondary" icon="play" onClick={() => setShowRun(true)} disabled={invalid || !datasets.data?.items.length}>
              Run
            </Button>
            <Button variant="primary" icon="check" onClick={() => void save()} loading={saving} disabled={invalid}>
              Save
            </Button>
          </>
        }
        meta={
          <>
            {dirty ? <Badge tone="warn">Unsaved changes</Badge> : savedId ? <Badge tone="ok">Saved</Badge> : <Badge tone="neutral">Draft</Badge>}
            {validate.isPending ? <Badge tone="info">Validating…</Badge> : valid ? <Badge tone="ok">Valid</Badge> : null}
            {invalid ? <Badge tone="danger">Needs attention</Badge> : null}
            {validate.data ? <span className="mono tiny">hash {validate.data.content_hash.slice(0, 16)}…</span> : null}
            {savedId ? <CopyButton value={savedId} label="Copy ID" compact /> : null}
          </>
        }
      />

      {saveError ? <InlineNotice tone="danger" title="Save failed">{saveError}</InlineNotice> : null}
      {importError ? <InlineNotice tone="danger" title="Import failed">{importError}</InlineNotice> : null}
      {!datasets.data?.items.length ? (
        <InlineNotice tone="warn" title="No dataset to run against">
          You can still design and save this workflow. Import a dataset in the{" "}
          <Link to={`/projects/${projectId}/library`}>compound library</Link> before running it.
        </InlineNotice>
      ) : null}

      <div className="editor-layout">
        <Card className="palette-card">
          <CardHeader title="Node palette" subtitle="Only registered, executable nodes appear here." icon="plus" />
          <div className="search-field small">
            <Icon name="search" size={15} />
            <input
              aria-label="Search node palette"
              placeholder="Search nodes…"
              value={paletteSearch}
              onChange={(event) => setPaletteSearch(event.target.value)}
            />
          </div>
          <div className="palette-list">
            {filteredPalette.map((item) => (
              <button key={item.type} className="palette-item" onClick={() => addNode(item)} title={item.description}>
                <span className="palette-icon">
                  <Icon
                    name={
                      item.category === "chemistry"
                        ? "flask"
                        : item.category === "prioritisation"
                          ? "results"
                          : item.category === "reporting"
                            ? "download"
                            : "filter"
                    }
                    size={16}
                  />
                </span>
                <span>
                  <strong>{item.title}</strong>
                  <span className="palette-type mono">{item.type}</span>
                </span>
                <Icon name="plus" size={14} />
              </button>
            ))}
            {!filteredPalette.length ? <p className="muted small">No node matches “{paletteSearch}”.</p> : null}
          </div>
          <p className="palette-foot">
            Planned engines (Vina, OpenMM, Boltz, Chai, Chemprop) are not palette items. See the{" "}
            <Link to="/models">model registry</Link> for status.
          </p>
        </Card>

        <div className="editor-center">
          <Card>
            <CardHeader
              title="Graph"
              subtitle="Click a node to inspect it. Keyboard focus and Enter select nodes."
              actions={<Badge tone="neutral">{definition.nodes.length} nodes · {definition.edges.length} edges</Badge>}
            />
            <WorkflowGraph
              definition={definition}
              selectedId={selectedId}
              onSelect={setSelectedId}
              statuses={validate.data ? Object.fromEntries(validate.data.order.map((id) => [id, "pending" as const])) : undefined}
            />
            <Field label="Description" htmlFor="workflow-description" hint="Shown in the template list and run previews.">
              <Textarea
                id="workflow-description"
                rows={2}
                maxLength={2000}
                value={definition.description ?? ""}
                onChange={(event) => update((current) => ({ ...current, description: event.target.value }))}
              />
            </Field>
          </Card>

          <Card>
            <CardHeader title="Validation" subtitle="Server-side schema, graph, column and configuration checks." icon="shield" />
            {validate.isPending ? (
              <Skeleton className="skeleton-block" />
            ) : invalid ? (
              <div className="validation-panel error">
                <strong>Workflow is not runnable</strong>
                <ul>
                  {issues.map((issue, index) => (
                    <li key={index}>{issue}</li>
                  ))}
                </ul>
                <p className="small muted">
                  Every node must form one connected, acyclic branch. This version supports one input per node and
                  exactly one entry node.
                </p>
              </div>
            ) : validate.data ? (
              <div className="validation-panel ok">
                <strong>Valid · {validate.data.order.length} execution steps</strong>
                <div className="pipeline">
                  {validate.data.nodes.map((node, index) => (
                    <div key={node.id} className="pipeline-step">
                      <span className="pipeline-index">{index + 1}</span>
                      <div>
                        <strong>{definition.nodes.find((item) => item.id === node.id)?.title ?? node.id}</strong>
                        <span className="mono tiny">{node.type}</span>
                      </div>
                      <span className="muted tiny">
                        {node.columns_after.length} output columns
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="muted small">Validation starts automatically after edits.</p>
            )}
          </Card>

          <Card>
            <CardHeader title="Connections" subtitle="Edges are typed by node contracts and validated server-side." icon="workflow" />
            {definition.edges.length ? (
              <ul className="edge-list">
                {definition.edges.map((edge) => (
                  <li key={`${edge.source}-${edge.target}`}>
                    <span className="mono">{edge.source}</span>
                    <Icon name="arrowRight" size={14} />
                    <span className="mono">{edge.target}</span>
                    <button className="icon-btn danger-hover" aria-label={`Remove edge ${edge.source} to ${edge.target}`} onClick={() => removeEdge(edge.source, edge.target)}>
                      <Icon name="trash" size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No connections. Add an edge so the nodes form one linear branch.</p>
            )}
            <div className="edge-builder">
              <Select aria-label="Edge source" value={edgeSource} onChange={(event) => setEdgeSource(event.target.value)}>
                <option value="">From node…</option>
                {definition.nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.title || node.type} ({node.id})
                  </option>
                ))}
              </Select>
              <Icon name="arrowRight" size={16} />
              <Select aria-label="Edge target" value={edgeTarget} onChange={(event) => setEdgeTarget(event.target.value)}>
                <option value="">To node…</option>
                {definition.nodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.title || node.type} ({node.id})
                  </option>
                ))}
              </Select>
              <Button size="sm" variant="secondary" icon="plus" onClick={addEdge} disabled={!edgeSource || !edgeTarget || edgeSource === edgeTarget}>
                Connect
              </Button>
            </div>
          </Card>

          <Card>
            <CardHeader title="Nodes" subtitle="Stable IDs are used in logs, cache keys and artifacts." icon="models" />
            {definition.nodes.length ? (
              <div className="table-wrap">
                <table className="data-table compact-table nodes-table">
                  <thead>
                    <tr>
                      <th>ID / type</th>
                      <th>Title</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {definition.nodes.map((node) => (
                      <tr key={node.id} className={selectedId === node.id ? "selected-row" : ""}>
                        <td className="mono small">
                          {node.id}
                          <div className="muted">{node.type}</div>
                        </td>
                        <td>{node.title || "—"}</td>
                        <td>
                          <div className="row-actions">
                            <button className="text-link" onClick={() => setSelectedId(node.id)}>
                              Edit
                            </button>
                            <button className="icon-btn danger-hover" aria-label={`Delete node ${node.id}`} onClick={() => removeNode(node.id)}>
                              <Icon name="trash" size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState compact icon="workflow" title="Empty graph" description="Add a node from the palette to begin." />
            )}
          </Card>
        </div>

        <Card className="inspector-card">
          <CardHeader title="Inspector" subtitle={selectedNode ? selectedNode.type : "Select a node in the graph."} icon="settings" />
          {selectedNode ? (
            <div className="form-stack">
              <Field label="Node ID" hint="Stable identifier; cannot be renamed." htmlFor="node-id">
                <Input id="node-id" value={selectedNode.id} readOnly className="mono" />
              </Field>
              <Field label="Display title" htmlFor="node-title">
                <Input
                  id="node-title"
                  value={selectedNode.title ?? ""}
                  maxLength={120}
                  onChange={(event) => updateNode(selectedNode.id, { title: event.target.value })}
                />
              </Field>
              <Field label="Timeout (seconds)" htmlFor="node-timeout" hint="1–86,400. Applied by the executor.">
                <Input
                  id="node-timeout"
                  type="number"
                  min={1}
                  max={86400}
                  value={selectedNode.timeout_seconds ?? 300}
                  onChange={(event) =>
                    updateNode(selectedNode.id, { timeout_seconds: Math.max(1, Math.min(86400, Number(event.target.value) || 1)) })
                  }
                />
              </Field>
              {selectedCatalog ? (
                <>
                  <div className="inspector-description">
                    <p className="small">{selectedCatalog.description}</p>
                    {selectedCatalog.documentation ? <p className="tiny muted">{selectedCatalog.documentation}</p> : null}
                  </div>
                  <ConfigForm
                    item={selectedCatalog}
                    config={selectedNode.config}
                    onChange={(config) => updateNode(selectedNode.id, { config })}
                  />
                </>
              ) : (
                <InlineNotice tone="warn" title="Unknown node type">
                  This node type is not in the current registry and will fail validation.
                </InlineNotice>
              )}
            </div>
          ) : (
            <EmptyState compact icon="settings" title="Nothing selected" description="Select a node to edit its validated configuration." />
          )}
        </Card>
      </div>

      <StartRunModal
        open={showRun}
        onClose={() => setShowRun(false)}
        projectId={projectId}
        datasets={datasets.data?.items ?? []}
        workflows={workflows.data?.items ?? []}
        templates={[]}
        preset={{ definition, workflowId: savedId || undefined }}
      />
    </div>
  );
}

type Schema = {
  type?: string | string[];
  title?: string;
  description?: string;
  properties?: Record<string, Schema>;
  required?: string[];
  enum?: Array<string | number>;
  default?: unknown;
  items?: Schema;
  minimum?: number;
  maximum?: number;
  anyOf?: Schema[];
};

function schemaType(schema: Schema): string {
  if (schema.type) return Array.isArray(schema.type) ? (schema.type.find((value) => value !== "null") ?? "string") : schema.type;
  if (schema.anyOf) {
    const match = schema.anyOf.find((entry) => entry.type && entry.type !== "null");
    if (match?.type) return Array.isArray(match.type) ? match.type[0] : match.type;
    if (schema.anyOf.some((entry) => entry.enum)) return "enum";
  }
  if (schema.enum) return "enum";
  return "string";
}

function ConfigForm({
  item,
  config,
  onChange,
}: {
  item: NodeCatalogItem;
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const schema = item.config_schema as Schema;
  const properties = schema.properties ?? {};
  const required = new Set(schema.required ?? []);
  const [advanced, setAdvanced] = useState(false);
  const [advancedText, setAdvancedText] = useState(() => JSON.stringify(config, null, 2));
  const [advancedError, setAdvancedError] = useState<string | null>(null);

  const setValue = (key: string, value: unknown) => {
    const next = { ...config };
    if (value === undefined) delete next[key];
    else next[key] = value;
    onChange(next);
  };

  const applyAdvanced = () => {
    try {
      const parsed = JSON.parse(advancedText) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Configuration must be a JSON object.");
      }
      onChange(parsed as Record<string, unknown>);
      setAdvancedError(null);
      setAdvanced(false);
    } catch (error) {
      setAdvancedError(error instanceof Error ? error.message : "Invalid JSON.");
    }
  };

  return (
    <div className="config-form">
      <div className="config-head">
        <span className="meta-label">Configuration</span>
        <button className="text-link small" onClick={() => {
          setAdvancedText(JSON.stringify(config, null, 2));
          setAdvanced((value) => !value);
        }}>
          {advanced ? "Use form" : "Advanced JSON"}
        </button>
      </div>

      {advanced ? (
        <div className="form-stack">
          <Textarea
            aria-label="Node configuration JSON"
            rows={16}
            className="mono"
            value={advancedText}
            onChange={(event) => setAdvancedText(event.target.value)}
          />
          {advancedError ? <p className="field-error">{advancedError}</p> : null}
          <Button size="sm" variant="secondary" icon="check" onClick={applyAdvanced}>
            Apply JSON
          </Button>
        </div>
      ) : (
        <div className="form-stack">
          {Object.entries(properties).map(([key, property]) => {
            const type = schemaType(property);
            const label = property.title ?? key.replaceAll("_", " ");
            const value = config[key];
            const isRequired = required.has(key);
            if (key === "descriptors" && type === "array") {
              const selected = Array.isArray(value) ? (value as string[]) : [];
              return (
                <fieldset className="fieldset" key={key}>
                  <legend>
                    {label}
                    {isRequired ? <span className="required"> *</span> : null}
                  </legend>
                  <p className="field-hint">Values are computed by RDKit; units appear in results.</p>
                  <div className="descriptor-checks">
                    {DESCRIPTORS.map(([id, name, unit]) => (
                      <Checkbox
                        key={id}
                        label={
                          <span>
                            {name} <span className="muted tiny">({unit})</span>
                          </span>
                        }
                        checked={selected.includes(id)}
                        onChange={(event) =>
                          setValue(
                            key,
                            event.target.checked ? [...selected, id] : selected.filter((entry) => entry !== id),
                          )
                        }
                      />
                    ))}
                  </div>
                </fieldset>
              );
            }
            if (type === "array" && property.items?.type === "string") {
              const selected = Array.isArray(value) ? (value as string[]) : [];
              return (
                <Field key={key} label={label} required={isRequired} hint="Comma-separated values.">
                  <Input
                    value={selected.join(", ")}
                    onChange={(event) =>
                      setValue(
                        key,
                        event.target.value
                          .split(",")
                          .map((entry) => entry.trim())
                          .filter(Boolean),
                      )
                    }
                  />
                </Field>
              );
            }
            if (type === "array" || type === "object") {
              return (
                <JsonConfigField
                  key={key}
                  label={label}
                  required={isRequired}
                  hint={property.description}
                  value={value}
                  onChange={(next) => setValue(key, next)}
                />
              );
            }
            if (type === "boolean") {
              return (
                <Checkbox
                  key={key}
                  label={label}
                  description={property.description}
                  checked={Boolean(value)}
                  onChange={(event) => setValue(key, event.target.checked)}
                />
              );
            }
            if (type === "number" || type === "integer") {
              return (
                <Field key={key} label={label} required={isRequired} hint={property.description}>
                  <Input
                    type="number"
                    value={value === undefined || value === null ? "" : String(value)}
                    min={property.minimum}
                    max={property.maximum}
                    step={type === "integer" ? 1 : "any"}
                    onChange={(event) => {
                      const raw = event.target.value;
                      setValue(key, raw === "" ? undefined : Number(raw));
                    }}
                  />
                </Field>
              );
            }
            if (property.enum) {
              return (
                <Field key={key} label={label} required={isRequired} hint={property.description}>
                  <Select value={String(value ?? property.enum[0])} onChange={(event) => setValue(key, event.target.value)}>
                    {property.enum.map((option) => (
                      <option key={String(option)} value={String(option)}>
                        {String(option)}
                      </option>
                    ))}
                  </Select>
                </Field>
              );
            }
            return (
              <Field key={key} label={label} required={isRequired} hint={property.description}>
                <Input value={typeof value === "string" ? value : value === undefined ? "" : String(value)} onChange={(event) => setValue(key, event.target.value)} />
              </Field>
            );
          })}
        </div>
      )}
    </div>
  );
}

function JsonConfigField({
  label,
  required,
  hint,
  value,
  onChange,
}: {
  label: string;
  required: boolean;
  hint?: string;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const [text, setText] = useState(() => JSON.stringify(value ?? [], null, 2));
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const apply = () => {
    try {
      const parsed = JSON.parse(text) as unknown;
      onChange(parsed);
      setError(null);
      setEditing(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Invalid JSON.");
    }
  };

  if (!editing) {
    return (
      <div className="json-field">
        <div className="row-between">
          <span className="field-label">
            {label}
            {required ? <span className="required"> *</span> : null}
          </span>
          <button className="text-link small" onClick={() => {
            setText(JSON.stringify(value ?? [], null, 2));
            setEditing(true);
          }}>
            Edit
          </button>
        </div>
        <pre className="json-preview">{JSON.stringify(value ?? [], null, 2)}</pre>
        {hint ? <p className="field-hint">{hint}</p> : null}
      </div>
    );
  }

  return (
    <div className="json-field">
      <span className="field-label">
        {label}
        {required ? <span className="required"> *</span> : null}
      </span>
      <Textarea aria-label={`${label} JSON`} rows={8} className="mono" value={text} onChange={(event) => setText(event.target.value)} />
      {error ? <p className="field-error">{error}</p> : null}
      <div className="row-actions">
        <Button size="sm" variant="secondary" icon="check" onClick={apply}>
          Apply
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
