import { useEffect, useState } from "react";

import {
  getBreezeAuth,
  getBreezeTest,
  getDeploymentStatus,
  getHealth,
  getMasterContractStatus,
  getReadiness,
  type BreezeAuthResponse,
  type BreezeTestResponse,
  type DeploymentStatusResponse,
  type HealthResponse,
  type MasterContractStatusResponse,
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

function statusClassName(value: string) {
  if (value === "online") {
    return "status-value status-online";
  }
  if (value === "offline") {
    return "status-value status-offline";
  }
  return "status-value status-unknown";
}

function getPrimaryQuote(
  quote: BreezeTestResponse["symbols"][number]["quote"],
): Record<string, unknown> | null {
  if (Array.isArray(quote)) {
    return (quote[0] as Record<string, unknown> | undefined) ?? null;
  }
  if (quote && typeof quote === "object") {
    return quote;
  }
  return null;
}

function renderQuoteValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value);
}

export function DashboardPage() {
  const [healthState, setHealthState] = useState<AsyncState<HealthResponse>>(createInitialState);
  const [readinessState, setReadinessState] = useState<AsyncState<ReadinessResponse>>(createInitialState);
  const [deploymentState, setDeploymentState] = useState<AsyncState<DeploymentStatusResponse>>(createInitialState);
  const [breezeAuthState, setBreezeAuthState] = useState<AsyncState<BreezeAuthResponse>>(createInitialState);
  const [breezeTestState, setBreezeTestState] = useState<AsyncState<BreezeTestResponse>>(createInitialState);
  const [masterContractState, setMasterContractState] =
    useState<AsyncState<MasterContractStatusResponse>>(createInitialState);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        const [health, readiness, deploymentStatus, breezeAuth, breezeTest, masterContractStatus] = await Promise.all([
          getHealth(),
          getReadiness(),
          getDeploymentStatus(),
          getBreezeAuth(),
          getBreezeTest(),
          getMasterContractStatus(),
        ]);
        if (!isMounted) {
          return;
        }
        setHealthState({ data: health, loading: false, error: null });
        setReadinessState({ data: readiness, loading: false, error: null });
        setDeploymentState({ data: deploymentStatus, loading: false, error: null });
        setBreezeAuthState({ data: breezeAuth, loading: false, error: null });
        setBreezeTestState({ data: breezeTest, loading: false, error: null });
        setMasterContractState({ data: masterContractStatus, loading: false, error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        if (!isMounted) {
          return;
        }
        setHealthState({ data: null, loading: false, error: message });
        setReadinessState({ data: null, loading: false, error: message });
        setDeploymentState({ data: null, loading: false, error: message });
        setBreezeAuthState({ data: null, loading: false, error: message });
        setBreezeTestState({ data: null, loading: false, error: message });
        setMasterContractState({ data: null, loading: false, error: message });
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
        <p className="eyebrow">Phase 5</p>
        <h3>Master contract foundation</h3>
        <p className="panel-copy">
          This phase persists instrument and alias data so later quote and options flows stop guessing broker symbols or
          futures expiries at runtime.
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
                <strong className={statusClassName(value)}>{value}</strong>
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
                <strong className={statusClassName(value)}>{value}</strong>
              </div>
            ))}
          </div>
        )}
      </article>
      <article className="panel">
        <div className="panel-header">
          <h3>Breeze auth</h3>
          <span className="badge badge-muted">{breezeAuthState.data?.status ?? "Pending"}</span>
        </div>
        {breezeAuthState.error ? (
          <p className="error-text">Breeze auth unavailable: {breezeAuthState.error}</p>
        ) : (
          <dl className="metric-list">
            <div>
              <dt>Configured</dt>
              <dd>{String(breezeAuthState.data?.configured ?? false)}</dd>
            </div>
            <div>
              <dt>User</dt>
              <dd>{breezeAuthState.data?.user_id ?? "pending"}</dd>
            </div>
            <div>
              <dt>Session token received</dt>
              <dd>{String(breezeAuthState.data?.session_token_received ?? false)}</dd>
            </div>
            <div>
              <dt>Missing config</dt>
              <dd>{breezeAuthState.data?.missing?.join(", ") ?? "none"}</dd>
            </div>
          </dl>
        )}
      </article>
      <article className="panel panel-full">
        <div className="panel-header">
          <h3>Master contract status</h3>
          <span className="badge badge-muted">
            {masterContractState.loading ? "Loading" : masterContractState.data?.latest_run?.status ?? masterContractState.data?.status ?? "Pending"}
          </span>
        </div>
        {masterContractState.error ? (
          <p className="error-text">Master contract status unavailable: {masterContractState.error}</p>
        ) : (
          <div className="master-contract-grid">
            <div className="status-card">
              <p>Instrument rows</p>
              <strong>{masterContractState.data?.instrument_count ?? 0}</strong>
            </div>
            <div className="status-card">
              <p>Alias rows</p>
              <strong>{masterContractState.data?.alias_count ?? 0}</strong>
            </div>
            <div className="status-card">
              <p>CSV available</p>
              <strong className={statusClassName(masterContractState.data?.csv_available ? "online" : "offline")}>
                {masterContractState.data?.csv_available ? "online" : "offline"}
              </strong>
            </div>
            <div className="status-card">
              <p>Last import</p>
              <strong>{masterContractState.data?.latest_run?.completed_at ?? "not imported"}</strong>
            </div>
            <div className="status-card panel-span-2">
              <p>Source</p>
              <strong>{masterContractState.data?.latest_run?.source_name ?? "pending"}</strong>
              <span className="symbol-meta">{masterContractState.data?.latest_run?.source_checksum ?? "checksum pending"}</span>
            </div>
            <div className="status-card panel-span-2">
              <p>Verified aliases</p>
              <div className="alias-list">
                {(masterContractState.data?.verified_aliases ?? []).map((alias) => (
                  <span key={`${alias.display_symbol}-${alias.broker_symbol}`} className="alias-chip">
                    {alias.display_symbol}
                    {" -> "}
                    {alias.broker_symbol}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </article>
      <article className="panel panel-full">
        <div className="panel-header">
          <h3>Breeze test symbols</h3>
          <span className="badge badge-muted">{breezeTestState.data?.status ?? "Pending"}</span>
        </div>
        {breezeTestState.error ? (
          <p className="error-text">Breeze test unavailable: {breezeTestState.error}</p>
        ) : (
          <div className="symbol-diagnostics">
            {(breezeTestState.data?.symbols ?? []).map((symbol) => {
              const quote = getPrimaryQuote(symbol.quote);

              return (
                <div key={symbol.symbol} className="status-card">
                  <p>
                    {symbol.symbol} / {symbol.broker_symbol}
                  </p>
                  <strong className={statusClassName(symbol.status === "ok" ? "online" : "offline")}>
                    {symbol.status}
                  </strong>
                  <span className="symbol-meta">
                    {symbol.exchange} {symbol.product_type}
                  </span>
                  {quote ? (
                    <dl className="quote-list">
                      <div>
                        <dt>LTP</dt>
                        <dd>{renderQuoteValue(quote.ltp)}</dd>
                      </div>
                      <div>
                        <dt>Previous close</dt>
                        <dd>{renderQuoteValue(quote.previous_close)}</dd>
                      </div>
                      <div>
                        <dt>Spot</dt>
                        <dd>{renderQuoteValue(quote.spot_price)}</dd>
                      </div>
                      <div>
                        <dt>Expiry</dt>
                        <dd>{renderQuoteValue(quote.expiry_date)}</dd>
                      </div>
                    </dl>
                  ) : null}
                  {symbol.error ? <span className="symbol-error">{symbol.error}</span> : null}
                </div>
              );
            })}
          </div>
        )}
      </article>
    </section>
  );
}
