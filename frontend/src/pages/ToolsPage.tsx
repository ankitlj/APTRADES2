import { Activity, BarChart3, Briefcase, Code2, Layers, type LucideIcon, Sigma } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/common/page";

interface Tool {
  title: string;
  subtitle: string;
  description: string;
  status: "next" | "deferred";
  href: string | null;
  icon: LucideIcon;
}

const tools: Tool[] = [
  {
    title: "Strategy Builder",
    subtitle: "Phase 14 live",
    description: "Build multi-leg option structures, preview payoff diagrams, and save to your portfolio.",
    status: "next",
    href: "/strategy-builder",
    icon: Code2,
  },
  {
    title: "Strategy Portfolio",
    subtitle: "Phase 14 live",
    description: "View saved strategies with on-demand payoff calculation, metrics, and delete controls.",
    status: "next",
    href: "/strategy-portfolio",
    icon: Briefcase,
  },
  {
    title: "Option Chain",
    subtitle: "Phase 11 live",
    description: "Open the first live option-chain tool with expiry control, ATM context, and normalized CE/PE rows.",
    status: "next",
    href: "/optionchain",
    icon: Layers,
  },
  {
    title: "Option Greeks",
    subtitle: "Manual calc later",
    description: "Reserved in the MVP grid, but real Greeks logic stays deferred until an explicit calculation phase.",
    status: "deferred",
    href: null,
    icon: Sigma,
  },
  {
    title: "OI Tracker",
    subtitle: "Phase 13 live",
    description: "Strikes ranked by total OI. Spot resistance at max CE OI strike, support at max PE OI strike.",
    status: "next",
    href: "/oi-tracker",
    icon: Activity,
  },
  {
    title: "OI Profile",
    subtitle: "Phase 13 live",
    description: "Full OI distribution across all strikes sorted by price with proportional CE/PE bars.",
    status: "next",
    href: "/oi-profile",
    icon: BarChart3,
  },
];

export function ToolsPage() {
  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      <PageHeader
        kicker="Reduced tools scope"
        title="Tools"
        description="Only the six approved APTRADES v2 tools remain visible in the MVP flow."
        actions={<Badge variant="secondary">6 visible</Badge>}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {tools.map((tool) => {
          const Icon = tool.icon;
          const content = (
            <Card className="glow-card h-full overflow-hidden dark:bg-white/[0.04] dark:backdrop-blur-md">
              <CardContent className="relative flex flex-col gap-3 p-5">
                <Icon className="engraved-icon h-24 w-24" aria-hidden="true" />
                <div className="relative flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 dark:shadow-[0_0_14px_-3px_rgba(0,242,255,0.6)]">
                    <Icon className="glow-icon h-5 w-5" aria-hidden="true" />
                  </div>
                  <Badge variant={tool.status === "next" ? "default" : "secondary"}>
                    {tool.subtitle}
                  </Badge>
                </div>
                <div className="relative">
                  <p className="font-semibold">{tool.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{tool.description}</p>
                </div>
              </CardContent>
            </Card>
          );

          return tool.href ? (
            <Link key={tool.title} to={tool.href} className="block">
              {content}
            </Link>
          ) : (
            <div key={tool.title}>{content}</div>
          );
        })}
      </div>

      <p className="text-xs text-muted-foreground">
        Removed from the visible MVP tools flow: Max Pain, Straddle Chart, Straddle P&amp;L, Vol
        Surface, GEX, and IV Smile.
      </p>
    </div>
  );
}
