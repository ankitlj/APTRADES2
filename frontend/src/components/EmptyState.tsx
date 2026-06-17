import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  message: string;
  title?: string;
  icon?: LucideIcon;
  action?: ReactNode;
}

export function EmptyState({
  message,
  title = "Nothing to show yet",
  icon: Icon = Inbox,
  action,
}: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center"
      role="status"
    >
      <Icon className="h-8 w-8 text-muted-foreground/50" aria-hidden="true" />
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-sm text-xs text-muted-foreground">{message}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
