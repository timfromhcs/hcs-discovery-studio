export type RunStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type NodeStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown> | unknown[] | null;
  };
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  purpose: string;
  compound_count: number;
  run_count: number;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RunSummary {
  id: string;
  workflow_name: string;
  status: RunStatus;
  project_id: string;
  dataset_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface DatasetSummary {
  id: string;
  project_id: string;
  name: string;
  source_format: string;
  original_filename: string;
  sha256: string;
  record_count: number;
  imported_count: number;
  error_count: number;
  duplicate_count: number;
  license: string;
  source_url: string | null;
  column_mapping: Record<string, unknown>;
  transformation_log: Array<Record<string, unknown>>;
  created_at: string;
}

export interface DatasetRow {
  row_index: number;
  status: string;
  error: string | null;
  compound_id: string | null;
  raw: Record<string, unknown>;
}

export interface DatasetRowsPage {
  total: number;
  limit: number;
  offset: number;
  items: DatasetRow[];
}

export interface ProjectOverview {
  project: {
    id: string;
    name: string;
    description: string;
    purpose: string;
    created_at: string;
    updated_at: string;
  };
  counts: {
    compounds: number;
    datasets: number;
    runs: number;
    workflows: number;
  };
  datasets: Array<{
    id: string;
    name: string;
    source_format: string;
    record_count: number;
    imported_count: number;
    error_count: number;
    created_at: string;
  }>;
  runs: RunSummary[];
  workflows: WorkflowSummary[];
}

export interface ColumnMeta {
  name: string;
  label: string;
  type: "string" | "number" | "boolean";
  unit: string | null;
  direction: "higher" | "lower" | "neutral" | null;
  method: string | null;
  description: string | null;
}

export interface CompoundSummary {
  id: string;
  name: string | null;
  smiles: string;
  canonical_smiles: string;
  formula: string | null;
  source_id: string | null;
  inchikey: string | null;
  dataset_id: string | null;
  warnings: string[];
  created_at: string;
  descriptors: Record<string, number | null>;
}

export interface CompoundList {
  total: number;
  limit: number;
  offset: number;
  items: CompoundSummary[];
  sort: string;
  order: "asc" | "desc";
}

export interface DescriptorDetail {
  value: number | null;
  label: string;
  unit: string | null;
  direction: string | null;
  method: string;
  description: string;
}

export interface CompoundRunAppearance {
  run_id: string;
  workflow_name: string;
  status: RunStatus;
  rank: number | null;
  composite_score: number | null;
  pareto_front: number | null;
  rejected: boolean;
  reasons: string[];
  metrics: Record<string, unknown>;
  created_at: string;
}

export interface CompoundDetail {
  id: string;
  project_id: string;
  name: string | null;
  input_smiles: string;
  canonical_smiles: string;
  isomeric_smiles: string;
  inchi: string | null;
  inchikey: string | null;
  formula: string | null;
  formal_charge: number;
  warnings: string[];
  created_at: string;
  source: {
    dataset_id: string | null;
    dataset_name: string | null;
    source_format: string | null;
    source_row_index: number | null;
    source_id: string | null;
    source_url: string | null;
    license: string;
    dataset_sha256: string | null;
  };
  descriptors: Record<string, DescriptorDetail>;
  runs: CompoundRunAppearance[];
  [key: string]: unknown;
}

export interface WorkflowNode {
  id: string;
  type: string;
  title?: string | null;
  config: Record<string, unknown>;
  timeout_seconds?: number;
}

export interface WorkflowEdge {
  source: string;
  target: string;
}

export interface WorkflowDefinition {
  schema_version: number;
  id: string;
  name: string;
  description?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  metadata?: Record<string, unknown>;
}

export interface WorkflowSummary {
  id: string;
  project_id?: string;
  name: string;
  description: string;
  schema_version?: number;
  content_hash: string;
  definition?: WorkflowDefinition;
  created_at?: string;
  updated_at: string;
}

export interface NodeCatalogItem {
  type: string;
  title: string;
  category: string;
  version: string;
  description: string;
  requires: string[];
  config_schema: Record<string, unknown>;
  documentation: string;
}

export interface WorkflowCatalog {
  items: NodeCatalogItem[];
  templates: WorkflowDefinition[];
}

export interface WorkflowValidation {
  valid: boolean;
  content_hash: string;
  order: string[];
  nodes: Array<{ id: string; type: string; columns_after: ColumnMeta[] }>;
}

export interface RunNode {
  node_id: string;
  type: string;
  status: NodeStatus;
  progress: number | null;
  cached: boolean;
  cache_key: string | null;
  summary: Record<string, unknown>;
  error: { code?: string; message?: string } | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Artifact {
  id: number;
  rel_path: string;
  node_id: string | null;
  kind: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
}

export interface RunDetail extends RunSummary {
  workflow_hash: string;
  workflow_snapshot: WorkflowDefinition;
  seed: number | null;
  attempt: number;
  cancel_requested: boolean;
  manifest: Record<string, unknown> & {
    columns?: ColumnMeta[];
    environment?: Record<string, unknown>;
    limitations?: string[];
  };
  nodes: RunNode[];
  artifacts: Artifact[];
}

export interface RunEvent {
  seq: number;
  ts: string;
  type: string;
  level: "info" | "warning" | "error" | string;
  message: string;
  node_id: string | null;
  data: Record<string, unknown>;
}

export interface RunEventsPage {
  items: RunEvent[];
  last_seq: number;
  run: RunSummary;
}

export interface ResultItem {
  compound_id: string;
  name: string | null;
  smiles: string | null;
  rank: number | null;
  composite_score: number | null;
  pareto_front: number | null;
  rejected: boolean;
  reasons: string[];
  metrics: Record<string, number | string | boolean | null>;
}

export interface ResultsPage {
  run: RunSummary;
  total: number;
  limit: number;
  offset: number;
  sort: string;
  order: "asc" | "desc";
  columns: ColumnMeta[];
  items: ResultItem[];
}

export interface ModelCard {
  id: string;
  display_name: string;
  category: string;
  version: string;
  license: { code: string; weights: string; data: string };
  capabilities: string[];
  device_providers: string[];
  network_required: boolean;
  resource_profile: { ram_mb_min: number | null; vram_mb_min: number | null };
  status: string;
  citation_url: string | null;
  documentation_url: string | null;
  notes: string[];
  implemented: boolean;
}

export interface SettingsView {
  values: {
    data_dir: string;
    network_policy: string;
    host: string;
    port: number;
    cpu_threads: number | null;
    max_import_rows: number;
    max_upload_mb: number;
    llm_base_url: string | null;
    llm_model: string | null;
    llm_api_key: string;
    remote_llm_enabled: boolean;
    remote_llm_api_key: string;
    api_token: string;
  };
  storage: {
    database_bytes: number;
    runs_bytes: number;
    cache: { entries: number; bytes: number };
  };
  product: { name: string; version: string; tagline: string; credit: string };
}

export interface Stats {
  projects: number;
  compounds: number;
  runs: number;
  queued_runs: number;
  running_runs: number;
  data_dir: string;
  cache: { entries: number; bytes: number };
}

export interface DiagnosticCheck {
  id: string;
  label: string;
  status: "ok" | "warning" | "error" | string;
  detail: string;
  remediation: string | null;
}

export interface Diagnostics {
  product: { name: string; version: string };
  status: "ok" | "degraded" | "error";
  generated_at: string;
  environment: {
    python: string;
    platform: string;
    machine: string;
    cpu_count: number | null;
    packages: Record<string, string>;
    backend: string;
  };
  checks: DiagnosticCheck[];
}

export interface AboutInfo {
  product: string;
  version: string;
  tagline: string;
  credit: string;
  license: string;
  local_first: boolean;
  network_policy: string;
}

export interface ImportOptions {
  name?: string;
  format: string;
  license: string;
  source_url?: string;
  smiles_column?: string;
  name_column?: string;
  id_column?: string;
  strip_salts: boolean;
  neutralize: boolean;
  canonical_tautomer: boolean;
}

export interface CreatedRun {
  id: string;
  status: RunStatus;
}
