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
    <aside className="hidden h-screen w-60 flex-shrink-0 flex-col border-r bg-background md:flex">
      <div className="px-4 pb-4 pt-4">
        <Link to="/dashboard" className="flex items-center gap-3 rounded-xl px-1 py-1.5">
          <img
            src="/oriens-logo-mark.png"
            alt="ORIENS"
            className="h-14 w-14 shrink-0 object-contain transition-[filter] duration-300 dark:drop-shadow-[0_0_16px_rgba(168,96,255,0.46)]"
          />
          <span className="min-w-0">
            <span className="block font-serif text-2xl font-semibold leading-none tracking-[0.06em] text-[#15163f] dark:text-[#d9d4ff]">
              ORIENS
            </span>
            <span className="mt-1.5 block whitespace-nowrap text-[7.5px] font-semibold tracking-[0.08em] text-[#6d5c92] dark:text-[#bda8ff]">
              TRACK | TRADE | TRIUMPH
            </span>
          </span>
        </Link>
      </div>

      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 scrollbar-thin">
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

      <div className="border-t px-4 py-4">
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
