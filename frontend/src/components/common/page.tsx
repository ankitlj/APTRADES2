import type { LucideIcon } from "lucide-react";
import type { PropsWithChildren, ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export { tone, pnlColor, toneColor } from "@/lib/format";

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
  icon: Icon,
}: {
  label: string;
  value: ReactNode;
  tone?: StatTone;
  icon?: LucideIcon;
}) {
  return (
    <Card className="glow-card overflow-hidden dark:bg-white/[0.04] dark:backdrop-blur-md">
      <CardContent className="relative p-4">
        {Icon ? <Icon className="engraved-icon h-24 w-24" aria-hidden="true" /> : null}
        <div className="relative flex items-center gap-2">
          {Icon ? <Icon className="glow-icon h-4 w-4 shrink-0" aria-hidden="true" /> : null}
          <p className="text-xs font-medium uppercase tracking-[0.1em] text-muted-foreground">
            {label}
          </p>
        </div>
        <p
          className={cn(
            "relative mt-1.5 text-xl font-bold tabular-nums",
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
