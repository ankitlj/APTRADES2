import { useEffect, useState, type PropsWithChildren } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { getDashboardSummary, type DashboardSummaryResponse } from "../lib/api";

const navigation = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/orderbook", label: "Orderbook" },
  { to: "/tradebook", label: "Tradebook" },
  { to: "/positions", label: "Positions" },
  { to: "/action-centre", label: "Action Centre" },
  { to: "/strategy", label: "Strategy" },
  { to: "/logs", label: "Logs" },
  { to: "/tools", label: "Tools" },
];

type TickerState = {
  data: DashboardSummaryResponse | null;
  loading: boolean;
};

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation();
  const isDashboard = location.pathname === "/" || location.pathname === "/dashboard";
  const currentPage = isDashboard
    ? "Dashboard"
    : navigation.find((item) => item.to === location.pathname)?.label ?? "APTRADES v2";
  const [tickerState, setTickerState] = useState<TickerState>({ data: null, loading: isDashboard });

  useEffect(() => {
    let isMounted = true;

    if (!isDashboard) {
      setTickerState({ data: null, loading: false });
      return () => {
        isMounted = false;
      };
    }

    setTickerState({ data: null, loading: true });
    getDashboardSummary()
      .then((data) => {
        if (isMounted) {
          setTickerState({ data, loading: false });
        }
      })
      .catch(() => {
        if (isMounted) {
          setTickerState({ data: null, loading: false });
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isDashboard]);

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
          {isDashboard ? (
            <div className="market-ticker" aria-label="Market ticker">
              {tickerState.loading ? (
                <span className="ticker-chip">Syncing market snapshot...</span>
              ) : (
                (tickerState.data?.ticker ?? []).map((item) => (
                  <span key={item.symbol} className="ticker-chip">
                    <strong>{item.symbol}</strong>
                    <span>{item.ltp ?? "n/a"}</span>
                    <em className={toneClassName(item.change_percent ?? 0)}>{item.change_percent ?? 0}%</em>
                  </span>
                ))
              )}
            </div>
          ) : (
            <div>
              <p className="topbar-label">Current page</p>
              <h2>{currentPage}</h2>
            </div>
          )}
          <div className="topbar-status">
            <span className="status-dot" />
            Phase 8 orderbook and tradebook
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

function toneClassName(value: number) {
  if (value > 0) {
    return "tone-positive";
  }
  if (value < 0) {
    return "tone-negative";
  }
  return "tone-neutral";
}
