import { NavLink, useLocation } from "react-router-dom";
import type { PropsWithChildren } from "react";

const navigation = [
  { to: "/", label: "Dashboard" },
  { to: "/orderbook", label: "Orderbook" },
  { to: "/tradebook", label: "Tradebook" },
  { to: "/positions", label: "Positions" },
  { to: "/action-centre", label: "Action Centre" },
  { to: "/strategy", label: "Strategy" },
  { to: "/logs", label: "Logs" },
  { to: "/tools", label: "Tools" },
];

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation();
  const currentPage = navigation.find((item) => item.to === location.pathname)?.label ?? "APTRADES v2";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="brand-kicker">Breeze only</p>
          <h1>APTRADES</h1>
          <p className="brand-caption">Track. Trade. Triumph.</p>
        </div>
        <nav className="nav-list" aria-label="Primary">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => (isActive ? "nav-item nav-item-active" : "nav-item")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="content-shell">
        <header className="topbar">
          <div>
            <p className="topbar-label">Current page</p>
            <h2>{currentPage}</h2>
          </div>
          <div className="topbar-status">
            <span className="status-dot" />
            Phase 1 skeleton
          </div>
        </header>
        <main className="main-content">{children}</main>
        <nav className="mobile-nav" aria-label="Mobile">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => (isActive ? "mobile-item mobile-item-active" : "mobile-item")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
