import { useEffect, useState } from "react";

import { getHealth, getReadiness, type HealthResponse, type ReadinessResponse } from "../lib/api";

type AsyncState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

function createInitialState<T>(): AsyncState<T> {
  return { data: null, loading: true, error: null };
}

export function DashboardPage() {
  const [healthState, setHealthState] = useState<AsyncState<HealthResponse>>(createInitialState);
  const [readinessState, setReadinessState] = useState<AsyncState<ReadinessResponse>>(createInitialState);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        const [health, readiness] = await Promise.all([getHealth(), getReadiness()]);
        if (!isMounted) {
          return;
        }
        setHealthState({ data: health, loading: false, error: null });
        setReadinessState({ data: readiness, loading: false, error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        if (!isMounted) {
          return;
        }
        setHealthState({ data: null, loading: false, error: message });
        setReadinessState({ data: null, loading: false, error: message });
      }
    }

    void load();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section className="dashboard-grid">
      <article className="panel panel-hero">
        <p className="eyebrow">Phase 1</p>
        <h3>Clean Breeze-only APTRADES v2 skeleton</h3>
        <p className="panel-copy">
          Backend contract first. Typed frontend second. Full trading workflows start after deployment and broker
          diagnostics are in place.
        </p>
      </article>
      <article className="panel">
        <div className="panel-header">
          <h3>API health</h3>
          <span className="badge">{healthState.loading ? "Loading" : "Live check"}</span>
        </div>
        {healthState.error ? (
          <p className="error-text">Backend unavailable: {healthState.error}</p>
        ) : (
          <dl className="metric-list">
            <div>
              <dt>Status</dt>
              <dd>{healthState.data?.status ?? "pending"}</dd>
            </div>
            <div>
              <dt>Service</dt>
              <dd>{healthState.data?.service ?? "pending"}</dd>
            </div>
            <div>
              <dt>Timestamp</dt>
              <dd>{healthState.data?.timestamp ?? "pending"}</dd>
            </div>
          </dl>
        )}
      </article>
      <article className="panel">
        <div className="panel-header">
          <h3>Readiness</h3>
          <span className="badge badge-muted">Environment</span>
        </div>
        {readinessState.error ? (
          <p className="error-text">Readiness unavailable: {readinessState.error}</p>
        ) : (
          <div className="status-grid">
            {Object.entries(readinessState.data?.checks ?? {}).map(([name, value]) => (
              <div key={name} className="status-card">
                <p>{name}</p>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        )}
      </article>
      <article className="panel">
        <div className="panel-header">
          <h3>Phase 1 route map</h3>
          <span className="badge badge-muted">MVP shell</span>
        </div>
        <ul className="route-list">
          <li>Dashboard</li>
          <li>Orderbook</li>
          <li>Tradebook</li>
          <li>Positions</li>
          <li>Action Centre</li>
          <li>Strategy</li>
          <li>Logs</li>
          <li>Tools</li>
        </ul>
      </article>
    </section>
  );
}
