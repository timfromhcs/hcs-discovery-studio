import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useCancelRun, useRun, useRunEvents, useRetryRun } from "../api/queries";
import { Icon } from "../components/Icon";
import { WorkflowGraph } from "../components/WorkflowGraph";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  CopyButton,
  EmptyState,
  ErrorState,
  InlineNotice,
  LinkButton,
  NodeStatusBadge,
  PageHeader,
  ProgressBar,
  RunStatusBadge,
  Skeleton,
  useToast,
} from "../components/ui";
import { downloadText, elapsed, formatBytes, formatDate, formatDuration, formatMetric, formatRelative } from "../lib/format";
import type { NodeStatus, RunEvent } from "../api/types";

export function RunMonitorPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const run = useRun(runId);
  const active = Boolean(run.data && (run.data.status === "queued" || run.data.status === "running"));
  const events = useRunEvents(runId, true, active);
  const cancelRun = useCancelRun(runId);
  const retryRun = useRetryRun(runId);
  const { notify } = useToast();
  const [streamEvents, setStreamEvents] = useState<RunEvent[]>([]);
  const [streamState, setStreamState] = useState<"connecting" | "live" | "closed" | "error">("connecting");
  const [level, setLevel] = useState<"all" | "info" | "warning" | "error">("all");
  const [nodeFilter, setNodeFilter] = useState("");
  const [logSearch, setLogSearch] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [confirmRetry, setConfirmRetry] = useState(false);
  const [showManifest, setShowManifest] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  useEffect(() => {
    setStreamEvents([]);
  }, [runId]);

  useEffect(() => {
    if (!active) {
      setStreamState("closed");
      return;
    }
    setStreamState("connecting");
    const source = new EventSource(api.runs.eventsUrl(runId, 0));
    source.addEventListener("open", () => setStreamState("live"));
    source.addEventListener("run-event", (message) => {
      try {
        const event = JSON.parse((message as MessageEvent<string>).data) as RunEvent;
        setStreamEvents((current) => (current.some((item) => item.seq === event.seq) ? current : [...current, event].slice(-2000)));
      } catch {
        // Ignore malformed stream frames; polling remains the fallback.
      }
    });
    source.addEventListener("done", () => {
      setStreamState("closed");
      source.close();
      void run.refetch();
    });
    source.addEventListener("timeout", () => {
      setStreamState("error");
      source.close();
    });
    source.onerror = () => setStreamState("error");
    return () => source.close();
  }, [runId, active]);

  const merged = useMemo(() => {
    const map = new Map<number, RunEvent>();
    for (const event of events.data?.items ?? []) map.set(event.seq, event);
    for (const event of streamEvents) map.set(event.seq, event);
    return Array.from(map.values()).sort((a, b) => a.seq - b.seq);
  }, [events.data, streamEvents]);

  const filteredEvents = useMemo(() => {
    const needle = logSearch.trim().toLowerCase();
    return merged.filter((event) => {
      if (level !== "all" && event.level !== level) return false;
      if (nodeFilter && event.node_id !== nodeFilter) return false;
      if (needle && !event.message.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [merged, level, nodeFilter, logSearch]);

  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [filteredEvents.length, autoScroll]);

  if (run.isLoading) {
    return (
      <div className="page">
        <Skeleton className="skeleton-hero" />
        <Skeleton className="skeleton-block tall-skeleton" />
      </div>
    );
  }

  if (run.error || !run.data) {
    return (
      <div className="page">
        <PageHeader title="Run unavailable" />
        <ErrorState
          error={run.error ?? new Error("Run not found.")}
          onRetry={() => void run.refetch()}
          headingLevel={2}
        />
        <LinkButton to="/" icon="arrowLeft">
          Back to workspace
        </LinkButton>
      </div>
    );
  }

  const detail = run.data;
  const statuses: Record<string, NodeStatus> = Object.fromEntries(detail.nodes.map((node) => [node.node_id, node.status]));
  const duration = elapsed(detail.started_at, detail.finished_at);
  const completed = detail.nodes.filter((node) => node.status === "succeeded").length;
  const durationMs = detail.nodes.reduce((sum, node) => sum + Number(node.summary?.duration_ms ?? 0), 0);
  const showCancel = detail.status === "queued" || detail.status === "running";
  const showRetry = detail.status === "failed" || detail.status === "cancelled";

  const doCancel = async () => {
    try {
      await cancelRun.mutateAsync();
      notify("Cancellation requested", "info");
      setConfirmCancel(false);
      void run.refetch();
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not request cancellation", "danger");
    }
  };

  const doRetry = async () => {
    try {
      const next = await retryRun.mutateAsync();
      setConfirmRetry(false);
      notify(`Retry queued as ${next.id}`, "ok");
      navigate(`/runs/${next.id}`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not retry this run", "danger");
    }
  };

  const downloadLogs = () => {
    const text = merged
      .map((event) => `${event.ts}\t${event.level}\t${event.type}\t${event.node_id ?? ""}\t${event.message}`)
      .join("\n");
    downloadText(`${detail.id}-events.tsv`, text, "text/tab-separated-values");
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow={
          <>
            <Link to={`/projects/${detail.project_id}`}>Project</Link>
            <Icon name="chevronRight" size={12} />
            <Link to={`/projects/${detail.project_id}/runs`}>Runs</Link>
            <Icon name="chevronRight" size={12} />
            <span className="mono">{detail.id}</span>
          </>
        }
        title={detail.workflow_name}
        description="Live state comes from persisted run and node rows. Logs arrive over Server-Sent Events with polling as fallback."
        actions={
          <>
            <CopyButton value={detail.id} label="Copy run ID" />
            {detail.status === "succeeded" ? (
              <LinkButton to={`/runs/${detail.id}/results`} variant="primary" icon="results">
                Results
              </LinkButton>
            ) : null}
            {showRetry ? (
              <Button variant="secondary" icon="retry" onClick={() => setConfirmRetry(true)}>
                Retry
              </Button>
            ) : null}
            {showCancel ? (
              <Button variant="danger" icon="stop" onClick={() => setConfirmCancel(true)} disabled={detail.cancel_requested}>
                {detail.cancel_requested ? "Cancellation requested" : "Cancel run"}
              </Button>
            ) : null}
          </>
        }
        meta={
          <>
            <RunStatusBadge status={detail.status} />
            {detail.cancel_requested && showCancel ? <Badge tone="warn">cancel requested</Badge> : null}
            <span className="muted small">Created {formatDate(detail.created_at)}</span>
            <span className="mono tiny">hash {detail.workflow_hash.slice(0, 14)}…</span>
            {detail.seed !== null ? <Badge tone="neutral">seed {detail.seed}</Badge> : null}
            <Badge tone="neutral">attempt {detail.attempt}</Badge>
          </>
        }
      />

      {detail.error ? (
        <InlineNotice tone="danger" title="Run failed">
          {detail.error}
        </InlineNotice>
      ) : null}

      <section className="stats-grid run-stats" aria-label="Run metrics">
        <div className="stat-card">
          <div className="stat-top"><span>Elapsed</span><Icon name="clock" size={16} /></div>
          <div className="stat-value tabular">{formatDuration(duration)}</div>
          <div className="stat-hint">{active ? "live" : detail.finished_at ? `finished ${formatRelative(detail.finished_at)}` : "not started"}</div>
        </div>
        <div className="stat-card">
          <div className="stat-top"><span>Nodes</span><Icon name="workflow" size={16} /></div>
          <div className="stat-value tabular">{completed} / {detail.nodes.length}</div>
          <div className="stat-hint">succeeded</div>
        </div>
        <div className="stat-card">
          <div className="stat-top"><span>Node time</span><Icon name="run" size={16} /></div>
          <div className="stat-value tabular">{durationMs ? formatDuration(durationMs / 1000) : "—"}</div>
          <div className="stat-hint">sum of recorded durations</div>
        </div>
        <div className="stat-card">
          <div className="stat-top"><span>Artifacts</span><Icon name="download" size={16} /></div>
          <div className="stat-value tabular">{detail.artifacts.length}</div>
          <div className="stat-hint">{formatBytes(detail.artifacts.reduce((sum, item) => sum + item.size_bytes, 0))}</div>
        </div>
      </section>

      <div className="monitor-grid">
        <Card className="span-2">
          <CardHeader
            title="Execution graph"
            subtitle="Node state is read from the persisted run, never inferred from the browser."
            actions={<Badge tone={active ? "info" : "neutral"}>{active ? "live" : "final"}</Badge>}
          />
          <WorkflowGraph definition={detail.workflow_snapshot} statuses={statuses} ariaLabel="Run execution graph with node statuses" />
          <div className="node-progress-list">
            {detail.nodes.map((node) => (
              <div key={node.node_id} className={`node-progress status-${node.status}`}>
                <div className="node-progress-head">
                  <span className="mono small">{node.node_id}</span>
                  <NodeStatusBadge status={node.status} cached={node.cached} />
                </div>
                <ProgressBar value={node.progress} label={`${node.node_id} progress`} />
                <div className="node-progress-meta">
                  <span className="mono tiny">{node.type}</span>
                  <span className="muted tiny">{node.started_at ? `${formatDuration(elapsed(node.started_at, node.finished_at))}` : "not started"}</span>
                  {node.cache_key ? <span className="mono tiny" title={node.cache_key}>cache {node.cache_key.slice(0, 12)}…</span> : null}
                </div>
                {node.error ? <p className="error-text small">{node.error.message ?? node.error.code}</p> : null}
                {node.summary && Object.keys(node.summary).length ? (
                  <div className="summary-chips">
                    {Object.entries(node.summary)
                      .filter(([key]) => key !== "artifacts")
                      .slice(0, 8)
                      .map(([key, value]) => (
                        <span className="chip tiny" key={key}>
                          {key.replaceAll("_", " ")}: <strong>{Array.isArray(value) ? value.join(", ") : formatMetric(value)}</strong>
                        </span>
                      ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Queue & provenance" icon="shield" />
          <dl className="key-value">
            <div><dt>Status</dt><dd><RunStatusBadge status={detail.status} /></dd></div>
            <div><dt>Queued</dt><dd>{formatDate(detail.created_at)}</dd></div>
            <div><dt>Started</dt><dd>{formatDate(detail.started_at)}</dd></div>
            <div><dt>Finished</dt><dd>{formatDate(detail.finished_at)}</dd></div>
            <div><dt>Dataset</dt><dd className="mono small">{detail.dataset_id ?? "—"}</dd></div>
            <div><dt>Workflow hash</dt><dd className="mono tiny break-all">{detail.workflow_hash}</dd></div>
            <div><dt>Cancel requested</dt><dd>{detail.cancel_requested ? "yes" : "no"}</dd></div>
            <div><dt>Attempt</dt><dd>{detail.attempt}</dd></div>
            <div><dt>Seed</dt><dd>{detail.seed ?? "not set"}</dd></div>
          </dl>
          {detail.artifacts.length ? (
            <div className="card-foot-link">
              <button className="text-link small" onClick={() => setShowManifest((value) => !value)}>
                {showManifest ? "Hide manifest" : "Inspect manifest"}
              </button>
            </div>
          ) : null}
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Event log"
          subtitle={`${merged.length} events · stream ${streamState}${active ? "" : " · run finished"}`}
          icon="run"
          actions={
            <>
              <Button size="sm" variant="quiet" icon="download" onClick={downloadLogs} disabled={!merged.length}>
                Download
              </Button>
              <Button size="sm" variant="quiet" icon="refresh" onClick={() => void events.refetch()}>
                Refresh
              </Button>
            </>
          }
        />
        <div className="log-toolbar">
          <select className="input select small" aria-label="Filter log level" value={level} onChange={(event) => setLevel(event.target.value as typeof level)}>
            <option value="all">All levels</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
          <select className="input select small" aria-label="Filter log node" value={nodeFilter} onChange={(event) => setNodeFilter(event.target.value)}>
            <option value="">All nodes</option>
            {detail.nodes.map((node) => (
              <option key={node.node_id} value={node.node_id}>
                {node.node_id}
              </option>
            ))}
          </select>
          <div className="search-field small">
            <Icon name="search" size={14} />
            <input aria-label="Search logs" placeholder="Search log messages…" value={logSearch} onChange={(event) => setLogSearch(event.target.value)} />
          </div>
          <label className="checkbox compact">
            <input type="checkbox" checked={autoScroll} onChange={(event) => setAutoScroll(event.target.checked)} />
            <span>Follow tail</span>
          </label>
        </div>
        {events.error && !merged.length ? (
          <ErrorState error={events.error} onRetry={() => void events.refetch()} />
        ) : filteredEvents.length ? (
          <div className="log-view" ref={logRef} role="log" aria-label="Run event log">
            {filteredEvents.map((event) => (
              <div key={event.seq} className={`log-line level-${event.level}`}>
                <span className="log-ts">{new Date(event.ts).toLocaleTimeString()}</span>
                <span className="log-level">{event.level}</span>
                <span className="log-node">{event.node_id ?? "run"}</span>
                <span className="log-msg">{event.message}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState compact icon="run" title="No matching events" description="Adjust the filters or wait for the next event." />
        )}
      </Card>

      {showManifest ? (
        <Card>
          <CardHeader
            title="Run manifest"
            subtitle="The immutable provenance record written with this run."
            icon="shield"
            actions={
              <Button
                size="sm"
                variant="quiet"
                icon="download"
                onClick={() => downloadText(`${detail.id}-manifest.json`, JSON.stringify(detail.manifest, null, 2))}
              >
                Download JSON
              </Button>
            }
          />
          <div className="manifest-grid">
            <div>
              <h3>Environment</h3>
              <pre className="json-preview">{JSON.stringify(detail.manifest.environment ?? {}, null, 2)}</pre>
            </div>
            <div>
              <h3>Limitations</h3>
              <ul className="plain-list small">
                {(detail.manifest.limitations ?? []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <h3>Columns</h3>
              <div className="table-wrap">
                <table className="data-table compact-table">
                  <thead>
                    <tr><th>Column</th><th>Unit</th><th>Method</th></tr>
                  </thead>
                  <tbody>
                    {(detail.manifest.columns ?? []).map((column) => (
                      <tr key={column.name}>
                        <td>{column.label} <span className="mono tiny muted">{column.name}</span></td>
                        <td className="small">{column.unit ?? "—"}</td>
                        <td className="mono tiny">{column.method ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <pre className="json-preview tall">{JSON.stringify(detail.manifest, null, 2)}</pre>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Artifacts & reports"
          subtitle="Downloads are served by the local API and every file has a recorded SHA-256."
          icon="download"
          actions={
            detail.status === "succeeded" ? (
              <>
                <a className="btn btn-quiet btn-sm" href={api.runs.reportUrl(detail.id, "html")}>HTML</a>
                <a className="btn btn-quiet btn-sm" href={api.runs.reportUrl(detail.id, "markdown")}>Markdown</a>
                <a className="btn btn-quiet btn-sm" href={api.runs.reportUrl(detail.id, "json")}>JSON</a>
                <a className="btn btn-quiet btn-sm" href={api.runs.reportUrl(detail.id, "csv")}>CSV</a>
              </>
            ) : null
          }
        />
        {detail.artifacts.length ? (
          <div className="table-wrap">
            <table className="data-table compact-table">
              <thead>
                <tr><th>Path</th><th>Kind</th><th>Media type</th><th className="num">Size</th><th>SHA-256</th><th aria-label="Download" /></tr>
              </thead>
              <tbody>
                {detail.artifacts.map((artifact) => (
                  <tr key={artifact.id}>
                    <td className="mono small">{artifact.rel_path}</td>
                    <td><Badge tone="neutral">{artifact.kind}</Badge></td>
                    <td className="small">{artifact.media_type}</td>
                    <td className="num tabular">{formatBytes(artifact.size_bytes)}</td>
                    <td className="mono tiny" title={artifact.sha256}>{artifact.sha256.slice(0, 14)}…</td>
                    <td>
                      <a className="text-link small" href={api.runs.artifactUrl(detail.id, artifact.id)} download>
                        Download
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState compact icon="download" title="No artifacts yet" description="Artifacts appear as nodes finish writing them." />
        )}
      </Card>

      <ConfirmDialog
        open={confirmCancel}
        title="Cancel this run?"
        description="The worker will stop at the next safe checkpoint. Partial artifacts remain on disk."
        confirmLabel="Request cancellation"
        onClose={() => setConfirmCancel(false)}
        onConfirm={() => void doCancel()}
        busy={cancelRun.isPending}
      >
        <p className="small">
          Cancellation is cooperative. A node in a tight native call may take a moment to stop, and the final status will
          be reported honestly as <code>cancelled</code>.
        </p>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmRetry}
        title="Retry this run?"
        description="A new run is created from the same workflow snapshot, dataset and seed."
        confirmLabel="Queue retry"
        confirmVariant="primary"
        onClose={() => setConfirmRetry(false)}
        onConfirm={() => void doRetry()}
        busy={retryRun.isPending}
      />
    </div>
  );
}
