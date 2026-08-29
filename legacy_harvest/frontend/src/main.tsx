import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/app-shell";
import AgentDetailPage from "./pages/agent-detail-page";
import AgentsPage from "./pages/agents-page";
import CalendarPage from "./pages/calendar-page";
import DashboardPage from "./pages/dashboard-page";
import DepartmentPage from "./pages/department-page";
import DepartmentsPage from "./pages/departments-page";
import DiscoveryPage from "./pages/discovery-page";
import GuardrailsPage from "./pages/guardrails-page";
import LabPage from "./pages/lab-page";
import McpDetailPage from "./pages/mcp-detail-page";
import McpsPage from "./pages/mcps-page";
import MonitorPage from "./pages/monitor-page";
import RuntimePage from "./pages/runtime-page";
import OrganizationPage from "./pages/organization-page";
import ProjectPage from "./pages/project-page";
import ApprovalsPage from "./pages/approvals-page";
import ValidationPage from "./pages/validation-page";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="projects/:projectId" element={<ProjectPage />} />
        <Route path="projects/:projectId/organization" element={<OrganizationPage />} />
        <Route path="projects/:projectId/departments" element={<DepartmentsPage />} />
        <Route path="projects/:projectId/departments/:departmentId" element={<DepartmentPage />} />
        <Route path="projects/:projectId/discovery" element={<DiscoveryPage />} />
        <Route path="projects/:projectId/guardrails" element={<GuardrailsPage />} />
        <Route path="projects/:projectId/runtime" element={<RuntimePage />} />
        <Route path="projects/:projectId/runtime/:specId" element={<RuntimePage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="agents/:specId" element={<AgentDetailPage />} />
        <Route path="mcps" element={<McpsPage />} />
        <Route path="mcps/:systemId" element={<McpDetailPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="runtime" element={<RuntimePage />} />
        <Route path="runtime/:specId" element={<RuntimePage />} />
        <Route path="monitor" element={<MonitorPage />} />
        <Route path="approvals" element={<ApprovalsPage />} />
        <Route path="validation" element={<ValidationPage />} />
        <Route path="labs/:kind" element={<LabPage />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/app">
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
