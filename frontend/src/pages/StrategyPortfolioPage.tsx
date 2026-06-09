import { useEffect, useState } from "react";

import { PayoffChart } from "../components/PayoffChart";
import {
  deleteStrategy,
  getStrategies,
  getStrategyPayoff,
  type PayoffResponse,
  type StrategyLeg,
  type StrategyRecord,
} from "../lib/api";

type PortfolioState = {
  strategies: StrategyRecord[];
  loading: boolean;
  error: string | null;
};

type PayoffEntry = {
  data: PayoffResponse | null;
  loading: boolean;
  error: string | null;
};

function fmt(v: number | null, dec = 2): string {
  if (v === null || v === undefined) return "n/a";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: dec }).format(v);
}

function LegTag({ leg }: { leg: StrategyLeg }) {
  const actionClass = leg.action === "buy" ? "leg-tag-buy" : "leg-tag-sell";
  const rightClass = leg.right === "call" ? "leg-tag-call" : "leg-tag-put";
  return (
    <span className={`strategy-leg-tag ${actionClass} ${rightClass}`}>
      {leg.action.toUpperCase()} {leg.quantity}x {fmt(leg.strike, 0)} {leg.right.toUpperCase()} @{leg.premium}
    </span>
  );
}

export function StrategyPortfolioPage() {
  const [state, setState] = useState<PortfolioState>({
    strategies: [],
    loading: true,
    error: null,
  });
  const [payoffs, setPayoffs] = useState<Record<number, PayoffEntry>>({});
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());

  function loadStrategies() {
    setState((s) => ({ ...s, loading: true, error: null }));
    getStrategies()
      .then((payload) => {
        setState({ strategies: payload.strategies, loading: false, error: null });
      })
      .catch((err) => {
        setState({
          strategies: [],
          loading: false,
          error: err instanceof Error ? err.message : "Load failed.",
        });
      });
  }

  useEffect(() => {
    loadStrategies();
  }, []);

  async function handleDelete(id: number) {
    setDeletingIds((s) => new Set(s).add(id));
    try {
      await deleteStrategy(id);
      setState((s) => ({ ...s, strategies: s.strategies.filter((st) => st.id !== id) }));
      setPayoffs((p) => {
        const next = { ...p };
        delete next[id];
        return next;
      });
    } catch {
      // silently ignore — user can retry
    } finally {
      setDeletingIds((s) => {
        const next = new Set(s);
        next.delete(id);
        return next;
      });
    }
  }

  async function handleTogglePayoff(strategy: StrategyRecord) {
    if (payoffs[strategy.id]?.data) {
      setPayoffs((p) => {
        const next = { ...p };
        delete next[strategy.id];
        return next;
      });
      return;
    }
    setPayoffs((p) => ({ ...p, [strategy.id]: { data: null, loading: true, error: null } }));
    try {
      const payload = await getStrategyPayoff(strategy.legs);
      setPayoffs((p) => ({ ...p, [strategy.id]: { data: payload, loading: false, error: null } }));
    } catch (err) {
      setPayoffs((p) => ({
        ...p,
        [strategy.id]: {
          data: null,
          loading: false,
          error: err instanceof Error ? err.message : "Payoff failed.",
        },
      }));
    }
  }

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Strategy tools</p>
          <h3>Strategy Portfolio</h3>
          <p className="panel-message">
            Saved option strategies. View on-demand payoff diagrams or delete positions.
          </p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Saved strategies</p>
            <h3>Portfolio</h3>
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span className="section-pill">{state.strategies.length}</span>
            <button
              type="button"
              className="toolbar-button"
              onClick={loadStrategies}
              disabled={state.loading}
            >
              {state.loading ? "Loading..." : "Refresh"}
            </button>
          </div>
        </div>

        {state.error && (
          <div className="option-chain-error-card">
            <p className="metric-label">Error</p>
            <p className="panel-message">{state.error}</p>
          </div>
        )}

        {!state.loading && state.strategies.length === 0 && !state.error && (
          <p className="panel-message">
            No strategies saved yet. Use the Strategy Builder to create one.
          </p>
        )}

        {state.strategies.map((strategy) => {
          const entry = payoffs[strategy.id];
          const payoffUid = `portfolio-${strategy.id}`;
          return (
            <article key={strategy.id} className="strategy-portfolio-card">
              <div className="strategy-card-header">
                <div className="strategy-card-info">
                  <strong className="strategy-card-name">{strategy.name}</strong>
                  <span className="strategy-card-meta">
                    {strategy.underlying} &middot; {strategy.exchange_code} &middot; {strategy.expiry}
                  </span>
                </div>
                <div className="strategy-card-actions">
                  <span
                    className={`strategy-net-premium ${strategy.net_premium >= 0 ? "tone-positive" : "tone-negative"}`}
                  >
                    {strategy.net_premium >= 0 ? "CR" : "DR"} {fmt(Math.abs(strategy.net_premium))}
                  </span>
                  <button
                    type="button"
                    className="toolbar-button"
                    onClick={() => void handleTogglePayoff(strategy)}
                    disabled={entry?.loading}
                  >
                    {entry?.loading ? "Loading..." : entry?.data ? "Hide Payoff" : "View Payoff"}
                  </button>
                  <button
                    type="button"
                    className="leg-remove-btn"
                    onClick={() => void handleDelete(strategy.id)}
                    disabled={deletingIds.has(strategy.id)}
                  >
                    {deletingIds.has(strategy.id) ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>

              <div className="strategy-legs-row">
                {strategy.legs.map((leg, i) => (
                  <LegTag key={i} leg={leg} />
                ))}
              </div>

              {entry?.error && (
                <p className="panel-message" style={{ color: "var(--negative)", marginTop: "8px" }}>
                  {entry.error}
                </p>
              )}

              {entry?.data && (
                <div className="strategy-payoff-inline">
                  <div className="stats-grid option-chain-summary-grid" style={{ marginBottom: "12px" }}>
                    <article className="stat-card">
                      <p className="metric-label">Net Premium</p>
                      <strong
                        className={`metric-value ${entry.data.net_premium >= 0 ? "tone-positive" : "tone-negative"}`}
                      >
                        {fmt(entry.data.net_premium)}
                      </strong>
                      <p className="metric-meta">
                        {entry.data.net_premium >= 0 ? "Credit" : "Debit"}
                      </p>
                    </article>
                    <article className="stat-card">
                      <p className="metric-label">Max Profit</p>
                      <strong className="metric-value tone-positive">{fmt(entry.data.max_profit)}</strong>
                      <p className="metric-meta">per lot</p>
                    </article>
                    <article className="stat-card">
                      <p className="metric-label">Max Loss</p>
                      <strong className="metric-value tone-negative">{fmt(entry.data.max_loss)}</strong>
                      <p className="metric-meta">per lot</p>
                    </article>
                    <article className="stat-card">
                      <p className="metric-label">Breakeven(s)</p>
                      <strong className="metric-value tone-neutral">
                        {entry.data.breakevens.length
                          ? entry.data.breakevens.map((b) => fmt(b, 0)).join(", ")
                          : "n/a"}
                      </strong>
                      <p className="metric-meta">spot price</p>
                    </article>
                  </div>
                  <PayoffChart payoff={entry.data} uid={payoffUid} />
                </div>
              )}
            </article>
          );
        })}
      </article>
    </section>
  );
}
