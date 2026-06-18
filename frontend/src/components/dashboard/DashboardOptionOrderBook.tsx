import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumber } from "@/lib/format";

const UNDERLYING_OPTIONS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYMID50"];

type Right = "call" | "put";

interface StrikeOption {
  strike: number;
  right: Right;
  label: string;
}

export function DashboardOptionOrderBook() {
  const [underlying, setUnderlying] = useState("");
  const [expiry, setExpiry] = useState("");
  const [selectedStrike, setSelectedStrike] = useState<StrikeOption | null>(null);

  const hasSelection = Boolean(underlying && expiry && selectedStrike);

  const handleUnderlyingChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setUnderlying(e.target.value);
      setExpiry("");
      setSelectedStrike(null);
    },
    []
  );

  const handleExpiryChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setExpiry(e.target.value);
      setSelectedStrike(null);
    },
    []
  );

  return (
    <Card className="overflow-hidden">
      <CardHeader className="min-h-14 gap-3 border-b px-4 py-3 md:flex-row md:items-center md:justify-between">
        <CardTitle className="text-sm">Order Book</CardTitle>
        <span className="inline-flex h-5 items-center rounded-full bg-muted px-2 text-[10px] font-medium text-muted-foreground">
          Awaiting selection
        </span>
      </CardHeader>

      <CardContent className="space-y-3 p-4">
        {/* Selector row */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div>
            <label htmlFor="ob-underlying" className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Underlying
            </label>
            <select
              id="ob-underlying"
              value={underlying}
              onChange={handleUnderlyingChange}
              className="h-8 w-full rounded-md border bg-background px-2 text-xs text-foreground shadow-xs focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none"
              aria-label="Select underlying index"
            >
              <option value="">Select...</option>
              {UNDERLYING_OPTIONS.map((sym) => (
                <option key={sym} value={sym}>
                  {sym}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="ob-expiry" className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Expiry
            </label>
            <select
              id="ob-expiry"
              value={expiry}
              onChange={handleExpiryChange}
              disabled={!underlying}
              className="h-8 w-full rounded-md border bg-background px-2 text-xs text-foreground shadow-xs focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Select expiry date"
            >
              <option value="">{underlying ? "No expiries loaded" : "Select underlying first"}</option>
            </select>
          </div>

          <div>
            <label htmlFor="ob-strike" className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Strike
            </label>
            <select
              id="ob-strike"
              value={selectedStrike ? `${selectedStrike.strike}-${selectedStrike.right}` : ""}
              onChange={(e) => {
                const val = e.target.value;
                if (!val) {
                  setSelectedStrike(null);
                  return;
                }
                const [strikeStr, right] = val.split("-");
                setSelectedStrike({ strike: Number(strikeStr), right: right as Right, label: val });
              }}
              disabled={!expiry}
              className="h-8 w-full rounded-md border bg-background px-2 text-xs text-foreground shadow-xs focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Select strike and right"
            >
              <option value="">{expiry ? "No strikes loaded" : "Select expiry first"}</option>
            </select>
          </div>
        </div>

        {/* Selected instrument summary */}
        {hasSelection && selectedStrike ? (
          <div className="flex items-center justify-between rounded-md border bg-muted/20 px-3 py-2">
            <div className="flex items-center gap-3 text-xs">
              <span className="font-semibold text-foreground">{underlying}</span>
              <span className="text-muted-foreground">|</span>
              <span className="font-medium text-foreground">{expiry}</span>
              <span className="text-muted-foreground">|</span>
              <span className="font-medium text-foreground">
                {formatNumber(selectedStrike.strike, 0)} {selectedStrike.right.toUpperCase()}
              </span>
            </div>
            <div className="text-xs tabular-nums text-muted-foreground">LTP: Awaiting data</div>
          </div>
        ) : (
          <div className="flex min-h-[36px] items-center justify-center rounded-md border border-dashed bg-muted/10 px-3 text-xs text-muted-foreground/60">
            Select underlying, expiry, and strike to view order book
          </div>
        )}

        {/* Orderbook table */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[10px] font-medium text-muted-foreground">Order Book</span>
            {hasSelection && (
              <span className="text-[10px] text-muted-foreground/50">Top-of-book only (Breeze)</span>
            )}
          </div>
          <div className="overflow-hidden rounded-md border">
            <table className="w-full text-xs tabular-nums">
              <thead>
                <tr className="border-b bg-muted/30 text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                  <th className="w-[25%] px-3 py-2 font-medium">Qty</th>
                  <th className="w-[25%] px-3 py-2 text-right font-medium">Bid</th>
                  <th className="w-[25%] px-3 py-2 text-right font-medium">Ask</th>
                  <th className="w-[25%] px-3 py-2 text-right font-medium">Qty</th>
                </tr>
              </thead>
              <tbody>
                {hasSelection ? (
                  <tr className="border-b border-border/40">
                    <td className="px-3 py-2 text-green-600 dark:text-green-400">—</td>
                    <td className="px-3 py-2 text-right text-green-600 dark:text-green-400">—</td>
                    <td className="px-3 py-2 text-right text-red-500">—</td>
                    <td className="px-3 py-2 text-right text-red-500">—</td>
                  </tr>
                ) : (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-3 py-6 text-center text-[10px] text-muted-foreground/50"
                    >
                      No option selected
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {hasSelection && (
            <p className="mt-1 text-[10px] text-muted-foreground/40">
              Full market depth is unavailable from Breeze. Only the best bid/ask is shown.
            </p>
          )}
        </div>

        {/* Market depth card */}
        <div className="rounded-md border bg-muted/10 p-3">
          <p className="mb-2 text-[10px] font-medium text-muted-foreground">Market Depth</p>
          {hasSelection ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-green-600 dark:text-green-400">Buy —%</span>
                <span className="text-red-500">Sell —%</span>
              </div>
              <div className="flex h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-green-500" style={{ width: "0%" }} />
                <div className="h-full rounded-full bg-red-500" style={{ width: "0%" }} />
              </div>
              <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                <span>Buy: —</span>
                <span>Sell: —</span>
              </div>
            </div>
          ) : (
            <p className="text-[10px] text-muted-foreground/50">
              Depth data will appear when an option is selected
            </p>
          )}
        </div>

        {/* BUY / SELL buttons */}
        <div className="flex gap-2">
          <Button
            variant="default"
            disabled={!hasSelection}
            className="flex-1 bg-green-600 text-white hover:bg-green-700 disabled:opacity-30"
            aria-label="Buy selected option"
          >
            BUY
          </Button>
          <Button
            variant="destructive"
            disabled={!hasSelection}
            className="flex-1 disabled:opacity-30"
            aria-label="Sell selected option"
          >
            SELL
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
