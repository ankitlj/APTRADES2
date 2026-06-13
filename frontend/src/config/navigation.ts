import {
  Activity,
  BarChart3,
  Bell,
  Briefcase,
  ClipboardList,
  Code2,
  FileBarChart,
  FileText,
  Layers,
  LayoutDashboard,
  type LucideIcon,
  TrendingUp,
  Wrench,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

// Primary navigation shown in the desktop sidebar.
export const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/orderbook", label: "Orderbook", icon: ClipboardList },
  { href: "/tradebook", label: "Tradebook", icon: FileText },
  { href: "/positions", label: "Positions", icon: TrendingUp },
  { href: "/action-centre", label: "Action Centre", icon: Bell },
  { href: "/logs", label: "Logs", icon: FileBarChart },
  { href: "/tools", label: "Tools", icon: Wrench },
];

// Secondary tools shown below the divider and inside the profile menu.
export const utilityItems: NavItem[] = [
  { href: "/optionchain", label: "Option Chain", icon: Layers },
  { href: "/oi-tracker", label: "OI Tracker", icon: Activity },
  { href: "/oi-profile", label: "OI Profile", icon: BarChart3 },
  { href: "/strategy-builder", label: "Strategy Builder", icon: Code2 },
  { href: "/strategy-portfolio", label: "Strategy Portfolio", icon: Briefcase },
];

// Items shown in the mobile bottom navigation.
export const bottomNavItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/orderbook", label: "Orderbook", icon: ClipboardList },
  { href: "/tradebook", label: "Tradebook", icon: FileText },
  { href: "/positions", label: "Positions", icon: TrendingUp },
  { href: "/tools", label: "Tools", icon: Wrench },
];

export function isActiveRoute(pathname: string, href: string): boolean {
  if (pathname === "/" && href === "/dashboard") return true;
  return pathname === href;
}
