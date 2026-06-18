import {
  AlertTriangle,
  Bell,
  CircleAlert,
} from "lucide-react";
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
import { formatNumber, formatCurrency, formatPercent, pnlColor, toneColor, alertDotColor } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageLayout } from "@/components/ui/page-layout";
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
        {(metrics.length
          ? metrics
          : (Array.from({ length: 4 }, () => undefined) as (DashboardMetric | undefined)[])
        ).map((metric, index) => (
            <Card
              key={metric?.key ?? `loading-${index}`}
              className="glow-card overflow-hidden dark:bg-white/[0.035] dark:backdrop-blur-md"
            >
              <CardContent className="flex min-h-[126px] flex-col justify-center p-5">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
                    {metric?.label ?? "Loading"}
                  </p>
                  <p
                    className={cn(
                      "mt-3 text-2xl font-bold tabular-nums",
                      toneColor(metric?.tone)
                    )}
                  >
                    {metric ? metricValue(metric) : "..."}
                  </p>
                  {metric?.submetrics?.length ? (
                    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground sm:text-[13px]">
                      {metric.submetrics.map((submetric, submetricIndex) => (
                        <span
                          key={`${metric.key}-${submetric.label}`}
                          className="inline-flex items-center gap-2 whitespace-nowrap"
                        >
                          {submetricIndex > 0 ? (
                            <span className="text-muted-foreground/45">|</span>
                          ) : null}
                          <span className={cn("tabular-nums", toneColor(submetric.tone))}>
                            {submetricLabel(submetric)}
                          </span>
                        </span>
                      ))}
                    </div>
                  ) : metric?.meta ? (
                    <p className="mt-2 text-xs text-muted-foreground">{metric.meta}</p>
                  ) : !metric ? (
                    <p className="mt-2 text-xs text-muted-foreground">Syncing dashboard summary...</p>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
      </div>

      {summaryState.error && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {summaryState.error}
        </div>
      )}

      <Card className="min-h-[306px] overflow-hidden">
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="text-sm">Active Positions</CardTitle>
          <Badge variant="secondary">{positions.length}</Badge>
        </CardHeader>
        <PositionsTable positions={positions} status={summaryState.data?.positions_status} />
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2.2fr)_minmax(280px,0.8fr)]">
        <DashboardOptionOrderBook />

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
    </PageLayout>
  );
}
