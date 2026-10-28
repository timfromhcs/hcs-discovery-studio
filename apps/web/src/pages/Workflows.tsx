import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useDatasets,
  useDeleteWorkflow,
  useProject,
  useProjectWorkflows,
  useWorkflowCatalog,
} from "../api/queries";
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
  Skeleton,
  useToast,
} from "../components/ui";
import { formatRelative } from "../lib/format";
import type { WorkflowSummary } from "../api/types";

export function WorkflowsPage() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const workflows = useProjectWorkflows(projectId);
  const catalog = useWorkflowCatalog();
  const datasets = useDatasets(projectId);
  const deleteWorkflow = useDeleteWorkflow(projectId);
  const { notify } = useToast();
  const [running, setRunning] = useState<WorkflowSummary | null>(null);
  const [deleting, setDeleting] = useState<WorkflowSummary | null>(null);

  const remove = async () => {
    if (!deleting) return;
    try {
      await deleteWorkflow.mutateAsync(deleting.id);
      notify(`Workflow “${deleting.name}” deleted`, "ok");
      setDeleting(null);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not delete the workflow", "danger");
    }
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow={
          <>
            <Link to={`/projects/${projectId}`}>{project.data?.project.name ?? "Project"}</Link>
            <Icon name="chevronRight" size={12} /> Workflows
          </>
        }
        title="Workflows"
        description="Typed, single-input DAGs. Validation runs before queueing and the exact definition is snapshotted into every run."
        actions={
          <LinkButton to={`/projects/${projectId}/workflows/new`} variant="primary" icon="plus">
            New workflow
          </LinkButton>
        }
      />

      <InlineNotice tone="info" title="Implemented node set">
        This release ships five deterministic node types: RDKit descriptors, Morgan/Tanimoto similarity, explicit rule
        filters, Pareto/composite ranking, and Markdown/HTML summary reports. Docking, structure prediction and ADMET
        nodes are listed as planned in the model registry and cannot be queued.
      </InlineNotice>

      <Card>
        <CardHeader
          title="Saved workflows"
          subtitle="Project-owned definitions with content hashes."
          actions={
            <LinkButton to={`/projects/${projectId}/workflows/new`} size="sm" variant="quiet" icon="plus">
              New
            </LinkButton>
          }
        />
        {workflows.isLoading ? (
          <Skeleton className="skeleton-block" />
        ) : workflows.error ? (
          <ErrorState error={workflows.error} onRetry={() => void workflows.refetch()} />
        ) : workflows.data?.items.length ? (
          <div className="workflow-list">
            {workflows.data.items.map((workflow) => (
              <article key={workflow.id} className="workflow-row">
                <div className="workflow-row-main">
                  <div className="workflow-row-title">
                    <Link to={`/projects/${projectId}/workflows/${workflow.id}`}>{workflow.name}</Link>
                    <Badge tone="neutral">{workflow.definition?.nodes.length ?? 0} nodes</Badge>
                  </div>
                  <p className="muted small">{workflow.description || "No description."}</p>
                  <div className="workflow-row-meta">
                    <span className="mono tiny">{workflow.content_hash.slice(0, 20)}…</span>
                    <span className="muted tiny">Updated {formatRelative(workflow.updated_at)}</span>
                  </div>
                </div>
                <div className="workflow-row-actions">
                  <Button size="sm" variant="secondary" icon="play" onClick={() => setRunning(workflow)} disabled={!datasets.data?.items.length}>
                    Run
                  </Button>
                  <LinkButton to={`/projects/${projectId}/workflows/${workflow.id}`} size="sm" variant="quiet" icon="workflow">
                    Edit
                  </LinkButton>
                  <button className="icon-btn danger-hover" aria-label={`Delete ${workflow.name}`} onClick={() => setDeleting(workflow)}>
                    <Icon name="trash" size={15} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="workflow"
            title="No saved workflows"
            description="Start from a built-in template. You can inspect and edit every node before saving."
          />
        )}
      </Card>

      <Card>
        <CardHeader title="Built-in templates" subtitle="Deterministic, offline starting points. Templates are copied into your project when saved." icon="flask" />
        {catalog.isLoading ? (
          <Skeleton className="skeleton-block" />
        ) : catalog.error ? (
          <ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} />
        ) : (
          <div className="template-grid">
            {catalog.data?.templates.map((template) => (
              <article key={template.id} className="template-card">
                <div className="template-head">
                  <span className="template-icon">
                    <Icon name="workflow" size={18} />
                  </span>
                  <Badge tone="accent">offline</Badge>
                </div>
                <h3>{template.name}</h3>
                <p className="small muted">{template.description}</p>
                <div className="chip-row">
                  {template.nodes.map((node) => (
                    <span key={node.id} className="chip mono">
                      {node.type}
                    </span>
                  ))}
                </div>
                <div className="template-actions">
                  <LinkButton
                    to={`/projects/${projectId}/workflows/new?template=${encodeURIComponent(template.id)}`}
                    size="sm"
                    variant="primary"
                    icon="plus"
                  >
                    Use template
                  </LinkButton>
                  {datasets.data?.items.length ? (
                    <Button
                      size="sm"
                      variant="quiet"
                      icon="play"
                      onClick={() => {
                        setRunning({
                          id: "",
                          name: template.name,
                          description: template.description ?? "",
                          content_hash: "",
                          definition: template,
                          updated_at: new Date().toISOString(),
                        });
                      }}
                    >
                      Run without saving
                    </Button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Node catalog" subtitle="The palette is generated from the live registry, including JSON schemas." icon="models" />
        <div className="catalog-grid">
          {catalog.data?.items.map((item) => (
            <div key={item.type} className="catalog-card">
              <div className="row-between">
                <span className="mono small">{item.type}</span>
                <Badge tone="neutral">v{item.version}</Badge>
              </div>
              <strong>{item.title}</strong>
              <p className="small muted">{item.description}</p>
              <div className="tiny muted">
                Category: {item.category}
                {item.requires.length ? ` · requires: ${item.requires.join(", ")}` : ""}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <StartRunModal
        open={Boolean(running)}
        onClose={() => setRunning(null)}
        projectId={projectId}
        datasets={datasets.data?.items ?? []}
        workflows={workflows.data?.items ?? []}
        templates={catalog.data?.templates ?? []}
        preset={running?.definition ? { definition: running.definition, workflowId: running.id || undefined, name: running.name } : null}
      />
      <ConfirmDialog
        open={Boolean(deleting)}
        title={`Delete workflow “${deleting?.name ?? ""}”?`}
        description="Existing runs keep their own workflow snapshots."
        confirmLabel="Delete workflow"
        onClose={() => setDeleting(null)}
        onConfirm={() => void remove()}
        busy={deleteWorkflow.isPending}
      />
    </div>
  );
}
