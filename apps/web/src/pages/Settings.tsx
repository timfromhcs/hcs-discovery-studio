import { useState } from "react";
import { Link } from "react-router-dom";
import { useClearCache, useDiagnostics, useSettings } from "../api/queries";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Checkbox,
  ConfirmDialog,
  CopyButton,
  ErrorState,
  InlineNotice,
  KeyValue,
  PageHeader,
  Skeleton,
  Stat,
  useToast,
} from "../components/ui";
import { formatBytes, formatDate } from "../lib/format";

const ENV_VARS: Array<{ name: string; description: string }> = [
  { name: "HCS_DATA_DIR", description: "Database, uploads, artifacts and cache directory (default ./data)." },
  { name: "HCS_NETWORK_POLICY", description: "local (default) or remote. Remote requires an explicit opt-in." },
  { name: "HCS_HOST / HCS_PORT", description: "Bind address. Non-loopback binding requires HCS_API_TOKEN." },
  { name: "HCS_API_TOKEN", description: "Bearer token enforced for API requests when not bound to loopback." },
  { name: "HCS_CPU_THREADS", description: "Optional thread cap for deterministic chemistry work." },
  { name: "HCS_MAX_IMPORT_ROWS", description: "Reject imports above this row count (default 50,000)." },
  { name: "HCS_MAX_UPLOAD_MB", description: "Upload size limit in MiB (default 64)." },
  {
    name: "HCS_ALLOW_EXTERNAL_RECEPTOR_PATHS",
    description: "Docking receptors are read from <data dir>/receptors. Set to true only on a trusted local install to allow other paths.",
  },
  {
    name: "HCS_LLM_BASE_URL / HCS_LLM_MODEL",
    description: "Optional OpenAI-compatible endpoint for the provider probe; no LLM workflow node is registered yet.",
  },
  { name: "HCS_LLM_API_KEY", description: "Provider key read from the environment; never persisted or displayed." },
];

