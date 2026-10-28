import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useCompounds, useDatasets, useProject } from "../api/queries";
import { ImportDatasetModal } from "../components/ImportDatasetModal";
import { Icon } from "../components/Icon";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  PageHeader,
  Select,
  Skeleton,
  useToast,
} from "../components/ui";
import { downloadText, formatMetric, formatRelative } from "../lib/format";

const DESCRIPTOR_LABELS: Record<string, string> = {
  mw: "MW",
  logp: "cLogP",
  tpsa: "TPSA",
  hbd: "HBD",
  hba: "HBA",
  rotb: "RotB",
  qed: "QED",
  fsp3: "Fsp³",
  rings: "Rings",
  heavy_atoms: "Heavy atoms",
  aromatic_rings: "Arom. rings",
  fraction_csp3: "Fsp³",
  molar_refractivity: "MR",
};

const DEFAULT_COLUMNS = ["mw", "logp", "tpsa", "qed", "hbd", "hba", "rotb"];
const PAGE_SIZE = 50;

interface SavedView {
  name: string;
  q: string;
  sort: string;
  order: "asc" | "desc";
  dataset: string;
}

function loadViews(projectId: string): SavedView[] {
  try {
    const raw = window.localStorage.getItem(`hcs.views.${projectId}`);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedView[];
    return Array.isArray(parsed) ? parsed.slice(0, 20) : [];
  } catch {
    return [];
  }
}

