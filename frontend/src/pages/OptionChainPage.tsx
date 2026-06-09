import { useEffect, useMemo, useState } from "react";

import {
  getOptionChain,
  getOptionExpiries,
  type OptionChainResponse,
  type OptionChainRow,
} from "../lib/api";

type OptionChainState = {
  expiries: string[];
  data: OptionChainResponse | null;
  loadingExpiries: boolean;
  loadingChain: boolean;
  error: string | null;
};

const underlyingOptions = ["NIFTY", "BANKNIFTY"];
const strikeWindowOptions = [8, 12, 16, 20];

function TrendingUpIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M4 16L10 10L14 14L20 8M14 8H20V14"
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

function toneClass(value: number | null | undefined) {
  if ((value ?? 0) > 0) {
    return "tone-positive";
  }
  if ((value ?? 0) < 0) {
    return "tone-negative";
  }
  return "tone-neutral";
}

function OptionChainLegCell({ row, side }: { row: OptionChainRow; side: "ce" | "pe" }) {
  const leg = row[side];
  return (
    <>
      <td className="numeric option-chain-cell">{formatNumber(leg?.oi, 0)}</td>
      <td className="numeric option-chain-cell">{formatNumber(leg?.volume, 0)}</td>
      <td className="numeric option-chain-cell">{formatNumber(leg?.bid)}</td>
      <td className="numeric option-chain-cell">{formatNumber(leg?.ask)}</td>
      <td className="numeric option-chain-cell">{formatNumber(leg?.ltp)}</td>
    </>
  );
}

