import type * as React from "react";

import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  meta?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "neutral" | "positive" | "negative" | "warning";
  loading?: boolean;
  error?: string | null;
}

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted/40", className)}
      aria-hidden="true"
    />
  );
}

const toneText: Record<string, string> = {
  positive: "text-green-600 dark:text-green-400",
  negative: "text-red-500",
  warning: "text-amber-500",
};

export function MetricCard({ label, value, meta, icon, tone = "neutral", loading = false, error = null }: MetricCardProps) {
  return (
    <div
      data-slot="metric-card"
      className={cn(
        "flex min-h-[110px] flex-col justify-center rounded-xl border bg-card p-5 shadow-sm",
        "dark:border-white/10 dark:bg-white/[0.035] dark:backdrop-blur-md",
      )}
    >
      <div className="flex items-center gap-2">
        {icon && <span className="shrink-0 text-muted-foreground/70">{icon}</span>}
        <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
          {label}
        </p>
      </div>

      {loading ? (
        <div className="mt-3 space-y-2">
          <SkeletonBar className="h-7 w-3/5" />
          {meta && <SkeletonBar className="h-3 w-2/5" />}
        </div>
      ) : error ? (
        <p className="mt-3 text-xs text-red-500 dark:text-red-400">
          {error}
        </p>
      ) : (
        <>
          <p
            className={cn(
              "mt-3 text-2xl font-bold tabular-nums leading-none tracking-tight",
              tone !== "neutral" && toneText[tone],
            )}
          >
            {value}
          </p>
          {meta && (
            <p className="mt-2 text-xs text-muted-foreground">{meta}</p>
          )}
        </>
      )}
    </div>
  );
}
