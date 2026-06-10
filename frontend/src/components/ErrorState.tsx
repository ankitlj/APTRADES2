interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  title?: string;
}

/** Consistent inline error card with an optional retry action. */
export function ErrorState({ message, onRetry, title = "Something went wrong" }: ErrorStateProps) {
  return (
    <div className="state-card state-error" role="alert">
      <p className="state-title">{title}</p>
      <p className="state-message">{message}</p>
      {onRetry ? (
        <button type="button" className="toolbar-button state-retry" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
