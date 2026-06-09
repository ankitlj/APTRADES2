import { useEffect, useState } from "react";

import {
  getOptionExpiries,
  getOIProfile,
  type OIProfileResponse,
  type OIRow,
} from "../lib/api";

type OIProfileState = {
  expiries: string[];
  data: OIProfileResponse | null;
  loadingExpiries: boolean;
  loadingData: boolean;
  error: string | null;
};

const underlyingOptions = ["NIFTY", "BANKNIFTY"];

function LayersIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M12 2L2 7L12 12L22 7L12 2Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M2 17L12 22L22 17"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M2 12L12 17L22 12"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
}

function OIProfileRow({ row, atmStrike, maxTotalOI }: { row: OIRow; atmStrike: number; maxTotalOI: number }) {
  const isAtm = row.strike_price === atmStrike;
  const ceBarWidth = maxTotalOI > 0 ? (row.ce_oi / maxTotalOI) * 100 : 0;
  const peBarWidth = maxTotalOI > 0 ? (row.pe_oi / maxTotalOI) * 100 : 0;
  return (
    <tr className={isAtm ? "oi-row-atm" : undefined}>
      <td className="numeric">{formatNumber(row.strike_price, 0)}</td>
      <td>
        <div className="oi-profile-bar-cell">
          <span className="numeric oi-profile-value tone-positive">{formatNumber(row.ce_oi, 0)}</span>
          <div className="oi-profile-bar-bg">
            <div className="oi-profile-bar-fill oi-profile-bar-ce" style={{ width: `${ceBarWidth.toFixed(1)}%` }} />
          </div>
        </div>
      </td>
      <td>
        <div className="oi-profile-bar-cell oi-profile-bar-cell-pe">
          <div className="oi-profile-bar-bg">
            <div className="oi-profile-bar-fill oi-profile-bar-pe" style={{ width: `${peBarWidth.toFixed(1)}%` }} />
          </div>
          <span className="numeric oi-profile-value tone-negative">{formatNumber(row.pe_oi, 0)}</span>
        </div>
      </td>
      <td className="numeric">{formatNumber(row.ce_ltp)}</td>
      <td className="numeric">{formatNumber(row.pe_ltp)}</td>
    </tr>
  );
}

export function OIProfilePage() {
  const [exchangeCode, setExchangeCode] = useState("NFO");
  const [underlying, setUnderlying] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [state, setState] = useState<OIProfileState>({
    expiries: [],
    data: null,
    loadingExpiries: true,
    loadingData: false,
    error: null,
  });

  useEffect(() => {
    let active = true;
    setSelectedExpiry("");
    setState((s) => ({ ...s, loadingExpiries: true, error: null, expiries: [], data: null }));

    getOptionExpiries({ underlying, exchange: exchangeCode })
      .then((payload) => {
        if (!active) return;
        const next = payload.expiries[0] ?? "";
        setSelectedExpiry(next);
        setState((s) => ({
          ...s,
          expiries: payload.expiries,
          loadingExpiries: false,
          error: payload.expiries.length ? null : "No expiries available.",
        }));
      })
      .catch((error) => {
        if (!active) return;
        setSelectedExpiry("");
        setState((s) => ({
          ...s,
          loadingExpiries: false,
          error: error instanceof Error ? error.message : "Unknown error",
        }));
      });

    return () => {
      active = false;
    };
  }, [exchangeCode, underlying]);

  const loadData = async () => {
    if (!selectedExpiry) return;
    setState((s) => ({ ...s, loadingData: true, error: null }));
    try {
      const payload = await getOIProfile({ underlying, expiry: selectedExpiry, exchange: exchangeCode });
      setState((s) => ({ ...s, data: payload, loadingData: false, error: null }));
    } catch (error) {
      setState((s) => ({
        ...s,
        data: null,
        loadingData: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  };

  useEffect(() => {
    void loadData();
  }, [selectedExpiry]);

  const maxTotalOI = state.data
    ? Math.max(...state.data.rows.map((r) => Math.max(r.ce_oi, r.pe_oi)), 1)
    : 1;

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Open interest</p>
          <h3 className="route-title-with-icon">
            <span className="icon-tile" aria-hidden="true">
              <LayersIcon />
            </span>
            OI Profile
          </h3>
          <p className="panel-message">
            OI distribution across all strikes sorted by price. ATM strike highlighted. CE left, PE right.
          </p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="route-toolbar">
          <div className="toolbar-group">
            <label className="toolbar-field">
              <span>Exchange</span>
              <select value={exchangeCode} onChange={(e) => setExchangeCode(e.target.value)}>
                <option value="NFO">NFO</option>
                <option value="BFO">BFO</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Underlying</span>
              <select value={underlying} onChange={(e) => setUnderlying(e.target.value)}>
                {underlyingOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="toolbar-field">
              <span>Expiry</span>
              <select
                value={selectedExpiry}
                onChange={(e) => setSelectedExpiry(e.target.value)}
                disabled={state.loadingExpiries || !state.expiries.length}
              >
                {state.expiries.map((expiry) => (
                  <option key={expiry} value={expiry}>
                    {expiry}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="toolbar-actions">
            <button
              type="button"
              className="toolbar-button"
              onClick={() => void loadData()}
              disabled={!selectedExpiry || state.loadingData}
            >
              {state.loadingData ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        <div className="stats-grid option-chain-summary-grid">
          <article className="stat-card">
            <p className="metric-label">Spot</p>
            <strong className="metric-value tone-neutral">{formatNumber(state.data?.underlying_ltp)}</strong>
            <p className="metric-meta">{underlying}</p>
          </article>
          <article className="stat-card">
            <p className="metric-label">ATM Strike</p>
            <strong className="metric-value tone-neutral">{formatNumber(state.data?.atm_strike, 0)}</strong>
            <p className="metric-meta">{selectedExpiry || "Select expiry"}</p>
          </article>
          <article className="stat-card">
            <p className="metric-label">PCR</p>
            <strong className="metric-value tone-neutral">
              {state.data?.pcr === null || state.data?.pcr === undefined ? "n/a" : state.data.pcr.toFixed(4)}
            </strong>
            <p className="metric-meta">Put OI / Call OI</p>
          </article>
          <article className="stat-card">
            <p className="metric-label">Total OI</p>
            <strong className="metric-value tone-neutral">
              {formatNumber((state.data?.total_call_oi ?? 0) + (state.data?.total_put_oi ?? 0), 0)}
            </strong>
            <p className="metric-meta">Calls + puts</p>
          </article>
        </div>

        {state.error ? (
          <div className="option-chain-error-card">
            <p className="metric-label">Data unavailable</p>
            <strong>OI Profile unavailable</strong>
            <p className="panel-message">{state.error}</p>
          </div>
        ) : null}

        {state.loadingData && !state.data ? <p className="panel-message">Loading OI profile...</p> : null}

        {state.data ? (
          <div className="table-wrap">
            <table className="data-table oi-profile-table">
              <thead>
                <tr>
                  <th>Strike</th>
                  <th className="tone-positive">CE OI</th>
                  <th className="tone-negative">PE OI</th>
                  <th className="numeric">CE LTP</th>
                  <th className="numeric">PE LTP</th>
                </tr>
              </thead>
              <tbody>
                {state.data.rows.map((row) => (
                  <OIProfileRow
                    key={row.strike_price}
                    row={row}
                    atmStrike={state.data!.atm_strike}
                    maxTotalOI={maxTotalOI}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
