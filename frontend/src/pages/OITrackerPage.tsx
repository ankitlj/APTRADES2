import { useEffect, useState } from "react";

import {
  getOptionExpiries,
  getOITracker,
  type OITrackerResponse,
  type OIRow,
} from "../lib/api";

type OITrackerState = {
  expiries: string[];
  data: OITrackerResponse | null;
  loadingExpiries: boolean;
  loadingData: boolean;
  error: string | null;
};

const underlyingOptions = ["NIFTY", "BANKNIFTY"];

function BarChartIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M4 20V10M8 20V4M12 20V14M16 20V8M20 20V12"
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

function OIBar({ ceOi, peOi }: { ceOi: number; peOi: number }) {
  const total = ceOi + peOi;
  if (total === 0) {
    return null;
  }
  const cePercent = (ceOi / total) * 100;
  return (
    <div className="oi-bar-wrap">
      <div className="oi-bar-ce" style={{ width: `${cePercent.toFixed(1)}%` }} />
    </div>
  );
}

function OITrackerRow({ row, atmStrike }: { row: OIRow; atmStrike: number }) {
  const isAtm = row.strike_price === atmStrike;
  return (
    <tr className={isAtm ? "oi-row-atm" : undefined}>
      <td className="numeric">{formatNumber(row.strike_price, 0)}</td>
      <td className="numeric tone-positive">{formatNumber(row.ce_oi, 0)}</td>
      <td className="numeric tone-negative">{formatNumber(row.pe_oi, 0)}</td>
      <td className="numeric">{formatNumber(row.total_oi, 0)}</td>
      <td>
        <OIBar ceOi={row.ce_oi} peOi={row.pe_oi} />
      </td>
      <td className="numeric">{formatNumber(row.ce_ltp)}</td>
      <td className="numeric">{formatNumber(row.pe_ltp)}</td>
    </tr>
  );
}

export function OITrackerPage() {
  const [exchangeCode, setExchangeCode] = useState("NFO");
  const [underlying, setUnderlying] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [state, setState] = useState<OITrackerState>({
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
      const payload = await getOITracker({ underlying, expiry: selectedExpiry, exchange: exchangeCode });
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

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Open interest</p>
          <h3 className="route-title-with-icon">
            <span className="icon-tile" aria-hidden="true">
              <BarChartIcon />
            </span>
            OI Tracker
          </h3>
          <p className="panel-message">
            Strikes ranked by total OI. Highest CE OI = resistance. Highest PE OI = support.
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
            <p className="metric-label">Resistance (Max CE OI)</p>
            <strong className="metric-value tone-positive">
              {formatNumber(state.data?.max_ce_oi_strike, 0)}
            </strong>
            <p className="metric-meta">Highest call OI strike</p>
          </article>
          <article className="stat-card">
            <p className="metric-label">Support (Max PE OI)</p>
            <strong className="metric-value tone-negative">
              {formatNumber(state.data?.max_pe_oi_strike, 0)}
            </strong>
            <p className="metric-meta">Highest put OI strike</p>
          </article>
        </div>

        {state.error ? (
          <div className="option-chain-error-card">
            <p className="metric-label">Data unavailable</p>
            <strong>OI Tracker unavailable</strong>
            <p className="panel-message">{state.error}</p>
          </div>
        ) : null}

        {state.loadingData && !state.data ? <p className="panel-message">Loading OI data...</p> : null}

        {state.data ? (
          <div className="table-wrap">
            <table className="data-table oi-tracker-table">
              <thead>
                <tr>
                  <th>Strike</th>
                  <th className="numeric tone-positive">CE OI</th>
                  <th className="numeric tone-negative">PE OI</th>
                  <th className="numeric">Total OI</th>
                  <th>CE / PE split</th>
                  <th className="numeric">CE LTP</th>
                  <th className="numeric">PE LTP</th>
                </tr>
              </thead>
              <tbody>
                {state.data.rows.map((row) => (
                  <OITrackerRow key={row.strike_price} row={row} atmStrike={state.data!.atm_strike} />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
