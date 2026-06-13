import { cn } from "@/lib/utils";

type QuoteStatusProps = {
  status: string;
};

export function QuoteStatus({ status }: QuoteStatusProps) {
  const normalized = status.toLowerCase();
  return (
    <strong
      className={cn(
        "font-semibold",
        normalized === "ok"
          ? "text-green-600 dark:text-green-400"
          : normalized === "error"
            ? "text-red-500"
            : "text-muted-foreground"
      )}
    >
      {normalized}
    </strong>
  );
}
