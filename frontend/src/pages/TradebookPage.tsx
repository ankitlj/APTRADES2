import { ArrowDownRight, ArrowUpRight, ListChecks } from "lucide-react";
import { useEffect, useState } from "react";

import { getTrades, type TradeRecord, type TradesResponse } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";

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
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <PageHeader
        kicker="Broker trades"
        title="Tradebook"
        description="Track normalized Breeze trades, apply quick filters, and export the visible book."
      />

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

      {state.error ? <ErrorState title="Trades unavailable" message={state.error} onRetry={() => void load()} /> : null}

      <Card className="overflow-hidden">
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="text-sm">Trades</CardTitle>
          <Badge variant="secondary">{trades.length}</Badge>
        </CardHeader>
        {state.loading ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Loading tradebook...</p>
        ) : !trades.length && !state.error ? (
          <EmptyState title="No trades" message="No trades returned for this filter window." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Symbol</th>
                  <th className="px-4 py-3 font-medium">Trade ID</th>
                  <th className="px-4 py-3 font-medium">Order ID</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 text-right font-medium">Qty</th>
                  <th className="px-4 py-3 text-right font-medium">Price</th>
                  <th className="px-4 py-3 font-medium">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {trades.map((trade) => (
                  <tr key={`${trade.trade_id}-${trade.order_id}`} className="hover:bg-muted/20">
                    <td className="px-4 py-3">
                      <div className="font-semibold">{trade.symbol}</div>
                      <div className="text-xs text-muted-foreground">
                        {trade.exchange_code} · {trade.product_type}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{trade.trade_id || "n/a"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{trade.order_id || "n/a"}</td>
                    <td className="px-4 py-3">
                      <span className={trade.action === "BUY" ? "badge-buy" : "badge-sell"}>{trade.action}</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatNumber(trade.quantity, 0)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatNumber(trade.price)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{trade.trade_time || "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
