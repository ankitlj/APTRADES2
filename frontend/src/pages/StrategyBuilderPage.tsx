import { Target, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PayoffChart } from "@/components/PayoffChart";
import {
  createStrategy,
  getOptionExpiries,
  getStrategyPayoff,
  type PayoffResponse,
  type StrategyLeg,
} from "@/lib/api";
import { useLiveMarketData, useLiveSubscribe, useLiveQuote } from "@/hooks/useLiveMarketData";
import type { SubscriptionRequest } from "@/lib/realtime";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";
import { PageLayout } from "@/components/ui/page-layout";

type LegDraft = {
  action: string;
  right: string;
  strike: string;
  quantity: string;
  premium: string;
};

type BuilderState = {
  name: string;
  underlying: string;
  exchangeCode: string;
  expiry: string;
  expiries: string[];
  loadingExpiries: boolean;
  legs: StrategyLeg[];
  payoff: PayoffResponse | null;
  computingPayoff: boolean;
  saving: boolean;
  error: string | null;
  saveMessage: string | null;
};

const BLANK_LEG: LegDraft = { action: "sell", right: "call", strike: "", quantity: "1", premium: "" };
const UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYMID50"];

function fmt(v: number | null, dec = 2): string {
  if (v === null || v === undefined) return "n/a";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: dec }).format(v);
}

