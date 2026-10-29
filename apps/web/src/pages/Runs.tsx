import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useProject, useRuns } from "../api/queries";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  LinkButton,
  PageHeader,
  RunStatusBadge,
  Select,
  Skeleton,
  Tabs,
} from "../components/ui";
import { elapsed, formatDuration, formatRelative } from "../lib/format";
import type { RunStatus } from "../api/types";

type StatusFilter = "all" | RunStatus;

const STATUSES: RunStatus[] = ["queued", "running", "succeeded", "failed", "cancelled"];

export function RunsPage() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  const runs = useRuns(projectId, 200);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [workflow, setWorkflow] = useState("all");

  const workflowNames = useMemo(
    () => Array.from(new Set((runs.data?.items ?? []).map((run) => run.workflow_name))).sort(),
    [runs.data],
  );

  const filtered = useMemo(() => {
    const items = runs.data?.items ?? [];
    return items.filter(
      (run) => (status === "all" || run.status === status) && (workflow === "all" || run.workflow_name === workflow),
    );
  }, [runs.data, status, workflow]);

  const counts = useMemo(() => {
    const items = runs.data?.items ?? [];
    return items.reduce<Record<string, number>>((acc, run) => {
      acc[run.status] = (acc[run.status] ?? 0) + 1;
      return acc;
    }, {});
  }, [runs.data]);

  return (
    <div className="page">
      <PageHeader
        eyebrow={
          <>
            <Link to={`/projects/${projectId}`}>{project.data?.project.name ?? "Project"}</Link>
            <Icon name="chevronRight" size={12} /> Runs
          </>
        }
        title="Runs"
        description="Every queued execution of a workflow in this project. Runs are durable, cancellable and keep an immutable workflow snapshot."
        actions={
          <LinkButton to={`/projects/${projectId}/workflows`} variant="primary" icon="play">
            Start a run
          </LinkButton>
        }
      />

      <Card>
        <CardHeader
          title="Execution history"
          subtitle="Newest first. Status is read from the persistent queue."
          actions={
            <LinkButton to="/" size="sm" variant="quiet" icon="workspace">
              All projects
            </LinkButton>
          }
        />

        <div className="toolbar">
          <Tabs
            label="Run status"
            value={status}
            onChange={setStatus}
            tabs={[
              { id: "all", label: "All", count: runs.data?.items.length },
              ...STATUSES.map((item) => ({ id: item, label: item[0].toUpperCase() + item.slice(1), count: counts[item] ?? 0 })),
            ]}
          />
          <div className="toolbar-spacer" />
          <label className="search-field small">
            <Icon name="workflow" size={15} />
            <Select value={workflow} onChange={(event) => setWorkflow(event.target.value)} aria-label="Filter by workflow">
              <option value="all">All workflows</option>
              {workflowNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </label>
        </div>

        {runs.isLoading ? (
          <Skeleton className="skeleton-block" />
        ) : runs.error ? (
          <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
        ) : filtered.length ? (
          <>
            <div className="table-wrap">
              <table className="data-table responsive-table">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th className="hide-narrow">Workflow</th>
                    <th>Status</th>
                    <th className="hide-narrow">Dataset</th>
                    <th className="num hide-narrow">Duration</th>
                    <th className="hide-narrow">Created</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((run) => {
                    const duration = elapsed(run.started_at, run.finished_at);
                    return (
                      <tr key={run.id}>
                        <td className="mono small run-id-cell" title={run.id}>{run.id}</td>
                        <td className="hide-narrow">
                          <span className="compound-name">{run.workflow_name}</span>
                        </td>
                        <td>
                          <RunStatusBadge status={run.status} />
                          {run.error ? <div className="error-text small">{run.error}</div> : null}
                        </td>
                        <td className="mono tiny muted hide-narrow">{run.dataset_id ?? "—"}</td>
                        <td className="num tabular small hide-narrow">{duration === null ? "—" : formatDuration(duration)}</td>
                        <td className="muted small hide-narrow" title={new Date(run.created_at).toLocaleString()}>
                          {formatRelative(run.created_at)}
                        </td>
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
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="table-note">
              Showing {filtered.length} of {runs.data?.items.length ?? 0} runs.
              {filtered.length < (runs.data?.items.length ?? 0) ? " Clear filters to see the rest." : ""}
            </div>
          </>
        ) : runs.data?.items.length ? (
          <EmptyState
            compact
            icon="filter"
            title="No runs match these filters"
            description="Try another status or workflow, or clear both filters."
            actions={
              <Button
                variant="secondary"
                icon="refresh"
                onClick={() => {
                  setStatus("all");
                  setWorkflow("all");
                }}
              >
                Reset filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon="run"
            title="No runs yet"
            description="Choose a workflow and dataset to queue the first run. A worker must be running to execute queued jobs."
            actions={
              <LinkButton to={`/projects/${projectId}/workflows`} variant="primary" icon="play">
                Open workflows
              </LinkButton>
            }
          />
        )}
      </Card>

      <Card>
        <CardHeader title="Queue semantics" subtitle="What the status column actually means." icon="clock" />
        <div className="grid-2">
          <ul className="plain-list small">
            <li>
              <Badge tone="warn" dot>
                Queued
              </Badge>{" "}
              The definition validated and was committed. No worker has leased it yet.
            </li>
            <li>
              <Badge tone="info" dot>
                Running
              </Badge>{" "}
              A worker holds a lease and is executing nodes. Logs stream while this is true.
            </li>
            <li>
              <Badge tone="ok" dot>
                Succeeded
              </Badge>{" "}
              Every node produced its table; results and artifacts were committed.
            </li>
          </ul>
          <ul className="plain-list small">
            <li>
              <Badge tone="danger" dot>
                Failed
              </Badge>{" "}
              A node raised a deterministic error. The message is kept on the run and in the manifest.
            </li>
            <li>
              <Badge tone="muted" dot>
                Cancelled
              </Badge>{" "}
              Cancellation was requested and observed at a node boundary. Partial artifacts remain downloadable.
            </li>
            <li>
              Execution is at-least-once. Node results are cached by a content key, so a retry reuses completed work
              instead of duplicating it.
            </li>
          </ul>
        </div>
      </Card>
    </div>
  );
}
