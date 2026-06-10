import { useEffect, useMemo, useState } from "react";

import { getPositions, type PositionRecord, type PositionsResponse } from "../lib/api";
import { useLiveMarketData, useLiveSubscribe } from "../hooks/useLiveMarketData";
import type { LiveTick, SubscriptionRequest } from "../lib/realtime";

function applyLiveTick(position: PositionRecord, tick: LiveTick | undefined): PositionRecord {
  if (!tick || tick.ltp === null || tick.ltp === undefined) {
    return position;
  }
  const ltp = tick.ltp;
  let pnl = position.pnl;
  let pnlPercent = position.pnl_percent;
  if (position.average_price !== null && position.average_price !== undefined) {
    pnl = Number(((ltp - position.average_price) * position.quantity).toFixed(2));
    const base = Math.abs(position.quantity) * position.average_price;
    pnlPercent = base ? Number(((pnl / base) * 100).toFixed(2)) : position.pnl_percent;
  }
  return { ...position, ltp, pnl, pnl_percent: pnlPercent };
}

type PositionsState = {
  data: PositionsResponse | null;
  loading: boolean;
  error: string | null;
};

type GroupBy = "none" | "exchange" | "product" | "direction";
type DirectionFilter = "all" | "long" | "short";

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
}

function exportCsv(rows: PositionRecord[]) {
  const headers = ["Symbol", "Broker Symbol", "Exchange", "Product", "Direction", "Qty", "Avg", "LTP", "P&L", "P&L%", "Expiry", "Quote Status", "Source"];
  const csvRows = rows.map((position) => [
    position.symbol,
    position.broker_symbol,
    position.exchange_code,
    position.product_type,
    position.direction,
    position.quantity,
    position.average_price ?? "",
    position.ltp ?? "",
    position.pnl ?? "",
    position.pnl_percent ?? "",
    position.expiry_date ?? "",
    position.quote_status,
    position.resolution_source ?? "",
  ]);
  const content = [headers, ...csvRows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, "\"\"")}"`).join(",")).join("\n");
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "aptrades-positions.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

