import { cn } from "@/lib/utils";

export function Footer({ className }: { className?: string }) {
  return (
    <footer className={cn("mt-auto border-t bg-muted/30", className)}>
      <div className="px-4 py-4">
        <div className="flex items-center justify-start gap-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">TRACK</span>
          <span className="opacity-40">|</span>
          <span className="font-medium text-foreground">TRADE</span>
          <span className="opacity-40">|</span>
          <span className="font-medium text-foreground">TRIUMPH</span>
          <span className="opacity-40 mx-1">-</span>
          <span>ORIENS Trading Dashboard</span>
        </div>
      </div>
    </footer>
  );
}
