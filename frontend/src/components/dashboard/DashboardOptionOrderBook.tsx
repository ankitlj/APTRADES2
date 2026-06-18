import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getDashboardOptionOrderbook, getOptionChain, getOptionExpiries } from "@/lib/api";
import type { OptionOrderbookResponse } from "@/lib/api";
import { formatNumber } from "@/lib/format";

const UNDERLYING_OPTIONS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYMID50"];
const POLL_INTERVAL_MS = 2500;

type Right = "call" | "put";

interface StrikeOption {
  strike: number;
  right: Right;
  label: string;
}

type FetchState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ok"; data: T };

export function DashboardOptionOrderBook() {
  const [underlying, setUnderlying] = useState("");
  const [expiry, setExpiry] = useState("");
  const [selectedStrike, setSelectedStrike] = useState<StrikeOption | null>(null);

  const [expiries, setExpiries] = useState<FetchState<string[]>>({ status: "idle" });
  const [strikes, setStrikes] = useState<FetchState<StrikeOption[]>>({ status: "idle" });
  const [orderbook, setOrderbook] = useState<FetchState<OptionOrderbookResponse>>({ status: "idle" });
  const [confirmAction, setConfirmAction] = useState<"BUY" | "SELL" | null>(null);
  const [confirmQty, setConfirmQty] = useState(1);

  const cancelRef = useRef<HTMLButtonElement | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const hasValidDataRef = useRef(false);

  const cancelPending = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    abortRef.current = new AbortController();
  }, []);

  const handleUnderlyingChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setUnderlying(val);
    setExpiry("");
    setSelectedStrike(null);
    setExpiries(val ? { status: "loading" } : { status: "idle" });
    setStrikes({ status: "idle" });
    setOrderbook({ status: "idle" });
    hasValidDataRef.current = false;
  }, []);

  const handleExpiryChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setExpiry(val);
    setSelectedStrike(null);
    setStrikes(val ? { status: "loading" } : { status: "idle" });
    setOrderbook({ status: "idle" });
    hasValidDataRef.current = false;
  }, []);

  const handleStrikeChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (!val) {
      setSelectedStrike(null);
      setOrderbook({ status: "idle" });
      hasValidDataRef.current = false;
      return;
    }
    const [strikeStr, right] = val.split("-");
    setSelectedStrike({ strike: Number(strikeStr), right: right as Right, label: val });
    setOrderbook({ status: "loading" });
    hasValidDataRef.current = false;
    setConfirmQty(1);
  }, []);

  const openConfirm = useCallback((action: "BUY" | "SELL") => {
    setConfirmAction(action);
    setConfirmQty(1);
  }, []);

  const closeConfirm = useCallback(() => {
    setConfirmAction(null);
  }, []);

  useEffect(() => {
    if (!underlying) return;
    cancelPending();
    const signal = abortRef.current!.signal;
    getOptionExpiries({ underlying })
      .then((res) => {
        if (signal.aborted) return;
        setExpiries({ status: "ok", data: res.expiries });
      })
      .catch((err: Error) => {
        if (signal.aborted) return;
        setExpiries({ status: "error", message: err.message });
      });
  }, [underlying, cancelPending]);

  useEffect(() => {
    if (!underlying || !expiry) return;
    cancelPending();
    const signal = abortRef.current!.signal;
    setStrikes({ status: "loading" });
    getOptionChain({ underlying, expiry })
      .then((res) => {
        if (signal.aborted) return;
        const extracted: StrikeOption[] = [];
        for (const row of res.rows) {
          if (row.ce) {
            extracted.push({ strike: row.strike_price, right: "call", label: `${row.strike_price}-call` });
          }
          if (row.pe) {
            extracted.push({ strike: row.strike_price, right: "put", label: `${row.strike_price}-put` });
          }
        }
        if (extracted.length === 0) {
          setStrikes({ status: "error", message: "No strikes available for this expiry" });
        } else {
          setStrikes({ status: "ok", data: extracted });
        }
      })
      .catch((err: Error) => {
        if (signal.aborted) return;
        setStrikes({ status: "error", message: err.message });
      });
  }, [underlying, expiry, cancelPending]);

  useEffect(() => {
    if (!underlying || !expiry || !selectedStrike) {
      hasValidDataRef.current = false;
      return;
    }

    cancelPending();
    const signal = abortRef.current!.signal;
    setOrderbook({ status: "loading" });

    const fetchData = () => {
      getDashboardOptionOrderbook({
        underlying,
        expiry,
        strike: selectedStrike.strike,
        right: selectedStrike.right,
      })
        .then((res) => {
          if (signal.aborted) return;
          hasValidDataRef.current = true;
          setOrderbook({ status: "ok", data: res });
        })
        .catch((err: Error) => {
          if (signal.aborted) return;
          if (!hasValidDataRef.current) {
            setOrderbook({ status: "error", message: err.message });
          }
        });
    };

    fetchData();

    const intervalId = setInterval(fetchData, POLL_INTERVAL_MS);

    return () => {
      clearInterval(intervalId);
    };
  }, [underlying, expiry, selectedStrike, cancelPending]);

  const numberOfStrikes =
    strikes.status === "ok" ? strikes.data.length : 0;
  const orderbookData = orderbook.status === "ok" ? orderbook.data : null;
  const hasSelection = Boolean(underlying && expiry && selectedStrike);
  const isLive = orderbook.status === "ok" && orderbook.data?.status === "ok";

  const statusBadge = () => {
    if (orderbook.status === "loading") {
      return (
        <span className="inline-flex h-5 items-center rounded-full bg-amber-100 px-2 text-[10px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
          Loading...
        </span>
      );
    }
    if (orderbook.status === "error") {
      return (
        <span className="inline-flex h-5 items-center rounded-full bg-red-100 px-2 text-[10px] font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
          Error
        </span>
      );
    }
    if (orderbook.status === "ok") {
      const isError = orderbook.data.status === "error";
      if (isError) {
        return (
          <span className="inline-flex h-5 items-center rounded-full bg-red-100 px-2 text-[10px] font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
            No data
          </span>
        );
      }
      return (
        <span className="inline-flex h-5 items-center gap-1 rounded-full bg-green-100 px-2 text-[10px] font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75 dark:bg-green-500" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green-500" />
          </span>
          Live
        </span>
      );
    }
    return (
      <span className="inline-flex h-5 items-center rounded-full bg-muted px-2 text-[10px] font-medium text-muted-foreground">
        Awaiting selection
      </span>
    );
  };

  return (
    <>
    <Card className="overflow-hidden">
      <CardHeader className="min-h-14 gap-3 border-b px-4 py-3 md:flex-row md:items-center md:justify-between">
        <CardTitle className="text-sm">Order Book</CardTitle>
        {statusBadge()}
      </CardHeader>

      <CardContent className="space-y-3 p-4">
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
              <option value="">
                {expiries.status === "loading"
                  ? "Loading..."
                  : expiries.status === "error"
                    ? "Failed to load"
                    : underlying
                      ? "Select expiry..."
                      : "Select underlying first"}
              </option>
              {expiries.status === "ok" &&
                expiries.data.map((d) => (
                  <option key={d} value={d}>
                    {d.slice(0, 10)}
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label htmlFor="ob-strike" className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Strike
            </label>
            <select
              id="ob-strike"
              value={selectedStrike ? selectedStrike.label : ""}
              onChange={handleStrikeChange}
              disabled={!expiry}
              className="h-8 w-full rounded-md border bg-background px-2 text-xs text-foreground shadow-xs focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Select strike and right"
            >
              <option value="">
                {strikes.status === "loading"
                  ? "Loading..."
                  : strikes.status === "error"
                    ? "Failed to load strikes"
                    : expiry
                      ? `Select strike (${numberOfStrikes} available)`
                      : "Select expiry first"}
              </option>
              {strikes.status === "ok" &&
                strikes.data.map((s) => (
                  <option key={s.label} value={s.label}>
                    {formatNumber(s.strike, 0)} {s.right === "call" ? "CE" : "PE"}
                  </option>
                ))}
            </select>
          </div>
        </div>

        {hasSelection && selectedStrike ? (
          <div className="flex items-center justify-between rounded-md border bg-muted/20 px-3 py-2">
            <div className="flex items-center gap-3 text-xs">
              <span className="font-semibold text-foreground">{underlying}</span>
              <span className="text-muted-foreground">|</span>
              <span className="font-medium text-foreground">{expiry.slice(0, 10)}</span>
              <span className="text-muted-foreground">|</span>
              <span className="font-medium text-foreground">
                {formatNumber(selectedStrike.strike, 0)} {selectedStrike.right === "call" ? "CE" : "PE"}
              </span>
            </div>
            <div className="text-xs tabular-nums text-muted-foreground">
              LTP:{" "}
              {orderbook.status === "loading" ? (
                "..."
              ) : orderbookData && orderbookData.ltp != null ? (
                formatNumber(orderbookData.ltp)
              ) : (
                <span className="text-muted-foreground/50">N/A</span>
              )}
            </div>
          </div>
        ) : (
          <div className="flex min-h-[36px] items-center justify-center rounded-md border border-dashed bg-muted/10 px-3 text-xs text-muted-foreground/60">
            Select underlying, expiry, and strike to view order book
          </div>
        )}

        {orderbook.status === "error" && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-400">
            {orderbook.message}
          </div>
        )}

        {orderbook.status === "ok" && orderbookData?.status === "error" && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-400">
            {orderbookData.error ?? "No data available for this contract"}
          </div>
        )}

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
                {orderbookData && orderbookData.status === "ok" && orderbookData.levels.length > 0 ? (
                  orderbookData.levels.map((level, i) => (
                    <tr key={i} className="border-b border-border/40">
                      <td className="px-3 py-2 text-green-600 dark:text-green-400">
                        {level.bid_qty != null ? formatNumber(level.bid_qty, 0) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right text-green-600 dark:text-green-400">
                        {level.bid_price != null ? formatNumber(level.bid_price) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right text-red-500">
                        {level.ask_price != null ? formatNumber(level.ask_price) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right text-red-500">
                        {level.ask_qty != null ? formatNumber(level.ask_qty, 0) : "—"}
                      </td>
                    </tr>
                  ))
                ) : orderbook.status === "loading" ? (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-[10px] text-muted-foreground/50">
                      Loading...
                    </td>
                  </tr>
                ) : hasSelection ? (
                  <tr className="border-b border-border/40">
                    <td className="px-3 py-2 text-green-600 dark:text-green-400">—</td>
                    <td className="px-3 py-2 text-right text-green-600 dark:text-green-400">—</td>
                    <td className="px-3 py-2 text-right text-red-500">—</td>
                    <td className="px-3 py-2 text-right text-red-500">—</td>
                  </tr>
                ) : (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-[10px] text-muted-foreground/50">
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

        <div className="rounded-md border bg-muted/10 p-3">
          <p className="mb-2 text-[10px] font-medium text-muted-foreground">Market Depth</p>
          {orderbookData && orderbookData.status === "ok" ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-green-600 dark:text-green-400">Buy {orderbookData.buy_percent}%</span>
                <span className="text-red-500">Sell {orderbookData.sell_percent}%</span>
              </div>
              <div className="flex h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-green-500"
                  style={{ width: `${orderbookData.buy_percent}%` }}
                />
                <div
                  className="h-full rounded-full bg-red-500"
                  style={{ width: `${orderbookData.sell_percent}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                <span>Buy: {formatNumber(orderbookData.total_buy_qty, 0)}</span>
                <span>Sell: {formatNumber(orderbookData.total_sell_qty, 0)}</span>
              </div>
            </div>
          ) : orderbook.status === "loading" ? (
            <p className="text-[10px] text-muted-foreground/50">Loading depth data...</p>
          ) : orderbook.status === "error" ? (
            <p className="text-[10px] text-muted-foreground/50">Failed to load depth data</p>
          ) : (
            <p className="text-[10px] text-muted-foreground/50">
              Depth data will appear when an option is selected
            </p>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            variant="default"
            disabled={!hasSelection || orderbook.status !== "ok" || orderbookData?.status !== "ok"}
            className="flex-1 bg-green-600 text-white hover:bg-green-700 disabled:opacity-30"
            aria-label="Buy selected option"
            onClick={() => openConfirm("BUY")}
          >
            BUY
          </Button>
          <Button
            variant="destructive"
            disabled={!hasSelection || orderbook.status !== "ok" || orderbookData?.status !== "ok"}
            className="flex-1 disabled:opacity-30"
            aria-label="Sell selected option"
            onClick={() => openConfirm("SELL")}
          >
            SELL
          </Button>
        </div>
      </CardContent>
    </Card>

    {confirmAction && orderbookData && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        onKeyDown={(e) => {
          if (e.key === "Escape") closeConfirm();
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) closeConfirm();
        }}
      >
        <div className="w-full max-w-sm rounded-lg border bg-background p-5 shadow-lg">
          <h3
            id="confirm-title"
            className={`text-sm font-semibold ${
              confirmAction === "BUY" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
            }`}
          >
            Confirm {confirmAction}
          </h3>

          <div className="mt-3 space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Contract</span>
              <span className="font-medium text-foreground">
                {underlying} {expiry.slice(0, 10)} {formatNumber(selectedStrike!.strike, 0)}{" "}
                {selectedStrike!.right === "call" ? "CE" : "PE"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">LTP</span>
              <span className="font-medium tabular-nums text-foreground">
                {orderbookData.ltp != null ? formatNumber(orderbookData.ltp) : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Bid / Ask</span>
              <span className="font-medium tabular-nums text-foreground">
                {orderbookData.bid_price != null ? formatNumber(orderbookData.bid_price) : "—"} /{" "}
                {orderbookData.ask_price != null ? formatNumber(orderbookData.ask_price) : "—"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Spread</span>
              <span className="font-medium tabular-nums text-foreground">
                {orderbookData.bid_price != null && orderbookData.ask_price != null
                  ? formatNumber(orderbookData.ask_price - orderbookData.bid_price)
                  : "—"}
              </span>
            </div>

            <div className="pt-1">
              <label htmlFor="confirm-qty" className="mb-1 block text-[10px] font-medium text-muted-foreground">
                Quantity (lots)
              </label>
              <Input
                id="confirm-qty"
                type="number"
                min={1}
                max={9999}
                value={confirmQty}
                onChange={(e) => setConfirmQty(Math.max(1, Math.min(9999, Number(e.target.value) || 1)))}
                className="h-8 text-xs tabular-nums"
                autoFocus
              />
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <Button variant="outline" size="sm" className="flex-1" onClick={closeConfirm} ref={cancelRef}>
              Cancel
            </Button>
            <Button
              size="sm"
              className={`flex-1 text-white ${
                confirmAction === "BUY"
                  ? "bg-green-600 hover:bg-green-700"
                  : "bg-red-600 hover:bg-red-700"
              }`}
              onClick={() => {
                closeConfirm();
              }}
              aria-label={`Confirm ${confirmAction}`}
            >
              {confirmAction} {confirmQty}
            </Button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