export function OptionChainPage() {
  const [exchangeCode, setExchangeCode] = useState("NFO");
  const [underlying, setUnderlying] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [strikeCount, setStrikeCount] = useState(12);
  const [state, setState] = useState<OptionChainState>({
    expiries: [],
    data: null,
    loadingExpiries: true,
    loadingChain: false,
    error: null,
  });

  useEffect(() => {
    let active = true;
    setSelectedExpiry("");
    setState((current) => ({
      ...current,
      loadingExpiries: true,
      error: null,
      expiries: [],
      data: null,
    }));

    getOptionExpiries({ underlying, exchange: exchangeCode })
      .then((payload) => {
        if (!active) {
          return;
        }
        const nextExpiry = payload.expiries[0] ?? "";
        setSelectedExpiry(nextExpiry);
        setState((current) => ({
          ...current,
          expiries: payload.expiries,
          loadingExpiries: false,
          error: payload.expiries.length ? null : "No expiries available.",
        }));
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        setSelectedExpiry("");
        setState((current) => ({
          ...current,
          loadingExpiries: false,
          error: error instanceof Error ? error.message : "Unknown error",
        }));
      });

    return () => {
      active = false;
    };
  }, [exchangeCode, underlying]);

  const loadChain = async () => {
    if (!selectedExpiry) {
      return;
    }

    setState((current) => ({ ...current, loadingChain: true, error: null }));
    try {
      const payload = await getOptionChain({
        underlying,
        expiry: selectedExpiry,
        exchange: exchangeCode,
        strike_count: strikeCount,
      });
      setState((current) => ({
        ...current,
        data: payload,
        loadingChain: false,
        error: null,
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        data: null,
        loadingChain: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  };

  useEffect(() => {
    void loadChain();
  }, [selectedExpiry, strikeCount]);

  const previousCloseDelta = useMemo(() => {
    if (!state.data?.underlying_ltp || !state.data.previous_close) {
      return null;
    }
    return state.data.underlying_ltp - state.data.previous_close;
  }, [state.data]);

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Options data</p>
          <h3 className="route-title-with-icon">
            <span className="icon-tile" aria-hidden="true">
              <TrendingUpIcon />
            </span>
            Option chain
          </h3>
          <p className="panel-message">Live Breeze chain normalized into a strike grid with expiry control, ATM context, and real broker errors.</p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="route-toolbar">
          <div className="toolbar-group">
            <label className="toolbar-field">
              <span>Exchange</span>
              <select value={exchangeCode} onChange={(event) => setExchangeCode(event.target.value)}>
                <option value="NFO">NFO</option>
                <option value="BFO">BFO</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Underlying</span>
              <select value={underlying} onChange={(event) => setUnderlying(event.target.value)}>
                {underlyingOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="toolbar-field">
              <span>Expiry</span>
              <select value={selectedExpiry} onChange={(event) => setSelectedExpiry(event.target.value)} disabled={state.loadingExpiries || !state.expiries.length}>
                {state.expiries.map((expiry) => (
                  <option key={expiry} value={expiry}>
                    {expiry}
                  </option>
                ))}
              </select>
            </label>
            <label className="toolbar-field">
              <span>Strike count</span>
              <select value={strikeCount} onChange={(event) => setStrikeCount(Number(event.target.value))}>
                {strikeWindowOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={() => void loadChain()} disabled={!selectedExpiry || state.loadingChain}>
              {state.loadingChain ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>

        <div className="stats-grid option-chain-summary-grid">
          <article className="stat-card">
            <p className="metric-label">Spot</p>
            <strong className={`metric-value ${toneClass(previousCloseDelta)}`}>{formatNumber(state.data?.underlying_ltp)}</strong>
            <p className="metric-meta">{previousCloseDelta === null ? "Awaiting Breeze response" : `${formatNumber(previousCloseDelta)} vs prev close`}</p>
          </article>
          <article className="stat-card">
            <p className="metric-label">ATM strike</p>
            <strong className="metric-value tone-neutral">{formatNumber(state.data?.atm_strike, 0)}</strong>
            <p className="metric-meta">{selectedExpiry || "Select expiry"}</p>
          </article>
          <article className="stat-card">
            <p className="metric-label">PCR</p>
            <strong className="metric-value tone-neutral">{state.data?.pcr === null || state.data?.pcr === undefined ? "n/a" : state.data.pcr.toFixed(4)}</strong>
            <p className="metric-meta">Put OI / Call OI</p>
          </article>
          <article className="stat-card">
            <p className="metric-label">Total OI</p>
            <strong className="metric-value tone-neutral">{formatNumber(state.data?.total_oi, 0)}</strong>
            <p className="metric-meta">Calls + puts</p>
          </article>
        </div>

        {state.error ? (
          <div className="option-chain-error-card">
            <p className="metric-label">Broker offline</p>
            <strong>Option chain unavailable</strong>
            <p className="panel-message">{state.error}</p>
          </div>
        ) : null}

        {state.loadingChain && !state.data ? <p className="panel-message">Loading option chain...</p> : null}

        {state.data ? (
          <div className="table-wrap">
            <table className="data-table option-chain-table">
              <thead>
                <tr>
                  <th colSpan={5} className="option-chain-head option-chain-head-calls">
                    Calls
                  </th>
                  <th className="option-chain-head option-chain-head-strike">Strike</th>
                  <th colSpan={5} className="option-chain-head option-chain-head-puts">
                    Puts
                  </th>
                </tr>
                <tr>
                  <th>OI</th>
                  <th>Vol</th>
                  <th>Bid</th>
                  <th>Ask</th>
                  <th>LTP</th>
                  <th>Strike</th>
                  <th>LTP</th>
                  <th>Bid</th>
                  <th>Ask</th>
                  <th>Vol</th>
                  <th>OI</th>
                </tr>
              </thead>
              <tbody>
                {state.data.rows.map((row) => (
                  <tr key={row.strike_price}>
                    <OptionChainLegCell row={row} side="ce" />
                    <td className={`numeric option-chain-strike-cell ${row.strike_price === state.data?.atm_strike ? "option-chain-strike-atm" : ""}`}>
                      {formatNumber(row.strike_price, 0)}
                    </td>
                    <td className="numeric option-chain-cell">{formatNumber(row.pe?.ltp)}</td>
                    <td className="numeric option-chain-cell">{formatNumber(row.pe?.bid)}</td>
                    <td className="numeric option-chain-cell">{formatNumber(row.pe?.ask)}</td>
                    <td className="numeric option-chain-cell">{formatNumber(row.pe?.volume, 0)}</td>
                    <td className="numeric option-chain-cell">{formatNumber(row.pe?.oi, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
