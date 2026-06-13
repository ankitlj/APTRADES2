import {
  AlertTriangle,
  Bell,
  CircleAlert,
  Layers,
  type LucideIcon,
  Percent,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getDashboardAlerts,
  getDashboardSummary,
  type DashboardAlertsResponse,
  type DashboardMetric,
  type DashboardPosition,
  type DashboardSummaryResponse,
} from "@/lib/api";
import { useLiveMarketData, useLiveSubscribe } from "@/hooks/useLiveMarketData";
import type { LiveTick, SubscriptionRequest } from "@/lib/realtime";
import { DashboardMarketChart } from "@/components/dashboard/DashboardMarketChart";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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
  if (metric.key === "open_positions" || metric.key === "total_pnl") {
    return metric.meta;
  }
  if (metric.change === null || metric.change === undefined) {
    return metric.meta;
  }
  return `${formatSignedNumber(metric.change)} vs prev close`;
}

function toneColor(tone: string | undefined) {
  if (tone === "positive") return "text-green-600 dark:text-green-400";
  if (tone === "negative") return "text-red-500";
  return "text-foreground";
}

// Distinct topic icons per box position, used when a metric is still loading or
// its key is unmapped, so the four boxes never share the same icon.
const FALLBACK_METRIC_ICONS: LucideIcon[] = [TrendingUp, Layers, Percent, Wallet];

function metricIcon(key: string | undefined, index: number): LucideIcon {
  switch (key) {
    case "total_pnl":
    case "day_pnl":
      return TrendingUp;
    case "open_positions":
      return Layers;
    case "margin":
    case "margin_used":
    case "utilised_margin":
      return Wallet;
    case "monthly_roi":
    case "annual_roi":
    case "roi":
      return Percent;
    default:
      return FALLBACK_METRIC_ICONS[index % FALLBACK_METRIC_ICONS.length];
  }
}

function pnlColor(value: number | null | undefined) {
  if ((value ?? 0) > 0) return "text-green-600 dark:text-green-400";
  if ((value ?? 0) < 0) return "text-red-500";
  return "text-foreground";
}

