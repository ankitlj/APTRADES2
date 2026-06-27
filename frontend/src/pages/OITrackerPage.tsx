import { ArrowDown, ArrowUp, BarChart3, Scale, Target } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getOptionExpiries, getOITracker, type OITrackerResponse, type OIRow } from "@/lib/api";
import { useLiveMarketData, useLiveSubscribe, useLiveQuote } from "@/hooks/useLiveMarketData";
import { buildLiveSpotSubscription, type LiveTick, type SubscriptionRequest } from "@/lib/realtime";
import { ErrorState } from "@/components/ErrorState";
import { formatNumber } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTableShell } from "@/components/ui/data-table-shell";
import { PageLayout } from "@/components/ui/page-layout";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";
import { cn } from "@/lib/utils";

type OITrackerState = {
  expiries: string[];
  data: OITrackerResponse | null;
  loadingExpiries: boolean;
  loadingData: boolean;
  error: string | null;
};

const underlyingOptions = ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYMID50"];

function OISplitBar({ ceOi, peOi }: { ceOi: number; peOi: number }) {
  const total = ceOi + peOi;
  if (total === 0) return <div className="h-2 w-full rounded-full bg-muted" />;
  const cePercent = (ceOi / total) * 100;
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-red-500/70">
      <div className="h-full bg-green-500/80" style={{ width: `${cePercent.toFixed(1)}%` }} />
    </div>
  );
}

function OITrackerRow({ row, atmStrike, ceTick, peTick }: { row: OIRow; atmStrike: number; ceTick?: LiveTick; peTick?: LiveTick }) {
  const isAtm = row.strike_price === atmStrike;
  const ceLtp = ceTick?.ltp ?? row.ce_ltp;
  const peLtp = peTick?.ltp ?? row.pe_ltp;
  return (
    <tr className={cn("hover:bg-muted/20", isAtm && "bg-primary/5")}>
      <td className={cn("px-4 py-3 text-right tabular-nums", isAtm && "font-semibold text-primary")}>
        {formatNumber(row.strike_price, 0)}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-green-600 dark:text-green-400">
        {formatNumber(row.ce_oi, 0)}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-red-500">{formatNumber(row.pe_oi, 0)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{formatNumber(row.total_oi, 0)}</td>
      <td className="px-4 py-3">
        <OISplitBar ceOi={row.ce_oi} peOi={row.pe_oi} />
      </td>
      <td className={cn("px-4 py-3 text-right tabular-nums", ceTick && "text-primary")}>{formatNumber(ceLtp)}</td>
      <td className={cn("px-4 py-3 text-right tabular-nums", peTick && "text-primary")}>{formatNumber(peLtp)}</td>
    </tr>
  );
}

