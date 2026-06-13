import type { PropsWithChildren, ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function PageHeader({
  kicker,
  title,
  description,
  actions,
}: {
  kicker?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        {kicker ? (
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
            {kicker}
          </p>
        ) : null}
        <h1 className="mt-0.5 text-xl font-bold tracking-tight">{title}</h1>
        {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export type StatTone = "positive" | "negative" | "neutral";

export function StatCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  tone?: StatTone;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium uppercase tracking-[0.1em] text-muted-foreground">
          {label}
        </p>
        <p
          className={cn(
            "mt-1.5 text-xl font-bold tabular-nums",
            tone === "positive" && "text-green-600 dark:text-green-400",
            tone === "negative" && "text-red-500"
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

/** A labelled control used inside page toolbars. */
export function Field({ label, children }: PropsWithChildren<{ label: string }>) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}

export const selectClass =
  "h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50";

export function tone(value: number | null | undefined): StatTone {
  if ((value ?? 0) > 0) return "positive";
  if ((value ?? 0) < 0) return "negative";
  return "neutral";
}

export function pnlColor(value: number | null | undefined) {
  if ((value ?? 0) > 0) return "text-green-600 dark:text-green-400";
  if ((value ?? 0) < 0) return "text-red-500";
  return "text-foreground";
}