export function PositionsPage() {
  const [state, setState] = useState<PositionsState>({ data: null, loading: true, error: null });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [productFilter, setProductFilter] = useState("all");
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>("all");
  const [exchangeFilter, setExchangeFilter] = useState("all");

  const load = async () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await getPositions();
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
  }, []);

  const { ticks, connectionState } = useLiveMarketData();

  const subscriptions = useMemo<SubscriptionRequest[]>(
    () =>
      (state.data?.positions ?? [])
        .filter((position) => position.exchange_code)
        .map((position) => ({
          symbol: position.symbol,
          exchange: position.exchange_code,
          product_type: position.product_type,
        })),
    [state.data],
  );
  useLiveSubscribe(subscriptions);

  const positions = useMemo(() => {
    const rows = state.data?.positions ?? [];
    return rows
      .filter((position) => {
        if (productFilter !== "all" && position.product_type !== productFilter) {
          return false;
        }
        if (directionFilter !== "all" && position.direction !== directionFilter) {
          return false;
        }
        if (exchangeFilter !== "all" && position.exchange_code !== exchangeFilter) {
          return false;
        }
        return true;
      })
      .map((position) => applyLiveTick(position, ticks[position.symbol.toUpperCase()]));
  }, [directionFilter, exchangeFilter, productFilter, state.data, ticks]);

  const stats = useMemo(() => {
    const openPositions = positions.length;
    const longPositions = positions.filter((position) => position.quantity > 0).length;
    const shortPositions = positions.filter((position) => position.quantity < 0).length;
    const totalPnl = positions.reduce((sum, position) => sum + (position.pnl ?? 0), 0);
    return [
      { label: "Open positions", value: openPositions, tone: "neutral" },
      { label: "Long", value: longPositions, tone: "neutral" },
      { label: "Short", value: shortPositions, tone: "neutral" },
      { label: "Total P&L", value: formatNumber(totalPnl), tone: totalPnl > 0 ? "positive" : totalPnl < 0 ? "negative" : "neutral" },
    ];
  }, [positions]);

  const groups = useMemo(() => {
    if (groupBy === "none") {
      return [{ key: "all", label: "All positions", items: positions }];
    }

    const mapped = new Map<string, PositionRecord[]>();
    for (const position of positions) {
      const key =
        groupBy === "exchange"
          ? position.exchange_code
          : groupBy === "product"
            ? position.product_type
            : position.direction;
      const current = mapped.get(key) ?? [];
      current.push(position);
      mapped.set(key, current);
    }

    return Array.from(mapped.entries()).map(([key, items]) => ({
      key,
      label: key,
      items,
    }));
  }, [groupBy, positions]);

  const quoteBadge = state.data?.status === "ok" ? "Live" : "Paused";
  const liveFeedMessage =
    connectionState === "live"
      ? "Streaming live LTP and P&L over the Breeze websocket."
      : connectionState === "connecting"
        ? "Connecting to the live websocket feed; showing REST values until ticks arrive."
        : "Live websocket feed is unavailable; showing REST quote values.";
  const quoteMessage =
    state.data?.status === "not_configured"
      ? "Breeze positions are not configured yet."
      : state.data?.quote_status === "partial"
        ? `Some rows are using raw Breeze position values because quote enrichment failed. ${liveFeedMessage}`
        : `Live quote enrichment is active. ${liveFeedMessage}`;

  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Broker positions</p>
          <h3>Main positions page</h3>
          <p className="panel-message">Track live Breeze positions with quote-enriched P&L and export the current view.</p>
        </div>
        <span className={`section-pill ${quoteBadge === "Live" ? "status-live" : "status-paused"}`}>{quoteBadge}</span>
      </div>

      <article className="panel route-panel">
        <div className="route-toolbar">
          <div className="toolbar-group">
            <button type="button" className="toolbar-button" onClick={() => setSettingsOpen((current) => !current)}>
              Settings
            </button>
          </div>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={() => void load()}>
              Refresh
            </button>
            <button type="button" className="toolbar-button" onClick={() => exportCsv(positions)} disabled={!positions.length}>
              Export
            </button>
            <button type="button" className="toolbar-button toolbar-button-danger" disabled>
              Close All
            </button>
          </div>
        </div>

        {settingsOpen ? (
          <div className="settings-panel">
            <label className="toolbar-field">
              <span>Grouping</span>
              <select value={groupBy} onChange={(event) => setGroupBy(event.target.value as GroupBy)}>
                <option value="none">None</option>
                <option value="exchange">Exchange</option>
                <option value="product">Product</option>
                <option value="direction">Direction</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Product</span>
              <select value={productFilter} onChange={(event) => setProductFilter(event.target.value)}>
                <option value="all">All</option>
                <option value="cash">Cash</option>
                <option value="futures">Futures</option>
                <option value="options">Options</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Direction</span>
              <select value={directionFilter} onChange={(event) => setDirectionFilter(event.target.value as DirectionFilter)}>
                <option value="all">All</option>
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </label>
            <label className="toolbar-field">
              <span>Exchange</span>
              <select value={exchangeFilter} onChange={(event) => setExchangeFilter(event.target.value)}>
                <option value="all">All</option>
                <option value="NFO">NFO</option>
                <option value="NSE">NSE</option>
                <option value="BFO">BFO</option>
                <option value="BSE">BSE</option>
              </select>
            </label>
          </div>
        ) : null}

        <div className="stats-grid stats-grid-positions">
          {stats.map((item) => (
            <article key={item.label} className="stat-card">
              <p className="metric-label">{item.label}</p>
              <strong className={`metric-value tone-${item.tone}`}>{item.value}</strong>
            </article>
          ))}
        </div>

        <p className="panel-message">{quoteMessage}</p>
        {state.error ? <p className="panel-message panel-error">Positions unavailable: {state.error}</p> : null}
        {state.loading ? <p className="panel-message">Loading positions...</p> : null}
        {!state.loading && !state.error && !positions.length ? <p className="panel-message">No open positions returned for this filtered view.</p> : null}

        {!state.loading && !state.error && positions.length ? (
          <div className="table-wrap">
            <table className="data-table data-table-positions">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Exchange</th>
                  <th>Product</th>
                  <th className="numeric">Qty</th>
                  <th className="numeric">Avg</th>
                  <th className="numeric">LTP</th>
                  <th className="numeric">P&amp;L</th>
                  <th className="numeric">P&amp;L%</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => (
                  group.items.flatMap((position, index) => {
                    const groupHeader =
                      groupBy !== "none" && index === 0 ? (
                        <tr key={`${group.key}-header`} className="group-row">
                          <td colSpan={9}>{group.label}</td>
                        </tr>
                      ) : null;

                    const dataRow = (
                      <tr key={`${group.key}-${position.symbol}-${position.exchange_code}-${position.product_type}-${index}`}>
                        <td>
                          <div className="table-symbol">
                            <strong>{position.symbol}</strong>
                            <span>
                              {position.broker_symbol}
                              {position.token ? ` · token ${position.token}` : ""}
                            </span>
                          </div>
                        </td>
                        <td>{position.exchange_code}</td>
                        <td>{position.product_type}</td>
                        <td className="numeric">{formatNumber(position.quantity, 0)}</td>
                        <td className="numeric">{formatNumber(position.average_price)}</td>
                        <td className={`numeric ${ticks[position.symbol.toUpperCase()] ? "cell-live" : ""}`}>{formatNumber(position.ltp)}</td>
                        <td className={`numeric ${(position.pnl ?? 0) > 0 ? "tone-positive" : (position.pnl ?? 0) < 0 ? "tone-negative" : "tone-neutral"}`}>
                          {formatNumber(position.pnl)}
                        </td>
                        <td className={`numeric ${(position.pnl_percent ?? 0) > 0 ? "tone-positive" : (position.pnl_percent ?? 0) < 0 ? "tone-negative" : "tone-neutral"}`}>
                          {position.pnl_percent === null ? "n/a" : `${formatNumber(position.pnl_percent)}%`}
                        </td>
                        <td>
                          <button type="button" className="row-action" disabled>
                            Close
                          </button>
                        </td>
                      </tr>
                    );

                    return groupHeader ? [groupHeader, dataRow] : [dataRow];
                  })
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </article>
    </section>
  );
}
