import type * as React from "react";

import { cn } from "@/lib/utils";

interface SurfaceCardProps {
  children: React.ReactNode;
  className?: string;
  tone?: "default" | "active" | "danger" | "success";
  interactive?: boolean;
  onClick?: () => void;
}

const toneBorder: Record<string, string> = {
  active: "border-l-[3px] border-l-sky-500/60",
  danger: "border-l-[3px] border-l-red-500/60",
  success: "border-l-[3px] border-l-green-500/60",
};

export function SurfaceCard({ children, className, tone = "default", interactive = false, onClick }: SurfaceCardProps) {
  return (
    <div
      data-slot="surface-card"
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={interactive ? onClick : undefined}
      onKeyDown={interactive ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick?.(); } } : undefined}
      className={cn(
        "rounded-xl border bg-card text-card-foreground shadow-sm dark:border-white/10 dark:bg-white/[0.035] dark:backdrop-blur-md",
        tone !== "default" && toneBorder[tone],
        interactive && [
          "cursor-pointer transition-[box-shadow,transform] duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)]",
          "hover:shadow-md hover:dark:border-white/20",
          "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
        ],
        className,
      )}
    >
      {children}
    </div>
  );
}