export function SettingsPage() {
  const settings = useSettings();
  const [providers, setProviders] = useState(false);
  const [vulkan, setVulkan] = useState(false);
  const diagnostics = useDiagnostics({ providers, vulkan });
  const clearCache = useClearCache();
  const { notify } = useToast();
  const [confirmClear, setConfirmClear] = useState(false);
  const [lastCleared, setLastCleared] = useState<{ entries: number; bytes: number } | null>(null);

  const values = settings.data?.values;
  const storage = settings.data?.storage;

  const runDiagnostics = async () => {
    const result = await diagnostics.refetch();
    if (result.error) {
      notify(result.error instanceof Error ? result.error.message : "Diagnostics failed", "danger");
    }
  };

  const doClearCache = async () => {
    try {
      const result = await clearCache.mutateAsync();
      setLastCleared({ entries: result.removed_entries, bytes: result.removed_bytes });
      await settings.refetch();
      notify(`Cache cleared: ${result.removed_entries} entries, ${formatBytes(result.removed_bytes)}`, "ok");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not clear the cache", "danger");
    } finally {
      setConfirmClear(false);
    }
  };

  return (
    <div className="page">
      <PageHeader
        eyebrow="Settings"
        title="Configuration, storage and diagnostics"
        description="This view is read-only. Secrets are shown only as “configured” or “missing”; changing them means editing the environment and restarting the service."
        actions={
          <Button variant="secondary" icon="refresh" onClick={() => void settings.refetch()} loading={settings.isFetching}>
            Refresh
          </Button>
        }
        meta={
          <>
            <Badge tone={values?.network_policy === "remote" ? "warn" : "accent"} dot>
              {values ? `${values.network_policy} network policy` : "…"}
            </Badge>
            <span className="muted small">
              {values ? `Bound to ${values.host}:${values.port}` : "Reading configuration…"}
            </span>
          </>
        }
      />

      {settings.error ? <ErrorState error={settings.error} onRetry={() => void settings.refetch()} /> : null}

      <section className="stats-grid" aria-label="Storage totals">
        <Stat label="Database" value={storage ? formatBytes(storage.database_bytes) : "—"} icon="database" hint="SQLite file" />
        <Stat label="Run artifacts" value={storage ? formatBytes(storage.runs_bytes) : "—"} icon="folder" hint="Immutable per-run files" />
        <Stat
          label="Node cache"
          value={storage ? storage.cache.entries.toLocaleString() : "—"}
          icon="cpu"
          hint={storage ? formatBytes(storage.cache.bytes) : undefined}
        />
        <Stat label="Upload limit" value={values ? `${values.max_upload_mb} MiB` : "—"} icon="upload" hint="Per file, enforced" />
      </section>

      <div className="grid-2">
        <Card>
          <CardHeader title="Runtime configuration" subtitle="Derived from HCS_* environment variables." icon="settings" />
          {settings.isLoading ? (
            <Skeleton className="skeleton-block" />
          ) : values ? (
            <KeyValue
              items={[
                { label: "Data directory", value: values.data_dir, mono: true },
                { label: "Network policy", value: values.network_policy },
                { label: "Bind address", value: `${values.host}:${values.port}`, mono: true },
                { label: "CPU threads", value: values.cpu_threads === null ? "automatic" : String(values.cpu_threads) },
                { label: "Max import rows", value: values.max_import_rows.toLocaleString() },
                { label: "Max upload", value: `${values.max_upload_mb} MiB` },
                { label: "LLM endpoint", value: values.llm_base_url ?? "not configured", mono: Boolean(values.llm_base_url) },
                { label: "LLM model", value: values.llm_model ?? "not configured" },
                { label: "LLM API key", value: values.llm_api_key },
                { label: "Remote LLM", value: values.remote_llm_enabled ? `enabled (${values.remote_llm_api_key})` : "disabled" },
                { label: "API token", value: values.api_token },
              ]}
            />
          ) : null}
          <div className="row-actions">
            <CopyButton value="GET /api/v1/settings" label="Copy API path" />
            <CopyButton value="hcs-discovery doctor --json" label="Copy doctor CLI" />
          </div>
        </Card>

        <Card>
          <CardHeader title="Local storage" subtitle="Everything lives under the data directory." icon="database" />
          {storage ? (
            <>
              <KeyValue
                items={[
                  { label: "SQLite", value: formatBytes(storage.database_bytes) },
                  { label: "Run artifacts", value: formatBytes(storage.runs_bytes) },
                  { label: "Cache entries", value: storage.cache.entries.toLocaleString() },
                  { label: "Cache size", value: formatBytes(storage.cache.bytes) },
                ]}
              />
              <InlineNotice tone="warn" title="Cache clear is safe but not free">
                Cached node outputs are deleted. Results already committed to runs are untouched, but future runs will
                recompute those nodes. Deleting the SQLite file would destroy projects, runs and provenance.
              </InlineNotice>
              {lastCleared ? (
                <p className="small muted">
                  Last clear removed {lastCleared.entries} entries ({formatBytes(lastCleared.bytes)}).
                </p>
              ) : null}
              <div className="danger-zone">
                <div>
                  <strong>Clear node cache</strong>
                  <p className="tiny muted">Derived data only. Requires confirm=true on the API.</p>
                </div>
                <Button variant="danger" icon="trash" disabled={!storage.cache.entries} onClick={() => setConfirmClear(true)}>
                  Clear cache
                </Button>
              </div>
            </>
          ) : settings.isLoading ? (
            <Skeleton className="skeleton-block" />
          ) : (
            <p className="muted small">Storage information unavailable.</p>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Diagnostics"
          subtitle="Probes only run when you ask for them. Results are not cached across restarts."
          icon="cpu"
          actions={
            <Button size="sm" variant="secondary" icon="refresh" onClick={() => void runDiagnostics()} loading={diagnostics.isFetching}>
              Run checks
            </Button>
          }
        />
        <div className="toolbar">
          <Checkbox label="Probe LLM providers" description="May make a network request if remote policy is enabled." checked={providers} onChange={(event) => setProviders(event.target.checked)} />
          <Checkbox label="Probe Vulkan devices" description="Reports device inventory; execution remains CPU-bound." checked={vulkan} onChange={(event) => setVulkan(event.target.checked)} />
          <div className="toolbar-spacer" />
          {diagnostics.data ? (
            <Badge tone={diagnostics.data.status === "ok" ? "ok" : diagnostics.data.status === "degraded" ? "warn" : "danger"} dot>
              {diagnostics.data.status}
            </Badge>
          ) : null}
        </div>

        {diagnostics.isLoading ? (
          <Skeleton className="skeleton-block" />
        ) : diagnostics.error ? (
          <ErrorState error={diagnostics.error} onRetry={() => void runDiagnostics()} />
        ) : diagnostics.data ? (
          <>
            <ul className="check-list">
              {diagnostics.data.checks.map((check) => (
                <li key={check.id}>
                  <span className={`check-dot ${check.status}`} aria-hidden="true" />
                  <div>
                    <span>{check.label}</span>
                    <p className="muted small">{check.detail}</p>
                    {check.remediation ? <p className="tiny muted">Remediation: {check.remediation}</p> : null}
                  </div>
                  <Badge tone={check.status === "ok" ? "ok" : check.status === "warning" ? "warn" : "danger"}>{check.status}</Badge>
                </li>
              ))}
            </ul>
            <div className="table-note">
              Python {diagnostics.data.environment.python} · {diagnostics.data.environment.platform} ·{" "}
              {diagnostics.data.environment.machine} · {diagnostics.data.environment.cpu_count ?? "?"} CPUs · generated{" "}
              {formatDate(diagnostics.data.generated_at)}
            </div>
          </>
        ) : null}
      </Card>

      <Card>
        <CardHeader title="Environment variables" subtitle="Set these before starting the service; the UI never writes them." icon="settings" />
        <div className="table-wrap">
          <table className="data-table env-table">
            <thead>
              <tr>
                <th>Variable</th>
                <th>Effect</th>
              </tr>
            </thead>
            <tbody>
              {ENV_VARS.map((item) => (
                <tr key={item.name}>
                  <td className="mono small">{item.name}</td>
                  <td className="small muted">{item.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="row-actions">
          <CopyButton value="hcs-discovery doctor --check-vulkan --check-providers" label="Copy doctor command" />
          <CopyButton value="hcs-discovery serve --host 127.0.0.1 --port 8787" label="Copy serve command" />
        </div>
        <p className="tiny muted">
          Prefer the <span className="mono">.env</span> file for local development, but never commit production secrets.
          See the <Link to="/about">security notes</Link> for the threat model.
        </p>
      </Card>

      <ConfirmDialog
        open={confirmClear}
        title="Clear the node cache?"
        description="Cached node outputs will be deleted. Existing run results and artifacts remain intact."
        confirmLabel="Clear cache"
        onClose={() => setConfirmClear(false)}
        onConfirm={() => void doClearCache()}
        busy={clearCache.isPending}
      >
        <p className="small muted">
          Removed entries: {storage?.cache.entries.toLocaleString() ?? 0} · {formatBytes(storage?.cache.bytes ?? 0)}
        </p>
      </ConfirmDialog>
    </div>
  );
}
