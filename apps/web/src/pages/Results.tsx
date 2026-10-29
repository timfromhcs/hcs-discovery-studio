import { useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useRun, useRunResults } from "../api/queries";
import { ParetoScatter } from "../components/ParetoScatter";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Checkbox,
  EmptyState,
  ErrorState,
  InlineNotice,
  LinkButton,
  PageHeader,
  RunStatusBadge,
  Skeleton,
  Stat,
} from "../components/ui";
import { formatMetric, formatNumber } from "../lib/format";
import type { ColumnMeta, ResultItem } from "../api/types";

const PAGE_SIZE = 100;

function valueFor(item: ResultItem, column: ColumnMeta): unknown {
  if (column.name === "rank") return item.rank;
  if (column.name === "composite_score") return item.composite_score;
  if (column.name === "pareto_rank") return item.pareto_front;
  if (column.name === "filter_pass") return !item.rejected;
  if (column.name === "filter_reasons") return item.reasons.join("; ");
  if (column.name === "name") return item.name;
  if (column.name === "smiles") return item.smiles;
  return item.metrics[column.name];
}

export function ResultsPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const run = useRun(runId);
  const sort = params.get("sort") ?? "rank";
  const order = (params.get("order") === "desc" ? "desc" : "asc") as "asc" | "desc";
  const q = params.get("q") ?? "";
  const onlyPassing = params.get("passing") === "1";
  const offset = Math.max(0, Number(params.get("offset") ?? "0") || 0);
  const [search, setSearch] = useState(q);

  const options = { sort, order, only_passing: onlyPassing, q: q || undefined, limit: PAGE_SIZE, offset };
  const results = useRunResults(runId, options);
  const chart = useRunResults(runId, {
    sort,
    order,
    only_passing: onlyPassing,
    q: q || undefined,
    limit: 1000,
    offset: 0,
  });

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    setParams(next);
  };

  const setSort = (column: ColumnMeta) => {
    const nextOrder = sort === column.name ? (order === "asc" ? "desc" : "asc") : column.direction === "higher" ? "desc" : "asc";
    update({ sort: column.name, order: nextOrder, offset: null });
  };

  const columns = useMemo(() => {
    const known = results.data?.columns ?? [];
    return known.filter(
      (column) =>
        !["rank", "composite_score", "pareto_rank", "filter_pass", "filter_reasons", "compound_id", "name", "smiles", "source_id"].includes(
          column.name,
        ),
    );
  }, [results.data]);

  const metrics = useMemo(() => {
    const items = chart.data?.items ?? [];
    const passing = items.filter((item) => !item.rejected);
    const front = passing.filter((item) => item.pareto_front === 1);
    const scores = passing.map((item) => item.composite_score).filter((value): value is number => value !== null);
    return {
      chartItems: items,
      passing: passing.length,
      front: front.length,
      top: scores.length ? Math.max(...scores) : null,
      truncated: (chart.data?.total ?? 0) > items.length,
    };
  }, [chart.data]);

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
        <PageHeader title="Results unavailable" />
        <ErrorState error={run.error ?? new Error("Run not found.")} onRetry={() => void run.refetch()} headingLevel={2} />
        <LinkButton to="/" icon="arrowLeft">
          Workspace
        </LinkButton>
      </div>
    );
  }

  const detail = run.data;
  const total = results.data?.total ?? 0;

  return (
    <div className="page">
      <PageHeader
        eyebrow={
          <>
            <Link to={`/projects/${detail.project_id}`}>Project</Link>
            <Icon name="chevronRight" size={12} />
            <Link to={`/runs/${detail.id}`}>Run</Link>
            <Icon name="chevronRight" size={12} /> Results
          </>
        }
        title={`${detail.workflow_name} — results`}
        description="Rankings reflect the configured objectives and weights. Filtered rows stay visible with their reasons; nothing is silently discarded."
        actions={
          <>
            <LinkButton to={`/runs/${detail.id}`} variant="secondary" icon="run">
              Monitor
            </LinkButton>
            <a className="btn btn-secondary btn-md" href={api.runs.reportUrl(detail.id, "csv")}>
              <Icon name="download" size={17} /> <span>CSV</span>
            </a>
            <a className="btn btn-primary btn-md" href={api.runs.reportUrl(detail.id, "html")}>
              <Icon name="download" size={17} /> <span>HTML report</span>
            </a>
          </>
        }
        meta={
          <>
            <RunStatusBadge status={detail.status} />
            <span className="mono small">{detail.id}</span>
            {detail.seed !== null ? <Badge tone="neutral">seed {detail.seed}</Badge> : null}
          </>
        }
      />

      {detail.status !== "succeeded" ? (
        <InlineNotice tone={detail.status === "failed" ? "danger" : "warn"} title="This run has no final result table">
          Results are only persisted after a successful execution. Open the{" "}
          <Link to={`/runs/${detail.id}`}>run monitor</Link> to inspect the failure or cancellation events.
        </InlineNotice>
      ) : null}

      <section className="stats-grid" aria-label="Result summary">
        <Stat label="Total rows" value={total.toLocaleString()} icon="results" hint="includes filtered rows" />
        <Stat label="Passing filters" value={metrics.passing.toLocaleString()} icon="check" hint={metrics.truncated ? "chart subset" : "all rows"} />
        <Stat label="Pareto front 1" value={metrics.front.toLocaleString()} icon="target" hint="non-dominated" />
        <Stat label="Best composite" value={metrics.top === null ? "—" : formatNumber(metrics.top, 3)} icon="results" hint="0–1, weights visible below" />
      </section>

      {results.error ? (
        <ErrorState error={results.error} onRetry={() => void results.refetch()} />
      ) : total === 0 ? (
        <Card>
          <EmptyState
            icon="results"
            title="No result rows"
            description={
              detail.status === "succeeded"
                ? "The run completed without producing a result table. Check whether the workflow modified or dropped every row."
                : "Run a successful workflow to populate this view."
            }
          />
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader
              title="Pareto & trade-off view"
              subtitle={
                metrics.truncated
                  ? `Showing the first 1,000 of ${total.toLocaleString()} rows. Change sorting/filtering to explore other subsets.`
                  : "Every row in this run is plotted. Hover or focus a point for values; select it to open the compound."
              }
              icon="results"
              actions={<Badge tone="neutral">{metrics.chartItems.length} points</Badge>}
            />
            <ParetoScatter
              items={metrics.chartItems}
              columns={results.data?.columns ?? []}
              onSelect={(compoundId) => navigate(`/compounds/${compoundId}`)}
            />
            <p className="table-note">
              Axes are independent properties. The composite score is only a weighted summary of the configured
              objectives; inspect its weights in the workflow definition and the manifest before using it to choose a
              compound.
            </p>
          </Card>

          <Card>
            <CardHeader
              title="Ranked results"
              subtitle="Server-side sorting and pagination. Filter and sort state is stored in the URL."
              icon="library"
              actions={
                detail.status === "succeeded" ? (
                  <>
                    <a className="text-link small" href={api.runs.reportUrl(detail.id, "json")}>JSON</a>
                    <a className="text-link small" href={api.runs.reportUrl(detail.id, "markdown")}>Markdown</a>
                  </>
                ) : null
              }
            />
            <div className="toolbar">
              <div className="search-field">
                <Icon name="search" size={16} />
                <input
                  aria-label="Search result rows"
                  placeholder="Search by name, SMILES or compound ID…"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") update({ q: search.trim(), offset: null });
                  }}
                />
                {search ? (
                  <button aria-label="Clear search" onClick={() => { setSearch(""); update({ q: null, offset: null }); }}>
                    <Icon name="close" size={14} />
                  </button>
                ) : null}
              </div>
              <Button size="sm" variant="secondary" icon="search" onClick={() => update({ q: search.trim(), offset: null })}>
                Search
              </Button>
              <Checkbox
                label="Passing only"
                checked={onlyPassing}
                onChange={(event) => update({ passing: event.target.checked ? "1" : null, offset: null })}
              />
              <div className="toolbar-spacer" />
              <span className="muted small tabular">
                {total ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total.toLocaleString()}` : ""}
              </span>
            </div>

            {results.isLoading ? (
              <Skeleton className="skeleton-block" />
            ) : (
              <div className="table-wrap">
                <table className="data-table results-table responsive-table">
                  <thead>
                    <tr>
                      <th className="sortable" aria-sort={sort === "rank" ? (order === "asc" ? "ascending" : "descending") : "none"}>
                        <button onClick={() => setSort({ name: "rank", label: "Rank", type: "number", unit: null, direction: "lower", method: null, description: null })}>
                          Rank
                        </button>
                      </th>
                      <th>Compound</th>
                      <th className="sortable" aria-sort={sort === "composite_score" ? (order === "asc" ? "ascending" : "descending") : "none"}>
                        <button onClick={() => setSort({ name: "composite_score", label: "Score", type: "number", unit: "0-1", direction: "higher", method: null, description: null })}>
                          Composite <span className="unit">0–1</span>
                        </button>
                      </th>
                      <th className="sortable hide-narrow" aria-sort={sort === "pareto_rank" ? (order === "asc" ? "ascending" : "descending") : "none"}>
                        <button onClick={() => setSort({ name: "pareto_rank", label: "Front", type: "number", unit: "front", direction: "lower", method: null, description: null })}>
                          Front
                        </button>
                      </th>
                      <th>Decision</th>
                      {columns.map((column) => (
                        <th
                          key={column.name}
                          className={`num sortable hide-narrow ${column.name === sort ? "sorted" : ""}`}
                          title={`${column.label}${column.method ? ` · ${column.method}` : ""}${column.description ? ` — ${column.description}` : ""}`}
                          aria-sort={sort === column.name ? (order === "asc" ? "ascending" : "descending") : "none"}
                        >
                          <button onClick={() => setSort(column)}>
                            {column.label}
                            {column.unit ? <span className="unit">{column.unit}</span> : null}
                          </button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.data?.items.map((item) => (
                      <tr key={item.compound_id} className={item.rejected ? "rejected-row" : ""}>
                        <td className="num tabular rank-cell">{item.rank ?? "—"}</td>
                        <td>
                          <Link className="compound-name" to={`/compounds/${item.compound_id}`}>
                            {item.name || item.compound_id}
                          </Link>
                          <div className="smiles-cell mono tiny" title={item.smiles ?? undefined}>
                            {item.smiles ?? "—"}
                          </div>
                        </td>
                        <td className="num tabular">{formatNumber(item.composite_score, 3)}</td>
                        <td className="num tabular hide-narrow">{item.pareto_front ?? "—"}</td>
                        <td>
                          {item.rejected ? (
                            <span className="decision rejected" title={item.reasons.join("; ")}>
                              <Icon name="x" size={12} /> filtered
                            </span>
                          ) : (
                            <span className="decision passed">
                              <Icon name="check" size={12} /> passed
                            </span>
                          )}
                          {item.rejected && item.reasons.length ? (
                            <div className="tiny muted reasons-cell" title={item.reasons.join("; ")}>
                              {item.reasons.join("; ")}
                            </div>
                          ) : null}
                        </td>
                        {columns.map((column) => (
                          <td key={column.name} className="num tabular small hide-narrow">
                            {formatMetric(valueFor(item, column))}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="pagination">
              <Button size="sm" variant="secondary" icon="arrowLeft" disabled={offset === 0} onClick={() => update({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}>
                Previous
              </Button>
              <span className="muted small tabular">Page {Math.floor(offset / PAGE_SIZE) + 1} of {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span>
              <Button
                size="sm"
                variant="secondary"
                iconRight="arrowRight"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => update({ offset: String(offset + PAGE_SIZE) })}
              >
                Next
              </Button>
            </div>
          </Card>

          <Card>
            <CardHeader title="Column meanings" subtitle="Every reported value carries its unit, direction and method." icon="info" />
            <div className="table-wrap">
              <table className="data-table compact-table responsive-table">
                <thead>
                  <tr><th>Column</th><th className="hide-narrow">Unit</th><th className="hide-narrow">Direction</th><th className="hide-narrow">Method</th><th>Description</th></tr>
                </thead>
                <tbody>
                  {(results.data?.columns ?? []).map((column) => (
                    <tr key={column.name}>
                      <td>
                        <strong>{column.label}</strong>
                        <div className="mono tiny muted">{column.name}</div>
                      </td>
                      <td className="small hide-narrow">{column.unit ?? "—"}</td>
                      <td className="small hide-narrow">{column.direction ?? "—"}</td>
                      <td className="mono tiny hide-narrow">{column.method ?? "—"}</td>
                      <td className="small muted">{column.description ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <InlineNotice tone="info" title="Interpretation">
            Composite scores are a transparent weighted summary, not a drug-likeness law or efficacy prediction. Pareto
            fronts describe dominance only on the selected objectives. Inspect the underlying columns before choosing a
            candidate, and validate experimentally.
          </InlineNotice>
        </>
      )}
    </div>
  );
}
