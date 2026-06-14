import { Ban, CheckCircle2, ClipboardList, Clock, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  cancelAllOrders,
  cancelOrder,
  getOrders,
  type OrderRecord,
  type OrdersResponse,
} from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";

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
  anchor.download = "oriens-orderbook.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
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

  const stats = [
    { label: "Total", value: state.data?.stats.total ?? 0, icon: ClipboardList },
    { label: "Completed", value: state.data?.stats.completed ?? 0, icon: CheckCircle2 },
    { label: "Open", value: state.data?.stats.open ?? 0, icon: Clock },
    { label: "Rejected", value: state.data?.stats.rejected ?? 0, icon: XCircle },
    { label: "Cancelled", value: state.data?.stats.cancelled ?? 0, icon: Ban },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <PageHeader
        kicker="Broker orders"
        title="Orderbook"
        description="Review live Breeze orders, filter by state, and export the current book."
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
          <Field label="Status">
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className={selectClass}>
              <option value="">All</option>
              <option value="open">Open</option>
              <option value="completed">Completed</option>
              <option value="rejected">Rejected</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </Field>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportCsv(orders)} disabled={!orders.length}>
            Export
          </Button>
          <Button variant="destructive" size="sm" onClick={() => void handleCancelAll()}>
            Cancel All
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {stats.map((item) => (
          <StatCard key={item.label} label={item.label} value={item.value} icon={item.icon} />
        ))}
      </div>

      {state.actionMessage ? (
        <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          {state.actionMessage}
        </div>
      ) : null}
      {state.error ? <ErrorState title="Orders unavailable" message={state.error} onRetry={() => void load()} /> : null}

      <Card className="overflow-hidden">
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="text-sm">Orders</CardTitle>
          <Badge variant="secondary">{orders.length}</Badge>
        </CardHeader>
        {state.loading ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Loading orderbook...</p>
        ) : !orders.length && !state.error ? (
          <EmptyState title="No orders" message="No orders returned for this filter window." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1000px] text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Symbol</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 text-right font-medium">Qty</th>
                  <th className="px-4 py-3 text-right font-medium">Pending</th>
                  <th className="px-4 py-3 text-right font-medium">Filled</th>
                  <th className="px-4 py-3 text-right font-medium">Limit</th>
                  <th className="px-4 py-3 text-right font-medium">Avg</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Control</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {orders.map((order) => (
                  <tr key={`${order.order_id}-${order.symbol}`} className="hover:bg-muted/20">
                    <td className="px-4 py-3">
                      <div className="font-semibold">{order.symbol}</div>
                      <div className="text-xs text-muted-foreground">
                        {order.exchange_code} · {order.product_type}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{order.status}</td>
                    <td className="px-4 py-3">
                      <span className={order.action === "BUY" ? "badge-buy" : "badge-sell"}>{order.action}</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatNumber(order.quantity, 0)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatNumber(order.pending_quantity, 0)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatNumber(order.filled_quantity, 0)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatNumber(order.limit_price)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{formatNumber(order.average_price)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{order.order_type || order.validity || "n/a"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{order.created_at || "n/a"}</td>
                    <td className="px-4 py-3">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void handleCancel(order)}
                        disabled={!(order.status_normalized === "open" || order.status_normalized === "pending" || order.status_normalized === "ordered")}
                      >
                        Cancel
                      </Button>
                    </td>
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
