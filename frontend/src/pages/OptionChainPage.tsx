import { TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getOptionChain,
  getOptionExpiries,
  type OptionChainResponse,
  type OptionChainRow,
} from "@/lib/api";
import { useLiveMarketData } from "@/hooks/useLiveMarketData";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, PageHeader, StatCard, selectClass, tone } from "@/components/common/page";
import { cn } from "@/lib/utils";

type OptionChainState = {
  expiries: string[];
  data: OptionChainResponse | null;
  loadingExpiries: boolean;
  loadingChain: boolean;
  error: string | null;
};

const underlyingOptions = ["NIFTY", "BANKNIFTY"];
const strikeWindowOptions = [8, 12, 16, 20];

function liveBadgeLabel(state: string): string {
  if (state === "live") return "Live feed";
  if (state === "connecting") return "Connecting";
  return "REST only";
}

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
}

function LegCells({ row, side }: { row: OptionChainRow; side: "ce" | "pe" }) {
  const leg = row[side];
  return (
    <>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(leg?.oi, 0)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(leg?.volume, 0)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(leg?.bid)}</td>
      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(leg?.ask)}</td>
      <td className="px-3 py-2 text-right font-medium tabular-nums">{formatNumber(leg?.ltp)}</td>
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

  const { connectionState } = useLiveMarketData();

  const previousCloseDelta = useMemo(() => {
    if (!state.data?.underlying_ltp || !state.data.previous_close) {
      return null;
    }
    return state.data.underlying_ltp - state.data.previous_close;
  }, [state.data]);

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <PageHeader
        kicker="Options data"
        title="Option Chain"
        description="Live Breeze chain normalized into a strike grid with expiry control, ATM context, and real broker errors."
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
        <StatCard
          label="Spot"
          value={formatNumber(state.data?.underlying_ltp)}
          tone={tone(previousCloseDelta)}
        />
        <StatCard label="ATM strike" value={formatNumber(state.data?.atm_strike, 0)} />
        <StatCard
          label="PCR"
          value={state.data?.pcr === null || state.data?.pcr === undefined ? "n/a" : state.data.pcr.toFixed(4)}
        />
        <StatCard label="Total OI" value={formatNumber(state.data?.total_oi, 0)} />
      </div>

      {state.error ? (
        <ErrorState title="Option chain unavailable" message={state.error} onRetry={() => void loadChain()} />
      ) : null}

      <Card className="overflow-hidden">
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <TrendingUp className="h-4 w-4" />
            Strike grid
          </CardTitle>
          {selectedExpiry ? <Badge variant="secondary">{selectedExpiry}</Badge> : null}
        </CardHeader>
        {state.loadingChain && !state.data ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Loading option chain...</p>
        ) : state.data ? (
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
                  return (
                    <tr key={row.strike_price} className={cn("hover:bg-muted/20", isAtm && "bg-primary/5")}>
                      <LegCells row={row} side="ce" />
                      <td
                        className={cn(
                          "px-3 py-2 text-center font-semibold tabular-nums",
                          isAtm ? "bg-primary/10 text-primary" : "bg-muted/40"
                        )}
                      >
                        {formatNumber(row.strike_price, 0)}
                      </td>
                      <td className="px-3 py-2 text-right font-medium tabular-nums">{formatNumber(row.pe?.ltp)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.pe?.bid)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.pe?.ask)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.pe?.volume, 0)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(row.pe?.oi, 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Select an expiry to load the chain.</p>
        )}
      </Card>
    </div>
  );
}
