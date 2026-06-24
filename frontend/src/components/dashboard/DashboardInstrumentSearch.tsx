import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

const TAB_PARAM: Record<SearchTab, string> = {
  all: "all",
  stocks: "stocks",
  fno: "fno",
};

const SECTION_LABELS: Record<string, string> = {
  cash: "Stocks",
  future: "Futures",
  option: "Options",
};

const DEFAULT_SECTION_ORDER: Record<string, number> = {
  cash: 0,
  future: 1,
  option: 2,
};

const DERIVATIVE_SECTION_ORDER: Record<string, number> = {
  option: 0,
  future: 1,
  cash: 2,
};

function hasDerivativeIntent(query: string): boolean {
  return /\b(CE|PE|FUT(?:URE)?S?)\b/i.test(query.trim());
}

function badgeClass(badge: string): string {
  switch (badge) {
    case "EQ":
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300";
    case "FUT":
      return "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300";
    case "OPT":
      return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
    case "CE":
      return "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300";
    case "PE":
      return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function exchangeClass(exchange: string): string {
  return exchange === "NSE"
    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
    : "bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300";
}

interface SectionedResults {
  kind: string;
  label: string;
  items: InstrumentSearchResult[];
  globalStartIdx: number;
}

function buildSections(results: InstrumentSearchResult[], query: string): SectionedResults[] {
  const groups: Record<string, InstrumentSearchResult[]> = {};
  for (const r of results) {
    const kind = r.instrument_kind || "cash";
    if (!groups[kind]) groups[kind] = [];
    groups[kind].push(r);
  }
  const order = hasDerivativeIntent(query) ? DERIVATIVE_SECTION_ORDER : DEFAULT_SECTION_ORDER;
  const kinds = Object.keys(groups).sort((a, b) => (order[a] ?? 99) - (order[b] ?? 99));
  const sections: SectionedResults[] = [];
  let offset = 0;
  for (const kind of kinds) {
    sections.push({ kind, label: SECTION_LABELS[kind] ?? kind, items: groups[kind], globalStartIdx: offset });
    offset += groups[kind].length;
  }
  return sections;
}

type SearchStatus = "idle" | "loading" | "empty" | "error" | "results";

export function DashboardInstrumentSearch({ isOpen, onClose, onSelect }: DashboardInstrumentSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstrumentSearchResult[]>([]);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tab, setTab] = useState<SearchTab>("all");
  const [activeIdx, setActiveIdx] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const sections = useMemo(() => buildSections(results, query), [results, query]);
  const hasQuery = query.trim().length > 0;

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setResults([]);
      setStatus("idle");
      setErrorMessage(null);
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
      setStatus("idle");
      setErrorMessage(null);
      return;
    }

    setStatus("loading");
    setErrorMessage(null);
    debounceRef.current = setTimeout(() => {
      searchInstruments(trimmed, TAB_PARAM[tab]).then(
        (data) => {
          setResults(data.results);
          setStatus(data.results.length === 0 ? "empty" : "results");
          setActiveIdx(0);
        },
        (reason: unknown) => {
          setResults([]);
          setStatus("error");
          setErrorMessage(reason instanceof Error ? reason.message : "Search failed");
        },
      );
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, tab, isOpen]);

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
        setActiveIdx((prev) => Math.min(prev + 1, results.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === "Enter" && results[activeIdx]) {
        handleSelect(results[activeIdx]);
      }
    },
    [onClose, results, activeIdx, handleSelect],
  );

  useEffect(() => {
    if (listRef.current && activeIdx >= 0) {
      const childIdx = activeIdx + sections.length;
      if (childIdx < listRef.current.children.length) {
        const item = listRef.current.children[childIdx] as HTMLElement | undefined;
        item?.scrollIntoView({ block: "nearest" });
      }
    }
  }, [activeIdx, sections.length]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[10vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Search instruments"
      onKeyDown={handleKeyDown}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex w-full max-w-lg flex-col rounded-xl border border-border/60 bg-background shadow-2xl dark:border-border/40">
        <div className="border-b border-border/50 px-4 py-3">
          <div className="relative">
            <svg
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/40"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <Input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='Search stocks, indices, futures, options... (e.g. "NIFTY", "SBIN")'
              className="h-10 border border-border/40 bg-muted/20 pl-9 pr-3 text-sm shadow-none transition-colors focus-visible:border-ring/50 focus-visible:ring-0"
              aria-label="Search instruments"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
        </div>

        <div className="flex gap-1 border-b border-border/50 px-3 py-2">
          {(["all", "stocks", "fno"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => {
                setTab(t);
                setActiveIdx(0);
                setResults([]);
                setStatus("idle");
                setErrorMessage(null);
                inputRef.current?.focus();
              }}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                tab === t
                  ? "bg-primary text-primary-foreground shadow-xs"
                  : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
              )}
              aria-pressed={tab === t}
            >
              {t === "all" ? "All" : t === "stocks" ? "Stocks" : "F&O"}
            </button>
          ))}
        </div>

        <div ref={listRef} className="max-h-[55vh] overflow-y-auto" role="listbox" aria-label="Search results" aria-activedescendant={status === "results" ? `search-result-${activeIdx}` : undefined}>
          {status === "loading" && (
            <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
              <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground/20 border-t-muted-foreground/60" />
              Searching...
            </div>
          )}

          {status === "error" && (
            <div className="flex flex-col items-center justify-center px-6 py-10 text-center" role="alert">
              <svg className="mb-2 h-8 w-8 text-destructive/40" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <p className="text-sm font-medium text-destructive">Search failed</p>
              {errorMessage && <p className="mt-1 max-w-xs text-xs text-muted-foreground">{errorMessage}</p>}
              <p className="mt-4 text-[10px] text-muted-foreground/40">Please try again</p>
            </div>
          )}

          {status === "empty" && (
            <div className="flex flex-col items-center justify-center py-12">
              <svg className="mb-2 h-8 w-8 text-muted-foreground/20" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <p className="text-sm text-muted-foreground">No matching instruments found</p>
              <p className="mt-1 text-xs text-muted-foreground/50">
                Try a different search term
              </p>
            </div>
          )}

          {status === "idle" && !hasQuery && (
            <div className="flex flex-col items-center justify-center py-12">
              <svg className="mb-2 h-8 w-8 text-muted-foreground/15" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <p className="text-xs text-muted-foreground/40">Type to search instruments</p>
            </div>
          )}

          {status === "results" && sections.map((section) => (
            <div key={section.kind}>
              <div className="sticky top-0 bg-background/95 px-4 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50 backdrop-blur-sm">
                {section.label}
              </div>
              {section.items.map((instrument, localIdx) => {
                const globalIdx = section.globalStartIdx + localIdx;
                const resultId = `search-result-${globalIdx}`;
                return (
                  <button
                    id={resultId}
                    key={`${instrument.id}-${instrument.broker_symbol}-${instrument.exchange_code}-${instrument.instrument_kind}-${instrument.expiry_date ?? ""}-${instrument.strike_price ?? ""}`}
                    type="button"
                    role="option"
                    aria-selected={globalIdx === activeIdx}
                    className={cn(
                      "flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors",
                      globalIdx === activeIdx
                        ? "bg-accent/60"
                        : "hover:bg-muted/30",
                    )}
                    onClick={() => handleSelect(instrument)}
                  >
                    <div className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-sm font-semibold text-foreground">
                        {instrument.label || instrument.display_symbol || instrument.broker_symbol}
                      </span>
                      {instrument.sublabel && (
                        <span className="mt-0.5 truncate text-[11px] text-muted-foreground/60">
                          {instrument.sublabel}
                        </span>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {instrument.badges.map((badge) => (
                        <span
                          key={badge}
                          className={cn(
                            "rounded px-1.5 py-0.5 text-[10px] font-medium",
                            ["CE", "PE", "EQ", "FUT", "OPT"].includes(badge)
                              ? badgeClass(badge)
                              : exchangeClass(badge),
                          )}
                        >
                          {badge}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {(status === "results" || status === "empty") && (
          <div className="border-t border-border/50 px-4 py-2 text-[10px] text-muted-foreground/35">
            <kbd className="rounded border border-border/50 bg-muted/30 px-1 font-mono text-[10px]">&uarr;</kbd>{" "}
            <kbd className="rounded border border-border/50 bg-muted/30 px-1 font-mono text-[10px]">&darr;</kbd> navigate{" "}
            <kbd className="rounded border border-border/50 bg-muted/30 px-1 font-mono text-[10px]">Enter</kbd> select{" "}
            <kbd className="rounded border border-border/50 bg-muted/30 px-1 font-mono text-[10px]">Esc</kbd> close
          </div>
        )}
      </div>
    </div>
  );
}
