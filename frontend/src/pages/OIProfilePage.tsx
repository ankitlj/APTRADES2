import { Layers, Scale, Target, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

import { getOptionExpiries, getOIProfile, type OIProfileResponse, type OIRow } from "@/lib/api";
import { ErrorState } from "@/components/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, PageHeader, StatCard, selectClass } from "@/components/common/page";
import { cn } from "@/lib/utils";

type OIProfileState = {
  expiries: string[];
  data: OIProfileResponse | null;
  loadingExpiries: boolean;
  loadingData: boolean;
  error: string | null;
};

const underlyingOptions = ["NIFTY", "BANKNIFTY"];

function formatNumber(value: number | null | undefined, maximumFractionDigits = 2) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
}

function OIProfileRow({ row, atmStrike, maxTotalOI }: { row: OIRow; atmStrike: number; maxTotalOI: number }) {
  const isAtm = row.strike_price === atmStrike;
  const ceBarWidth = maxTotalOI > 0 ? (row.ce_oi / maxTotalOI) * 100 : 0;
  const peBarWidth = maxTotalOI > 0 ? (row.pe_oi / maxTotalOI) * 100 : 0;
  return (
    <tr className={cn("hover:bg-muted/20", isAtm && "bg-primary/5")}>
      <td className={cn("px-4 py-3 text-center tabular-nums", isAtm && "font-semibold text-primary")}>
        {formatNumber(row.strike_price, 0)}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-2">
          <span className="tabular-nums text-green-600 dark:text-green-400">{formatNumber(row.ce_oi, 0)}</span>
          <div className="h-2.5 w-32 overflow-hidden rounded-full bg-muted">
            <div
              className="ml-auto h-full rounded-full bg-green-500/80"
              style={{ width: `${ceBarWidth.toFixed(1)}%` }}
            />
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="h-2.5 w-32 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-red-500/70" style={{ width: `${peBarWidth.toFixed(1)}%` }} />
          </div>
          <span className="tabular-nums text-red-500">{formatNumber(row.pe_oi, 0)}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{formatNumber(row.ce_ltp)}</td>
      <td className="px-4 py-3 text-right tabular-nums">{formatNumber(row.pe_ltp)}</td>
    </tr>
  );
}

export function OIProfilePage() {
  const [exchangeCode, setExchangeCode] = useState("NFO");
  const [underlying, setUnderlying] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [state, setState] = useState<OIProfileState>({
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
      const payload = await getOIProfile({ underlying, expiry: selectedExpiry, exchange: exchangeCode });
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

  const maxTotalOI = state.data
    ? Math.max(...state.data.rows.map((r) => Math.max(r.ce_oi, r.pe_oi)), 1)
    : 1;

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <PageHeader
        kicker="Open interest"
        title="OI Profile"
        description="OI distribution across all strikes sorted by price. ATM strike highlighted. CE left, PE right."
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

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatCard label="Spot" value={formatNumber(state.data?.underlying_ltp)} icon={TrendingUp} />
        <StatCard label="ATM Strike" value={formatNumber(state.data?.atm_strike, 0)} icon={Target} />
        <StatCard
          label="PCR"
          value={state.data?.pcr === null || state.data?.pcr === undefined ? "n/a" : state.data.pcr.toFixed(4)}
          icon={Scale}
        />
        <StatCard
          label="Total OI"
          value={formatNumber((state.data?.total_call_oi ?? 0) + (state.data?.total_put_oi ?? 0), 0)}
          icon={Layers}
        />
      </div>

      {state.error ? (
        <ErrorState title="OI Profile unavailable" message={state.error} onRetry={() => void loadData()} />
      ) : null}

      <Card className="overflow-hidden">
        <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Layers className="h-4 w-4" />
            OI distribution
          </CardTitle>
          {selectedExpiry ? <Badge variant="secondary">{selectedExpiry}</Badge> : null}
        </CardHeader>
        {state.loadingData && !state.data ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Loading OI profile...</p>
        ) : state.data ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3 text-center font-medium">Strike</th>
                  <th className="px-4 py-3 text-right font-medium">CE OI</th>
                  <th className="px-4 py-3 font-medium">PE OI</th>
                  <th className="px-4 py-3 text-right font-medium">CE LTP</th>
                  <th className="px-4 py-3 text-right font-medium">PE LTP</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {state.data.rows.map((row) => (
                  <OIProfileRow
                    key={row.strike_price}
                    row={row}
                    atmStrike={state.data!.atm_strike}
                    maxTotalOI={maxTotalOI}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">Select an expiry to load OI profile.</p>
        )}
      </Card>
    </div>
  );
}
