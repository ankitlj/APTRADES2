import { useEffect, useState } from "react";

import {
  getDeploymentStatus,
  getHealth,
  getReadiness,
  type DeploymentStatusResponse,
  type HealthResponse,
  type ReadinessResponse,
} from "../lib/api";

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
  const [deploymentState, setDeploymentState] = useState<AsyncState<DeploymentStatusResponse>>(createInitialState);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        const [health, readiness, deploymentStatus] = await Promise.all([
          getHealth(),
          getReadiness(),
          getDeploymentStatus(),
        ]);
        if (!isMounted) {
          return;
        }
        setHealthState({ data: health, loading: false, error: null });
        setReadinessState({ data: readiness, loading: false, error: null });
        setDeploymentState({ data: deploymentStatus, loading: false, error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        if (!isMounted) {
          return;
        }
        setHealthState({ data: null, loading: false, error: message });
        setReadinessState({ data: null, loading: false, error: message });
        setDeploymentState({ data: null, loading: false, error: message });
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
          <h3>Deployment status</h3>
          <span className="badge badge-muted">
            {deploymentState.loading ? "Loading" : deploymentState.data?.environment ?? "Unknown"}
          </span>
        </div>
        {deploymentState.error ? (
          <p className="error-text">Deployment status unavailable: {deploymentState.error}</p>
        ) : (
          <div className="status-grid">
            {Object.entries(deploymentState.data?.checks ?? {}).map(([name, value]) => (
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
          <h3>Deployment targets</h3>
          <span className="badge badge-muted">Phase 2</span>
        </div>
        <dl className="metric-list">
          <div>
            <dt>Frontend</dt>
            <dd>Vercel</dd>
          </div>
          <div>
            <dt>Backend</dt>
            <dd>Railway</dd>
          </div>
          <div>
            <dt>Database</dt>
            <dd>PostgreSQL planned</dd>
          </div>
          <div>
            <dt>Cache</dt>
            <dd>Redis planned</dd>
          </div>
        </dl>
      </article>
    </section>
  );
}
