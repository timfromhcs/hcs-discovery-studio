import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { useProject, useSettings, useStats } from "../api/queries";
import { useTheme } from "../lib/theme";
import { Icon, Logo, type IconName } from "./Icon";
import { Badge, IconButton, Skeleton } from "./ui";
import { CREDIT } from "../lib/constants";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
}

const primary: NavItem[] = [
  { to: "/", label: "Workspace", icon: "workspace", end: true },
  { to: "/models", label: "Model registry", icon: "models" },
  { to: "/sources", label: "Data sources", icon: "database" },
  { to: "/settings", label: "Settings", icon: "settings" },
  { to: "/about", label: "About & help", icon: "info" },
];

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { projectId } = useParams();
  const { theme, toggle } = useTheme();
  const stats = useStats();
  const settings = useSettings();
  const project = useProject(projectId ?? "");
  const closeMenu = () => setMenuOpen(false);

  useEffect(() => {
    closeMenu();
  }, [location.pathname]);

  const projectNav: NavItem[] = projectId
    ? [
        { to: `/projects/${projectId}`, label: "Overview", icon: "folder", end: true },
        { to: `/projects/${projectId}/library`, label: "Compound library", icon: "library" },
        { to: `/projects/${projectId}/workflows`, label: "Workflows", icon: "workflow" },
        { to: `/projects/${projectId}/runs`, label: "Runs", icon: "run" },
      ]
    : [];

  const crumbs: Array<{ label: string; to?: string }> = [{ label: "Workspace", to: "/" }];
  if (projectId) {
    crumbs.push({ label: project.data?.project.name ?? "Project", to: `/projects/${projectId}` });
    if (location.pathname.includes("/library")) crumbs.push({ label: "Library" });
    else if (location.pathname.includes("/workflows")) crumbs.push({ label: "Workflows" });
    else if (location.pathname.includes("/runs")) crumbs.push({ label: "Runs" });
  } else if (location.pathname.startsWith("/compounds/")) {
    crumbs.push({ label: "Compound detail" });
  } else if (location.pathname.startsWith("/runs/")) {
    crumbs.push({ label: "Run" });
  } else if (location.pathname.startsWith("/models")) {
    crumbs.push({ label: "Model registry" });
  } else if (location.pathname.startsWith("/sources")) {
    crumbs.push({ label: "Data sources" });
  } else if (location.pathname.startsWith("/settings")) {
    crumbs.push({ label: "Settings" });
  } else if (location.pathname.startsWith("/about")) {
    crumbs.push({ label: "About" });
  }

  const activeJobs = (stats.data?.queued_runs ?? 0) + (stats.data?.running_runs ?? 0);
  const localOnly = settings.data?.values.network_policy !== "remote";

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {menuOpen ? <button className="sidebar-scrim" aria-label="Close navigation" onClick={closeMenu} /> : null}
      <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Primary navigation">
        <div className="brand">
          <Logo />
          <div className="brand-text">
            <strong>HCS Discovery</strong>
            <span>Research studio</span>
          </div>
          <IconButton icon="close" label="Close navigation" className="mobile-only" onClick={closeMenu} />
        </div>

        <nav className="nav">
          {primary.slice(0, 1).map((item) => (
            <NavItemLink key={item.to} item={item} />
          ))}
        </nav>

        {projectId ? (
          <div className="nav-group">
            <div className="nav-label">Project</div>
            {project.isLoading ? (
              <Skeleton className="skeleton-nav" />
            ) : (
              <div className="nav-project-name" title={project.data?.project.name}>
                {project.data?.project.name ?? "Unavailable"}
              </div>
            )}
            <nav className="nav">
              {projectNav.map((item) => (
                <NavItemLink key={item.to} item={item} />
              ))}
            </nav>
          </div>
        ) : null}

        <div className="nav-group">
          <div className="nav-label">System</div>
          <nav className="nav">
            {primary.slice(1).map((item) => (
              <NavItemLink key={item.to} item={item} activeCount={item.to === "/runs" ? activeJobs : undefined} />
            ))}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className={`policy-pill ${localOnly ? "" : "remote"}`}>
            <Icon name="shield" size={15} />
            <span>{localOnly ? "Local-only policy" : "Remote network enabled"}</span>
          </div>
          {stats.data ? (
            <div className="sidebar-stats">
              <span>{stats.data.projects} project{stats.data.projects === 1 ? "" : "s"}</span>
              <span aria-hidden="true">·</span>
              <span>{stats.data.compounds.toLocaleString()} compounds</span>
            </div>
          ) : null}
          <div className="sidebar-credit">{CREDIT}</div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <IconButton icon="menu" label="Open navigation" className="mobile-only" onClick={() => setMenuOpen(true)} />
            <nav aria-label="Breadcrumb" className="breadcrumbs">
              {crumbs.map((crumb, index) => (
                <span key={index}>
                  {index > 0 ? <Icon name="chevronRight" size={13} /> : null}
                  {crumb.to && index < crumbs.length - 1 ? (
                    <NavLink to={crumb.to}>{crumb.label}</NavLink>
                  ) : (
                    <span aria-current={index === crumbs.length - 1 ? "page" : undefined}>{crumb.label}</span>
                  )}
                </span>
              ))}
            </nav>
          </div>
          <div className="topbar-right">
            {activeJobs > 0 ? (
              <Badge tone="info" dot>
                {activeJobs} active {activeJobs === 1 ? "job" : "jobs"}
              </Badge>
            ) : null}
            <span className="version-chip">v{settings.data?.product.version ?? "…"}</span>
            <IconButton
              icon={theme === "dark" ? "sun" : "moon"}
              label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              onClick={toggle}
            />
          </div>
        </header>

        <main id="main" className="content" tabIndex={-1}>
          <Outlet />
        </main>

        <footer className="app-footer">
          <span>
            {settings.data ? `${settings.data.product.name} ${settings.data.product.version}` : "HCS Discovery Studio"}
          </span>
          <span className="footer-credit">{CREDIT}</span>
          <span>
            Predictions are prioritisation signals, not experimental evidence.{" "}
            <NavLink to="/about">Read limitations</NavLink>
          </span>
        </footer>
      </div>
    </div>
  );
}

function NavItemLink({ item, activeCount }: { item: NavItem; activeCount?: number }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
    >
      <Icon name={item.icon} size={18} />
      <span>{item.label}</span>
      {activeCount ? <span className="nav-count">{activeCount}</span> : null}
    </NavLink>
  );
}
