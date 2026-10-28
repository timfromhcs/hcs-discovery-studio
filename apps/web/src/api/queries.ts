import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type CompoundQuery, type ResultsQuery } from "./client";
import type { ImportOptions, WorkflowDefinition } from "./types";

export const queryKeys = {
  about: ["about"] as const,
  stats: ["stats"] as const,
  diagnostics: ["diagnostics"] as const,
  projects: ["projects"] as const,
  project: (id: string) => ["project", id] as const,
  datasets: (id: string) => ["project", id, "datasets"] as const,
  workflows: (id: string) => ["project", id, "workflows"] as const,
  compounds: (id: string, options: CompoundQuery) => ["project", id, "compounds", options] as const,
  compound: (id: string) => ["compound", id] as const,
  run: (id: string) => ["run", id] as const,
  runEvents: (id: string) => ["run", id, "events"] as const,
  results: (id: string, options: ResultsQuery) => ["run", id, "results", options] as const,
  runs: (projectId?: string) => ["runs", projectId ?? "all"] as const,
  catalog: ["workflow-catalog"] as const,
  workflow: (id: string) => ["workflow", id] as const,
  models: (probe: boolean) => ["models", probe] as const,
  settings: ["settings"] as const,
};

export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects, queryFn: api.projects.list });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => api.projects.overview(projectId),
    enabled: Boolean(projectId),
  });
}

export function useDatasets(projectId: string) {
  return useQuery({
    queryKey: queryKeys.datasets(projectId),
    queryFn: () => api.projects.datasets(projectId),
    enabled: Boolean(projectId),
  });
}

export function useCompounds(projectId: string, options: CompoundQuery) {
  return useQuery({
    queryKey: queryKeys.compounds(projectId, options),
    queryFn: () => api.projects.compounds(projectId, options),
    enabled: Boolean(projectId),
    placeholderData: (previous) => previous,
  });
}

export function useCompound(compoundId: string) {
  return useQuery({
    queryKey: queryKeys.compound(compoundId),
    queryFn: () => api.compounds.get(compoundId),
    enabled: Boolean(compoundId),
  });
}

export function useProjectWorkflows(projectId: string) {
  return useQuery({
    queryKey: queryKeys.workflows(projectId),
    queryFn: () => api.projects.workflows(projectId),
    enabled: Boolean(projectId),
  });
}

export function useWorkflowCatalog() {
  return useQuery({ queryKey: queryKeys.catalog, queryFn: api.workflows.catalog, staleTime: 60_000 });
}

export function useWorkflow(workflowId: string) {
  return useQuery({
    queryKey: queryKeys.workflow(workflowId),
    queryFn: () => api.workflows.get(workflowId),
    enabled: Boolean(workflowId),
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: queryKeys.run(runId),
    queryFn: () => api.runs.get(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1500 : false;
    },
  });
}

export function useRunEvents(runId: string, enabled: boolean, active = false) {
  return useQuery({
    queryKey: queryKeys.runEvents(runId),
    queryFn: () => api.runs.events(runId, 0, 2000),
    enabled: Boolean(runId) && enabled,
    refetchInterval: active ? 2000 : false,
  });
}

export function useRunResults(runId: string, options: ResultsQuery) {
  return useQuery({
    queryKey: queryKeys.results(runId, options),
    queryFn: () => api.runs.results(runId, options),
    enabled: Boolean(runId),
    placeholderData: (previous) => previous,
  });
}

export function useRuns(projectId?: string, limit = 50) {
  return useQuery({
    queryKey: queryKeys.runs(projectId),
    queryFn: () => api.runs.list(projectId, limit),
  });
}

export function useModels(probe: boolean) {
  return useQuery({
    queryKey: queryKeys.models(probe),
    queryFn: () => api.models.list(probe),
    staleTime: 30_000,
  });
}

export function useSettings() {
  return useQuery({ queryKey: queryKeys.settings, queryFn: api.settings });
}

export function useAbout() {
  return useQuery({ queryKey: queryKeys.about, queryFn: api.about, staleTime: 300_000 });
}

export function useStats() {
  return useQuery({ queryKey: queryKeys.stats, queryFn: api.stats });
}

export function useDiagnostics(options?: { providers?: boolean; vulkan?: boolean }) {
  return useQuery({
    queryKey: [...queryKeys.diagnostics, options ?? {}],
    queryFn: () => api.diagnostics(options),
    staleTime: 30_000,
  });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.projects.create,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.projects });
      void client.invalidateQueries({ queryKey: queryKeys.stats });
    },
  });
}

export function useDeleteProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.projects.remove,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.projects });
      void client.invalidateQueries({ queryKey: queryKeys.stats });
    },
  });
}

export function useImportDataset(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ file, options }: { file: File; options: ImportOptions }) =>
      api.datasets.import(projectId, file, options),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.project(projectId) });
      void client.invalidateQueries({ queryKey: queryKeys.stats });
    },
  });
}

export function useDeleteDataset(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.datasets.remove,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.project(projectId) });
      void client.invalidateQueries({ queryKey: queryKeys.stats });
    },
  });
}

export function useSaveWorkflow(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ definition, workflowId }: { definition: WorkflowDefinition; workflowId?: string }) =>
      api.workflows.save(projectId, definition, workflowId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.workflows(projectId) });
      void client.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    },
  });
}

export function useDeleteWorkflow(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.workflows.remove,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.workflows(projectId) });
      void client.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    },
  });
}

export function useCreateRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.runs.create,
    onSuccess: (run) => {
      client.setQueryData(queryKeys.run(run.id), run);
      void client.invalidateQueries({ queryKey: ["runs"] });
      void client.invalidateQueries({ queryKey: queryKeys.project(run.project_id) });
    },
  });
}

export function useCancelRun(runId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.runs.cancel(runId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.run(runId) });
    },
  });
}

export function useRetryRun(runId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.runs.retry(runId),
    onSuccess: (run) => {
      client.setQueryData(queryKeys.run(run.id), run);
      void client.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

export function useClearCache() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.clearCache,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.settings });
      void client.invalidateQueries({ queryKey: queryKeys.stats });
    },
  });
}
