import { useEffect, useMemo, useState } from "react";

import {
  cancelAllOrders,
  cancelOrder,
  getOrders,
  type OrderRecord,
  type OrdersResponse,
} from "../lib/api";

type OrderbookState = {
  data: OrdersResponse | null;
  loading: boolean;
  error: string | null;
  actionMessage: string | null;
};

function exportCsv(rows: OrderRecord[]) {
  const headers = ["Order ID", "Symbol", "Exchange", "Product", "Action", "Status", "Qty", "Pending", "Filled", "Limit", "Avg", "Type", "Validity", "Created"];
  const csvRows = rows.map((order) => [
    order.order_id,
    order.symbol,
    order.exchange_code,
    order.product_type,
    order.action,
    order.status,
    order.quantity ?? "",
    order.pending_quantity ?? "",
    order.filled_quantity ?? "",
    order.limit_price ?? "",
    order.average_price ?? "",
    order.order_type,
    order.validity,
    order.created_at,
  ]);
  const content = [headers, ...csvRows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, "\"\"")}"`).join(",")).join("\n");
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "aptrades-orderbook.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
}

function statItems(data: OrdersResponse | null) {
  return [
    { label: "Total", value: data?.stats.total ?? 0 },
    { label: "Completed", value: data?.stats.completed ?? 0 },
    { label: "Open", value: data?.stats.open ?? 0 },
    { label: "Rejected", value: data?.stats.rejected ?? 0 },
    { label: "Cancelled", value: data?.stats.cancelled ?? 0 },
  ];
}

export function OrderbookPage() {
  const [exchange, setExchange] = useState("NFO");
  const [statusFilter, setStatusFilter] = useState("");
  const [state, setState] = useState<OrderbookState>({ data: null, loading: true, error: null, actionMessage: null });

  const load = async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await getOrders({ exchange, status: statusFilter || undefined });
      setState((current) => ({ ...current, data, loading: false, error: null }));
    } catch (error) {
      setState((current) => ({
        ...current,
        data: null,
        loading: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  };

  useEffect(() => {
    void load();
  }, [exchange, statusFilter]);

  const orders = useMemo(() => state.data?.orders ?? [], [state.data]);

  const handleCancel = async (order: OrderRecord) => {
    try {
      const response = await cancelOrder(order.order_id, order.exchange_code);
      setState((current) => ({ ...current, actionMessage: `Cancel requested for order ${response.order_id}.` }));
      await load();
    } catch (error) {
      setState((current) => ({
        ...current,
        actionMessage: error instanceof Error ? error.message : "Unable to cancel order.",
      }));
    }
  };

  const handleCancelAll = async () => {
    try {
      const response = await cancelAllOrders(exchange);
      setState((current) => ({
        ...current,
        actionMessage: `Cancel-all processed: ${response.cancelled_count}/${response.requested} requests sent.`,
      }));
      await load();
    } catch (error) {
      setState((current) => ({
        ...current,
        actionMessage: error instanceof Error ? error.message : "Unable to cancel all orders.",
      }));
    }
  };

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Broker orders</p>
          <h3>Compact orderbook</h3>
          <p className="panel-message">Review live Breeze orders, filter by state, and export the current book.</p>
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
              <span>Status</span>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="">All</option>
                <option value="open">Open</option>
                <option value="completed">Completed</option>
                <option value="rejected">Rejected</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>
          </div>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={() => void load()}>
              Refresh
            </button>
            <button type="button" className="toolbar-button" onClick={() => exportCsv(orders)} disabled={!orders.length}>
              Export
            </button>
            <button type="button" className="toolbar-button toolbar-button-danger" onClick={() => void handleCancelAll()}>
              Cancel All
            </button>
          </div>
        </div>

        <div className="tab-strip">
          <span className="tab-chip tab-chip-active">Orders</span>
          <span className="tab-chip">GTT unavailable</span>
        </div>

        <div className="stats-grid stats-grid-orders">
          {statItems(state.data).map((item) => (
            <article key={item.label} className="stat-card">
              <p className="metric-label">{item.label}</p>
              <strong className="metric-value">{item.value}</strong>
            </article>
          ))}
        </div>

        {state.actionMessage ? <p className="panel-message">{state.actionMessage}</p> : null}
        {state.error ? <p className="panel-message panel-error">Orders unavailable: {state.error}</p> : null}
        {state.loading ? <p className="panel-message">Loading orderbook...</p> : null}
        {!state.loading && !state.error && !orders.length ? <p className="panel-message">No orders returned for this filter window.</p> : null}

        {!state.loading && !state.error && orders.length ? (
          <div className="table-wrap">
            <table className="data-table data-table-orders">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Status</th>
                  <th>Action</th>
                  <th className="numeric">Qty</th>
                  <th className="numeric">Pending</th>
                  <th className="numeric">Filled</th>
                  <th className="numeric">Limit</th>
                  <th className="numeric">Avg</th>
                  <th>Type</th>
                  <th>Created</th>
                  <th>Control</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={`${order.order_id}-${order.symbol}`}>
                    <td>
                      <div className="table-symbol">
                        <strong>{order.symbol}</strong>
                        <span>{order.exchange_code} · {order.product_type}</span>
                      </div>
                    </td>
                    <td>{order.status}</td>
                    <td>{order.action}</td>
                    <td className="numeric">{formatNumber(order.quantity, 0)}</td>
                    <td className="numeric">{formatNumber(order.pending_quantity, 0)}</td>
                    <td className="numeric">{formatNumber(order.filled_quantity, 0)}</td>
                    <td className="numeric">{formatNumber(order.limit_price)}</td>
                    <td className="numeric">{formatNumber(order.average_price)}</td>
                    <td>{order.order_type || order.validity || "n/a"}</td>
                    <td>{order.created_at || "n/a"}</td>
                    <td>
                      <button
                        type="button"
                        className="row-action"
                        onClick={() => void handleCancel(order)}
                        disabled={!(order.status_normalized === "open" || order.status_normalized === "pending" || order.status_normalized === "ordered")}
                      >
                        Cancel
                      </button>
                    </td>
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
