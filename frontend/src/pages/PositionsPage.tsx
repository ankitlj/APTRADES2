import { Layers, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getPositions, type PositionRecord, type PositionsResponse } from "@/lib/api";
import { useLiveMarketData, useLiveSubscribe } from "@/hooks/useLiveMarketData";
import type { LiveTick, SubscriptionRequest } from "@/lib/realtime";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, PageHeader, StatCard, pnlColor, selectClass, tone } from "@/components/common/page";
import { cn } from "@/lib/utils";

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
      { label: "Open positions", value: openPositions, tone: tone(undefined), icon: Layers },
      { label: "Long", value: longPositions, tone: tone(undefined), icon: TrendingUp },
      { label: "Short", value: shortPositions, tone: tone(undefined), icon: TrendingDown },
      { label: "Total P&L", value: formatNumber(totalPnl), tone: tone(totalPnl), icon: Wallet },
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

    return Array.from(mapped.entries()).map(([key, items]) => ({ key, label: key, items }));
  }, [groupBy, positions]);

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
  const isLive = state.data?.status === "ok";

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <PageHeader
        kicker="Broker positions"
        title="Positions"
        description="Track live Breeze positions with quote-enriched P&L and export the current view."
        actions={
          <Badge variant={isLive ? "default" : "secondary"}>{isLive ? "Live" : "Paused"}</Badge>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" size="sm" onClick={() => setSettingsOpen((current) => !current)}>
          Settings
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportCsv(positions)} disabled={!positions.length}>
            Export
          </Button>
          <Button variant="destructive" size="sm" disabled>
            Close All
          </Button>
        </div>
      </div>

      {settingsOpen ? (
        <Card>
          <div className="flex flex-wrap gap-4 px-4 py-3">
            <Field label="Grouping">
              <select value={groupBy} onChange={(event) => setGroupBy(event.target.value as GroupBy)} className={selectClass}>
                <option value="none">None</option>
                <option value="exchange">Exchange</option>
                <option value="product">Product</option>
                <option value="direction">Direction</option>
              </select>
            </Field>
            <Field label="Product">
              <select value={productFilter} onChange={(event) => setProductFilter(event.target.value)} className={selectClass}>
                <option value="all">All</option>
                <option value="cash">Cash</option>
                <option value="futures">Futures</option>
                <option value="options">Options</option>
              </select>
            </Field>
            <Field label="Direction">
              <select value={directionFilter} onChange={(event) => setDirectionFilter(event.target.value as DirectionFilter)} className={selectClass}>
                <option value="all">All</option>
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </Field>
            <Field label="Exchange">
              <select value={exchangeFilter} onChange={(event) => setExchangeFilter(event.target.value)} className={selectClass}>
                <option value="all">All</option>
                <option value="NFO">NFO</option>
                <option value="NSE">NSE</option>
                <option value="BFO">BFO</option>
                <option value="BSE">BSE</option>
              </select>
            </Field>
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {stats.map((item) => (
          <StatCard key={item.label} label={item.label} value={item.value} tone={item.tone} icon={item.icon} />
        ))}
      </div>

      <p className="text-xs text-muted-foreground">{quoteMessage}</p>
      {state.error ? <ErrorState title="Positions unavailable" message={state.error} onRetry={() => void load()} /> : null}

      <Card className="overflow-hidden">
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="text-sm">Active Positions</CardTitle>
          <Badge variant="secondary">{positions.length}</Badge>
        </CardHeader>
        {state.loading ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Loading positions...</p>
        ) : !positions.length && !state.error ? (
          <EmptyState title="No open positions" message="No open positions returned for this filtered view." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Symbol</th>
                  <th className="px-4 py-3 font-medium">Exchange</th>
                  <th className="px-4 py-3 font-medium">Product</th>
                  <th className="px-4 py-3 text-right font-medium">Qty</th>
                  <th className="px-4 py-3 text-right font-medium">Avg</th>
                  <th className="px-4 py-3 text-right font-medium">LTP</th>
                  <th className="px-4 py-3 text-right font-medium">P&amp;L</th>
                  <th className="px-4 py-3 text-right font-medium">P&amp;L%</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {groups.map((group) =>
                  group.items.flatMap((position, index) => {
                    const groupHeader =
                      groupBy !== "none" && index === 0 ? (
                        <tr key={`${group.key}-header`} className="bg-muted/50">
                          <td colSpan={9} className="px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            {group.label}
                          </td>
                        </tr>
                      ) : null;

                    const dataRow = (
                      <tr
                        key={`${group.key}-${position.symbol}-${position.exchange_code}-${position.product_type}-${index}`}
                        className="hover:bg-muted/20"
                      >
                        <td className="px-4 py-3">
                          <div className="font-semibold">{position.symbol}</div>
                          <div className="text-xs text-muted-foreground">
                            {position.broker_symbol}
                            {position.token ? ` · token ${position.token}` : ""}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{position.exchange_code}</td>
                        <td className="px-4 py-3 text-muted-foreground">{position.product_type}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{formatNumber(position.quantity, 0)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{formatNumber(position.average_price)}</td>
                        <td
                          className={cn(
                            "px-4 py-3 text-right tabular-nums",
                            ticks[position.symbol.toUpperCase()] && "font-medium"
                          )}
                        >
                          {formatNumber(position.ltp)}
                        </td>
                        <td className={cn("px-4 py-3 text-right font-medium tabular-nums", pnlColor(position.pnl))}>
                          {formatNumber(position.pnl)}
                        </td>
                        <td className={cn("px-4 py-3 text-right font-medium tabular-nums", pnlColor(position.pnl_percent))}>
                          {position.pnl_percent === null ? "n/a" : `${formatNumber(position.pnl_percent)}%`}
                        </td>
                        <td className="px-4 py-3">
                          <Button variant="outline" size="sm" disabled>
                            Close
                          </Button>
                        </td>
                      </tr>
                    );

                    return groupHeader ? [groupHeader, dataRow] : [dataRow];
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
