import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/ui/loading";

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
        <LoadingState />
      ) : error ? (
        <CardContent className="p-4">
          <ErrorState message={error} onRetry={onRetry} />
        </CardContent>
      ) : !count && count === 0 ? (
        <EmptyState
          title={emptyTitle ?? `No ${title.toLowerCase()}`}
          message={emptyMessage ?? "No data available."}
        />
      ) : (
        <div className="overflow-x-auto" style={minWidth ? { minWidth } : undefined}>
          {children}
        </div>
      )}
    </Card>
  );
}
