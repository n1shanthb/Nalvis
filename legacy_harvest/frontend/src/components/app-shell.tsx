import { Outlet, useLocation } from "react-router-dom";
import { useActiveProjectId } from "../hooks/use-active-project";
import { LoadingProvider } from "./loading-overlay";
import { ApprovalSnackbar } from "./approval-snackbar";
import { useState } from "react";
import { Link, NavLink } from "react-router-dom";

const projectNav = (projectId: string) =>
  [
    [`/projects/${projectId}`, "Workspace"],
    [`/projects/${projectId}/runtime`, "Runtime"],
    ["/mcps", "Systems"],
    [`/projects/${projectId}/guardrails`, "Guardrails"],
  ] as const;

const platformNavWhenProject = [
  ["/", "Dashboard"],
  ["/approvals", "Approvals"],
  ["/validation", "Validation"],
  ["/calendar", "Calendar"],
  ["/agents", "Agents"],
] as const;

const platformNavStandalone = [
  ["/", "Dashboard"],
  ["/runtime", "Runtime"],
  ["/mcps", "Systems"],
  ["/approvals", "Approvals"],
  ["/validation", "Validation"],
  ["/calendar", "Calendar"],
  ["/agents", "Agents"],
] as const;

function NavItem({
  to,
  label,
  end,
  className,
  onClick,
}: {
  to: string;
  label: string;
  end?: boolean;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <NavLink to={to} end={end} className={className} title={label} onClick={onClick}>
      <span className="nav-link-full">{label}</span>
      <span className="nav-link-short" aria-hidden="true">
        {label.slice(0, 1)}
      </span>
    </NavLink>
  );
}

export function AppShell() {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const { pathname } = useLocation();
  const storedProjectId = useActiveProjectId();
  const inProjectRoute = pathname.startsWith("/projects/");
  const projectId = inProjectRoute ? storedProjectId : undefined;
  const platformNav = projectId ? platformNavWhenProject : platformNavStandalone;

  return (
    <LoadingProvider>
      <button className="menu-toggle" type="button" onClick={() => setOpen(!open)} aria-label="Toggle menu">
        Menu
      </button>
      <div className={collapsed ? "app sidebar-collapsed" : "app"}>
        <aside className={[open ? "sidebar open" : "sidebar", collapsed ? "collapsed" : ""].filter(Boolean).join(" ")}>
          <Link className="brand" to="/" onClick={() => setOpen(false)} title="AgentSuite">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-text">AgentSuite</span>
          </Link>

          {projectId && (
            <div className="nav-group nav-group-project">
              <p className="nav-label">Project</p>
              <Link className="nav-project-name" to={`/projects/${projectId}`} onClick={() => setOpen(false)} title={projectId}>
                {projectId}
              </Link>
              <nav className="nav-links" aria-label="Project">
                {projectNav(projectId).map(([to, label]) => (
                  <NavItem
                    key={`${to}-${label}`}
                    to={to}
                    label={label}
                    end={label === "Workspace"}
                    className={label === "Workspace" ? "nav-workspace" : undefined}
                    onClick={() => setOpen(false)}
                  />
                ))}
              </nav>
            </div>
          )}

          <div className="nav-group">
            <p className="nav-label">Platform</p>
            <nav className="nav-links" aria-label="Platform">
              {platformNav.map(([to, label]) => {
                const href =
                  label === "Runtime" && storedProjectId && !projectId
                    ? `/projects/${storedProjectId}/runtime`
                    : to;
                return (
                  <NavItem
                    key={to}
                    to={href}
                    label={label}
                    end={to === "/"}
                    onClick={() => setOpen(false)}
                  />
                );
              })}
            </nav>
          </div>

          <p className="sidebar-foot">AgentSuite · v2</p>

          <button
            type="button"
            className="sidebar-collapse"
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand" : "Collapse"}
          >
            <span className="sidebar-collapse-label">{collapsed ? "Expand" : "Collapse"}</span>
            <span className="sidebar-collapse-icon" aria-hidden="true">
              {collapsed ? "»" : "«"}
            </span>
          </button>
        </aside>
        <main className="main wide">
          <Outlet />
        </main>
        <ApprovalSnackbar />
      </div>
    </LoadingProvider>
  );
}
