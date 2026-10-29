import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  useDatasets,
  useDeleteDataset,
  useDeleteProject,
  useDiagnostics,
  useProject,
  useProjectWorkflows,
  useWorkflowCatalog,
} from "../api/queries";
import { DatasetRowsModal } from "../components/DatasetRowsModal";
import { ImportDatasetModal } from "../components/ImportDatasetModal";
import { StartRunModal } from "../components/StartRunModal";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  InlineNotice,
  LinkButton,
  PageHeader,
  RunStatusBadge,
  Skeleton,
  Stat,
  useToast,
} from "../components/ui";
import { formatDate, formatRelative } from "../lib/format";
import type { DatasetSummary } from "../api/types";

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const project = useProject(projectId);
  const datasets = useDatasets(projectId);
  const workflows = useProjectWorkflows(projectId);
  const catalog = useWorkflowCatalog();
  const diagnostics = useDiagnostics();
  const deleteProject = useDeleteProject();
  const deleteDataset = useDeleteDataset(projectId);
  const { notify } = useToast();
  const [importing, setImporting] = useState(false);
  const [running, setRunning] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<DatasetSummary | null>(null);
  const [deletingDataset, setDeletingDataset] = useState<DatasetSummary | null>(null);
  const [confirmProject, setConfirmProject] = useState(false);

  if (project.isLoading) {
    return (
      <div className="page">
        <Skeleton className="skeleton-hero" />
        <div className="stats-grid">
          <Skeleton className="skeleton-card" />
          <Skeleton className="skeleton-card" />
          <Skeleton className="skeleton-card" />
        </div>
        <Skeleton className="skeleton-block" />
      </div>
    );
  }

  if (project.error || !project.data) {
    return (
      <div className="page">
        <PageHeader title="Project unavailable" />
        <ErrorState error={project.error ?? new Error("Project not found.")} onRetry={() => void project.refetch()} headingLevel={2} />
        <LinkButton to="/" icon="arrowLeft" variant="secondary">
          Back to workspace
        </LinkButton>
      </div>
    );
  }

  const overview = project.data;
  const fullDatasets = datasets.data?.items ?? [];
  const savedWorkflows = workflows.data?.items ?? [];
  const templates = catalog.data?.templates ?? [];

  const removeProject = async () => {
    try {
      await deleteProject.mutateAsync(projectId);
      notify("Project deleted", "ok");
      navigate("/");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not delete the project", "danger");
    }
  };

  const removeDataset = async () => {
    if (!deletingDataset) return;
    try {
      await deleteDataset.mutateAsync(deletingDataset.id);
      notify(`Dataset “${deletingDataset.name}” deleted`, "ok");
      setDeletingDataset(null);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not delete the dataset", "danger");
    }
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow={
          <>
            <Link to="/">Workspace</Link>
            <Icon name="chevronRight" size={12} /> Project
          </>
        }
        title={overview.project.name}
        description={overview.project.description || "No description recorded for this project."}
        actions={
          <>
            <Button variant="secondary" icon="upload" onClick={() => setImporting(true)}>
              Import dataset
            </Button>
            <Button variant="primary" icon="play" onClick={() => setRunning(true)} disabled={!fullDatasets.length}>
              Start run
            </Button>
          </>
        }
        meta={
          <>
            <span className="mono small">{overview.project.id}</span>
            {overview.project.purpose ? <span className="muted small">Purpose: {overview.project.purpose}</span> : null}
            <span className="muted small">Created {formatDate(overview.project.created_at)}</span>
          </>
        }
      />

      <section className="stats-grid" aria-label="Project totals">
        <Stat label="Compounds" value={overview.counts.compounds.toLocaleString()} icon="molecule" to={`/projects/${projectId}/library`} />
        <Stat label="Datasets" value={overview.counts.datasets} icon="database" hint="Provenance preserved" />
        <Stat label="Runs" value={overview.counts.runs} icon="run" to={`/projects/${projectId}/runs`} />
        <Stat label="Saved workflows" value={overview.counts.workflows} icon="workflow" to={`/projects/${projectId}/workflows`} />
      </section>

      {!fullDatasets.length ? (
        <InlineNotice tone="info" title="Start with a library">
          Import a small CSV of SMILES, an SDF file or a .smi list. Columns are auto-detected and every row is checked
          with RDKit before it becomes a compound.
        </InlineNotice>
      ) : null}

      <div className="overview-grid">
        <Card className="span-2">
          <CardHeader
            title="Datasets"
            subtitle="Original files, checksums, row-level outcomes and transformation logs."
            actions={
              <Button size="sm" variant="quiet" icon="upload" onClick={() => setImporting(true)}>
                Import
              </Button>
            }
          />
          {datasets.isLoading ? (
            <Skeleton className="skeleton-block" />
          ) : datasets.error ? (
            <ErrorState error={datasets.error} onRetry={() => void datasets.refetch()} />
          ) : fullDatasets.length ? (
            <div className="table-wrap">
              <table className="data-table responsive-table">
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th className="hide-narrow">Format</th>
                    <th className="num hide-narrow">Records</th>
                    <th className="num">Imported</th>
                    <th className="num">Errors</th>
                    <th className="hide-narrow">Imported at</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {fullDatasets.map((dataset) => (
                    <tr key={dataset.id}>
                      <td>
                        <button className="link-button dataset-name" title={dataset.name} onClick={() => setSelectedDataset(dataset)}>
                          {dataset.name}
                        </button>
                        <div className="mono tiny muted hide-narrow" title={dataset.sha256}>
                          {dataset.sha256.slice(0, 16)}…
                        </div>
                      </td>
                      <td className="hide-narrow">
                        <Badge tone="neutral">{dataset.source_format}</Badge>
                      </td>
                      <td className="num tabular hide-narrow">{dataset.record_count}</td>
                      <td className="num tabular success-text">{dataset.imported_count}</td>
                      <td className="num tabular">
                        {dataset.error_count ? <span className="error-text">{dataset.error_count}</span> : "0"}
                      </td>
                      <td className="muted small hide-narrow">{formatRelative(dataset.created_at)}</td>
                      <td>
                        <div className="row-actions">
                          <button className="text-link hide-narrow" onClick={() => setSelectedDataset(dataset)}>
                            Inspect rows
                          </button>
                          <button className="icon-btn danger-hover" aria-label={`Delete ${dataset.name}`} onClick={() => setDeletingDataset(dataset)}>
                            <Icon name="trash" size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              compact
              icon="database"
              title="No datasets imported"
              description="Import the demo library from examples/datasets/demo_library.csv or use your own file."
              actions={
                <Button size="sm" variant="primary" icon="upload" onClick={() => setImporting(true)}>
                  Import dataset
                </Button>
              }
            />
          )}
        </Card>

        <Card>
          <CardHeader title="Provenance" icon="shield" subtitle="What gets recorded with every import and run." />
          <ul className="provenance-list">
            <li>
              <Icon name="check" size={14} /> Source filename, size class and SHA-256
            </li>
            <li>
              <Icon name="check" size={14} /> Original structure string plus canonical isomeric SMILES
            </li>
            <li>
              <Icon name="check" size={14} /> Salt, charge and tautomer policy
            </li>
            <li>
              <Icon name="check" size={14} /> Workflow snapshot and content hash
            </li>
            <li>
              <Icon name="check" size={14} /> RDKit/Python versions and CPU backend
            </li>
            <li>
              <Icon name="check" size={14} /> Artifact SHA-256 checksums
            </li>
          </ul>
          <div className="card-foot-link">
            <Link to="/about">Read reproducibility limits <Icon name="arrowRight" size={14} /></Link>
          </div>
        </Card>
      </div>

      <div className="overview-grid two-up">
        <Card>
          <CardHeader
            title="Recent runs"
            subtitle="Open a run to stream events and inspect artifacts."
            actions={
              <LinkButton to={`/projects/${projectId}/runs`} size="sm" variant="quiet" icon="arrowRight">
                All runs
              </LinkButton>
            }
          />
          {overview.runs.length ? (
            <ul className="activity-list">
              {overview.runs.slice(0, 5).map((run) => (
                <li key={run.id}>
                  <span className="activity-icon">
                    <Icon name="run" size={16} />
                  </span>
                  <div className="activity-main">
                    <Link to={`/runs/${run.id}`}>{run.workflow_name}</Link>
                    <span className="muted small">
                      {run.id} · {formatRelative(run.created_at)}
                    </span>
                  </div>
                  <RunStatusBadge status={run.status} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState compact icon="run" title="No runs yet" description="Import a dataset, then start the Basic triage template." />
          )}
        </Card>

        <Card>
          <CardHeader
            title="Workflows"
            subtitle="Validated DAGs saved to this project."
            actions={
              <LinkButton to={`/projects/${projectId}/workflows`} size="sm" variant="quiet" icon="arrowRight">
                Open
              </LinkButton>
            }
          />
          {overview.workflows.length ? (
            <ul className="activity-list">
              {overview.workflows.map((workflow) => (
                <li key={workflow.id}>
                  <span className="activity-icon">
                    <Icon name="workflow" size={16} />
                  </span>
                  <div className="activity-main">
                    <Link to={`/projects/${projectId}/workflows/${workflow.id}`}>{workflow.name}</Link>
                    <span className="muted small mono">{workflow.content_hash.slice(0, 14)}…</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState compact icon="workflow" title="No saved workflows" description="Start from a built-in template in the workflow editor." />
          )}
        </Card>
      </div>

      <Card className="danger-zone">
        <CardHeader title="Project maintenance" subtitle="Deletion is permanent and removes linked datasets, compounds and runs." />
        <div className="row-between">
          <p className="muted small">
            Export anything you need first. Deletion also removes this project&apos;s run directories and uploaded files;
            shared node-cache entries remain until <code>hcs-discovery cache prune</code>.
          </p>
          <Button variant="danger" icon="trash" onClick={() => setConfirmProject(true)}>
            Delete project
          </Button>
        </div>
      </Card>

      <ImportDatasetModal projectId={projectId} open={importing} onClose={() => setImporting(false)} />
      <DatasetRowsModal dataset={selectedDataset} open={Boolean(selectedDataset)} onClose={() => setSelectedDataset(null)} />
      <StartRunModal
        open={running}
        onClose={() => setRunning(false)}
        projectId={projectId}
        datasets={fullDatasets}
        workflows={savedWorkflows}
        templates={templates}
      />
      <ConfirmDialog
        open={confirmProject}
        title={`Delete “${overview.project.name}”?`}
        description="This cannot be undone."
        confirmLabel="Delete project"
        onClose={() => setConfirmProject(false)}
        onConfirm={() => void removeProject()}
        busy={deleteProject.isPending}
      >
        <p className="small">
          The project currently contains <strong>{overview.counts.compounds.toLocaleString()} compounds</strong>,{" "}
          <strong>{overview.counts.datasets} datasets</strong> and <strong>{overview.counts.runs} runs</strong>. Their
          database records will be removed.
        </p>
      </ConfirmDialog>
      <ConfirmDialog
        open={Boolean(deletingDataset)}
        title={`Delete dataset “${deletingDataset?.name ?? ""}”?`}
        description="Compounds imported from this dataset will also be removed."
        confirmLabel="Delete dataset"
        onClose={() => setDeletingDataset(null)}
        onConfirm={() => void removeDataset()}
        busy={deleteDataset.isPending}
      >
        <p className="small">
          {deletingDataset?.imported_count ?? 0} imported compounds and {deletingDataset?.record_count ?? 0} source rows
          are linked to this dataset.
        </p>
      </ConfirmDialog>
      {diagnostics.data && diagnostics.data.status !== "ok" ? (
        <InlineNotice tone="warn" title="Environment check is not fully green">
          See <Link to="/settings">Settings → diagnostics</Link> for the exact failing checks.
        </InlineNotice>
      ) : null}
    </div>
  );
}
