import { useState } from "react";
import { Link } from "react-router-dom";
import { useDiagnostics, useModels, useProjects, useRuns, useStats } from "../api/queries";
import { NewProjectModal } from "../components/NewProjectModal";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  InlineNotice,
  LinkButton,
  PageHeader,
  RunStatusBadge,
  Skeleton,
  Stat,
} from "../components/ui";
import { Icon } from "../components/Icon";
import { formatRelative } from "../lib/format";

export function WorkspacePage() {
  const projects = useProjects();
  const stats = useStats();
  const runs = useRuns(undefined, 8);
  const diagnostics = useDiagnostics();
  const models = useModels(false);
  const [creating, setCreating] = useState(false);

  const available = models.data?.items.filter((model) => model.status === "available" || model.status === "available_with_limits") ?? [];
  const warning = diagnostics.data?.checks.filter((check) => check.status !== "ok") ?? [];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Workspace"
        title="Your local discovery bench"
        description="Import a library, run a transparent triage workflow, and inspect every row, event and artifact. Everything here runs on this machine."
        actions={
          <>
            <Button variant="secondary" icon="refresh" onClick={() => void diagnostics.refetch()} loading={diagnostics.isFetching}>
              Re-run checks
            </Button>
            <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
              New project
            </Button>
          </>
        }
        meta={
          <>
            <Badge tone="accent">
              <Icon name="shield" size={13} /> {diagnostics.data?.environment.backend ?? "Local CPU baseline"}
            </Badge>
            <span className="muted small">{diagnostics.data ? `Python ${diagnostics.data.environment.python}` : "Checking environment…"}</span>
            {available.length ? (
              <span className="muted small">
                {available.length} executable {available.length === 1 ? "engine" : "engines"} detected
              </span>
            ) : null}
          </>
        }
      />

      {diagnostics.error ? (
        <InlineNotice tone="danger" title="Diagnostics unavailable">
          {diagnostics.error instanceof Error ? diagnostics.error.message : "The local API did not return diagnostics."}
        </InlineNotice>
      ) : warning.length ? (
        <InlineNotice tone="warn" title={`${warning.length} environment check${warning.length === 1 ? "" : "s"} need attention`}>
          {warning.slice(0, 2).map((check) => (
            <span key={check.id}>
              <strong>{check.label}:</strong> {check.detail}{" "}
            </span>
          ))}
          <Link to="/settings">Open diagnostics</Link>
        </InlineNotice>
      ) : null}

      <section className="stats-grid" aria-label="Workspace totals">
        <Stat label="Projects" value={stats.data?.projects ?? "—"} icon="folder" to="/" hint="Local workspaces" />
        <Stat label="Compounds" value={stats.data?.compounds.toLocaleString() ?? "—"} icon="molecule" hint="Imported structures" />
        <Stat label="Runs" value={stats.data?.runs ?? "—"} icon="run" hint="Persisted executions" />
        <Stat
          label="Queue"
          value={stats.data ? `${stats.data.running_runs} active / ${stats.data.queued_runs} queued` : "—"}
          icon="clock"
          hint={stats.data ? (stats.data.queued_runs + stats.data.running_runs > 0 ? "Worker is processing work" : "Idle") : undefined}
        />
      </section>

      <div className="workspace-grid">
        <Card className="span-2">
          <CardHeader
            title="Projects"
            subtitle="One provenance graph per research question."
            actions={
              <Button size="sm" variant="quiet" icon="plus" onClick={() => setCreating(true)}>
                New
              </Button>
            }
          />
          {projects.isLoading ? (
            <div className="project-grid">
              <Skeleton className="skeleton-card" />
              <Skeleton className="skeleton-card" />
            </div>
          ) : projects.error ? (
            <ErrorState error={projects.error} onRetry={() => void projects.refetch()} />
          ) : projects.data?.items.length ? (
            <div className="project-grid">
              {projects.data.items.map((project) => (
                <Link key={project.id} to={`/projects/${project.id}`} className="project-card">
                  <div className="project-card-top">
                    <span className="project-mark">
                      <Icon name="flask" size={17} />
                    </span>
                    <span className="muted small">{formatRelative(project.updated_at)}</span>
                  </div>
                  <h3>{project.name}</h3>
                  <p>{project.description || "No description yet."}</p>
                  <div className="project-card-foot">
                    <span>{project.compound_count.toLocaleString()} compounds</span>
                    <span>{project.run_count} runs</span>
                    <span className="project-open">
                      Open <Icon name="arrowRight" size={14} />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="flask"
              title="Create your first project"
              description="A project groups a library, its provenance, saved workflows and every run. It takes one click and no account."
              actions={
                <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
                  New project
                </Button>
              }
            />
          )}
        </Card>

        <Card>
          <CardHeader title="This machine" subtitle="Probed, not assumed." icon="cpu" />
          {diagnostics.isLoading ? (
            <Skeleton className="skeleton-block" />
          ) : diagnostics.data ? (
            <ul className="check-list">
              {diagnostics.data.checks.slice(0, 7).map((check) => (
                <li key={check.id}>
                  <span className={`check-dot ${check.status}`} aria-hidden="true" />
                  <div>
                    <span>{check.label}</span>
                    <p className="muted small">{check.detail}</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">No diagnostics available.</p>
          )}
          <div className="card-foot-link">
            <Link to="/models">
              Inspect model registry <Icon name="arrowRight" size={14} />
            </Link>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Recent runs"
          subtitle="Status comes from the persistent queue, not optimistic UI."
          actions={
            <LinkButton to="/models" size="sm" variant="quiet" icon="models">
              Model registry
            </LinkButton>
          }
        />
        {runs.isLoading ? (
          <Skeleton className="skeleton-block" />
        ) : runs.error ? (
          <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
        ) : runs.data?.items.length ? (
          <div className="table-wrap">
            <table className="data-table responsive-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th className="hide-narrow">Workflow</th>
                  <th>Status</th>
                  <th className="hide-narrow">Created</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map((run) => (
                  <tr key={run.id}>
                    <td className="mono small run-id-cell" title={run.id}>{run.id}</td>
                    <td className="hide-narrow">{run.workflow_name}</td>
                    <td>
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="muted small hide-narrow">{formatRelative(run.created_at)}</td>
                    <td>
                      <div className="row-actions">
                        <Link className="text-link" to={`/runs/${run.id}`}>
                          Monitor
                        </Link>
                        <Link className="text-link" to={`/runs/${run.id}/results`}>
                          Results
                        </Link>
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
            icon="run"
            title="No runs yet"
            description="Open a project, import a library and run the Basic triage template. It is deterministic, offline and requires no API key."
            actions={
              projects.data?.items[0] ? (
                <LinkButton to={`/projects/${projects.data.items[0].id}`} variant="primary" icon="arrowRight">
                  Open {projects.data.items[0].name}
                </LinkButton>
              ) : null
            }
          />
        )}
      </Card>

      <InlineNotice tone="info" title="Scientific scope">
        Descriptor values, rule flags and rankings are prioritisation signals. They are not measurements of binding,
        safety, efficacy or clinical utility. Read the{" "}
        <Link to="/about">limitations register</Link> before using results in a decision.
      </InlineNotice>

      <NewProjectModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}
