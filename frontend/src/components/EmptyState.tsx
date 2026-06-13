import { Inbox } from "lucide-react";

interface EmptyStateProps {
  message: string;
  title?: string;
}

/** Consistent inline empty-state card. */
export function EmptyState({ message, title = "Nothing to show yet" }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <Inbox className="h-8 w-8 text-muted-foreground/50" />
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-sm text-xs text-muted-foreground">{message}</p>
    </div>
  );
}
