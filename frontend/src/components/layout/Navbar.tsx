import { Link, useLocation } from "react-router-dom";

import { navItems, utilityItems, isActiveRoute } from "@/config/navigation";
import { useLiveMarketData } from "@/hooks/useLiveMarketData";
import { cn } from "@/lib/utils";

export function Navbar() {
  const location = useLocation();
  const { connectionState } = useLiveMarketData();
  const online = connectionState === "live";

  const linkClass = (active: boolean) =>
    cn(
      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
      active
        ? "bg-primary text-primary-foreground dark:shadow-[0_0_16px_-3px_rgba(0,242,255,0.55)]"
        : "text-muted-foreground hover:bg-muted hover:text-foreground"
    );

  return (
    <aside className="hidden md:flex flex-col w-56 border-r bg-background flex-shrink-0 h-screen sticky top-0 overflow-y-auto scrollbar-thin">
      <div className="px-4 pt-5 pb-4">
        <Link to="/dashboard" className="flex items-start gap-3">
          <img
            src="/oriens-mark.svg"
            alt="ORIENS"
            className="h-9 w-9 shrink-0 rounded-md object-contain transition-[filter,transform] duration-300 dark:drop-shadow-[0_0_18px_rgba(74,214,228,0.45)]"
          />
          <span className="min-w-0">
            <span className="block font-serif text-[1.7rem] font-semibold leading-none tracking-[0.08em] text-[#0e5168] dark:text-[#a9ecf8]">
              ORIENS
            </span>
            <span className="mt-1 block whitespace-nowrap text-[9px] font-semibold tracking-[0.13em] text-muted-foreground">
              TRACK | TRADE | TRIUMPH
            </span>
          </span>
        </Link>
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            to={item.href}
            className={linkClass(isActiveRoute(location.pathname, item.href))}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </Link>
        ))}

        <div className="my-2 border-t" />

        {utilityItems.map((item) => (
          <Link
            key={item.href}
            to={item.href}
            className={linkClass(isActiveRoute(location.pathname, item.href))}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="px-4 py-4 border-t">
        <div
          className={cn(
            "flex min-h-5 items-center gap-2 text-xs",
            online ? "text-green-600" : "text-muted-foreground"
          )}
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full inline-block shrink-0",
              online ? "bg-green-500" : "bg-red-500"
            )}
          />
          ICICI Direct
        </div>
      </div>
    </aside>
  );
}
