import { Loader2 } from "lucide-react";
import type * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ActionButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  loading?: boolean;
}

const variantMap: Record<string, React.ComponentProps<typeof Button>["variant"]> = {
  primary: "default",
  secondary: "secondary",
  danger: "destructive",
  ghost: "ghost",
};

export function ActionButton({ variant = "primary", loading = false, disabled, children, className, ...props }: ActionButtonProps) {
  return (
    <Button
      variant={variantMap[variant]}
      disabled={disabled || loading}
      className={cn("relative", className)}
      {...props}
    >
      {loading && (
        <Loader2 className="absolute h-4 w-4 animate-spin" aria-hidden="true" />
      )}
      <span className={cn(loading && "invisible")}>{children}</span>
    </Button>
  );
}
