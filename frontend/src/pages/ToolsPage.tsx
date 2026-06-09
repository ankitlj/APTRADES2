const tools = [
  {
    title: "Strategy Builder",
    subtitle: "Strategy design",
    description: "Build multi-leg option and futures structures after the core market-data tools are live.",
    status: "planned",
  },
  {
    title: "Strategy Portfolio",
    subtitle: "Portfolio tracking",
    description: "Track saved structures, grouped payoffs, and deployment status from one reduced-scope portfolio view.",
    status: "planned",
  },
  {
    title: "Option Chain",
    subtitle: "Phase 11 next",
    description: "Core strike grid, expiries, ATM context, and normalized CE/PE rows land in the next phase.",
    status: "next",
  },
  {
    title: "Option Greeks",
    subtitle: "Manual calc later",
    description: "Reserved in the MVP grid, but real Greeks logic stays deferred until an explicit calculation phase.",
    status: "deferred",
  },
  {
    title: "OI Tracker",
    subtitle: "Open-interest trend",
    description: "Watch directional open-interest shifts across strikes once option-chain data is stable.",
    status: "planned",
  },
  {
    title: "OI Profile",
    subtitle: "Open-interest structure",
    description: "Review where open interest is concentrated and how the profile changes through the session.",
    status: "planned",
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
          {tools.map((tool) => (
            <article key={tool.title} className="tool-card">
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
          ))}
        </div>

        <p className="panel-message">
          Removed from the visible MVP tools flow: Max Pain, Straddle Chart, Straddle P&amp;L, Vol Surface, GEX, and IV Smile.
        </p>
      </article>
    </section>
  );
}
