import { useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { getDashboardSummary, type DashboardSummaryResponse } from "../lib/api";
import { useLiveMarketData } from "../hooks/useLiveMarketData";
import type { MarketDataState } from "../lib/realtime";

const primaryNavigation = [
  { to: "/dashboard", label: "Dashboard", short: "DB" },
  { to: "/orderbook", label: "Orderbook", short: "OB" },
  { to: "/tradebook", label: "Tradebook", short: "TB" },
  { to: "/positions", label: "Positions", short: "PS" },
  { to: "/action-centre", label: "Action Centre", short: "AC" },
  { to: "/logs", label: "Logs", short: "LG" },
  { to: "/tools", label: "Tools", short: "TL" },
] as const;

const utilityNavigation = [
  { to: "/optionchain", label: "Option Chain", short: "OC" },
  { to: "/oi-tracker", label: "OI Tracker", short: "OI" },
  { to: "/oi-profile", label: "OI Profile", short: "OP" },
  { to: "/strategy-builder", label: "Strategy Builder", short: "SB" },
  { to: "/strategy-portfolio", label: "Strategy Portfolio", short: "SP" },
] as const;

const mobileNavigation = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/orderbook", label: "Orderbook" },
  { to: "/tradebook", label: "Tradebook" },
  { to: "/positions", label: "Positions" },
  { to: "/tools", label: "Tools" },
] as const;

type TickerState = {
  data: DashboardSummaryResponse | null;
  loading: boolean;
};

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation();
  const isDashboard = location.pathname === "/" || location.pathname === "/dashboard";
  const allNavigation = useMemo(() => [...primaryNavigation, ...utilityNavigation], []);
  const currentPage = isDashboard
    ? "Dashboard"
    : allNavigation.find((item) => item.to === location.pathname)?.label ?? "APTRADES v2";
  const [tickerState, setTickerState] = useState<TickerState>({ data: null, loading: isDashboard });
  const { connectionState, ticks } = useLiveMarketData();

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
          <NavLink to="/dashboard" className="brand-link">
            <img src="/logo.png" alt="APTRADES" className="brand-logo" />
            <span>
              <p className="brand-kicker">Breeze only</p>
              <h1>APTRADES</h1>
              <p className="brand-caption">Track | Trade | Triumph</p>
            </span>
          </NavLink>
        </div>

        <nav className="nav-list" aria-label="Primary">
          {primaryNavigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) => (isActive ? "nav-item nav-item-active" : "nav-item")}
            >
              <span className="nav-icon" aria-hidden="true">
                {item.short}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="nav-divider" />

        <div className="nav-section">
          <p className="nav-section-label">Utilities</p>
          <nav className="nav-list" aria-label="Utilities">
            {utilityNavigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => (isActive ? "nav-item nav-item-active" : "nav-item")}
              >
                <span className="nav-icon" aria-hidden="true">
                  {item.short}
                </span>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className={`live-pill live-pill-${connectionState}`}>
            <span className={`status-dot status-dot-${connectionState}`} />
            {liveStatusLabel(connectionState)}
          </div>
        </div>
      </aside>
      <div className="content-shell">
        <header className="topbar">
          {isDashboard ? (
            <div className="market-ticker" aria-label="Market ticker">
              {tickerState.loading ? (
                <span className="ticker-chip">Syncing market snapshot...</span>
              ) : (
                (tickerState.data?.ticker ?? []).map((item) => {
                  const live = ticks[item.symbol.toUpperCase()];
                  const ltp = live?.ltp ?? item.ltp;
                  const changePercent = live?.change_percent ?? item.change_percent ?? 0;
                  return (
                    <span key={item.symbol} className={`ticker-chip${live ? " ticker-chip-live" : ""}`}>
                      <strong>{item.symbol}</strong>
                      <span>{ltp ?? "n/a"}</span>
                      <em className={toneClassName(changePercent)}>{changePercent}%</em>
                    </span>
                  );
                })
              )}
            </div>
          ) : (
            <div className="topbar-page">
              <p className="topbar-label">Current page</p>
              <h2>{currentPage}</h2>
            </div>
          )}
          <div className="topbar-actions">
            <div className={`topbar-status topbar-status-${connectionState}`} title={liveStatusLabel(connectionState)}>
              <span className={`status-dot status-dot-${connectionState}`} />
              {liveStatusLabel(connectionState)}
            </div>
            <div className="user-avatar" aria-label="User profile">
              A
            </div>
          </div>
        </header>
        <main className="main-content">{children}</main>
        <nav className="mobile-nav" aria-label="Mobile">
          {mobileNavigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
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

function liveStatusLabel(state: MarketDataState): string {
  switch (state) {
    case "live":
      return "Live market data";
    case "connecting":
      return "Connecting live feed";
    case "degraded":
      return "Live degraded - REST fallback";
    default:
      return "Live offline - REST fallback";
  }
}
