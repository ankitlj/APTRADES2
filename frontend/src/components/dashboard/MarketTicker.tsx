import { useEffect, useState } from "react";

import { getDashboardSummary, type DashboardSummaryResponse } from "@/lib/api";
import { useLiveMarketData } from "@/hooks/useLiveMarketData";
import { cn } from "@/lib/utils";

interface TickerQuote {
  label: string;
  ltp: number | null;
  changePercent: number | null;
}

// Mirrors the APTRADES dashboard ticker: index quotes scrolling right -> left,
// merging the REST snapshot with any live websocket ticks. Data layer unchanged.
export function MarketTicker() {
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const { ticks } = useLiveMarketData();

  useEffect(() => {
    let mounted = true;
    getDashboardSummary()
      .then((data) => {
        if (mounted) setSummary(data);
      })
      .catch(() => {
        /* degraded-safe: ticker simply stays empty */
      });
    return () => {
      mounted = false;
    };
  }, []);

  const quotes: TickerQuote[] = (summary?.ticker ?? []).map((item) => {
    const live = ticks[item.symbol.toUpperCase()];
    return {
      label: item.symbol,
      ltp: live?.ltp ?? item.ltp,
      changePercent: live?.change_percent ?? item.change_percent,
    };
  });

  if (!quotes.length) {
    return <section className="min-w-0 flex-1 overflow-hidden" aria-label="Market index ticker" />;
  }

  const repeated = [...quotes, ...quotes];

  return (
    <section className="min-w-0 flex-1 overflow-hidden" aria-label="Market index ticker">
      <div className="market-ticker-track flex w-max items-center">
        {repeated.map((quote, index) => {
          const isPositive = (quote.changePercent ?? 0) >= 0;
          return (
            <div
              key={`${quote.label}-${index}`}
              className="flex items-center gap-2 border-r px-5 text-xs tabular-nums"
              aria-hidden={index >= quotes.length}
            >
              <span className="font-semibold text-foreground">{quote.label}</span>
              <span className="text-muted-foreground">
                {quote.ltp === null
                  ? "Unavailable"
                  : quote.ltp.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
              </span>
              {quote.changePercent !== null && (
                <span
                  className={cn(
                    "font-medium",
                    isPositive ? "text-green-600 dark:text-green-400" : "text-red-500"
                  )}
                >
                  {isPositive ? "+" : ""}
                  {quote.changePercent.toFixed(2)}%
                </span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
