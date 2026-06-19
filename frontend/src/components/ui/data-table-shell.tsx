import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataState } from "@/components/ui/data-state";

interface DataTableShellProps {
  title: string;
  count?: number;
  loading: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyMessage?: string;
  emptyTitle?: string;
  children: ReactNode;
  minWidth?: string;
  className?: string;
}

export function DataTableShell({
  title,
  count,
  loading,
  error,
  onRetry,
  emptyMessage,
  emptyTitle,
  children,
  minWidth,
  className,
}: DataTableShellProps) {
  return (
    <Card className={`overflow-hidden ${className ?? ""}`}>
      <CardHeader className="flex-row items-center gap-2 border-b px-4 py-3">
        <CardTitle className="text-sm">{title}</CardTitle>
        {count !== undefined ? (
          <Badge variant="secondary">{count}</Badge>
        ) : null}
      </CardHeader>
      {loading ? (
        <DataState state="loading" />
      ) : error ? (
        <CardContent className="p-4">
          <DataState state="error" message={error} action={onRetry ? <button onClick={onRetry} className="mt-1 text-xs font-medium text-foreground underline underline-offset-2">Retry</button> : undefined} />
        </CardContent>
      ) : !count && count === 0 ? (
        <CardContent className="p-4">
          <DataState state="empty" title={emptyTitle ?? `No ${title.toLowerCase()}`} message={emptyMessage ?? "No data available."} />
        </CardContent>
      ) : (
        <div className="overflow-x-auto" style={minWidth ? { minWidth } : undefined}>
          {children}
        </div>
      )}
    </Card>
  );
}
