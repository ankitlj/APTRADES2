import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useLiveQuote, useLiveSubscribe } from "@/hooks/useLiveMarketData";
import {
  getDashboardOrderbook,
  getOrderPreview,
  placeOrder,
  type DashboardOrderbookResponse,
  type InstrumentSearchResult,
  type OrderPreviewResponse,
  type PlaceOrderResponse,
} from "@/lib/api";
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
  const [confirmPrice, setConfirmPrice] = useState("");
  const [confirmProduct, setConfirmProduct] = useState<"MIS" | "NORMAL">("NORMAL");
  const [previewState, setPreviewState] = useState<{
    status: "idle" | "loading" | "refreshing" | "ok" | "error";
    data?: OrderPreviewResponse;
    error?: string;
  }>({ status: "idle" });
  const [placeState, setPlaceState] = useState<{
    status: "idle" | "placing" | "ok" | "error";
    data?: PlaceOrderResponse;
    error?: string;
  }>({ status: "idle" });

  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const hasValidDataRef = useRef(false);
  const previewIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const previewRequestIdRef = useRef(0);

  const cancelPending = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    abortRef.current = new AbortController();
  }, []);

  const stopPreviewInterval = useCallback(() => {
    if (previewIntervalRef.current !== null) {
      clearInterval(previewIntervalRef.current);
      previewIntervalRef.current = null;
    }
  }, []);

  const startPreviewInterval = useCallback(() => {
    stopPreviewInterval();
    previewIntervalRef.current = setInterval(() => {
      setPreviewState((prev) => {
        if (prev.status === "ok" || prev.status === "error") {
          return { ...prev, status: "refreshing" };
        }
        return prev;
      });
    }, 1000);
  }, [stopPreviewInterval]);

  const doFetchPreview = useCallback(
    (action: string, qty: number, price: string, product: string) => {
      if (!selectedInstrument) return;
      const reqId = ++previewRequestIdRef.current;

      const productType = selectedInstrument.instrument_kind === "option"
        ? "options"
        : selectedInstrument.instrument_kind === "future"
        ? "futures"
        : "cash";

      getOrderPreview({
        broker_symbol: selectedInstrument.broker_symbol,
        exchange_code: selectedInstrument.exchange_code,
        product_type: productType,
        action: action,
        quantity: qty,
        price: price ? parseFloat(price) : 0,
        expiry_date: selectedInstrument.expiry_date,
        right: selectedInstrument.right,
        strike_price: selectedInstrument.strike_price,
      }).then((res) => {
        if (reqId !== previewRequestIdRef.current) return;
        setPreviewState({ status: "ok", data: res });
      }).catch((err: Error) => {
        if (reqId !== previewRequestIdRef.current) return;
        setPreviewState((prev) => ({ status: "error", error: err.message, data: prev.data }));
      });
    },
    [selectedInstrument],
  );

  const handleSelect = useCallback((instrument: InstrumentSearchResult) => {
    setSelectedInstrument(instrument);
    setOrderbook({ status: "loading" });
    hasValidDataRef.current = false;
    setConfirmQty(1);
    setConfirmPrice("");
  }, []);

  const handleChange = useCallback(() => {
    setSearchOpen(true);
  }, []);

  const openConfirm = useCallback((action: "BUY" | "SELL") => {
    setConfirmAction(action);
    setConfirmQty(1);
    setConfirmPrice("");
    setConfirmProduct("NORMAL");
    setPreviewState({ status: "loading" });
    setPlaceState({ status: "idle" });
    setConfirmQty(1);
  }, []);

  const closeConfirm = useCallback(() => {
    stopPreviewInterval();
    previewRequestIdRef.current++;
    setConfirmAction(null);
    setPreviewState({ status: "idle" });
    setPlaceState({ status: "idle" });
  }, [stopPreviewInterval]);

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

  useEffect(() => {
    if (!confirmAction || !selectedInstrument) return;

    if (previewState.status === "loading") {
      doFetchPreview(confirmAction, confirmQty, confirmPrice, confirmProduct);
      startPreviewInterval();
    } else if (previewState.status === "refreshing") {
      doFetchPreview(confirmAction, confirmQty, confirmPrice, confirmProduct);
    }
  }, [
    confirmAction,
    confirmQty,
    confirmPrice,
    confirmProduct,
    previewState.status,
    selectedInstrument,
    doFetchPreview,
    startPreviewInterval,
  ]);

  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    setValidationError(null);
  }, [confirmPrice, confirmQty, confirmAction]);

  const validateOrder = useCallback((): string | null => {
    if (!confirmPrice || parseFloat(confirmPrice) <= 0) {
      return "Price must be greater than 0";
    }
    if (!confirmQty || confirmQty < 1) {
      return "Quantity must be at least 1";
    }
    if (selectedInstrument?.lot_size && confirmQty * selectedInstrument.lot_size > 999999) {
      return "Total quantity exceeds maximum allowed";
    }
    return null;
  }, [confirmPrice, confirmQty, selectedInstrument]);

  const handlePlaceOrder = useCallback(() => {
    setValidationError(null);

    const error = validateOrder();
    if (error) {
      setValidationError(error);
      return;
    }

    if (!selectedInstrument || !confirmAction) return;

    setPlaceState({ status: "placing" });

    const productType = selectedInstrument.instrument_kind === "option"
      ? "options"
      : selectedInstrument.instrument_kind === "future"
      ? "futures"
      : "cash";

    const price = confirmPrice ? parseFloat(confirmPrice) : 0;

    placeOrder({
      broker_symbol: selectedInstrument.broker_symbol,
      exchange_code: selectedInstrument.exchange_code,
      product_type: productType,
      action: confirmAction,
      quantity: confirmQty,
      price: price,
      expiry_date: selectedInstrument.expiry_date,
      right: selectedInstrument.right,
      strike_price: selectedInstrument.strike_price,
    }).then((res) => {
      setPlaceState({ status: "ok", data: res });
    }).catch((err: Error) => {
      setPlaceState({ status: "error", error: err.message });
    });
  }, [selectedInstrument, confirmAction, confirmQty, confirmPrice, validateOrder]);

  const orderbookData = orderbook.status === "ok" ? orderbook.data : null;
  const liveTick = useLiveQuote(orderbookData?.instrument?.display_symbol ?? null);
  const hasSelection = Boolean(selectedInstrument);

  const effectiveLtp = liveTick?.ltp ?? orderbookData?.ltp ?? null;
  const effectiveBidPrice = liveTick?.bid_price ?? orderbookData?.bid_price ?? null;
  const effectiveAskPrice = liveTick?.ask_price ?? orderbookData?.ask_price ?? null;
  const effectiveBidQty = liveTick?.bid_qty ?? orderbookData?.bid_qty ?? null;
  const effectiveAskQty = liveTick?.ask_qty ?? orderbookData?.ask_qty ?? null;
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
      <div className="flex items-center justify-between gap-3 border-b px-4 py-2">
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
      </div>

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

    {confirmAction && selectedInstrument && (
      <div
        className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 pt-12"
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
          <div className="flex items-center justify-between">
            <h3
              id="confirm-title"
              className={`text-sm font-semibold ${
                confirmAction === "BUY" ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
              }`}
            >
              {confirmAction}
            </h3>
            <div className="flex items-center gap-2">
              {previewState.status === "loading" && (
                <span className="text-[10px] text-muted-foreground/60">Loading preview...</span>
              )}
              {previewState.status === "refreshing" && (
                <span className="text-[10px] text-muted-foreground/60">Refreshing...</span>
              )}
              <button
                onClick={closeConfirm}
                className="text-muted-foreground/50 hover:text-foreground"
                aria-label="Close"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="2" y1="2" x2="12" y2="12" />
                  <line x1="12" y1="2" x2="2" y2="12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Instrument info */}
          <div className="mt-3 rounded-md border bg-muted/20 px-3 py-2 text-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-muted-foreground">Contract</span>
              <span className="font-medium text-foreground">{instrumentLabel(selectedInstrument)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">LTP</span>
              <span className="font-medium tabular-nums text-foreground">
                {effectiveLtp != null ? formatNumber(effectiveLtp) : "\u2014"}
              </span>
            </div>
          </div>

          {/* Price input */}
          <div className="mt-3">
            <label htmlFor="confirm-price" className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Price
            </label>
            <Input
              id="confirm-price"
              type="number"
              step="any"
              min={0}
              value={confirmPrice}
              onChange={(e) => setConfirmPrice(e.target.value)}
              placeholder={effectiveLtp != null ? String(effectiveLtp) : "0"}
              className="h-8 text-xs tabular-nums"
              autoFocus
            />
          </div>

          {/* Quantity input with lot size info */}
          <div className="mt-3">
            <label htmlFor="confirm-qty" className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Quantity (lots)
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="confirm-qty"
                type="number"
                min={1}
                max={9999}
                value={confirmQty}
                onChange={(e) => setConfirmQty(Math.max(1, Math.min(9999, Number(e.target.value) || 1)))}
                className="h-8 flex-1 text-xs tabular-nums"
              />
              {selectedInstrument.lot_size && selectedInstrument.lot_size > 1 && (
                <span className="whitespace-nowrap text-[10px] text-muted-foreground/60">
                  {selectedInstrument.lot_size} lot{selectedInstrument.lot_size > 1 ? "s" : ""}
                </span>
              )}
            </div>
          </div>

          {/* Margin preview section */}
          <div className="mt-3 rounded-md border px-3 py-2 text-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-medium text-muted-foreground">Margin Preview</span>
              {previewState.status === "ok" && (
                <span className="text-[9px] text-green-600 dark:text-green-400">Live</span>
              )}
              {previewState.status === "error" && (
                <span className="text-[9px] text-red-500">Error</span>
              )}
            </div>
            {previewState.status === "loading" && (
              <div className="py-2 text-center text-[10px] text-muted-foreground/50">
                Loading margin...
              </div>
            )}
            {previewState.status === "ok" && previewState.data && (
              <>
                {previewState.data.preview.margin.margin_status === "not_calculated" && (
                  <div className="text-[10px] text-muted-foreground/60">
                    Margin not calculated (cash product or zero price).
                  </div>
                )}
                {previewState.data.preview.margin.margin_status === "error" && (
                  <div className="text-[10px] text-red-500">
                    {previewState.data.preview.margin.error ?? "Margin calculation failed"}
                  </div>
                )}
                {(previewState.data.preview.margin.margin_status === "success" || previewState.data.preview.margin.margin_status === "ok") && (
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground/70">Total Margin</span>
                      <span className="font-medium tabular-nums text-foreground">
                        {previewState.data.preview.margin.total_margin != null
                          ? formatNumber(previewState.data.preview.margin.total_margin)
                          : "\u2014"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground/70">Order Value</span>
                      <span className="font-medium tabular-nums text-foreground">
                        {previewState.data.preview.margin.order_value != null
                          ? formatNumber(previewState.data.preview.margin.order_value)
                          : "\u2014"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground/70">Span Margin</span>
                      <span className="font-medium tabular-nums text-foreground">
                        {previewState.data.preview.margin.span_margin != null
                          ? formatNumber(previewState.data.preview.margin.span_margin)
                          : "\u2014"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground/70">Non-Span Margin</span>
                      <span className="font-medium tabular-nums text-foreground">
                        {previewState.data.preview.margin.non_span_margin != null
                          ? formatNumber(previewState.data.preview.margin.non_span_margin)
                          : "\u2014"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground/70">Trade Margin</span>
                      <span className="font-medium tabular-nums text-foreground">
                        {previewState.data.preview.margin.trade_margin != null
                          ? formatNumber(previewState.data.preview.margin.trade_margin)
                          : "\u2014"}
                      </span>
                    </div>
                  </div>
                )}
              </>
            )}
            {previewState.status === "error" && (
              <div className="text-[10px] text-red-500">{previewState.error}</div>
            )}
          </div>

          {/* Funds section */}
          <div className="mt-2 rounded-md border px-3 py-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-medium text-muted-foreground">Available Funds</span>
            </div>
            {previewState.status === "ok" && previewState.data?.preview.funds.fund_status === "ok" && (

              <>
                <div className="mt-1 flex justify-between">
                  <span className="text-muted-foreground/70">Balance</span>
                  <span className="font-medium tabular-nums text-foreground">
                    {previewState.data.preview.funds.unallocated_balance != null
                      ? formatNumber(previewState.data.preview.funds.unallocated_balance)
                      : "\u2014"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground/70">Blocked</span>
                  <span className="font-medium tabular-nums text-foreground">
                    {previewState.data.preview.funds.blocked_by_trade != null
                      ? formatNumber(previewState.data.preview.funds.blocked_by_trade)
                      : "\u2014"}
                  </span>
                </div>
              </>
            )}
            {previewState.status === "ok" && previewState.data?.preview.funds.fund_status === "error" && (
              <div className="mt-1 text-[10px] text-red-500">{previewState.data.preview.funds.error}</div>
            )}
            {previewState.status === "loading" && (
              <div className="py-1 text-center text-[10px] text-muted-foreground/50">
                Loading funds...
              </div>
            )}
          </div>

          {/* Validation error */}
          {validationError && (
            <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-400">
              {validationError}
            </div>
          )}

          {/* Place order error/success */}
          {placeState.status === "error" && (
            <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-400">
              {placeState.error}
            </div>
          )}
          {placeState.status === "ok" && placeState.data && (
            <div className="mt-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700 dark:border-green-900/50 dark:bg-green-950/20 dark:text-green-400">
              {(placeState.data.status === "success" || placeState.data.status === "ok")
                ? `Order placed: ${placeState.data.order_id}`
                : placeState.data.message ?? "Order placed"}
            </div>
          )}

          {/* Action buttons */}
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
              disabled={
                placeState.status === "placing" ||
                placeState.status === "ok"
              }
              onClick={handlePlaceOrder}
              aria-label={`Place ${confirmAction} order`}
            >
              {placeState.status === "placing"
                ? "Placing..."
                : placeState.status === "ok"
                ? "Placed"
                : `${confirmAction} ${confirmQty}`}
            </Button>
          </div>

          {selectedInstrument.lot_size && selectedInstrument.lot_size > 1 && (
            <p className="mt-2 text-[9px] text-muted-foreground/40">
              Total qty: {confirmQty} &times; {selectedInstrument.lot_size} = {confirmQty * selectedInstrument.lot_size}
            </p>
          )}
        </div>
      </div>
    )}
    </>
  );
}