export function OITrackerPage() {
  const [exchangeCode, setExchangeCode] = useState("NFO");
  const [underlying, setUnderlying] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [state, setState] = useState<OITrackerState>({
    expiries: [],
    data: null,
    loadingExpiries: true,
    loadingData: false,
    error: null,
  });

  useEffect(() => {
    let active = true;
    setSelectedExpiry("");
    setState((s) => ({ ...s, loadingExpiries: true, error: null, expiries: [], data: null }));

    getOptionExpiries({ underlying, exchange: exchangeCode })
      .then((payload) => {
        if (!active) return;
        const next = payload.expiries[0] ?? "";
        setSelectedExpiry(next);
        setState((s) => ({
          ...s,
          expiries: payload.expiries,
          loadingExpiries: false,
          error: payload.expiries.length ? null : "No expiries available.",
        }));
      })
      .catch((error) => {
        if (!active) return;
        setSelectedExpiry("");
        setState((s) => ({
          ...s,
          loadingExpiries: false,
          error: error instanceof Error ? error.message : "Unknown error",
        }));
      });

    return () => {
      active = false;
    };
  }, [exchangeCode, underlying]);

  const loadData = async () => {
    if (!selectedExpiry) return;
    setState((s) => ({ ...s, loadingData: true, error: null }));
    try {
      const payload = await getOITracker({ underlying, expiry: selectedExpiry, exchange: exchangeCode });
      setState((s) => ({ ...s, data: payload, loadingData: false, error: null }));
    } catch (error) {
      setState((s) => ({
        ...s,
        data: null,
        loadingData: false,
        error: error instanceof Error ? error.message : "Unknown error",
      }));
    }
  };

  useEffect(() => {
    void loadData();
  }, [selectedExpiry]);

  const { connectionState, ticks } = useLiveMarketData();
  const liveQuote = useLiveQuote(underlying);
  const liveSpot = liveQuote?.ltp ?? state.data?.underlying_ltp;
  const spotSub = useMemo<SubscriptionRequest[]>(
    () => {
      const request = buildLiveSpotSubscription(underlying);
      return request ? [request] : [];
    },
    [underlying],
  );
  useLiveSubscribe(spotSub);

  const contractSubs = useMemo<SubscriptionRequest[]>(() => {
    const rows = state.data?.rows ?? [];
    const subs: SubscriptionRequest[] = [];
    for (const row of rows) {
      if (row.ce_token) {
        subs.push({
          symbol: `${underlying}|${row.strike_price}|CE`,
          exchange: exchangeCode,
          product_type: "options",
          token: row.ce_token,
        });
      }
      if (row.pe_token) {
        subs.push({
          symbol: `${underlying}|${row.strike_price}|PE`,
          exchange: exchangeCode,
          product_type: "options",
          token: row.pe_token,
        });
      }
    }
    return subs;
  }, [state.data, underlying, exchangeCode]);
  useLiveSubscribe(contractSubs);

  function liveBadgeLabel(state: string): string {
    if (state === "live") return "Live feed";
    if (state === "connecting") return "Connecting";
    return "REST only";
  }

  return (
    <PageLayout>
      <PageHeader
        title="OI Tracker"
        actions={
          <Badge variant={connectionState === "live" ? "default" : "secondary"}>
            {liveBadgeLabel(connectionState)}
          </Badge>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Field label="Exchange">
            <select value={exchangeCode} onChange={(e) => setExchangeCode(e.target.value)} className={selectClass}>
              <option value="NFO">NFO</option>
              <option value="BFO">BFO</option>
            </select>
          </Field>
          <Field label="Underlying">
            <select value={underlying} onChange={(e) => setUnderlying(e.target.value)} className={selectClass}>
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
              onChange={(e) => setSelectedExpiry(e.target.value)}
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
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadData()} disabled={!selectedExpiry || state.loadingData}>
          {state.loadingData ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        <StatCard label="Spot" value={formatNumber(liveSpot)} icon={Target} />
        <StatCard label="ATM Strike" value={formatNumber(state.data?.atm_strike, 0)} icon={Target} />
        <StatCard
          label="PCR"
          value={state.data?.pcr === null || state.data?.pcr === undefined ? "n/a" : state.data.pcr.toFixed(4)}
          icon={Scale}
        />
        <StatCard label="Resistance (Max CE OI)" value={formatNumber(state.data?.max_ce_oi_strike, 0)} tone="positive" icon={ArrowUp} />
        <StatCard label="Support (Max PE OI)" value={formatNumber(state.data?.max_pe_oi_strike, 0)} tone="negative" icon={ArrowDown} />
      </div>

      {state.error ? (
        <ErrorState title="OI Tracker unavailable" message={state.error} onRetry={() => void loadData()} />
      ) : null}

      <DataTableShell
        title="Open interest by strike"
        loading={state.loadingData && !state.data}
        error={state.error}
        onRetry={() => void loadData()}
        emptyMessage="Select an expiry to load OI data."
        emptyTitle="No data"
      >
        {!state.data ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Select an expiry to load OI data.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 text-right font-medium">Strike</th>
                  <th className="px-4 py-3 text-right font-medium">CE OI</th>
                  <th className="px-4 py-3 text-right font-medium">PE OI</th>
                  <th className="px-4 py-3 text-right font-medium">Total OI</th>
                  <th className="px-4 py-3 font-medium">CE / PE split</th>
                  <th className="px-4 py-3 text-right font-medium">CE LTP</th>
                  <th className="px-4 py-3 text-right font-medium">PE LTP</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {state.data.rows.map((row) => (
                  <OITrackerRow
                    key={row.strike_price}
                    row={row}
                    atmStrike={state.data!.atm_strike}
                    ceTick={ticks[`${underlying}|${row.strike_price}|CE`]}
                    peTick={ticks[`${underlying}|${row.strike_price}|PE`]}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DataTableShell>
    </PageLayout>
  );
}
