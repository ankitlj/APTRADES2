import { Layers, Scale, Target, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getOptionChain,
  getOptionExpiries,
  type OptionChainResponse,
  type OptionChainRow,
} from "@/lib/api";
import { useLiveMarketData, useLiveSubscribe, useLiveQuote } from "@/hooks/useLiveMarketData";
import { buildLiveSpotSubscription, type LiveTick, type SubscriptionRequest } from "@/lib/realtime";
import { ErrorState } from "@/components/ErrorState";
import { formatNumber, tone, toneColor } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTableShell } from "@/components/ui/data-table-shell";
import { PageLayout } from "@/components/ui/page-layout";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";
import { cn } from "@/lib/utils";

type OptionChainState = {
  expiries: string[];
  data: OptionChainResponse | null;
  loadingExpiries: boolean;
  loadingChain: boolean;
  error: string | null;
};

const underlyingOptions = ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYMID50"];
const strikeWindowOptions = [8, 12, 16, 20];

function liveBadgeLabel(state: string): string {
  if (state === "live") return "Live feed";
  if (state === "connecting") return "Connecting";
  return "REST only";
}

function LegCells({ row, side, liveTick }: { row: OptionChainRow; side: "ce" | "pe"; liveTick?: LiveTick }) {
  const leg = row[side];
  const ltp = liveTick?.ltp ?? leg?.ltp;
  const bid = liveTick?.bid_price ?? leg?.bid;
  const ask = liveTick?.ask_price ?? leg?.ask;
  return (
    <>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(leg?.oi, 0)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(leg?.volume, 0)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(bid)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(ask)}</td>
      <td className={cn("px-3 py-2 text-right font-medium tabular-nums", liveTick && "text-primary")}>{formatNumber(ltp)}</td>
    </>
  );
}

