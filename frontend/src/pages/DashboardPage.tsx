import { Bell } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
import { DashboardOptionOrderBook } from "@/components/dashboard/DashboardOptionOrderBook";
import { formatNumber, formatCurrency, formatPercent, pnlColor } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { DataState } from "@/components/ui/data-state";
import { MetricCard } from "@/components/ui/metric-card";
import { PageLayout } from "@/components/ui/page-layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";

type AsyncState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
};

function createInitialState<T>(): AsyncState<T> {
  return { data: null, loading: true, error: null };
}

function metricValue(metric: DashboardSummaryResponse["metrics"][number]) {
  switch (metric.format) {
    case "currency":
      return formatCurrency(metric.value);
    case "percent":
      return formatPercent(metric.value);
    case "number":
      return formatNumber(metric.value, 0);
    default:
      return formatNumber(metric.value);
  }
}

function submetricValue(submetric: NonNullable<DashboardMetric["submetrics"]>[number]) {
  if (submetric.format === "currency") return formatCurrency(submetric.value);
  if (submetric.format === "percent") return formatPercent(submetric.value);
  return formatNumber(submetric.value, 0);
}

function submetricLabel(submetric: NonNullable<DashboardMetric["submetrics"]>[number]) {
  const value = submetricValue(submetric);
  if (
    submetric.format === "number" &&
    ["Options", "Future", "Equity"].includes(submetric.label)
  ) {
    return `${value} ${submetric.label}`;
  }
  return `${submetric.label}: ${value}`;
}

function submetricsNode(submetrics: NonNullable<DashboardMetric["submetrics"]>) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      {submetrics.map((sm, i) => (
        <span key={sm.label} className="inline-flex items-center gap-1.5 whitespace-nowrap">
          {i > 0 && <span className="text-muted-foreground/45">|</span>}
          <span className="tabular-nums">{submetricLabel(sm)}</span>
        </span>
      ))}
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

  useEffect(() => {
    setSummaryState((current) => ({ ...current, loading: true, error: null }));
    setAlertsState((current) => ({ ...current, loading: true, error: null }));

    getDashboardSummary().then(
      (data) => {
        setSummaryState({ data, loading: false, error: null });
      },
      (reason: unknown) => {
        setSummaryState({
          data: null,
          loading: false,
          error: reason instanceof Error ? reason.message : "Unknown error",
        });
      }
    );

    getDashboardAlerts().then(
      (data) => {
        setAlertsState({ data, loading: false, error: null });
      },
      (reason: unknown) => {
        setAlertsState({
          data: null,
          loading: false,
          error: reason instanceof Error ? reason.message : "Unknown error",
        });
      }
    );
  }, []);

  const metrics = summaryState.data?.metrics ?? [];
  const alerts = alertsState.data?.alerts ?? [];
  const positions = summaryState.data?.positions ?? [];

  return (
    <PageLayout>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {(summaryState.loading && metrics.length === 0
          ? ([null, null, null, null] as const)
          : metrics
        ).map((metric, index) => (
          <MetricCard
            key={metric?.key ?? `loading-${index}`}
            label={metric?.label ?? "Loading"}
            value={metric ? metricValue(metric) : "..."}
            meta={metric?.key === "margin_used" && metric ? (
              <span className="tabular-nums">Total Margin: {formatCurrency(metric.value)}</span>
            ) : metric?.submetrics?.length ? submetricsNode(metric.submetrics) : (metric?.meta ?? undefined)}
            tone={metric?.key === "margin_used" ? "neutral" : metric?.tone === "positive" ? "positive" : metric?.tone === "negative" ? "negative" : metric?.tone === "warning" ? "warning" : "neutral"}
            loading={summaryState.loading}
            error={summaryState.error && !metric ? summaryState.error : null}
          />
        ))}
      </div>

      <Card className="min-h-[306px] overflow-hidden">
        <div className="flex items-center justify-between gap-2 border-b px-4 py-2">
          <CardTitle className="text-sm">Active Positions</CardTitle>
          <Badge variant="secondary">{positions.length}</Badge>
        </div>
        <PositionsTable positions={positions} status={summaryState.data?.positions_status} />
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2.2fr)_minmax(280px,0.8fr)]">
        <DashboardOptionOrderBook />

        <Card>
          <div className="flex items-center justify-between border-b px-4 py-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Bell className="h-4 w-4" />
              Alerts
            </CardTitle>
            <Badge variant="secondary">{alerts.length} Active</Badge>
          </div>
          <CardContent className={alertsState.error ? "p-4" : "p-0"}>
            {alertsState.loading ? (
              <DataState state="loading" compact />
            ) : alertsState.error ? (
              <DataState state="error" message={alertsState.error} compact />
            ) : alerts.length === 0 ? (
              <DataState
                state="empty"
                title="No active trade alerts"
                message="Stop-loss, target, and rejected-order alerts will appear here."
                compact
              />
            ) : (
              <div className="divide-y">
                {alerts.map((alert) => (
                  <div key={`${alert.level}-${alert.title}`} className="flex gap-3 p-4">
                    <StatusBadge status={alert.level === "error" ? "error" : alert.level === "warning" ? "warning" : "success"}>
                      {alert.level}
                    </StatusBadge>
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
    </PageLayout>
  );
}
