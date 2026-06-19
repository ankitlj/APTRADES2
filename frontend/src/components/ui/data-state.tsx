import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type * as React from "react";

import { cn } from "@/lib/utils";

interface DataStateProps {
  state: "loading" | "empty" | "error";
  title?: string;
  message?: string;
  action?: React.ReactNode;
  compact?: boolean;
}

export function DataState({ state, title, message, action, compact = false }: DataStateProps) {
  if (state === "loading") {
    return (
      <div
        role="status"
        className={cn(
          "flex items-center justify-center gap-2 text-sm text-muted-foreground",
          compact ? "py-4" : "py-10",
        )}
      >
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        <span>{title ?? "Loading..."}</span>
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center px-6 text-center",
          compact ? "py-6" : "py-10",
        )}
        role="status"
      >
        <Inbox className={cn("text-muted-foreground/40", compact ? "h-6 w-6" : "h-8 w-8")} aria-hidden="true" />
        <p className={cn("mt-2 font-medium text-foreground", compact ? "text-xs" : "text-sm")}>
          {title ?? "Nothing to show"}
        </p>
        {message && (
          <p className={cn("mt-1 max-w-sm text-muted-foreground", compact ? "text-[11px]" : "text-xs")}>
            {message}
          </p>
        )}
        {action && <div className="mt-3">{action}</div>}
      </div>
    );
  }

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3",
        compact && "py-2",
      )}
    >
      <p className="flex items-center gap-2 text-sm font-semibold text-destructive">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        {title ?? "Something went wrong"}
      </p>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      {action}
    </div>
  );
}
