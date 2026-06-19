import type * as React from "react";

import { cn } from "@/lib/utils";

type StatusType = "live" | "connected" | "stale" | "offline" | "loading" | "error" | "success" | "warning";

interface StatusBadgeProps {
  status: StatusType;
  children: React.ReactNode;
}

const statusStyles: Record<StatusType, string> = {
  live: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  connected: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300",
  stale: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  offline: "bg-muted text-muted-foreground dark:bg-muted/50",
  loading: "bg-muted text-muted-foreground dark:bg-muted/50",
  error: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  success: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  warning: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

const dotStyles: Record<StatusType, string> = {
  live: "bg-green-500",
  connected: "bg-sky-500",
  stale: "bg-amber-500",
  offline: "bg-muted-foreground/50",
  loading: "bg-muted-foreground/50",
  error: "bg-red-500",
  success: "bg-green-500",
  warning: "bg-amber-500",
};

export function StatusBadge({ status, children }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium leading-none",
        statusStyles[status],
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", dotStyles[status])} aria-hidden="true" />
      {children}
    </span>
  );
}