function alertDotColor(level: string) {
  if (level === "error") return "bg-red-500";
  if (level === "warning") return "bg-amber-500";
  if (level === "success") return "bg-green-500";
  return "bg-blue-500";
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
}: {
  positions: DashboardPosition[];
  status: string | undefined;
}) {
  const { ticks } = useLiveMarketData();

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm">
        <thead>
          <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-3 font-medium">Symbol</th>
            <th className="px-4 py-3 font-medium">Exchange</th>
            <th className="px-4 py-3 font-medium">Product</th>
            <th className="px-4 py-3 text-right font-medium">Qty</th>
            <th className="px-4 py-3 text-right font-medium">Avg</th>
            <th className="px-4 py-3 text-right font-medium">LTP</th>
            <th className="px-4 py-3 text-right font-medium">P&amp;L</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {positions.length === 0 ? (
            <tr>
              <td
                colSpan={7}
                className="h-[206px] px-4 text-center text-sm text-muted-foreground"
              >
                {status === "not_configured"
                  ? "Breeze positions are not configured yet."
                  : "No active positions"}
              </td>
            </tr>
          ) : (
            positions.map((rawPosition) => {
              const position = applyLiveTick(
                rawPosition,
                ticks[rawPosition.symbol.toUpperCase()]
              );
              const isLive = Boolean(ticks[rawPosition.symbol.toUpperCase()]);
              return (
                <tr
                  key={`${position.symbol}-${position.exchange_code}-${position.product_type}`}
                  className="hover:bg-muted/20"
                >
                  <td className="px-4 py-3">
                    <div className="font-semibold">{position.symbol}</div>
                    <div className="text-xs text-muted-foreground">{position.broker_symbol}</div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{position.exchange_code}</td>
                  <td className="px-4 py-3 text-muted-foreground">{position.product_type}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatNumber(position.quantity, 0)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatNumber(position.average_price)}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-3 text-right tabular-nums",
                      isLive && "text-foreground font-medium"
                    )}
                  >
                    {formatNumber(position.ltp)}
                  </td>
                  <td
                    className={cn(
                      "px-4 py-3 text-right font-medium tabular-nums",
                      pnlColor(position.pnl)
                    )}
                  >
                    {formatNumber(position.pnl)}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export function DashboardPage() {
  const [summaryState, setSummaryState] =
    useState<AsyncState<DashboardSummaryResponse>>(createInitialState);
  const [alertsState, setAlertsState] =
    useState<AsyncState<DashboardAlertsResponse>>(createInitialState);

  const positionSubscriptions = useMemo<SubscriptionRequest[]>(
    () =>
      (summaryState.data?.positions ?? [])
        .filter((position) => position.exchange_code)
        .map((position) => ({
          symbol: position.symbol,
          exchange: position.exchange_code,
          product_type: position.product_type,
        })),
    [summaryState.data]
  );
  useLiveSubscribe(positionSubscriptions);

  const loadDashboard = useCallback(async () => {
    setSummaryState((current) => ({ ...current, loading: true, error: null }));
    setAlertsState((current) => ({ ...current, loading: true, error: null }));

    const [summaryResult, alertsResult] = await Promise.allSettled([
      getDashboardSummary(),
      getDashboardAlerts(),
    ]);

    setSummaryState(
      summaryResult.status === "fulfilled"
        ? { data: summaryResult.value, loading: false, error: null }
        : {
            data: null,
            loading: false,
            error:
              summaryResult.reason instanceof Error ? summaryResult.reason.message : "Unknown error",
          }
    );
    setAlertsState(
      alertsResult.status === "fulfilled"
        ? { data: alertsResult.value, loading: false, error: null }
        : {
            data: null,
            loading: false,
            error:
              alertsResult.reason instanceof Error ? alertsResult.reason.message : "Unknown error",
          }
    );
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const metrics = summaryState.data?.metrics ?? [];
  const alerts = alertsState.data?.alerts ?? [];
  const positions = summaryState.data?.positions ?? [];

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {(metrics.length
          ? metrics
          : (Array.from({ length: 4 }, () => undefined) as (DashboardMetric | undefined)[])
        ).map((metric, index) => {
          const Icon = metricIcon(metric?.key, index);
          return (
            <Card
              key={metric?.key ?? `loading-${index}`}
              className="glow-card overflow-hidden dark:bg-white/[0.04] dark:backdrop-blur-md"
            >
              <CardContent className="relative p-5">
                <Icon className="engraved-icon h-28 w-28" aria-hidden="true" />
                <div className="relative flex items-center gap-2">
                  <Icon className="glow-icon h-4 w-4 shrink-0" aria-hidden="true" />
                  <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
                    {metric?.label ?? "Loading"}
                  </p>
                </div>
                <p
                  className={cn(
                    "relative mt-2 text-2xl font-bold tabular-nums",
                    toneColor(metric?.tone)
                  )}
                >
                  {metric ? metricValue(metric) : "..."}
                </p>
                <p className="relative mt-1 text-xs text-muted-foreground">
                  {metric ? metricChangeText(metric) : "Syncing dashboard summary..."}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {summaryState.error && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {summaryState.error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2.2fr)_minmax(280px,0.8fr)]">
        <DashboardMarketChart />

        <Card>
          <CardHeader className="flex-row items-center justify-between border-b px-4 py-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Bell className="h-4 w-4" />
              Alerts
            </CardTitle>
            <Badge variant="secondary">{alerts.length} Active</Badge>
          </CardHeader>
          <CardContent className="p-0">
            {alerts.length === 0 ? (
              <div className="flex min-h-[250px] flex-col items-center justify-center px-6 text-center">
                <CircleAlert className="h-8 w-8 text-muted-foreground/50" />
                <p className="mt-3 text-sm font-medium">No active trade alerts</p>
                <p className="mt-1 max-w-56 text-xs text-muted-foreground">
                  Stop-loss, target, and rejected-order alerts will appear here.
                </p>
              </div>
            ) : (
              <div className="divide-y">
                {alerts.map((alert) => (
                  <div key={`${alert.level}-${alert.title}`} className="flex gap-3 p-4">
                    <span
                      className={cn(
                        "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                        alertDotColor(alert.level)
                      )}
                    />
                    <div>
                      <p className="text-sm font-medium">{alert.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{alert.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="min-h-[306px] overflow-hidden">
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="text-sm">Active Positions</CardTitle>
          <Badge variant="secondary">{positions.length}</Badge>
        </CardHeader>
        <PositionsTable positions={positions} status={summaryState.data?.positions_status} />
      </Card>
    </div>
  );
}
