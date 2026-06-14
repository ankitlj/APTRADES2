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
    <aside className="hidden h-screen w-72 flex-shrink-0 flex-col border-r bg-background md:flex">
      <div className="px-5 pb-4 pt-5">
        <Link to="/dashboard" className="block rounded-xl">
          <img
            src="/oriens-logo.svg"
            alt="ORIENS"
            className="h-32 w-full rounded-lg bg-white object-contain p-1 transition-[filter] duration-300 dark:drop-shadow-[0_0_22px_rgba(74,214,228,0.45)]"
          />
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