export function StrategyBuilderPage() {
  const [state, setState] = useState<BuilderState>({
    name: "",
    underlying: "NIFTY",
    exchangeCode: "NFO",
    expiry: "",
    expiries: [],
    loadingExpiries: true,
    legs: [],
    payoff: null,
    computingPayoff: false,
    saving: false,
    error: null,
    saveMessage: null,
  });
  const [draft, setDraft] = useState<LegDraft>({ ...BLANK_LEG });

  useEffect(() => {
    let active = true;
    setState((s) => ({ ...s, loadingExpiries: true, expiry: "", expiries: [], payoff: null }));
    getOptionExpiries({ underlying: state.underlying, exchange: state.exchangeCode })
      .then((payload) => {
        if (!active) return;
        setState((s) => ({
          ...s,
          expiries: payload.expiries,
          expiry: payload.expiries[0] ?? "",
          loadingExpiries: false,
        }));
      })
      .catch(() => {
        if (!active) return;
        setState((s) => ({ ...s, loadingExpiries: false }));
      });
    return () => {
      active = false;
    };
  }, [state.underlying, state.exchangeCode]);

  function addLeg() {
    const strike = parseFloat(draft.strike);
    const quantity = parseInt(draft.quantity, 10);
    const premium = parseFloat(draft.premium);
    if (!draft.strike || isNaN(strike) || strike <= 0) {
      setState((s) => ({ ...s, error: "Strike must be a positive number." }));
      return;
    }
    if (!draft.quantity || isNaN(quantity) || quantity <= 0) {
      setState((s) => ({ ...s, error: "Quantity must be a positive integer." }));
      return;
    }
    if (draft.premium === "" || isNaN(premium) || premium < 0) {
      setState((s) => ({ ...s, error: "Premium must be a non-negative number." }));
      return;
    }
    if (state.legs.length >= 8) {
      setState((s) => ({ ...s, error: "Maximum 8 legs allowed." }));
      return;
    }
    setState((s) => ({
      ...s,
      legs: [...s.legs, { action: draft.action, right: draft.right, strike, quantity, premium }],
      error: null,
      payoff: null,
    }));
    setDraft({ ...BLANK_LEG });
  }

  function removeLeg(index: number) {
    setState((s) => ({ ...s, legs: s.legs.filter((_, i) => i !== index), payoff: null }));
  }

  async function previewPayoff() {
    if (!state.legs.length) return;
    setState((s) => ({ ...s, computingPayoff: true, error: null, payoff: null }));
    try {
      const payload = await getStrategyPayoff(state.legs);
      setState((s) => ({ ...s, payoff: payload, computingPayoff: false }));
    } catch (err) {
      setState((s) => ({
        ...s,
        computingPayoff: false,
        error: err instanceof Error ? err.message : "Payoff calculation failed.",
      }));
    }
  }

  async function saveStrategy() {
    if (!state.name.trim()) {
      setState((s) => ({ ...s, error: "Strategy name is required." }));
      return;
    }
    if (!state.expiry) {
      setState((s) => ({ ...s, error: "Select an expiry." }));
      return;
    }
    if (!state.legs.length) {
      setState((s) => ({ ...s, error: "Add at least one leg." }));
      return;
    }
    setState((s) => ({ ...s, saving: true, error: null, saveMessage: null }));
    try {
      const saved = await createStrategy({
        name: state.name.trim(),
        underlying: state.underlying,
        exchange_code: state.exchangeCode,
        expiry: state.expiry,
        legs: state.legs,
      });
      setState((s) => ({
        ...s,
        saving: false,
        saveMessage: `Strategy "${saved.strategy.name}" saved to portfolio.`,
        legs: [],
        payoff: null,
        name: "",
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        saving: false,
        error: err instanceof Error ? err.message : "Save failed.",
      }));
    }
  }

  const { connectionState } = useLiveMarketData();
  const spotSub = useMemo<SubscriptionRequest[]>(
    () => [{ symbol: state.underlying, exchange: "NSE", product_type: "cash" }],
    [state.underlying],
  );
  useLiveSubscribe(spotSub);
  useLiveQuote(state.underlying);

  function liveBadgeLabel(state: string): string {
    if (state === "live") return "Live feed";
    if (state === "connecting") return "Connecting";
    return "REST only";
  }

  const payoffUid = state.payoff ? `builder-${state.legs.map((l) => l.strike).join("-")}` : "builder";

  return (
    <PageLayout>
      <PageHeader
        kicker="Strategy tools"
        title="Strategy Builder"
        description="Compose multi-leg option structures, preview the payoff diagram, and save to your portfolio."
        actions={
          <Badge variant={connectionState === "live" ? "default" : "secondary"}>
            {liveBadgeLabel(connectionState)}
          </Badge>
        }
      />

      <Card>
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="text-sm">Step 1 · Strategy details</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4 pt-4">
          <Field label="Exchange">
            <select
              value={state.exchangeCode}
              onChange={(e) => setState((s) => ({ ...s, exchangeCode: e.target.value }))}
              className={selectClass}
            >
              <option value="NFO">NFO</option>
              <option value="BFO">BFO</option>
            </select>
          </Field>
          <Field label="Underlying">
            <select
              value={state.underlying}
              onChange={(e) => setState((s) => ({ ...s, underlying: e.target.value }))}
              className={selectClass}
            >
              {UNDERLYINGS.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Expiry">
            <select
              value={state.expiry}
              onChange={(e) => setState((s) => ({ ...s, expiry: e.target.value }))}
              disabled={state.loadingExpiries || !state.expiries.length}
              className={selectClass}
            >
              {state.expiries.map((ex) => (
                <option key={ex} value={ex}>
                  {ex}
                </option>
              ))}
            </select>
          </Field>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span className="font-medium">Strategy name</span>
            <Input
              type="text"
              placeholder="e.g. Bear Call Spread"
              value={state.name}
              onChange={(e) => setState((s) => ({ ...s, name: e.target.value }))}
              maxLength={128}
              className="h-9 w-56"
            />
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="text-sm">Step 2 · Add legs</CardTitle>
          <Badge variant="secondary">{state.legs.length} / 8</Badge>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <Field label="Action">
              <select value={draft.action} onChange={(e) => setDraft((d) => ({ ...d, action: e.target.value }))} className={selectClass}>
                <option value="sell">Sell</option>
                <option value="buy">Buy</option>
              </select>
            </Field>
            <Field label="Right">
              <select value={draft.right} onChange={(e) => setDraft((d) => ({ ...d, right: e.target.value }))} className={selectClass}>
                <option value="call">Call</option>
                <option value="put">Put</option>
              </select>
            </Field>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              <span className="font-medium">Strike</span>
              <Input type="number" placeholder="23300" value={draft.strike} onChange={(e) => setDraft((d) => ({ ...d, strike: e.target.value }))} min="0" step="50" className="h-9 w-28" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              <span className="font-medium">Qty</span>
              <Input type="number" placeholder="1" value={draft.quantity} onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))} min="1" step="1" className="h-9 w-24" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              <span className="font-medium">Premium</span>
              <Input type="number" placeholder="100" value={draft.premium} onChange={(e) => setDraft((d) => ({ ...d, premium: e.target.value }))} min="0" step="0.05" className="h-9 w-28" />
            </label>
            <Button variant="outline" size="sm" onClick={addLeg} disabled={state.legs.length >= 8}>
              Add Leg
            </Button>
          </div>

          {state.legs.length > 0 && (
            <div className="mt-4 overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                    <th className="px-4 py-2.5 font-medium">#</th>
                    <th className="px-4 py-2.5 font-medium">Action</th>
                    <th className="px-4 py-2.5 font-medium">Right</th>
                    <th className="px-4 py-2.5 text-right font-medium">Strike</th>
                    <th className="px-4 py-2.5 text-right font-medium">Qty</th>
                    <th className="px-4 py-2.5 text-right font-medium">Premium</th>
                    <th className="px-4 py-2.5" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {state.legs.map((leg, i) => (
                    <tr key={i} className="hover:bg-muted/20">
                      <td className="px-4 py-2.5 text-muted-foreground">{i + 1}</td>
                      <td className="px-4 py-2.5">
                        <span className={leg.action === "buy" ? "badge-buy" : "badge-sell"}>{leg.action.toUpperCase()}</span>
                      </td>
                      <td className={leg.right === "call" ? "px-4 py-2.5 text-green-600 dark:text-green-400" : "px-4 py-2.5 text-red-500"}>
                        {leg.right.toUpperCase()}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{fmt(leg.strike, 0)}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{leg.quantity}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{fmt(leg.premium)}</td>
                      <td className="px-4 py-2.5">
                        <Button variant="ghost" size="sm" onClick={() => removeLeg(i)}>
                          Remove
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {state.error && <ErrorState title="Builder error" message={state.error} />}
          {state.saveMessage && (
            <p className="mt-3 text-sm font-medium text-green-600 dark:text-green-400">{state.saveMessage}</p>
          )}

          <div className="mt-4 flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => void previewPayoff()} disabled={!state.legs.length || state.computingPayoff}>
              {state.computingPayoff ? "Computing..." : "Preview Payoff"}
            </Button>
            <Button size="sm" onClick={() => void saveStrategy()} disabled={!state.legs.length || state.saving}>
              {state.saving ? "Saving..." : "Save Strategy"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {state.payoff && (
        <Card>
          <CardHeader className="border-b px-4 py-3">
            <CardTitle className="text-sm">Step 3 · Payoff preview</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <StatCard
                label="Net Premium"
                value={fmt(state.payoff.net_premium)}
                tone={state.payoff.net_premium >= 0 ? "positive" : "negative"}
                icon={Wallet}
              />
              <StatCard label="Max Profit" value={fmt(state.payoff.max_profit)} tone="positive" icon={TrendingUp} />
              <StatCard label="Max Loss" value={fmt(state.payoff.max_loss)} tone="negative" icon={TrendingDown} />
              <StatCard
                label="Breakeven(s)"
                value={state.payoff.breakevens.length ? state.payoff.breakevens.map((b) => fmt(b, 0)).join(", ") : "n/a"}
                icon={Target}
              />
            </div>
            <div className="mt-4">
              <PayoffChart payoff={state.payoff} uid={payoffUid} />
            </div>
          </CardContent>
        </Card>
      )}
    </PageLayout>
  );
}
