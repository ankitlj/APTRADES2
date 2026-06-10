import { useEffect, useMemo, useState } from "react";

import {
  getDashboardAlerts,
  getDashboardChart,
  getDashboardSummary,
  type DashboardAlertsResponse,
  type DashboardChartPoint,
  type DashboardChartResponse,
  type DashboardPosition,
  type DashboardSummaryResponse,
} from "../lib/api";
import { useLiveMarketData, useLiveSubscribe } from "../hooks/useLiveMarketData";
import type { LiveTick, SubscriptionRequest } from "../lib/realtime";

type AsyncState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

function createInitialState<T>(): AsyncState<T> {
  return { data: null, loading: true, error: null };
}

function formatNumber(value: number | string | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return String(value);
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(numeric);
}

function formatSignedNumber(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "Flat";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatNumber(value)}`;
}

function metricValue(metric: DashboardSummaryResponse["metrics"][number]) {
  if (metric.key === "open_positions") {
    return formatNumber(metric.value, 0);
  }
  return formatNumber(metric.value);
}

function metricChangeText(metric: DashboardSummaryResponse["metrics"][number]) {
  if (metric.key === "open_positions") {
    return metric.meta;
  }
  if (metric.key === "total_pnl") {
    return metric.meta;
  }
  if (metric.change === null || metric.change === undefined) {
    return metric.meta;
  }
  return `${formatSignedNumber(metric.change)} vs prev close`;
}

function toneClassName(tone: string) {
  if (tone === "positive") {
    return "tone-positive";
  }
  if (tone === "negative") {
    return "tone-negative";
  }
  return "tone-neutral";
}

function alertClassName(level: string) {
  if (level === "success") {
    return "alert-card alert-success";
  }
  if (level === "warning") {
    return "alert-card alert-warning";
  }
  if (level === "error") {
    return "alert-card alert-error";
  }
  return "alert-card alert-info";
}

function chartPath(points: DashboardChartPoint[]) {
  const closes = points.map((point) => point.close ?? 0);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const width = 720;
  const height = 280;
  return points
    .map((point, index) => {
      const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
      const close = point.close ?? min;
      const y = max === min ? height / 2 : height - ((close - min) / (max - min)) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function ChartPanel({ state }: { state: AsyncState<DashboardChartResponse> }) {
  if (state.error) {
    return <p className="panel-message panel-error">Chart unavailable: {state.error}</p>;
  }
  if (state.loading) {
    return <p className="panel-message">Loading chart data...</p>;
  }
  const points = state.data?.points ?? [];
  if (!points.length) {
    return <p className="panel-message">No chart candles returned for this symbol yet.</p>;
  }

  const latest = points[points.length - 1];
  const earliest = points[0];
  return (
    <div className="chart-panel">
      <div className="chart-meta">
        <div>
          <p className="section-kicker">{state.data?.resolved.display_symbol}</p>
          <strong>{formatNumber(latest.close)}</strong>
        </div>
        <div>
          <p className="section-kicker">Range</p>
          <strong>
            {earliest.time?.slice(0, 10)} to {latest.time?.slice(0, 10)}
          </strong>
        </div>
      </div>
      <svg className="chart-svg" viewBox="0 0 720 280" role="img" aria-label="Historical price chart">
        <defs>
          <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(14, 116, 144, 0.28)" />
            <stop offset="100%" stopColor="rgba(14, 116, 144, 0)" />
          </linearGradient>
        </defs>
        <path d={`${chartPath(points)} L 720 280 L 0 280 Z`} fill="url(#chartFill)" />
        <path d={chartPath(points)} fill="none" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <div className="chart-axis">
        <span>{earliest.time?.slice(0, 10)}</span>
        <span>{latest.time?.slice(0, 10)}</span>
      </div>
    </div>
  );
}

function applyLiveTick(position: DashboardPosition, tick: LiveTick | undefined): DashboardPosition {
  if (!tick || tick.ltp === null || tick.ltp === undefined) {
    return position;
  }
  const ltp = tick.ltp;
  const pnl =
    position.average_price !== null && position.average_price !== undefined
      ? Number(((ltp - position.average_price) * position.quantity).toFixed(2))
      : position.pnl;
  return { ...position, ltp, pnl };
}

function PositionsTable({
  positions,
  status,
  error,
}: {
  positions: DashboardPosition[];
  status: string | undefined;
  error: string | null | undefined;
}) {
  const { ticks } = useLiveMarketData();

  if (error) {
    return <p className="panel-message panel-error">Positions unavailable: {error}</p>;
  }
  if (!positions.length) {
    return (
      <p className="panel-message">
        {status === "not_configured"
          ? "Breeze positions are not configured yet."
          : "No active positions returned by Breeze right now."}
      </p>
    );
  }

  return (
    <div className="table-wrap">
      <table className="positions-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Exchange</th>
            <th>Product</th>
            <th className="numeric">Qty</th>
            <th className="numeric">Avg</th>
            <th className="numeric">LTP</th>
            <th className="numeric">P&amp;L</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((rawPosition) => {
            const position = applyLiveTick(rawPosition, ticks[rawPosition.symbol.toUpperCase()]);
            const isLive = Boolean(ticks[rawPosition.symbol.toUpperCase()]);
            return (
              <tr key={`${position.symbol}-${position.exchange_code}-${position.product_type}`}>
                <td>
                  <div className="table-symbol">
                    <strong>{position.symbol}</strong>
                    <span>{position.broker_symbol}</span>
                  </div>
                </td>
                <td>{position.exchange_code}</td>
                <td>{position.product_type}</td>
                <td className="numeric">{formatNumber(position.quantity, 0)}</td>
                <td className="numeric">{formatNumber(position.average_price)}</td>
                <td className={`numeric ${isLive ? "cell-live" : ""}`}>{formatNumber(position.ltp)}</td>
                <td className={`numeric ${toneClassName((position.pnl ?? 0) > 0 ? "positive" : (position.pnl ?? 0) < 0 ? "negative" : "neutral")}`}>
                  {formatNumber(position.pnl)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function DashboardPage() {
  const [summaryState, setSummaryState] = useState<AsyncState<DashboardSummaryResponse>>(createInitialState);
  const [alertsState, setAlertsState] = useState<AsyncState<DashboardAlertsResponse>>(createInitialState);
  const [chartState, setChartState] = useState<AsyncState<DashboardChartResponse>>(createInitialState);

  const positionSubscriptions = useMemo<SubscriptionRequest[]>(
    () =>
      (summaryState.data?.positions ?? [])
        .filter((position) => position.exchange_code)
        .map((position) => ({
          symbol: position.symbol,
          exchange: position.exchange_code,
          product_type: position.product_type,
        })),
    [summaryState.data],
  );
  useLiveSubscribe(positionSubscriptions);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      const [summaryResult, alertsResult, chartResult] = await Promise.allSettled([
        getDashboardSummary(),
        getDashboardAlerts(),
        getDashboardChart("NIFTY"),
      ]);
      if (!isMounted) {
        return;
      }

      setSummaryState(
        summaryResult.status === "fulfilled"
          ? { data: summaryResult.value, loading: false, error: null }
          : {
              data: null,
              loading: false,
              error: summaryResult.reason instanceof Error ? summaryResult.reason.message : "Unknown error",
            },
      );
      setAlertsState(
        alertsResult.status === "fulfilled"
          ? { data: alertsResult.value, loading: false, error: null }
          : {
              data: null,
              loading: false,
              error: alertsResult.reason instanceof Error ? alertsResult.reason.message : "Unknown error",
            },
      );
      setChartState(
        chartResult.status === "fulfilled"
          ? { data: chartResult.value, loading: false, error: null }
          : {
              data: null,
              loading: false,
              error: chartResult.reason instanceof Error ? chartResult.reason.message : "Unknown error",
            },
      );
    }

    void load();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section className="dashboard-page">
      <div className="metrics-grid">
        {(summaryState.data?.metrics ?? Array.from({ length: 4 })).map((metric, index) => (
          <article key={metric?.key ?? `loading-${index}`} className="metric-card">
            <p className="metric-label">{metric?.label ?? "Loading metric"}</p>
            <strong className={`metric-value ${toneClassName(metric?.tone ?? "neutral")}`}>{metric ? metricValue(metric) : "..."}</strong>
            <p className="metric-meta">{metric ? metricChangeText(metric) : "Syncing dashboard summary..."}</p>
            {metric?.expiry_date ? <span className="metric-footnote">Expiry {metric.expiry_date}</span> : null}
          </article>
        ))}
      </div>

      <div className="dashboard-split">
        <article className="panel chart-card">
          <div className="section-header">
            <div>
              <p className="section-kicker">Chart panel</p>
              <h3>NIFTY market structure</h3>
            </div>
            <span className="section-pill">{chartState.loading ? "Loading" : chartState.data?.interval ?? "1day"}</span>
          </div>
          <ChartPanel state={chartState} />
        </article>

        <article className="panel alerts-card">
          <div className="section-header">
            <div>
              <p className="section-kicker">Alerts</p>
              <h3>Operational watchlist</h3>
            </div>
            <span className="section-pill">{alertsState.loading ? "Syncing" : `${alertsState.data?.alerts.length ?? 0} items`}</span>
          </div>
          {alertsState.error ? (
            <p className="panel-message panel-error">Alerts unavailable: {alertsState.error}</p>
          ) : (
            <div className="alerts-stack">
              {(alertsState.data?.alerts ?? []).map((alert) => (
                <article key={`${alert.level}-${alert.title}`} className={alertClassName(alert.level)}>
                  <p>{alert.level}</p>
                  <strong>{alert.title}</strong>
                  <span>{alert.message}</span>
                </article>
              ))}
            </div>
          )}
        </article>
      </div>

      <article className="panel positions-card">
        <div className="section-header">
          <div>
            <p className="section-kicker">Active positions</p>
            <h3>Live Breeze positions snapshot</h3>
          </div>
          <span className="section-pill">
            {summaryState.loading ? "Loading" : `${summaryState.data?.positions.length ?? 0} rows`}
          </span>
        </div>
        <PositionsTable
          positions={summaryState.data?.positions ?? []}
          status={summaryState.data?.positions_status}
          error={summaryState.error ?? summaryState.data?.positions_error}
        />
      </article>
    </section>
  );
}
