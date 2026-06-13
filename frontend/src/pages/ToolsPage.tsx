import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/common/page";
import { cn } from "@/lib/utils";

const tools = [
  {
    title: "Strategy Builder",
    subtitle: "Phase 14 live",
    description: "Build multi-leg option structures, preview payoff diagrams, and save to your portfolio.",
    status: "next",
    href: "/strategy-builder",
  },
  {
    title: "Strategy Portfolio",
    subtitle: "Phase 14 live",
    description: "View saved strategies with on-demand payoff calculation, metrics, and delete controls.",
    status: "next",
    href: "/strategy-portfolio",
  },
  {
    title: "Option Chain",
    subtitle: "Phase 11 live",
    description: "Open the first live option-chain tool with expiry control, ATM context, and normalized CE/PE rows.",
    status: "next",
    href: "/optionchain",
  },
  {
    title: "Option Greeks",
    subtitle: "Manual calc later",
    description: "Reserved in the MVP grid, but real Greeks logic stays deferred until an explicit calculation phase.",
    status: "deferred",
    href: null,
  },
  {
    title: "OI Tracker",
    subtitle: "Phase 13 live",
    description: "Strikes ranked by total OI. Spot resistance at max CE OI strike, support at max PE OI strike.",
    status: "next",
    href: "/oi-tracker",
  },
  {
    title: "OI Profile",
    subtitle: "Phase 13 live",
    description: "Full OI distribution across all strikes sorted by price with proportional CE/PE bars.",
    status: "next",
    href: "/oi-profile",
  },
];

function initials(title: string) {
  return title
    .split(" ")
    .map((word) => word[0])
    .join("")
    .slice(0, 2);
}

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
          const content = (
            <Card
              className={cn(
                "h-full transition-colors",
                tool.href && "hover:border-primary/50 hover:bg-muted/30"
              )}
            >
              <CardContent className="flex flex-col gap-3 p-5">
                <div className="flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground">
                    {initials(tool.title)}
                  </div>
                  <Badge variant={tool.status === "next" ? "default" : "secondary"}>
                    {tool.subtitle}
                  </Badge>
                </div>
                <div>
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
