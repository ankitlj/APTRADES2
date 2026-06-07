import { useEffect, useState } from "react";

import {
  getBreezeAuth,
  getDeploymentStatus,
  getHealth,
  getMasterContractStatus,
  getReadiness,
  type BreezeAuthResponse,
  type BatchQuoteRequestItem,
  type BatchQuoteResponse,
  type DeploymentStatusResponse,
  type HealthResponse,
  type MasterContractStatusResponse,
  type ReadinessResponse,
} from "../lib/api";
import { QuoteStatus } from "../components/QuoteStatus";
import { useBatchQuotes } from "../hooks/useQuotes";

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
  quote: Record<string, unknown> | undefined,
): Record<string, unknown> | null {
  if (quote && typeof quote === "object") {
    return quote;
  }
  return null;
}

const quoteRequests: BatchQuoteRequestItem[] = [
  { symbol: "NIFTY", exchange: "NFO", product_type: "futures" },
  { symbol: "BANKNIFTY", exchange: "NFO", product_type: "futures" },
  { symbol: "RELIANCE", exchange: "NSE", product_type: "cash" },
  { symbol: "ADANIPORTS", exchange: "NSE", product_type: "cash" },
  { symbol: "SBIN", exchange: "NSE", product_type: "cash" },
];

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
  const [masterContractState, setMasterContractState] =
    useState<AsyncState<MasterContractStatusResponse>>(createInitialState);
  const quoteState = useBatchQuotes(quoteRequests);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        const [health, readiness, deploymentStatus, breezeAuth, masterContractStatus] = await Promise.all([
          getHealth(),
          getReadiness(),
          getDeploymentStatus(),
          getBreezeAuth(),
          getMasterContractStatus(),
        ]);
        if (!isMounted) {
          return;
        }
        setHealthState({ data: health, loading: false, error: null });
        setReadinessState({ data: readiness, loading: false, error: null });
        setDeploymentState({ data: deploymentStatus, loading: false, error: null });
        setBreezeAuthState({ data: breezeAuth, loading: false, error: null });
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
        <p className="eyebrow">Phase 6</p>
        <h3>Symbol resolution and quote service</h3>
        <p className="panel-copy">
          Imported instruments now drive resolver-backed quote requests so display symbols, Breeze stock codes, and
          nearest futures contracts flow through one backend contract.
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
          <h3>Resolver-backed quotes</h3>
          <span className="badge badge-muted">
            {quoteState.loading ? "Loading" : (quoteState.data?.status ?? "Pending")}
          </span>
        </div>
        {quoteState.error ? (
          <p className="error-text">Quote service unavailable: {quoteState.error}</p>
        ) : (
          <div className="symbol-diagnostics">
            {(quoteState.data?.results ?? []).map((result) => {
              const quote = getPrimaryQuote(result.quote);
              const resolved = result.resolved;

              return (
                <div key={`${result.symbol}-${resolved?.exchange_code ?? result.exchange_code ?? "NA"}`} className="status-card">
                  <p>
                    {result.symbol} / {resolved?.broker_symbol ?? "unresolved"}
                  </p>
                  <QuoteStatus status={result.status} />
                  <span className="symbol-meta">
                    {resolved?.exchange_code ?? result.exchange_code} {resolved?.product_type ?? result.product_type}
                  </span>
                  {resolved ? (
                    <span className="symbol-meta">
                      token {resolved.token ?? "n/a"} | via {resolved.resolution_source}
                    </span>
                  ) : null}
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
                        <dd>{renderQuoteValue(quote.expiry_date ?? resolved?.expiry_date)}</dd>
                      </div>
                    </dl>
                  ) : null}
                  {result.error ? <span className="symbol-error">{result.error}</span> : null}
                </div>
              );
            })}
          </div>
        )}
      </article>
    </section>
  );
}
