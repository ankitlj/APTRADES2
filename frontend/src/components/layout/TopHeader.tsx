import { Moon, Palette, Sun } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { MarketTicker } from "@/components/dashboard/MarketTicker";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { utilityItems } from "@/config/navigation";
import { useLiveMarketData } from "@/hooks/useLiveMarketData";
import { useTheme, type ThemeColor } from "@/components/theme/ThemeProvider";
import { cn } from "@/lib/utils";

const ACCENTS: { value: ThemeColor; label: string }[] = [
  { value: "zinc", label: "Zinc" },
  { value: "blue", label: "Blue" },
  { value: "green", label: "Green" },
  { value: "violet", label: "Violet" },
  { value: "orange", label: "Orange" },
  { value: "slate", label: "Slate" },
];

export function TopHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const { mode, toggleMode, color, setColor } = useTheme();
  const { connectionState } = useLiveMarketData();

  const isDashboard = location.pathname === "/" || location.pathname === "/dashboard";
  const isLive = connectionState === "live";

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-12 items-center gap-3 px-4">
        {isDashboard ? <MarketTicker /> : <div className="flex-1" />}

        <div className="flex shrink-0 items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className={cn(
                "h-2 w-2 rounded-full shrink-0",
                isLive ? "bg-green-500 animate-pulse" : "bg-red-500"
              )}
            />
            <span className={cn("font-medium", isLive ? "text-green-600" : "text-red-500")}>
              {isLive ? "Live" : "Offline"}
            </span>
          </div>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={toggleMode}
            title={mode === "light" ? "Switch to dark mode" : "Switch to light mode"}
            aria-label="Toggle color theme"
          >
            {mode === "light" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 rounded-full bg-primary text-primary-foreground dark:shadow-[0_0_12px_-2px_rgba(0,242,255,0.5)]"
                aria-label="Open menu"
              >
                <span className="text-sm font-medium">A</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>Tools</DropdownMenuLabel>
              {utilityItems.map((item) => (
                <DropdownMenuItem
                  key={item.href}
                  onSelect={() => navigate(item.href)}
                  className="cursor-pointer"
                >
                  <item.icon className="h-4 w-4 mr-2" />
                  {item.label}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="flex items-center gap-2">
                <Palette className="h-4 w-4" /> Accent
              </DropdownMenuLabel>
              {ACCENTS.map((accent) => (
                <DropdownMenuItem
                  key={accent.value}
                  onSelect={() => setColor(accent.value)}
                  className="cursor-pointer"
                >
                  <span
                    data-theme={accent.value}
                    className={cn(
                      "h-3 w-3 rounded-full mr-2 border",
                      color === accent.value && "ring-2 ring-ring"
                    )}
                    style={{ background: "var(--primary)" }}
                  />
                  {accent.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