export function LibraryPage() {
  const { projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const project = useProject(projectId);
  const datasets = useDatasets(projectId);
  const { notify } = useToast();
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [importing, setImporting] = useState(false);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [savingView, setSavingView] = useState(false);
  const [viewName, setViewName] = useState("");
  const [views, setViews] = useState<SavedView[]>(() => loadViews(projectId));

  const q = params.get("q") ?? "";
  const sort = params.get("sort") ?? "created_at";
  const order = (params.get("order") === "asc" ? "asc" : "desc") as "asc" | "desc";
  const dataset = params.get("dataset") ?? "";
  const offset = Math.max(0, Number(params.get("offset") ?? "0") || 0);
  const [visibleColumns, setVisibleColumns] = useState<string[]>(() => {
    try {
      const raw = window.localStorage.getItem(`hcs.columns.${projectId}`);
      const parsed = raw ? (JSON.parse(raw) as string[]) : null;
      return Array.isArray(parsed) && parsed.length ? parsed : DEFAULT_COLUMNS;
    } catch {
      return DEFAULT_COLUMNS;
    }
  });

  useEffect(() => {
    setViews(loadViews(projectId));
  }, [projectId]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (search === q) return;
      const next = new URLSearchParams(params);
      if (search.trim()) next.set("q", search.trim());
      else next.delete("q");
      next.delete("offset");
      setParams(next, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [search, q, params, setParams]);

  useEffect(() => {
    window.localStorage.setItem(`hcs.columns.${projectId}`, JSON.stringify(visibleColumns));
  }, [projectId, visibleColumns]);

  const compounds = useCompounds(projectId, {
    q: q || undefined,
    dataset_id: dataset || undefined,
    sort,
    order,
    limit: PAGE_SIZE,
    offset,
  });

  const descriptorKeys = useMemo(() => {
    const first = compounds.data?.items[0]?.descriptors;
    return first ? Object.keys(first) : DEFAULT_COLUMNS;
  }, [compounds.data]);

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    setParams(next);
  };

  const setSort = (key: string) => {
    if (sort === key) update({ order: order === "asc" ? "desc" : "asc" });
    else update({ sort: key, order: "asc", offset: null });
  };

  const saveView = () => {
    const name = viewName.trim();
    if (!name) return;
    const next = [...views.filter((view) => view.name !== name), { name, q, sort, order, dataset }].slice(-20);
    setViews(next);
    window.localStorage.setItem(`hcs.views.${projectId}`, JSON.stringify(next));
    setSavingView(false);
    setViewName("");
    notify(`View “${name}” saved in this browser`, "ok");
  };

  const applyView = (name: string) => {
    const view = views.find((item) => item.name === name);
    if (!view) return;
    const next = new URLSearchParams();
    if (view.q) next.set("q", view.q);
    if (view.dataset) next.set("dataset", view.dataset);
    if (view.sort !== "created_at") next.set("sort", view.sort);
    if (view.order !== "desc") next.set("order", view.order);
    setSearch(view.q);
    setParams(next);
  };

  const removeView = (name: string) => {
    const next = views.filter((view) => view.name !== name);
    setViews(next);
    window.localStorage.setItem(`hcs.views.${projectId}`, JSON.stringify(next));
  };

  const exportPage = () => {
    if (!compounds.data?.items.length) return;
    const header = ["compound_id", "name", "smiles", "formula", "source_id", ...visibleColumns];
    const lines = [header.join(",")];
    for (const item of compounds.data.items) {
      const values = [
        item.id,
        item.name ?? "",
        item.smiles,
        item.formula ?? "",
        item.source_id ?? "",
        ...visibleColumns.map((key) => formatMetric(item.descriptors[key])),
      ];
      lines.push(values.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","));
    }
    downloadText(`library-${projectId}-page.csv`, lines.join("\n"), "text/csv");
    notify(`Exported ${compounds.data.items.length} rows from this page`, "ok");
  };

  const total = compounds.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="page">
      <PageHeader
        eyebrow={
          <>
            <Link to={`/projects/${projectId}`}>{project.data?.project.name ?? "Project"}</Link>
            <Icon name="chevronRight" size={12} /> Library
          </>
        }
        title="Compound library"
        description="Server-paginated structures with canonical identifiers and on-demand descriptors. The table never renders the whole library into the DOM."
        actions={
          <>
            <Button variant="secondary" icon="upload" onClick={() => setImporting(true)}>
              Import
            </Button>
            <Button variant="secondary" icon="download" onClick={exportPage} disabled={!compounds.data?.items.length}>
              Export page
            </Button>
          </>
        }
        meta={
          <>
            <Badge tone="neutral">{total.toLocaleString()} compounds</Badge>
            {q ? <Badge tone="info">filtered: “{q}”</Badge> : null}
            {dataset ? <Badge tone="info">dataset filter</Badge> : null}
          </>
        }
      />

      <Card>
        <div className="toolbar">
          <div className="search-field">
            <Icon name="search" size={16} />
            <input
              aria-label="Search compounds by name, SMILES, source ID, InChIKey or formula"
              placeholder="Search name, SMILES, source ID, InChIKey, formula…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            {search ? (
              <button aria-label="Clear search" onClick={() => setSearch("")}>
                <Icon name="close" size={14} />
              </button>
            ) : null}
          </div>
          <Select
            aria-label="Filter by dataset"
            value={dataset}
            onChange={(event) => update({ dataset: event.target.value, offset: null })}
          >
            <option value="">All datasets</option>
            {datasets.data?.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Saved views"
            value=""
            onChange={(event) => applyView(event.target.value)}
          >
            <option value="">Saved views…</option>
            {views.map((view) => (
              <option key={view.name} value={view.name}>
                {view.name}
              </option>
            ))}
          </Select>
          <Button size="sm" variant="quiet" icon="plus" onClick={() => setSavingView(true)}>
            Save view
          </Button>
          <div className="toolbar-spacer" />
          <div className="columns-menu">
            <Button size="sm" variant="quiet" icon="eye" onClick={() => setColumnsOpen((open) => !open)} aria-expanded={columnsOpen}>
              Columns
            </Button>
            {columnsOpen ? (
              <>
                <button className="popover-scrim" aria-label="Close column chooser" onClick={() => setColumnsOpen(false)} />
                <div className="popover columns-popover">
                  <div className="popover-title">Descriptor columns</div>
                  {descriptorKeys.map((key) => (
                    <label key={key} className="checkbox compact">
                      <input
                        type="checkbox"
                        checked={visibleColumns.includes(key)}
                        onChange={(event) =>
                          setVisibleColumns((current) =>
                            event.target.checked ? [...current, key] : current.filter((item) => item !== key),
                          )
                        }
                      />
                      <span>{DESCRIPTOR_LABELS[key] ?? key}</span>
                    </label>
                  ))}
                  <Button size="sm" variant="ghost" onClick={() => setVisibleColumns(DEFAULT_COLUMNS)}>
                    Reset defaults
                  </Button>
                </div>
              </>
            ) : null}
          </div>
        </div>

        {views.length ? (
          <div className="chip-row">
            {views.map((view) => (
              <span key={view.name} className="chip chip-removable">
                <button className="chip-apply" onClick={() => applyView(view.name)}>
                  {view.name}
                </button>
                <button className="chip-remove" aria-label={`Delete view ${view.name}`} onClick={() => removeView(view.name)}>
                  <Icon name="close" size={12} />
                </button>
              </span>
            ))}
          </div>
        ) : null}

        {compounds.isLoading ? (
          <div className="table-loading">
            <Skeleton className="skeleton-row" />
            <Skeleton className="skeleton-row" />
            <Skeleton className="skeleton-row" />
            <Skeleton className="skeleton-row" />
          </div>
        ) : compounds.error ? (
          <ErrorState error={compounds.error} onRetry={() => void compounds.refetch()} />
        ) : compounds.data?.items.length ? (
          <>
            <p className="narrow-only small muted library-narrow-note">
              Narrow screens show name and structure. Open a compound for descriptors, formula and import details.
            </p>
            <div className="table-wrap">
              <table className="data-table library-table">
                <thead>
                  <tr>
                    <th className="sortable" aria-sort={sort === "name" ? (order === "asc" ? "ascending" : "descending") : "none"}>
                      <button onClick={() => setSort("name")}>
                        Name {sort === "name" ? <Icon name={order === "asc" ? "chevronDown" : "chevronDown"} size={12} className={order === "asc" ? "flip" : ""} /> : null}
                      </button>
                    </th>
                    <th>Structure</th>
                    <th
                      className="sortable hide-narrow"
                      aria-sort={sort === "formula" ? (order === "asc" ? "ascending" : "descending") : "none"}
                    >
                      <button onClick={() => setSort("formula")}>Formula</button>
                    </th>
                    {visibleColumns.map((key) => (
                      <th key={key} className="num hide-narrow">
                        {DESCRIPTOR_LABELS[key] ?? key}
                        {key === "mw" ? <span className="unit">g/mol</span> : key === "tpsa" ? <span className="unit">Å²</span> : null}
                      </th>
                    ))}
                    <th
                      className="sortable hide-narrow"
                      aria-sort={sort === "created_at" ? (order === "asc" ? "ascending" : "descending") : "none"}
                    >
                      <button onClick={() => setSort("created_at")}>Imported</button>
                    </th>
                    <th className="hide-narrow" aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {compounds.data.items.map((compound) => (
                    <tr key={compound.id}>
                      <td>
                        <Link className="compound-name" to={`/compounds/${compound.id}`}>
                          {compound.name || "Unnamed compound"}
                        </Link>
                        <div className="tiny muted mono" title={compound.id}>
                          {compound.source_id ?? compound.id}
                        </div>
                      </td>
                      <td>
                        <Link to={`/compounds/${compound.id}`} className="smiles-cell mono" title={compound.smiles}>
                          {compound.smiles}
                        </Link>
                        {compound.warnings.length ? (
                          <span className="warning-chip" title={compound.warnings.join("; ")}>
                            <Icon name="alert" size={12} /> {compound.warnings.length}
                          </span>
                        ) : null}
                      </td>
                      <td className="mono small hide-narrow">{compound.formula ?? "—"}</td>
                      {visibleColumns.map((key) => (
                        <td key={key} className="num tabular hide-narrow">
                          {formatMetric(compound.descriptors[key])}
                        </td>
                      ))}
                      <td className="muted small hide-narrow">{formatRelative(compound.created_at)}</td>
                      <td className="row-actions hide-narrow">
                        <Link className="text-link" to={`/compounds/${compound.id}`}>
                          Detail
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <span className="muted small">
                Showing {(offset + 1).toLocaleString()}–{Math.min(offset + PAGE_SIZE, total).toLocaleString()} of{" "}
                {total.toLocaleString()}
              </span>
              <div className="pagination-buttons">
                <Button
                  size="sm"
                  variant="secondary"
                  icon="arrowLeft"
                  disabled={offset === 0}
                  onClick={() => update({ offset: String(Math.max(0, offset - PAGE_SIZE)) })}
                >
                  Previous
                </Button>
                <span className="muted small tabular">
                  {page} / {pages}
                </span>
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
            </div>
          </>
        ) : (
          <EmptyState
            icon="molecule"
            title={q || dataset ? "No compounds match these filters" : "No compounds yet"}
            description={
              q || dataset
                ? "Clear the search or dataset filter to see the full library."
                : "Import a CSV, SDF or .smi file. Malformed rows are retained as errors rather than silently dropped."
            }
            actions={
              q || dataset ? (
                <Button
                  variant="secondary"
                  icon="refresh"
                  onClick={() => {
                    setSearch("");
                    setParams(new URLSearchParams());
                  }}
                >
                  Clear filters
                </Button>
              ) : (
                <Button variant="primary" icon="upload" onClick={() => setImporting(true)}>
                  Import dataset
                </Button>
              )
            }
          />
        )}
      </Card>

      <ImportDatasetModal projectId={projectId} open={importing} onClose={() => setImporting(false)} />
      <Modal
        open={savingView}
        onClose={() => setSavingView(false)}
        title="Save current view"
        description="Saved in this browser only. The same filters are always shareable through the URL."
        width="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setSavingView(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={saveView} disabled={!viewName.trim()}>
              Save view
            </Button>
          </>
        }
      >
        <Field label="View name" htmlFor="view-name" required>
          <Input
            id="view-name"
            autoFocus
            value={viewName}
            maxLength={60}
            placeholder="e.g. Lead-like, rule-of-five"
            onChange={(event) => setViewName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") saveView();
            }}
          />
        </Field>
      </Modal>
    </div>
  );
}
