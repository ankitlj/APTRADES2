import { cn } from "@/lib/utils";

export type StatTone = "positive" | "negative" | "neutral";

export function formatNumber(value: number | string | null | undefined, maximumFractionDigits = 2): string {
  if (value === null || value === undefined || value === "") return "n/a";
  const num = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(num)) return "n/a";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(num);
}

export function formatCurrency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "--";
  const num = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(num)) return "--";
  return `₹${new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)}`;
}

export function formatPercent(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "--";
  const num = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(num)) return "--";
  return `${formatNumber(num)}%`;
}

export function pnlColor(value: number | null | undefined) {
  if ((value ?? 0) > 0) return "text-green-600 dark:text-green-400";
  if ((value ?? 0) < 0) return "text-red-500";
  return "text-foreground";
}

export function tone(value: number | null | undefined): StatTone {
  if ((value ?? 0) > 0) return "positive";
  if ((value ?? 0) < 0) return "negative";
  return "neutral";
}

export function toneColor(tone: string | undefined) {
  if (tone === "positive") return "text-green-600 dark:text-green-400";
  if (tone === "negative") return "text-red-500";
  if (tone === "warning") return "text-amber-500";
  return "text-foreground";
}

export function alertDotColor(level: string) {
  if (level === "error") return "bg-red-500";
  if (level === "warning") return "bg-amber-500";
  if (level === "success") return "bg-green-500";
  return "bg-blue-500";
}
