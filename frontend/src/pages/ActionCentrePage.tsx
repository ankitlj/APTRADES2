import { CheckCircle2, Clock, Filter, Inbox, XCircle } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";

import {
  approveAction,
  getActionCentre,
  rejectAction,
  type ActionCentreRecord,
  type ActionCentreResponse,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { BuySellBadge } from "@/components/ui/buy-sell-badge";
import { DataTableShell } from "@/components/ui/data-table-shell";
import { PageLayout } from "@/components/ui/page-layout";
import { SymbolCell } from "@/components/ui/symbol-cell";
import { PageHeader, StatCard } from "@/components/common/page";
import { cn } from "@/lib/utils";

type ActionCentreState = {
  data: ActionCentreResponse | null;
  loading: boolean;
  error: string | null;
  message: string | null;
};

const tabs = ["pending", "approved", "rejected", "all"] as const;

function formatDateTime(value: string | null) {
  if (!value) return "n/a";
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value)
  );
}

export function ActionCentrePage() {
  const [statusFilter, setStatusFilter] = useState<(typeof tabs)[number]>("pending");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [state, setState] = useState<ActionCentreState>({ data: null, loading: true, error: null, message: null });

  const load = async (nextStatus = statusFilter) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await getActionCentre(nextStatus);
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
    void load(statusFilter);
  }, [statusFilter]);

  const actions = useMemo(() => state.data?.actions ?? [], [state.data]);

  const mutate = async (row: ActionCentreRecord, operation: "approve" | "reject") => {
    try {
      const response = operation === "approve" ? await approveAction(row.id) : await rejectAction(row.id);
      setState((current) => ({
        ...current,
        message: `${operation === "approve" ? "Approved" : "Rejected"} order ${response.action.order_id}.`,
      }));
      await load(statusFilter);
    } catch (error) {
      setState((current) => ({
        ...current,
        message: error instanceof Error ? error.message : `Unable to ${operation} this action.`,
      }));
    }
  };

  const stats = state.data?.stats ?? { pending: 0, approved: 0, rejected: 0, all: 0 };

  return (
    <PageLayout>
      <PageHeader
        kicker="Broker actions"
        title="Action Centre"
        description="Review queued broker actions, approve live requests, or reject them with full audit rows."
      />

      <Card>
        <CardContent className="p-4">
          <p className="text-sm font-semibold">Semi-auto workflow</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Pending rows are sourced from live broker orders. Approve sends the linked Breeze action.
            Reject keeps the audit trail without touching the broker.
          </p>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-lg border bg-muted/30 p-1">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setStatusFilter(tab)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                tab === statusFilter
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab}
            </button>
          ))}
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <StatCard label="Pending" value={stats.pending} icon={Clock} />
        <StatCard label="Approved" value={stats.approved} icon={CheckCircle2} />
        <StatCard label="Rejected" value={stats.rejected} icon={XCircle} />
        <StatCard label="All" value={stats.all} icon={Inbox} />
        <StatCard label="Current tab" value={<span className="capitalize">{statusFilter}</span>} icon={Filter} />
      </div>

      {state.message ? (
        <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          {state.message}
        </div>
      ) : null}
      <DataTableShell
        title="Action queue"
        count={actions.length}
        loading={state.loading}
        error={state.error}
        onRetry={() => void load()}
        emptyMessage="No rows returned for this status."
        emptyTitle="No actions"
        minWidth="1000px"
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3 font-medium">Symbol</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Action</th>
              <th className="px-4 py-3 font-medium">Order ID</th>
              <th className="px-4 py-3 text-right font-medium">Qty</th>
              <th className="px-4 py-3 font-medium">Requested</th>
              <th className="px-4 py-3 font-medium">Reviewed</th>
              <th className="px-4 py-3 font-medium">Controls</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {actions.map((row) => (
              <Fragment key={row.id}>
                <tr className="hover:bg-muted/20">
                  <SymbolCell symbol={row.symbol} exchange={row.exchange_code} product={row.product_type} />
                  <td className="px-4 py-3 text-muted-foreground">{row.status}</td>
                  <td className="px-4 py-3">
                    <BuySellBadge action={row.action_type} />
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{row.order_id}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{row.quantity ?? "n/a"}</td>
                  <td className="px-4 py-3 text-muted-foreground">{formatDateTime(row.requested_at)}</td>
                  <td className="px-4 py-3 text-muted-foreground">{formatDateTime(row.reviewed_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={() => void mutate(row, "approve")} disabled={!row.can_approve}>
                        Approve
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => void mutate(row, "reject")} disabled={!row.can_reject}>
                        Reject
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedId((current) => (current === row.id ? null : row.id))}
                      >
                        {expandedId === row.id ? "Hide" : "Details"}
                      </Button>
                    </div>
                  </td>
                </tr>
                {expandedId === row.id ? (
                  <tr className="bg-muted/20">
                    <td colSpan={8} className="px-4 py-4">
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Requested by</p>
                          <p className="mt-0.5 text-sm font-medium">{row.requested_by}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Created from</p>
                          <p className="mt-0.5 text-sm font-medium">{row.created_from}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Note</p>
                          <p className="mt-0.5 text-sm font-medium">{row.resolution_note ?? "Awaiting review"}</p>
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
                        <div>
                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Request payload</p>
                          <pre className="overflow-auto rounded-md border bg-muted/50 p-3 text-xs font-mono">
                            {JSON.stringify(row.request_payload ?? {}, null, 2)}
                          </pre>
                        </div>
                        <div>
                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Broker result</p>
                          <pre className="overflow-auto rounded-md border bg-muted/50 p-3 text-xs font-mono">
                            {JSON.stringify(row.broker_result ?? {}, null, 2)}
                          </pre>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      </DataTableShell>
    </PageLayout>
  );
}
