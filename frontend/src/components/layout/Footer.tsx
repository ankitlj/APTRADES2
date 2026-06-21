import { cn } from "@/lib/utils";

export function Footer({ className }: { className?: string }) {
  return (
    <footer className={cn("mt-auto border-t bg-muted/30", className)}>
      <div className="px-4 py-4" />
    </footer>
  );
}