export function OptionChainPage() {
  const [exchangeCode, setExchangeCode] = useState("NFO");
  const [underlying, setUnderlying] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [strikeCount, setStrikeCount] = useState(12);
  const [state, setState] = useState<OptionChainState>({
    expiries: [],
    data: null,
    loadingExpiries: true,
    loadingChain: false,
    error: null,
  });

  useEffect(() => {
    let active = true;
    setSelectedExpiry("");
    setState((current) => ({
      ...current,
      loadingExpiries: true,
      error: null,
      expiries: [],
      data: null,
    }));

    getOptionExpiries({ underlying, exchange: exchangeCode })
      .then((payload) => {
        if (!active) return;
        const nextExpiry = payload.expiries[0] ?? "";
        setSelectedExpiry(nextExpiry);
        setState((current) => ({
          ...current,
          expiries: payload.expiries,
          loadingExpiries: false,
          error: payload.expiries.length ? null : "No expiries available.",
        }));
      })
      .catch((error) => {
        if (!active) return;
        setSelectedExpiry("");
        setState((current) => ({
          ...current,
          loadingExpiries: false,
          error: error instanceof Error ? error.message : "Unknown error",
        }));
      });

    return () => {
      active = false;
    };
  }, [exchangeCode, underlying]);

  const loadChain = async () => {
    if (!selectedExpiry) return;
    setState((current) => ({ ...current, loadingChain: true, error: null }));
    try {
      const payload = await getOptionChain({
        underlying,
        expiry: selectedExpiry,
        exchange: exchangeCode,
        strike_count: strikeCount,
      });
      setState((current) => ({ ...current, data: payload, loadingChain: false, error: null }));
    } catch (error) {
      setState((current) => ({
        ...current,
        data: null,
        loadingChain: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  };

  useEffect(() => {
    void loadChain();
  }, [selectedExpiry, strikeCount]);

  const { connectionState, ticks } = useLiveMarketData();
  const spotSub = useMemo<SubscriptionRequest[]>(
    () => {
      const request = buildLiveSpotSubscription(underlying);
      return request ? [request] : [];
    },
    [underlying],
  );
  useLiveSubscribe(spotSub);
  const liveQuote = useLiveQuote(underlying);
  const liveSpot = liveQuote?.ltp ?? state.data?.underlying_ltp;

  const contractSubs = useMemo<SubscriptionRequest[]>(() => {
    const rows = state.data?.rows ?? [];
    const subs: SubscriptionRequest[] = [];
    for (const row of rows) {
      for (const side of ["ce", "pe"] as const) {
        const leg = row[side];
        if (leg?.token) {
          subs.push({
            symbol: `${underlying}|${row.strike_price}|${side.toUpperCase()}`,
            exchange: exchangeCode,
            product_type: "options",
            token: leg.token,
            broker_symbol: leg.broker_symbol ?? state.data?.broker_symbol,
            expiry_date: leg.expiry_date ?? state.data?.expiry,
            strike_price: leg.strike_price ?? row.strike_price,
            right: leg.right ?? (side === "ce" ? "call" : "put"),
          });
        }
      }
    }
    return subs;
  }, [state.data, underlying, exchangeCode]);
  useLiveSubscribe(contractSubs);

  const previousCloseDelta = useMemo(() => {
    if (liveSpot == null || !state.data?.previous_close) return null;
    return liveSpot - state.data.previous_close;
  }, [liveSpot, state.data?.previous_close]);

  return (
    <PageLayout>
      <PageHeader
        title="Option Chain"
        actions={
          <Badge variant={connectionState === "live" ? "default" : "secondary"}>
            {liveBadgeLabel(connectionState)}
          </Badge>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Field label="Exchange">
            <select value={exchangeCode} onChange={(event) => setExchangeCode(event.target.value)} className={selectClass}>
              <option value="NFO">NFO</option>
              <option value="BFO">BFO</option>
            </select>
          </Field>
          <Field label="Underlying">
            <select value={underlying} onChange={(event) => setUnderlying(event.target.value)} className={selectClass}>
              {underlyingOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Expiry">
            <select
              value={selectedExpiry}
              onChange={(event) => setSelectedExpiry(event.target.value)}
              disabled={state.loadingExpiries || !state.expiries.length}
              className={selectClass}
            >
              {state.expiries.map((expiry) => (
                <option key={expiry} value={expiry}>
                  {expiry}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Strikes">
            <select value={strikeCount} onChange={(event) => setStrikeCount(Number(event.target.value))} className={selectClass}>
              {strikeWindowOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadChain()} disabled={!selectedExpiry || state.loadingChain}>
          {state.loadingChain ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatCard label="Spot" value={formatNumber(liveSpot)} tone={tone(previousCloseDelta)} icon={TrendingUp} />
        <StatCard label="ATM strike" value={formatNumber(state.data?.atm_strike, 0)} icon={Target} />
        <StatCard
          label="PCR"
          value={state.data?.pcr === null || state.data?.pcr === undefined ? "n/a" : state.data.pcr.toFixed(4)}
          icon={Scale}
        />
        <StatCard label="Total OI" value={formatNumber(state.data?.total_oi, 0)} icon={Layers} />
      </div>

      {state.error ? (
        <ErrorState title="Option chain unavailable" message={state.error} onRetry={() => void loadChain()} />
      ) : null}

      <DataTableShell
        title="Strike grid"
        loading={state.loadingChain && !state.data}
        error={state.error}
        onRetry={() => void loadChain()}
        emptyMessage="Select an expiry to load the chain."
        emptyTitle="No data"
      >
        {!state.data ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Select an expiry to load the chain.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-sm">
              <thead>
                <tr className="border-b text-[11px] uppercase tracking-wider">
                  <th colSpan={5} className="bg-green-500/10 px-3 py-2 text-center font-semibold text-green-700 dark:text-green-400">
                    Calls
                  </th>
                  <th className="bg-muted px-3 py-2 text-center font-semibold text-muted-foreground">Strike</th>
                  <th colSpan={5} className="bg-red-500/10 px-3 py-2 text-center font-semibold text-red-600 dark:text-red-400">
                    Puts
                  </th>
                </tr>
                <tr className="border-b bg-muted/30 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-2 text-right font-medium">OI</th>
                  <th className="px-3 py-2 text-right font-medium">Vol</th>
                  <th className="px-3 py-2 text-right font-medium">Bid</th>
                  <th className="px-3 py-2 text-right font-medium">Ask</th>
                  <th className="px-3 py-2 text-right font-medium">LTP</th>
                  <th className="px-3 py-2 text-center font-medium">Strike</th>
                  <th className="px-3 py-2 text-right font-medium">LTP</th>
                  <th className="px-3 py-2 text-right font-medium">Bid</th>
                  <th className="px-3 py-2 text-right font-medium">Ask</th>
                  <th className="px-3 py-2 text-right font-medium">Vol</th>
                  <th className="px-3 py-2 text-right font-medium">OI</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {state.data.rows.map((row) => {
                  const isAtm = row.strike_price === state.data?.atm_strike;
                  const ceKey = `${underlying}|${row.strike_price}|CE`;
                  const peKey = `${underlying}|${row.strike_price}|PE`;
                  const ceTick = ticks[ceKey] ?? ticks[row.ce?.token ? `${exchangeCode}:${row.ce.token}` : ""];
                  const peTick = ticks[peKey] ?? ticks[row.pe?.token ? `${exchangeCode}:${row.pe.token}` : ""];
                  return (
                    <tr key={row.strike_price} className={cn("hover:bg-muted/20", isAtm && "bg-primary/5")}>
                      <LegCells row={row} side="ce" liveTick={ceTick} />
                      <td
                        className={cn(
                          "px-3 py-2 text-center font-semibold tabular-nums",
                          isAtm ? "bg-primary/10 text-primary" : "bg-muted/40"
                        )}
                      >
                        {formatNumber(row.strike_price, 0)}
                      </td>
                      <LegCells row={row} side="pe" liveTick={peTick} />
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </DataTableShell>
    </PageLayout>
  );
}
