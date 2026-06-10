interface EmptyStateProps {
  message: string;
  title?: string;
}

/** Consistent inline empty-state card. */
export function EmptyState({ message, title = "Nothing to show yet" }: EmptyStateProps) {
  return (
    <div className="state-card state-empty">
      <p className="state-title">{title}</p>
      <p className="state-message">{message}</p>
    </div>
  );
}
