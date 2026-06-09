import { Link } from "react-router-dom";

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

function toneClassName(status: string) {
  if (status === "next") {
    return "tone-positive";
  }
  if (status === "deferred") {
    return "tone-warning";
  }
  return "tone-neutral";
}

export function ToolsPage() {
  return (
    <section className="route-page">
      <div className="route-header">
        <div>
          <p className="section-kicker">Reduced tools scope</p>
          <h3>MVP tools only</h3>
          <p className="panel-message">Only the six approved APTRADES v2 tools remain visible in the MVP flow.</p>
        </div>
      </div>

      <article className="panel route-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Tools grid</p>
            <h3>Selected toolset</h3>
          </div>
          <span className="section-pill">6 visible</span>
        </div>

        <div className="tools-grid">
          {tools.map((tool) => {
            const card = (
              <article key={tool.title} className={`tool-card ${tool.href ? "tool-card-link" : ""}`}>
                <div className="tool-card-top">
                  <div className="tool-icon-tile" aria-hidden="true">
                    {tool.title
                      .split(" ")
                      .map((word) => word[0])
                      .join("")
                      .slice(0, 2)}
                  </div>
                  <span className={`tool-status ${toneClassName(tool.status)}`}>{tool.subtitle}</span>
                </div>
                <div className="tool-card-body">
                  <strong>{tool.title}</strong>
                  <p className="panel-message">{tool.description}</p>
                </div>
              </article>
            );

            return tool.href ? (
              <Link key={tool.title} to={tool.href}>
                {card}
              </Link>
            ) : (
              card
            );
          })}
        </div>

        <p className="panel-message">
          Removed from the visible MVP tools flow: Max Pain, Straddle Chart, Straddle P&amp;L, Vol Surface, GEX, and IV Smile.
        </p>
      </article>
    </section>
  );
}
