import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/ui";
import { ThemeProvider } from "./lib/theme";
import { AboutPage } from "./pages/About";
import { CompoundPage } from "./pages/Compound";
import { DataSourcesPage } from "./pages/DataSources";
import { LibraryPage } from "./pages/Library";
import { ModelsPage } from "./pages/Models";
import { NotFoundPage } from "./pages/NotFound";
import { ProjectPage } from "./pages/Project";
import { ResultsPage } from "./pages/Results";
import { RunMonitorPage } from "./pages/RunMonitor";
import { RunsPage } from "./pages/Runs";
import { SettingsPage } from "./pages/Settings";
import { WorkflowEditorPage } from "./pages/WorkflowEditor";
import { WorkflowsPage } from "./pages/Workflows";
import { WorkspacePage } from "./pages/Workspace";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
  },
});

/**
 * The editor keeps local state for the graph being edited. Keying the route
 * component by workflow id forces a clean mount when switching between saved
 * workflows instead of leaking the previous definition into the next one.
 */
function WorkflowEditorRoute() {
  const { projectId = "", workflowId = "new" } = useParams();
  return <WorkflowEditorPage key={`${projectId}:${workflowId}`} />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<WorkspacePage />} />
                <Route path="projects/:projectId" element={<ProjectPage />} />
                <Route path="projects/:projectId/library" element={<LibraryPage />} />
                <Route path="projects/:projectId/workflows" element={<WorkflowsPage />} />
                <Route path="projects/:projectId/workflows/:workflowId" element={<WorkflowEditorRoute />} />
                <Route path="projects/:projectId/runs" element={<RunsPage />} />
                <Route path="runs/:runId" element={<RunMonitorPage />} />
                <Route path="runs/:runId/results" element={<ResultsPage />} />
                <Route path="compounds/:compoundId" element={<CompoundPage />} />
                <Route path="models" element={<ModelsPage />} />
                <Route path="sources" element={<DataSourcesPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="about" element={<AboutPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
