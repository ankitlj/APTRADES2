import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useLiveQuote, useLiveSubscribe } from "@/hooks/useLiveMarketData";
import { getDashboardOrderbook, type DashboardOrderbookResponse, type InstrumentSearchResult } from "@/lib/api";
import type { SubscriptionRequest } from "@/lib/realtime";
import { formatNumber } from "@/lib/format";
import { DashboardInstrumentSearch } from "./DashboardInstrumentSearch";

const POLL_INTERVAL_MS = 2500;

type FetchState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ok"; data: T };

function instrumentLabel(instrument: InstrumentSearchResult): string {
  return instrument.label || instrument.broker_symbol;
}

function instrumentShortLabel(instrument: InstrumentSearchResult): string {
  if (instrument.instrument_kind === "option") {
    return `${instrument.display_strike ?? instrument.strike_price ?? "?"} ${instrument.right ?? ""}`;
  }
  if (instrument.instrument_kind === "future" && instrument.expiry_date) {
    return instrument.expiry_date.slice(0, 10);
  }
  return instrument.broker_symbol;
}

function productBadge(kind: string): string {
  if (kind === "cash") return "EQ";
  if (kind === "future") return "FUT";
  if (kind === "option") return "OPT";
  return kind.toUpperCase();
}

export function DashboardOptionOrderBook() {
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentSearchResult | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [orderbook, setOrderbook] = useState<FetchState<DashboardOrderbookResponse>>({ status: "idle" });
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

  const handleSelect = useCallback((instrument: InstrumentSearchResult) => {
    setSelectedInstrument(instrument);
    setOrderbook({ status: "loading" });
    hasValidDataRef.current = false;
    setConfirmQty(1);
  }, []);

  const handleChange = useCallback(() => {
    setSearchOpen(true);
  }, []);

  const openConfirm = useCallback((action: "BUY" | "SELL") => {
    setConfirmAction(action);
    setConfirmQty(1);
  }, []);

  const closeConfirm = useCallback(() => {
    setConfirmAction(null);
  }, []);

  const orderbookSubscriptions: SubscriptionRequest[] = selectedInstrument
    ? [
        {
          symbol: selectedInstrument.broker_symbol,
          exchange: selectedInstrument.exchange_code,
          product_type: selectedInstrument.product_type,
        },
      ]
    : [];
  useLiveSubscribe(orderbookSubscriptions);

  useEffect(() => {
    if (!selectedInstrument) {
      hasValidDataRef.current = false;
      return;
    }

    cancelPending();
    const signal = abortRef.current!.signal;
    setOrderbook({ status: "loading" });

    const fetchData = () => {
      getDashboardOrderbook({
        broker_symbol: selectedInstrument.broker_symbol,
        exchange_code: selectedInstrument.exchange_code,
        product_type: selectedInstrument.instrument_kind === "option" ? "options" : selectedInstrument.instrument_kind === "future" ? "futures" : "cash",
        expiry_date: selectedInstrument.expiry_date,
        right: selectedInstrument.right ? selectedInstrument.right.toLowerCase() : null,
        strike_price: selectedInstrument.strike_price,
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
  }, [selectedInstrument, cancelPending]);

  const orderbookData = orderbook.status === "ok" ? orderbook.data : null;
  const liveTick = useLiveQuote(orderbookData?.instrument?.display_symbol ?? null);
  const hasSelection = Boolean(selectedInstrument);
  const isLive = orderbook.status === "ok" && orderbookData?.status === "ok";

  const effectiveLtp = liveTick?.ltp ?? orderbookData?.ltp ?? null;
  const effectiveBidPrice = liveTick?.bid_price ?? orderbookData?.bid_price ?? null;
  const effectiveAskPrice = liveTick?.ask_price ?? orderbookData?.ask_price ?? null;
  const effectiveBidQty = liveTick?.bid_qty ?? orderbookData?.bid_qty ?? null;
  const effectiveAskQty = liveTick?.ask_qty ?? orderbookData?.ask_qty ?? null;
  const effectiveTotalBuyQty = liveTick?.total_buy_qty ?? orderbookData?.total_buy_qty ?? 0;
  const effectiveTotalSellQty = liveTick?.total_sell_qty ?? orderbookData?.total_sell_qty ?? 0;

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
      const isError = orderbookData?.status === "error";
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
        Inactive
      </span>
    );
  };

  return (
    <>
    <Card className="overflow-hidden">
      <CardHeader className="min-h-14 gap-3 border-b px-4 py-3 md:flex-row md:items-center md:justify-between">
        <CardTitle className="text-sm">Order Book</CardTitle>
        <div className="flex items-center gap-2">
          {hasSelection && (
            <button
              onClick={handleChange}
              className="text-[11px] font-medium text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              Change
            </button>
          )}
          {statusBadge()}
        </div>
      </CardHeader>

      <CardContent className="space-y-3 p-4">
        <div>
          <label className="mb-1 block text-[10px] font-medium text-muted-foreground">
            Instrument
          </label>
          <button
            onClick={() => setSearchOpen(true)}
            className="flex h-9 w-full items-center justify-between rounded-md border bg-background px-3 text-xs text-muted-foreground shadow-xs hover:border-ring hover:text-foreground focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] focus-visible:outline-none"
          >
            {hasSelection && selectedInstrument ? (
              <span className="flex items-center gap-2">
                <span className="font-semibold text-foreground">
                  {selectedInstrument.display_symbol || selectedInstrument.broker_symbol}
                </span>
                <span className="rounded bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {productBadge(selectedInstrument.instrument_kind)}
                </span>
                <span className="rounded bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {selectedInstrument.exchange_code}
                </span>
                {(selectedInstrument.instrument_kind === "option" || selectedInstrument.instrument_kind === "future") && selectedInstrument.expiry_date && (
                  <span className="text-muted-foreground/60">
                    {instrumentShortLabel(selectedInstrument)}
                  </span>
                )}
              </span>
            ) : (
              <span className="text-muted-foreground/60">Search instrument...</span>
            )}
            <kbd className="rounded border bg-muted px-1 font-mono text-[10px] text-muted-foreground/50">
              /
            </kbd>
          </button>
        </div>

        {hasSelection && orderbookData && (
          <div className="flex items-center justify-between rounded-md border bg-muted/20 px-3 py-2">
            <div className="flex items-center gap-3 text-xs">
              <span className="font-semibold text-foreground">
                {orderbookData.instrument.broker_symbol}
              </span>
              <span className="text-muted-foreground">|</span>
              <span className="font-medium text-foreground">
                {orderbookData.product_type.toUpperCase()}
              </span>
              <span className="text-muted-foreground">|</span>
              <span className="tabular-nums text-muted-foreground">
                LTP:{" "}
                {orderbook.status === "loading" ? (
                  "..."
                ) : effectiveLtp != null ? (
                  formatNumber(effectiveLtp)
                ) : (
                  <span className="text-muted-foreground/50">N/A</span>
                )}
              </span>
            </div>
          </div>
        )}

        {!hasSelection && (
          <div className="flex min-h-[36px] items-center justify-center rounded-md border border-dashed bg-muted/10 px-3 text-xs text-muted-foreground/60">
            Search and select an instrument to view the order book
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
                {orderbookData && orderbookData.status === "ok" ? (
                  <tr className="border-b border-border/40">
                    <td className="px-3 py-2 text-green-600 dark:text-green-400">
                      {effectiveBidQty != null ? formatNumber(effectiveBidQty, 0) : "\u2014"}
                    </td>
                    <td className="px-3 py-2 text-right text-green-600 dark:text-green-400">
                      {effectiveBidPrice != null ? formatNumber(effectiveBidPrice) : "\u2014"}
                    </td>
                    <td className="px-3 py-2 text-right text-red-500">
                      {effectiveAskPrice != null ? formatNumber(effectiveAskPrice) : "\u2014"}
                    </td>
                    <td className="px-3 py-2 text-right text-red-500">
                      {effectiveAskQty != null ? formatNumber(effectiveAskQty, 0) : "\u2014"}
                    </td>
                  </tr>
                ) : orderbook.status === "loading" ? (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-[10px] text-muted-foreground/50">
                      Loading...
                    </td>
                  </tr>
                  ) : hasSelection && !orderbookData ? (
                  <tr className="border-b border-border/40">
                    <td className="px-3 py-2 text-green-600 dark:text-green-400">\u2014</td>
                    <td className="px-3 py-2 text-right text-green-600 dark:text-green-400">\u2014</td>
                    <td className="px-3 py-2 text-right text-red-500">\u2014</td>
                    <td className="px-3 py-2 text-right text-red-500">\u2014</td>
                  </tr>
                ) : (
                  <tr>
                    <td colSpan={4} className="px-3 py-6 text-center text-[10px] text-muted-foreground/50">
                      No instrument selected
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
                <span>Buy: {formatNumber(effectiveTotalBuyQty, 0)}</span>
                <span>Sell: {formatNumber(effectiveTotalSellQty, 0)}</span>
              </div>
            </div>
          ) : orderbook.status === "loading" ? (
            <p className="text-[10px] text-muted-foreground/50">Loading depth data...</p>
          ) : orderbook.status === "error" ? (
            <p className="text-[10px] text-muted-foreground/50">Failed to load depth data</p>
          ) : (
            <p className="text-[10px] text-muted-foreground/50">
              Depth data will appear when an instrument is selected
            </p>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            variant="default"
            disabled={!hasSelection || orderbook.status !== "ok" || orderbookData?.status !== "ok"}
            className="flex-1 bg-green-600 text-white hover:bg-green-700 disabled:opacity-30"
            aria-label="Buy selected instrument"
            onClick={() => openConfirm("BUY")}
          >
            BUY
          </Button>
          <Button
            variant="destructive"
            disabled={!hasSelection || orderbook.status !== "ok" || orderbookData?.status !== "ok"}
            className="flex-1 disabled:opacity-30"
            aria-label="Sell selected instrument"
            onClick={() => openConfirm("SELL")}
          >
            SELL
          </Button>
        </div>
      </CardContent>
    </Card>

    <DashboardInstrumentSearch
      isOpen={searchOpen}
      onClose={() => setSearchOpen(false)}
      onSelect={handleSelect}
    />

    {confirmAction && orderbookData && selectedInstrument && (
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
                {instrumentLabel(selectedInstrument)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">LTP</span>
              <span className="font-medium tabular-nums text-foreground">
                {effectiveLtp != null ? formatNumber(effectiveLtp) : "\u2014"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Bid / Ask</span>
              <span className="font-medium tabular-nums text-foreground">
                {effectiveBidPrice != null ? formatNumber(effectiveBidPrice) : "\u2014"} /{" "}
                {effectiveAskPrice != null ? formatNumber(effectiveAskPrice) : "\u2014"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Spread</span>
              <span className="font-medium tabular-nums text-foreground">
                {effectiveBidPrice != null && effectiveAskPrice != null
                  ? formatNumber(effectiveAskPrice - effectiveBidPrice)
                  : "\u2014"}
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
