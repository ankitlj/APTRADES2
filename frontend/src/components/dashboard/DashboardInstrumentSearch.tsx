import { useCallback, useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { searchInstruments, type InstrumentSearchResult } from "@/lib/api";
import { cn } from "@/lib/utils";

const DEBOUNCE_MS = 250;

type SearchTab = "all" | "stocks" | "fno";

interface DashboardInstrumentSearchProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (instrument: InstrumentSearchResult) => void;
}

function productLabel(productType: string): string {
  switch (productType) {
    case "cash":
      return "EQ";
    case "futures":
      return "FUT";
    case "options":
      return "OPT";
    default:
      return productType.toUpperCase();
  }
}

function productBadgeColor(productType: string): string {
  switch (productType) {
    case "cash":
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300";
    case "futures":
      return "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300";
    case "options":
      return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function exchangeBadgeColor(exchange: string): string {
  return exchange === "NSE"
    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
    : "bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300";
}

function matchesTab(instrument: InstrumentSearchResult, tab: SearchTab): boolean {
  if (tab === "all") return true;
  if (tab === "stocks") return instrument.product_type === "cash";
  return instrument.product_type === "futures" || instrument.product_type === "options";
}

export function DashboardInstrumentSearch({ isOpen, onClose, onSelect }: DashboardInstrumentSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstrumentSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<SearchTab>("all");
  const [activeIdx, setActiveIdx] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setResults([]);
      setTab("all");
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const trimmed = query.trim();
    if (trimmed.length < 1) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(() => {
      searchInstruments(trimmed).then(
        (data) => {
          setResults(data.results);
          setActiveIdx(0);
          setLoading(false);
        },
        () => {
          setResults([]);
          setLoading(false);
        },
      );
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, isOpen]);

  const filtered = results.filter((r) => matchesTab(r, tab));

  const handleSelect = useCallback(
    (instrument: InstrumentSearchResult) => {
      onSelect(instrument);
      onClose();
    },
    [onSelect, onClose],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((prev) => Math.min(prev + 1, filtered.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === "Enter" && filtered[activeIdx]) {
        handleSelect(filtered[activeIdx]);
      }
    },
    [onClose, filtered, activeIdx, handleSelect],
  );

  useEffect(() => {
    if (listRef.current && activeIdx >= 0) {
      const item = listRef.current.children[activeIdx] as HTMLElement | undefined;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIdx]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Search instruments"
      onKeyDown={handleKeyDown}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-lg overflow-hidden rounded-xl border bg-background shadow-2xl">
        <div className="border-b px-4 py-3">
          <Input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Search stocks, indices, futures, options... (e.g. "NIFTY", "SBIN")'
            className="h-10 border-none bg-muted/30 pl-3 text-sm shadow-none focus-visible:ring-0"
            aria-label="Search instruments"
          />
        </div>

        <div className="flex gap-1 border-b px-3 py-2">
          {(["all", "stocks", "fno"] as const).map((t) => (
            <button
              key={t}
              onClick={() => {
                setTab(t);
                setActiveIdx(0);
              }}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                tab === t
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
              )}
            >
              {t === "all" ? "All" : t === "stocks" ? "Stocks" : "F&O"}
            </button>
          ))}
        </div>

        <div ref={listRef} className="max-h-[50vh] overflow-y-auto" role="listbox" aria-label="Search results">
          {loading && results.length === 0 && (
            <div className="flex items-center justify-center py-10 text-xs text-muted-foreground">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground mr-2" />
              Searching...
            </div>
          )}

          {!loading && query.trim().length > 0 && filtered.length === 0 && (
            <div className="flex flex-col items-center justify-center py-10">
              <p className="text-sm text-muted-foreground">No matching instruments found</p>
              <p className="mt-1 text-xs text-muted-foreground/50">
                Try a different search term
              </p>
            </div>
          )}

          {!query.trim() && (
            <div className="flex flex-col items-center justify-center py-10">
              <p className="text-xs text-muted-foreground/50">Type to search instruments</p>
            </div>
          )}

          {filtered.map((instrument, idx) => (
            <button
              key={`${instrument.broker_symbol}-${instrument.exchange_code}-${instrument.product_type}-${instrument.expiry_date ?? ""}-${instrument.strike_price ?? ""}`}
              role="option"
              aria-selected={idx === activeIdx}
              className={cn(
                "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors",
                idx === activeIdx
                  ? "bg-muted/50"
                  : "hover:bg-muted/20",
              )}
              onClick={() => handleSelect(instrument)}
            >
              <div className="flex min-w-0 flex-1 flex-col">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold text-foreground">
                    {instrument.display_symbol || instrument.broker_symbol}
                  </span>
                  {instrument.name && (
                    <span className="truncate text-xs text-muted-foreground">
                      {instrument.name}
                    </span>
                  )}
                </div>
                {instrument.product_type === "options" && instrument.expiry_date && (
                  <span className="mt-0.5 truncate text-[11px] tabular-nums text-muted-foreground/60">
                    {instrument.expiry_date.slice(0, 10)}{" "}
                    {instrument.strike_price && `${instrument.strike_price} `}
                    {instrument.option_right === "call" ? "CE" : instrument.option_right === "put" ? "PE" : ""}
                  </span>
                )}
                {instrument.product_type === "futures" && instrument.expiry_date && (
                  <span className="mt-0.5 truncate text-[11px] tabular-nums text-muted-foreground/60">
                    {instrument.expiry_date.slice(0, 10)}
                  </span>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", exchangeBadgeColor(instrument.exchange_code))}>
                  {instrument.exchange_code}
                </span>
                <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", productBadgeColor(instrument.product_type))}>
                  {productLabel(instrument.product_type)}
                </span>
              </div>
            </button>
          ))}
        </div>

        <div className="border-t px-4 py-2 text-[10px] text-muted-foreground/40">
          <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">&uarr;</kbd> <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">&darr;</kbd> navigate{" "}
          <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">Enter</kbd> select{" "}
          <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">Esc</kbd> close
        </div>
      </div>
    </div>
  );
}
