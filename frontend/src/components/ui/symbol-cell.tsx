interface SymbolCellProps {
  symbol: string;
  exchange?: string | null;
  product?: string | null;
  brokerSymbol?: string | null;
}

export function SymbolCell({ symbol, exchange, product, brokerSymbol }: SymbolCellProps) {
  const subtitle = [exchange, product].filter(Boolean).join(" \u00B7 ");
  return (
    <td className="px-4 py-3">
      <div className="font-semibold">{symbol}</div>
      {brokerSymbol ? (
        <div className="text-xs text-muted-foreground">{brokerSymbol}</div>
      ) : subtitle ? (
        <div className="text-xs text-muted-foreground">{subtitle}</div>
      ) : null}
    </td>
  );
}
