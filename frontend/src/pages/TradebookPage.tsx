import { ArrowDownRight, ArrowUpRight, ListChecks } from "lucide-react";
import { useEffect, useState } from "react";

import { getTrades, type TradeRecord, type TradesResponse } from "@/lib/api";
import { useLiveMarketData, useLiveSubscribe } from "@/hooks/useLiveMarketData";
import type { SubscriptionRequest } from "@/lib/realtime";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { BuySellBadge } from "@/components/ui/buy-sell-badge";
import { DataTableShell } from "@/components/ui/data-table-shell";
import { PageLayout } from "@/components/ui/page-layout";
import { SymbolCell } from "@/components/ui/symbol-cell";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";
import { cn } from "@/lib/utils";

type TradebookState = {
  data: TradesResponse | null;
  loading: boolean;
  error: string | null;
};

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
  anchor.download = "oriens-tradebook.csv";
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

  const { ticks } = useLiveMarketData();
  const tradeSubs = trades
    .filter((t) => t.symbol && t.exchange_code)
    .map((t) => ({
      symbol: t.symbol,
      exchange: t.exchange_code,
      product_type: t.product_type,
    }));
  useLiveSubscribe(tradeSubs);

  return (
    <PageLayout>
      <PageHeader title="Tradebook" />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Field label="Exchange">
            <select value={exchange} onChange={(event) => setExchange(event.target.value)} className={selectClass}>
              <option value="NFO">NFO</option>
              <option value="NSE">NSE</option>
              <option value="BFO">BFO</option>
              <option value="BSE">BSE</option>
            </select>
          </Field>
          <Field label="Action">
            <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)} className={selectClass}>
              <option value="">All</option>
              <option value="BUY">Buy</option>
              <option value="SELL">Sell</option>
            </select>
          </Field>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportCsv(trades)} disabled={!trades.length}>
            Export CSV
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="Total trades" value={state.data?.stats.total ?? 0} icon={ListChecks} />
        <StatCard label="Buy trades" value={state.data?.stats.buy ?? 0} icon={ArrowUpRight} />
        <StatCard label="Sell trades" value={state.data?.stats.sell ?? 0} icon={ArrowDownRight} />
      </div>

      <DataTableShell
        title="Trades"
        count={trades.length}
        loading={state.loading}
        error={state.error}
        onRetry={() => void load()}
        emptyMessage="No trades returned for this filter window."
        emptyTitle="No trades"
        minWidth="800px"
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3 font-medium">Symbol</th>
              <th className="px-4 py-3 font-medium">Trade ID</th>
              <th className="px-4 py-3 font-medium">Order ID</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 text-right font-medium">Qty</th>
              <th className="px-4 py-3 text-right font-medium">Price</th>
              <th className="px-4 py-3 text-right font-medium">LTP</th>
              <th className="px-4 py-3 font-medium">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {trades.map((trade) => (
              <tr key={`${trade.trade_id}-${trade.order_id}`} className="hover:bg-muted/20">
                <SymbolCell symbol={trade.symbol} exchange={trade.exchange_code} product={trade.product_type} />
                <td className="px-4 py-3 text-muted-foreground">{trade.trade_id || "n/a"}</td>
                <td className="px-4 py-3 text-muted-foreground">{trade.order_id || "n/a"}</td>
                <td className="px-4 py-3">
                  <BuySellBadge action={trade.action} />
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{formatNumber(trade.quantity, 0)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatNumber(trade.price)}</td>
                <td className={cn("px-4 py-3 text-right tabular-nums", ticks[trade.symbol.toUpperCase()] && "text-primary")}>
                  {formatNumber(ticks[trade.symbol.toUpperCase()]?.ltp)}
                </td>
                <td className="px-4 py-3 text-muted-foreground">{trade.trade_time || "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DataTableShell>
    </PageLayout>
  );
}
