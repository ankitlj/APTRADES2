type QuoteStatusProps = {
  status: string;
};

export function QuoteStatus({ status }: QuoteStatusProps) {
  const normalized = status.toLowerCase();
  const className =
    normalized === "ok"
      ? "status-value status-online"
      : normalized === "error"
        ? "status-value status-offline"
        : "status-value status-unknown";

  return <strong className={className}>{normalized}</strong>;
}
