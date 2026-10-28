import type {
  AboutInfo,
  CompoundDetail,
  CompoundList,
  CreatedRun,
  DatasetRowsPage,
  DatasetSummary,
  DiagnosticCheck,
  Diagnostics,
  ImportOptions,
  ModelCard,
  ProjectOverview,
  ProjectSummary,
  ResultsPage,
  RunDetail,
  RunEventsPage,
  RunSummary,
  SettingsView,
  Stats,
  WorkflowCatalog,
  WorkflowDefinition,
  WorkflowSummary,
  WorkflowValidation,
} from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(message: string, status: number, code = "request_failed", details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; details?: unknown };
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ErrorEnvelope | null = null;
  try {
    body = (await response.json()) as ErrorEnvelope;
  } catch {
    // Non-JSON error body: keep a generic message rather than echoing HTML.
  }
  const code = body?.error?.code ?? `http_${response.status}`;
  const message =
    body?.error?.message?.trim() ||
    (response.status === 0 ? "The local service is unreachable." : `Request failed (${response.status}).`);
  return new ApiError(message, response.status, code, body?.error?.details ?? null);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new ApiError(
      error instanceof Error ? error.message : "The local service is unreachable.",
      0,
      "network_error",
    );
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export interface CompoundQuery {
  q?: string;
  dataset_id?: string;
  sort?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

export interface ResultsQuery {
  sort?: string;
  order?: "asc" | "desc";
  only_passing?: boolean;
  q?: string;
  limit?: number;
  offset?: number;
}

export const api = {
  about: () => request<AboutInfo>("/about"),
  stats: () => request<Stats>("/stats"),
  diagnostics: (options?: { providers?: boolean; vulkan?: boolean }) =>
    request<Diagnostics>(
      `/diagnostics${query({ check_providers: options?.providers ?? false, check_vulkan: options?.vulkan ?? false })}`,
    ),

  projects: {
    list: () => request<{ items: ProjectSummary[] }>("/projects"),
    create: (payload: { name: string; description?: string; purpose?: string }) =>
      request<ProjectSummary>("/projects", { method: "POST", body: JSON.stringify(payload) }),
    overview: (id: string) => request<ProjectOverview>(`/projects/${encodeURIComponent(id)}`),
    remove: (id: string) => request<void>(`/projects/${encodeURIComponent(id)}`, { method: "DELETE" }),
    datasets: (id: string) =>
      request<{ items: DatasetSummary[] }>(`/projects/${encodeURIComponent(id)}/datasets`),
    compounds: (id: string, options: CompoundQuery = {}) =>
      request<CompoundList>(`/projects/${encodeURIComponent(id)}/compounds${query({ ...options })}`),
    workflows: (id: string) =>
      request<{ items: WorkflowSummary[] }>(`/projects/${encodeURIComponent(id)}/workflows`),
  },

  datasets: {
    get: (id: string) => request<DatasetSummary>(`/datasets/${encodeURIComponent(id)}`),
    rows: (id: string, options: { status?: string; limit?: number; offset?: number } = {}) =>
      request<DatasetRowsPage>(`/datasets/${encodeURIComponent(id)}/rows${query({ ...options })}`),
    remove: (id: string) => request<void>(`/datasets/${encodeURIComponent(id)}`, { method: "DELETE" }),
    import: (projectId: string, file: File, options: ImportOptions) => {
      const form = new FormData();
      form.set("file", file);
      form.set("format", options.format || "auto");
      form.set("license", options.license || "unknown");
      if (options.name) form.set("name", options.name);
      if (options.source_url) form.set("source_url", options.source_url);
      if (options.smiles_column) form.set("smiles_column", options.smiles_column);
      if (options.name_column) form.set("name_column", options.name_column);
      if (options.id_column) form.set("id_column", options.id_column);
      form.set("strip_salts", String(options.strip_salts));
      form.set("neutralize", String(options.neutralize));
      form.set("canonical_tautomer", String(options.canonical_tautomer));
      return request<DatasetSummary>(`/projects/${encodeURIComponent(projectId)}/datasets`, {
        method: "POST",
        body: form,
      });
    },
  },

  compounds: {
    get: (id: string) => request<CompoundDetail>(`/compounds/${encodeURIComponent(id)}`),
    depictionUrl: (id: string, theme: "dark" | "light") =>
      `${BASE}/compounds/${encodeURIComponent(id)}/depiction.svg?theme=${theme}&width=520&height=360`,
  },

  workflows: {
    catalog: () => request<WorkflowCatalog>("/workflow-catalog"),
    get: (id: string) => request<WorkflowSummary>(`/workflows/${encodeURIComponent(id)}`),
    validate: (definition: WorkflowDefinition) =>
      request<WorkflowValidation>("/workflows/validate", {
        method: "POST",
        body: JSON.stringify({ definition }),
      }),
    save: (projectId: string, definition: WorkflowDefinition, workflowId?: string) =>
      request<WorkflowSummary>(workflowId ? `/workflows/${encodeURIComponent(workflowId)}` : "/workflows", {
        method: workflowId ? "PUT" : "POST",
        body: JSON.stringify({ project_id: projectId, definition }),
      }),
    remove: (id: string) => request<void>(`/workflows/${encodeURIComponent(id)}`, { method: "DELETE" }),
  },

  runs: {
    list: (projectId?: string, limit = 50) =>
      request<{ items: RunSummary[] }>(`/runs${query({ project_id: projectId, limit })}`),
    create: (payload: {
      project_id: string;
      dataset_id: string;
      workflow?: WorkflowDefinition;
      workflow_id?: string;
      seed?: number | null;
    }) => request<RunDetail>("/runs", { method: "POST", body: JSON.stringify(payload) }),
    get: (id: string) => request<RunDetail>(`/runs/${encodeURIComponent(id)}`),
    cancel: (id: string) =>
      request<{ id: string; status: string; cancel_requested: boolean }>(
        `/runs/${encodeURIComponent(id)}/cancel`,
        { method: "POST" },
      ),
    retry: (id: string) =>
      request<RunDetail>(`/runs/${encodeURIComponent(id)}/retry`, { method: "POST" }),
    events: (id: string, after = 0, limit = 500) =>
      request<RunEventsPage>(`/runs/${encodeURIComponent(id)}/events${query({ after, limit })}`),
    eventsUrl: (id: string, after = 0) =>
      `${BASE}/runs/${encodeURIComponent(id)}/events/stream${query({ after })}`,
    results: (id: string, options: ResultsQuery = {}) =>
      request<ResultsPage>(`/runs/${encodeURIComponent(id)}/results${query({ ...options })}`),
    artifactUrl: (runId: string, artifactId: number) =>
      `${BASE}/runs/${encodeURIComponent(runId)}/artifacts/${artifactId}`,
    reportUrl: (runId: string, format: "html" | "markdown" | "json" | "csv", download = true) =>
      `${BASE}/runs/${encodeURIComponent(runId)}/report${query({ format, download })}`,
  },

  models: {
    list: (probe = false) => request<{ items: ModelCard[]; note: string }>(`/models${query({ probe })}`),
  },

  settings: () => request<SettingsView>("/settings"),
  clearCache: () => request<{ removed_entries: number; removed_bytes: number }>("/cache?confirm=true", { method: "DELETE" }),
  diagnosticsOnly: () => request<Diagnostics>("/diagnostics"),
};

export function checkTone(status: DiagnosticCheck["status"]): "ok" | "warning" | "error" {
  return status === "ok" ? "ok" : status === "warning" ? "warning" : "error";
}

export type { CreatedRun };
