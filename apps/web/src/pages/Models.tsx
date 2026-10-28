import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useDiagnostics, useModels } from "../api/queries";
import { Icon, type IconName } from "../components/Icon";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  CopyButton,
  EmptyState,
  ErrorState,
  InlineNotice,
  KeyValue,
  Modal,
  ModelStatusBadge,
  PageHeader,
  Select,
  Skeleton,
} from "../components/ui";
import type { ModelCard } from "../api/types";

type Category = "all" | "chemistry" | "ml" | "llm" | "structure";

const CATEGORY_ICONS: Record<string, IconName> = {
  chemistry: "molecule",
  ml: "cpu",
  llm: "models",
  structure: "flask",
};

export function ModelsPage() {
  const [probe, setProbe] = useState(false);
  const [category, setCategory] = useState<Category>("all");
  const [selected, setSelected] = useState<ModelCard | null>(null);
  const models = useModels(probe);
  const diagnostics = useDiagnostics({ providers: probe });

  const items = models.data?.items ?? [];
  const categories = useMemo(() => Array.from(new Set(items.map((item) => item.category))).sort(), [items]);
  const filtered = category === "all" ? items : items.filter((item) => item.category === category);
  const runnable = items.filter((item) => item.status === "available" || item.status === "available_with_limits");
  const planned = items.filter((item) => item.status === "planned");

  return (
    <div className="page">
      <PageHeader
        eyebrow="Model registry"
        title="Engines, adapters and their real status"
        description="Every card below maps to code in this repository. Status comes from a local probe, never from a hard-coded marketing claim. Planned engines are visible for transparency and cannot be queued."
        actions={
          <Button
            variant={probe ? "primary" : "secondary"}
            icon="refresh"
            loading={models.isFetching}
            onClick={() => setProbe((current) => !current)}
          >
            {probe ? "Probed" : "Run live probe"}
          </Button>
        }
        meta={
          <>
            <Badge tone="ok" dot>
              {runnable.length} runnable
            </Badge>
            <Badge tone="muted">{planned.length} planned</Badge>
            <span className="muted small">{probe ? "Availability probes executed just now." : "Static registry view; toggle the probe to test availability."}</span>
          </>
        }
      />

      <InlineNotice tone="info" title="What “available” means here">
        <p>
          A runnable engine passed its dependency and import checks on this machine. It does not mean the model is
          validated for your target, and no model in this release predicts binding affinity, toxicity or clinical
          outcomes. See the <Link to="/about">limitations register</Link>.
        </p>
      </InlineNotice>

      {models.error ? <ErrorState error={models.error} onRetry={() => void models.refetch()} /> : null}

      <Card>
        <CardHeader
          title="Registry"
          subtitle={models.data?.note ?? "Loading the registry from the local API."}
          icon="models"
          actions={
            <Select
              aria-label="Filter by category"
              value={category}
              onChange={(event) => setCategory(event.target.value as Category)}
            >
              <option value="all">All categories</option>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          }
        />

        {models.isLoading ? (
          <div className="catalog-grid">
            <Skeleton className="skeleton-card" />
            <Skeleton className="skeleton-card" />
            <Skeleton className="skeleton-card" />
          </div>
        ) : filtered.length ? (
          <div className="catalog-grid">
            {filtered.map((model) => (
              <article key={model.id} className="catalog-card model-card">
                <div className="row-between">
                  <span className="model-icon">
                    <Icon name={CATEGORY_ICONS[model.category] ?? "models"} size={18} />
                  </span>
                  <ModelStatusBadge status={model.status} />
                </div>
                <strong>{model.display_name}</strong>
                <span className="mono tiny muted">{model.id}</span>
                <p className="small muted">
                  {model.capabilities.length ? model.capabilities.join(" · ") : "No declared capabilities."}
                </p>
                <div className="chip-row">
                  <span className="chip mono">v{model.version}</span>
                  <span className="chip">{model.category}</span>
                  {model.network_required ? <span className="chip warning-chip">network</span> : <span className="chip">offline</span>}
                  {model.implemented ? <span className="chip">implemented</span> : <span className="chip">spec only</span>}
                </div>
                <div className="template-actions">
                  <Button size="sm" variant="quiet" icon="eye" onClick={() => setSelected(model)}>
                    Inspect
                  </Button>
                  {model.documentation_url ? (
                    <a className="text-link small" href={model.documentation_url} target="_blank" rel="noreferrer">
                      Docs <Icon name="external" size={12} />
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="models"
            title="No models match this category"
            description="Reset the category filter to see the full registry."
            actions={
              <Button variant="secondary" icon="refresh" onClick={() => setCategory("all")}>
                Show all
              </Button>
            }
          />
        )}
      </Card>

      <div className="grid-2">
        <Card>
          <CardHeader title="Device and library probes" subtitle="Only probes explicitly requested by the UI or CLI." icon="cpu" />
          {diagnostics.isLoading ? (
            <Skeleton className="skeleton-block" />
          ) : diagnostics.data ? (
            <ul className="check-list">
              {diagnostics.data.checks.map((check) => (
                <li key={check.id}>
                  <span className={`check-dot ${check.status}`} aria-hidden="true" />
                  <div>
                    <span>{check.label}</span>
                    <p className="muted small">{check.detail}</p>
                    {check.remediation ? <p className="tiny muted">Fix: {check.remediation}</p> : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">Diagnostics unavailable.</p>
          )}
          <div className="card-foot-link">
            <Link to="/settings">
              Open full diagnostics <Icon name="arrowRight" size={14} />
            </Link>
          </div>
        </Card>

        <Card>
          <CardHeader title="Adding an engine" subtitle="The registry is code, not configuration." icon="flask" />
          <p className="small muted">
            An adapter declares its capabilities, license, device providers and validation hooks. It is only reported as
            runnable when its imports and runtime checks pass. Planned entries deliberately have no execution path, so
            they cannot be selected in the workflow editor.
          </p>
          <KeyValue
            items={[
              { label: "Registry endpoint", value: <span className="mono small">GET /api/v1/models</span>, mono: false },
              { label: "Live probe", value: <span className="mono small">GET /api/v1/models?probe=true</span>, mono: false },
              { label: "CLI parity", value: <span className="mono small">hcs-discovery models list --probe</span>, mono: false },
              { label: "Device policy", value: "CPU baseline; Vulkan is reported but not used for execution" },
            ]}
          />
          <div className="row-actions">
            <CopyButton value="GET /api/v1/models?probe=true" label="Copy endpoint" />
            <CopyButton value="hcs-discovery models list --probe" label="Copy CLI" />
          </div>
        </Card>
      </div>

      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.display_name ?? "Model"}
        description={selected?.id}
        width="lg"
        footer={
          <>
            {selected?.citation_url ? (
              <a className="btn btn-quiet btn-sm" href={selected.citation_url} target="_blank" rel="noreferrer">
                <Icon name="external" size={15} /> Citation
              </a>
            ) : null}
            <Button variant="secondary" onClick={() => setSelected(null)}>
              Close
            </Button>
          </>
        }
      >
        {selected ? (
          <>
            <div className="row-between">
              <ModelStatusBadge status={selected.status} />
              <span className="mono small">v{selected.version}</span>
            </div>
            <KeyValue
              items={[
                { label: "Category", value: selected.category },
                { label: "Code license", value: selected.license.code },
                { label: "Weights license", value: selected.license.weights },
                { label: "Data license", value: selected.license.data },
                { label: "Device providers", value: selected.device_providers.join(", ") || "none" },
                { label: "Network required", value: selected.network_required ? "yes" : "no" },
                {
                  label: "Minimum RAM",
                  value: selected.resource_profile.ram_mb_min === null ? "not declared" : `${selected.resource_profile.ram_mb_min} MiB`,
                },
                {
                  label: "Minimum VRAM",
                  value: selected.resource_profile.vram_mb_min === null ? "not declared" : `${selected.resource_profile.vram_mb_min} MiB`,
                },
                { label: "Implemented", value: selected.implemented ? "yes" : "specification only" },
              ]}
            />
            <h3>Capabilities</h3>
            <div className="chip-row">
              {selected.capabilities.map((capability) => (
                <span key={capability} className="chip">
                  {capability}
                </span>
              ))}
            </div>
            <h3>Notes</h3>
            <ul className="plain-list small">
              {selected.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
            <InlineNotice tone={selected.status === "planned" ? "warn" : "info"} title="Scope">
              {selected.status === "planned"
                ? "This engine is planned. It has no execution path in this release and cannot be selected in a workflow."
                : "Availability is a local runtime check. Scientific validity for a given target or endpoint is out of scope for this release."}
            </InlineNotice>
          </>
        ) : null}
      </Modal>
    </div>
  );
}
