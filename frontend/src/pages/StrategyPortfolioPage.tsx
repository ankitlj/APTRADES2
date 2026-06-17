import { Target, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { useEffect, useState } from "react";

import { PayoffChart } from "@/components/PayoffChart";
import {
  deleteStrategy,
  getStrategies,
  getStrategyPayoff,
  type PayoffResponse,
  type StrategyLeg,
  type StrategyRecord,
} from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageLayout } from "@/components/ui/page-layout";
import { PageHeader, StatCard } from "@/components/common/page";
import { cn } from "@/lib/utils";

type PortfolioState = {
  strategies: StrategyRecord[];
  loading: boolean;
  error: string | null;
};

type PayoffEntry = {
  data: PayoffResponse | null;
  loading: boolean;
  error: string | null;
};

function fmt(v: number | null, dec = 2): string {
  if (v === null || v === undefined) return "n/a";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: dec }).format(v);
}

function LegTag({ leg }: { leg: StrategyLeg }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        leg.action === "buy"
          ? "border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-400"
          : "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400"
      )}
    >
      {leg.action.toUpperCase()} {leg.quantity}x {fmt(leg.strike, 0)} {leg.right.toUpperCase()} @{leg.premium}
    </span>
  );
}

export function StrategyPortfolioPage() {
  const [state, setState] = useState<PortfolioState>({ strategies: [], loading: true, error: null });
  const [payoffs, setPayoffs] = useState<Record<number, PayoffEntry>>({});
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());

  function loadStrategies() {
    setState((s) => ({ ...s, loading: true, error: null }));
    getStrategies()
      .then((payload) => {
        setState({ strategies: payload.strategies, loading: false, error: null });
      })
      .catch((err) => {
        setState({
          strategies: [],
          loading: false,
          error: err instanceof Error ? err.message : "Load failed.",
        });
      });
  }

  useEffect(() => {
    loadStrategies();
  }, []);

  async function handleDelete(id: number) {
    setDeletingIds((s) => new Set(s).add(id));
    try {
      await deleteStrategy(id);
      setState((s) => ({ ...s, strategies: s.strategies.filter((st) => st.id !== id) }));
      setPayoffs((p) => {
        const next = { ...p };
        delete next[id];
        return next;
      });
    } catch {
      // silently ignore — user can retry
    } finally {
      setDeletingIds((s) => {
        const next = new Set(s);
        next.delete(id);
        return next;
      });
    }
  }

  async function handleTogglePayoff(strategy: StrategyRecord) {
    if (payoffs[strategy.id]?.data) {
      setPayoffs((p) => {
        const next = { ...p };
        delete next[strategy.id];
        return next;
      });
      return;
    }
    setPayoffs((p) => ({ ...p, [strategy.id]: { data: null, loading: true, error: null } }));
    try {
      const payload = await getStrategyPayoff(strategy.legs);
      setPayoffs((p) => ({ ...p, [strategy.id]: { data: payload, loading: false, error: null } }));
    } catch (err) {
      setPayoffs((p) => ({
        ...p,
        [strategy.id]: {
          data: null,
          loading: false,
          error: err instanceof Error ? err.message : "Payoff failed.",
        },
      }));
    }
  }

  return (
    <PageLayout>
      <PageHeader
        kicker="Strategy tools"
        title="Strategy Portfolio"
        description="Saved option strategies. View on-demand payoff diagrams or delete positions."
        actions={
          <Button variant="outline" size="sm" onClick={loadStrategies} disabled={state.loading}>
            {state.loading ? "Loading..." : "Refresh"}
          </Button>
        }
      />

      {state.error && <ErrorState title="Portfolio unavailable" message={state.error} onRetry={loadStrategies} />}

      {!state.loading && state.strategies.length === 0 && !state.error && (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            No strategies saved yet. Use the Strategy Builder to create one.
          </CardContent>
        </Card>
      )}

      {state.strategies.map((strategy) => {
        const entry = payoffs[strategy.id];
        const payoffUid = `portfolio-${strategy.id}`;
        return (
          <Card key={strategy.id}>
            <CardContent className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">{strategy.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {strategy.underlying} · {strategy.exchange_code} · {strategy.expiry}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "text-sm font-semibold tabular-nums",
                      strategy.net_premium >= 0 ? "text-green-600 dark:text-green-400" : "text-red-500"
                    )}
                  >
                    {strategy.net_premium >= 0 ? "CR" : "DR"} {fmt(Math.abs(strategy.net_premium))}
                  </span>
                  <Button variant="outline" size="sm" onClick={() => void handleTogglePayoff(strategy)} disabled={entry?.loading}>
                    {entry?.loading ? "Loading..." : entry?.data ? "Hide Payoff" : "View Payoff"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => void handleDelete(strategy.id)}
                    disabled={deletingIds.has(strategy.id)}
                  >
                    {deletingIds.has(strategy.id) ? "Deleting..." : "Delete"}
                  </Button>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {strategy.legs.map((leg, i) => (
                  <LegTag key={i} leg={leg} />
                ))}
              </div>

              {entry?.error && <p className="mt-3 text-sm text-red-500">{entry.error}</p>}

              {entry?.data && (
                <div className="mt-4">
                  <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                    <StatCard
                      label="Net Premium"
                      value={fmt(entry.data.net_premium)}
                      tone={entry.data.net_premium >= 0 ? "positive" : "negative"}
                      icon={Wallet}
                    />
                    <StatCard label="Max Profit" value={fmt(entry.data.max_profit)} tone="positive" icon={TrendingUp} />
                    <StatCard label="Max Loss" value={fmt(entry.data.max_loss)} tone="negative" icon={TrendingDown} />
                    <StatCard
                      label="Breakeven(s)"
                      value={entry.data.breakevens.length ? entry.data.breakevens.map((b) => fmt(b, 0)).join(", ") : "n/a"}
                      icon={Target}
                    />
                  </div>
                  <div className="mt-4">
                    <PayoffChart payoff={entry.data} uid={payoffUid} />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        );
      }      )}
    </PageLayout>
  );
}
