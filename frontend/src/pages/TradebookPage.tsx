import { useEffect, useState } from "react";

import { getTrades, type TradeRecord, type TradesResponse } from "../lib/api";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";

type TradebookState = {
  data: TradesResponse | null;
  loading: boolean;
  error: string | null;
};

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
}

function exportCsv(rows: TradeRecord[]) {
  const headers = ["Trade ID", "Order ID", "Symbol", "Exchange", "Product", "Action", "Qty", "Price", "Trade Time"];
  const csvRows = rows.map((trade) => [
    trade.trade_id,
    trade.order_id,
    trade.symbol,
    trade.exchange_code,
    trade.product_type,
    trade.action,
    trade.quantity ?? "",
    trade.price ?? "",
    trade.trade_time,
  ]);
  const content = [headers, ...csvRows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, "\"\"")}"`).join(",")).join("\n");
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "aptrades-tradebook.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

export function TradebookPage() {
  const [exchange, setExchange] = useState("NFO");
  const [actionFilter, setActionFilter] = useState("");
  const [state, setState] = useState<TradebookState>({ data: null, loading: true, error: null });

  const load = async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await getTrades({ exchange, action: actionFilter || undefined });
      setState({ data, loading: false, error: null });
    } catch (error) {
      setState({
        data: null,
        loading: false,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  };

  useEffect(() => {
    void load();
  }, [exchange, actionFilter]);

  const trades = state.data?.trades ?? [];

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Broker trades</p>
          <h3>Compact tradebook</h3>
          <p className="panel-message">Track normalized Breeze trades, apply quick filters, and export the visible book.</p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="route-toolbar">
          <div className="toolbar-group">
            <label className="toolbar-field">
              <span>Exchange</span>
              <select value={exchange} onChange={(event) => setExchange(event.target.value)}>
                <option value="NFO">NFO</option>
                <option value="NSE">NSE</option>
                <option value="BFO">BFO</option>
                <option value="BSE">BSE</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Action</span>
              <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)}>
                <option value="">All</option>
                <option value="BUY">Buy</option>
                <option value="SELL">Sell</option>
              </select>
            </label>
          </div>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={() => void load()}>
              Refresh
            </button>
            <button type="button" className="toolbar-button" onClick={() => exportCsv(trades)} disabled={!trades.length}>
              Export CSV
            </button>
          </div>
        </div>

        <div className="stats-grid stats-grid-trades">
          <article className="stat-card">
            <p className="metric-label">Total trades</p>
            <strong className="metric-value">{state.data?.stats.total ?? 0}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">Buy trades</p>
            <strong className="metric-value">{state.data?.stats.buy ?? 0}</strong>
          </article>
          <article className="stat-card">
            <p className="metric-label">Sell trades</p>
            <strong className="metric-value">{state.data?.stats.sell ?? 0}</strong>
          </article>
        </div>

        {state.error ? <ErrorState title="Trades unavailable" message={state.error} onRetry={() => void load()} /> : null}
        {state.loading ? <p className="panel-message">Loading tradebook...</p> : null}
        {!state.loading && !state.error && !trades.length ? (
          <EmptyState title="No trades" message="No trades returned for this filter window." />
        ) : null}

        {!state.loading && !state.error && trades.length ? (
          <div className="table-wrap">
            <table className="data-table data-table-trades">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Trade ID</th>
                  <th>Order ID</th>
                  <th>Action</th>
                  <th className="numeric">Qty</th>
                  <th className="numeric">Price</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => (
                  <tr key={`${trade.trade_id}-${trade.order_id}`}>
                    <td>
                      <div className="table-symbol">
                        <strong>{trade.symbol}</strong>
                        <span>{trade.exchange_code} · {trade.product_type}</span>
                      </div>
                    </td>
                    <td>{trade.trade_id || "n/a"}</td>
                    <td>{trade.order_id || "n/a"}</td>
                    <td>{trade.action}</td>
                    <td className="numeric">{formatNumber(trade.quantity, 0)}</td>
                    <td className="numeric">{formatNumber(trade.price)}</td>
                    <td>{trade.trade_time || "n/a"}</td>
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
