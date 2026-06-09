import { useEffect, useState } from "react";

import { PayoffChart } from "../components/PayoffChart";
import {
  createStrategy,
  getOptionExpiries,
  getStrategyPayoff,
  type PayoffResponse,
  type StrategyLeg,
} from "../lib/api";

type LegDraft = {
  action: string;
  right: string;
  strike: string;
  quantity: string;
  premium: string;
};

type BuilderState = {
  name: string;
  underlying: string;
  exchangeCode: string;
  expiry: string;
  expiries: string[];
  loadingExpiries: boolean;
  legs: StrategyLeg[];
  payoff: PayoffResponse | null;
  computingPayoff: boolean;
  saving: boolean;
  error: string | null;
  saveMessage: string | null;
};

const BLANK_LEG: LegDraft = { action: "sell", right: "call", strike: "", quantity: "1", premium: "" };
const UNDERLYINGS = ["NIFTY", "BANKNIFTY"];

function fmt(v: number | null, dec = 2): string {
  if (v === null || v === undefined) return "n/a";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: dec }).format(v);
}

export function StrategyBuilderPage() {
  const [state, setState] = useState<BuilderState>({
    name: "",
    underlying: "NIFTY",
    exchangeCode: "NFO",
    expiry: "",
    expiries: [],
    loadingExpiries: true,
    legs: [],
    payoff: null,
    computingPayoff: false,
    saving: false,
    error: null,
    saveMessage: null,
  });
  const [draft, setDraft] = useState<LegDraft>({ ...BLANK_LEG });

  useEffect(() => {
    let active = true;
    setState((s) => ({ ...s, loadingExpiries: true, expiry: "", expiries: [], payoff: null }));
    getOptionExpiries({ underlying: state.underlying, exchange: state.exchangeCode })
      .then((payload) => {
        if (!active) return;
        setState((s) => ({
          ...s,
          expiries: payload.expiries,
          expiry: payload.expiries[0] ?? "",
          loadingExpiries: false,
        }));
      })
      .catch(() => {
        if (!active) return;
        setState((s) => ({ ...s, loadingExpiries: false }));
      });
    return () => {
      active = false;
    };
  }, [state.underlying, state.exchangeCode]);

  function addLeg() {
    const strike = parseFloat(draft.strike);
    const quantity = parseInt(draft.quantity, 10);
    const premium = parseFloat(draft.premium);
    if (!draft.strike || isNaN(strike) || strike <= 0) {
      setState((s) => ({ ...s, error: "Strike must be a positive number." }));
      return;
    }
    if (!draft.quantity || isNaN(quantity) || quantity <= 0) {
      setState((s) => ({ ...s, error: "Quantity must be a positive integer." }));
      return;
    }
    if (draft.premium === "" || isNaN(premium) || premium < 0) {
      setState((s) => ({ ...s, error: "Premium must be a non-negative number." }));
      return;
    }
    if (state.legs.length >= 8) {
      setState((s) => ({ ...s, error: "Maximum 8 legs allowed." }));
      return;
    }
    setState((s) => ({
      ...s,
      legs: [...s.legs, { action: draft.action, right: draft.right, strike, quantity, premium }],
      error: null,
      payoff: null,
    }));
    setDraft({ ...BLANK_LEG });
  }

  function removeLeg(index: number) {
    setState((s) => ({ ...s, legs: s.legs.filter((_, i) => i !== index), payoff: null }));
  }

  async function previewPayoff() {
    if (!state.legs.length) return;
    setState((s) => ({ ...s, computingPayoff: true, error: null, payoff: null }));
    try {
      const payload = await getStrategyPayoff(state.legs);
      setState((s) => ({ ...s, payoff: payload, computingPayoff: false }));
    } catch (err) {
      setState((s) => ({
        ...s,
        computingPayoff: false,
        error: err instanceof Error ? err.message : "Payoff calculation failed.",
      }));
    }
  }

  async function saveStrategy() {
    if (!state.name.trim()) {
      setState((s) => ({ ...s, error: "Strategy name is required." }));
      return;
    }
    if (!state.expiry) {
      setState((s) => ({ ...s, error: "Select an expiry." }));
      return;
    }
    if (!state.legs.length) {
      setState((s) => ({ ...s, error: "Add at least one leg." }));
      return;
    }
    setState((s) => ({ ...s, saving: true, error: null, saveMessage: null }));
    try {
      const saved = await createStrategy({
        name: state.name.trim(),
        underlying: state.underlying,
        exchange_code: state.exchangeCode,
        expiry: state.expiry,
        legs: state.legs,
      });
      setState((s) => ({
        ...s,
        saving: false,
        saveMessage: `Strategy "${saved.strategy.name}" saved to portfolio.`,
        legs: [],
        payoff: null,
        name: "",
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        saving: false,
        error: err instanceof Error ? err.message : "Save failed.",
      }));
    }
  }

  const payoffUid = state.payoff
    ? `builder-${state.legs.map((l) => l.strike).join("-")}`
    : "builder";

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Strategy tools</p>
          <h3>Strategy Builder</h3>
          <p className="panel-message">
            Compose multi-leg option structures, preview the payoff diagram, and save to your portfolio.
          </p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Step 1</p>
            <h3>Strategy details</h3>
          </div>
        </div>

        <div className="route-toolbar">
          <div className="toolbar-group">
            <label className="toolbar-field">
              <span>Exchange</span>
              <select
                value={state.exchangeCode}
                onChange={(e) => setState((s) => ({ ...s, exchangeCode: e.target.value }))}
              >
                <option value="NFO">NFO</option>
                <option value="BFO">BFO</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Underlying</span>
              <select
                value={state.underlying}
                onChange={(e) => setState((s) => ({ ...s, underlying: e.target.value }))}
              >
                {UNDERLYINGS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </label>
            <label className="toolbar-field">
              <span>Expiry</span>
              <select
                value={state.expiry}
                onChange={(e) => setState((s) => ({ ...s, expiry: e.target.value }))}
                disabled={state.loadingExpiries || !state.expiries.length}
              >
                {state.expiries.map((ex) => (
                  <option key={ex} value={ex}>
                    {ex}
                  </option>
                ))}
              </select>
            </label>
            <label className="toolbar-field strategy-name-field">
              <span>Strategy name</span>
              <input
                type="text"
                placeholder="e.g. Bear Call Spread"
                value={state.name}
                onChange={(e) => setState((s) => ({ ...s, name: e.target.value }))}
                maxLength={128}
              />
            </label>
          </div>
        </div>

        <div className="section-header" style={{ marginTop: "24px" }}>
          <div>
            <p className="section-kicker">Step 2</p>
            <h3>Add legs</h3>
          </div>
          <span className="section-pill">{state.legs.length} / 8</span>
        </div>

        <div className="route-toolbar">
          <div className="toolbar-group">
            <label className="toolbar-field">
              <span>Action</span>
              <select value={draft.action} onChange={(e) => setDraft((d) => ({ ...d, action: e.target.value }))}>
                <option value="sell">Sell</option>
                <option value="buy">Buy</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Right</span>
              <select value={draft.right} onChange={(e) => setDraft((d) => ({ ...d, right: e.target.value }))}>
                <option value="call">Call</option>
                <option value="put">Put</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Strike</span>
              <input
                type="number"
                placeholder="23300"
                value={draft.strike}
                onChange={(e) => setDraft((d) => ({ ...d, strike: e.target.value }))}
                min="0"
                step="50"
              />
            </label>
            <label className="toolbar-field">
              <span>Qty</span>
              <input
                type="number"
                placeholder="1"
                value={draft.quantity}
                onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))}
                min="1"
                step="1"
              />
            </label>
            <label className="toolbar-field">
              <span>Premium</span>
              <input
                type="number"
                placeholder="100"
                value={draft.premium}
                onChange={(e) => setDraft((d) => ({ ...d, premium: e.target.value }))}
                min="0"
                step="0.05"
              />
            </label>
          </div>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={addLeg} disabled={state.legs.length >= 8}>
              Add Leg
            </button>
          </div>
        </div>

        {state.legs.length > 0 && (
          <div className="table-wrap" style={{ marginTop: "12px" }}>
            <table className="data-table strategy-leg-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Action</th>
                  <th>Right</th>
                  <th className="numeric">Strike</th>
                  <th className="numeric">Qty</th>
                  <th className="numeric">Premium</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {state.legs.map((leg, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td>
                      <span className={`leg-action-badge ${leg.action === "buy" ? "leg-buy" : "leg-sell"}`}>
                        {leg.action.toUpperCase()}
                      </span>
                    </td>
                    <td className={leg.right === "call" ? "tone-positive" : "tone-negative"}>
                      {leg.right.toUpperCase()}
                    </td>
                    <td className="numeric">{fmt(leg.strike, 0)}</td>
                    <td className="numeric">{leg.quantity}</td>
                    <td className="numeric">{fmt(leg.premium)}</td>
                    <td>
                      <button type="button" className="leg-remove-btn" onClick={() => removeLeg(i)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {state.error && (
          <div className="option-chain-error-card" style={{ marginTop: "12px" }}>
            <p className="metric-label">Error</p>
            <p className="panel-message">{state.error}</p>
          </div>
        )}

        {state.saveMessage && (
          <p className="panel-message" style={{ marginTop: "12px", color: "var(--positive)" }}>
            {state.saveMessage}
          </p>
        )}

        <div className="strategy-action-row">
          <button
            type="button"
            className="toolbar-button"
            onClick={() => void previewPayoff()}
            disabled={!state.legs.length || state.computingPayoff}
          >
            {state.computingPayoff ? "Computing..." : "Preview Payoff"}
          </button>
          <button
            type="button"
            className="toolbar-button toolbar-button-primary"
            onClick={() => void saveStrategy()}
            disabled={!state.legs.length || state.saving}
          >
            {state.saving ? "Saving..." : "Save Strategy"}
          </button>
        </div>

        {state.payoff && (
          <div style={{ marginTop: "24px" }}>
            <div className="section-header">
              <div>
                <p className="section-kicker">Step 3</p>
                <h3>Payoff preview</h3>
              </div>
            </div>

            <div className="stats-grid option-chain-summary-grid" style={{ marginBottom: "16px" }}>
              <article className="stat-card">
                <p className="metric-label">Net Premium</p>
                <strong
                  className={`metric-value ${state.payoff.net_premium >= 0 ? "tone-positive" : "tone-negative"}`}
                >
                  {fmt(state.payoff.net_premium)}
                </strong>
                <p className="metric-meta">{state.payoff.net_premium >= 0 ? "Credit received" : "Debit paid"}</p>
              </article>
              <article className="stat-card">
                <p className="metric-label">Max Profit</p>
                <strong className="metric-value tone-positive">{fmt(state.payoff.max_profit)}</strong>
                <p className="metric-meta">per lot</p>
              </article>
              <article className="stat-card">
                <p className="metric-label">Max Loss</p>
                <strong className="metric-value tone-negative">{fmt(state.payoff.max_loss)}</strong>
                <p className="metric-meta">per lot</p>
              </article>
              <article className="stat-card">
                <p className="metric-label">Breakeven(s)</p>
                <strong className="metric-value tone-neutral">
                  {state.payoff.breakevens.length
                    ? state.payoff.breakevens.map((b) => fmt(b, 0)).join(", ")
                    : "n/a"}
                </strong>
                <p className="metric-meta">spot price</p>
              </article>
            </div>

            <PayoffChart payoff={state.payoff} uid={payoffUid} />
          </div>
        )}
      </article>
    </section>
  );
}
