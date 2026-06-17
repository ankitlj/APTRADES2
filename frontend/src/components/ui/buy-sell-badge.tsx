interface BuySellBadgeProps {
  action: string;
}

export function BuySellBadge({ action }: BuySellBadgeProps) {
  const isBuy = action.toUpperCase() === "BUY";
  return (
    <span className={isBuy ? "badge-buy" : "badge-sell"}>{action}</span>
  );
}
