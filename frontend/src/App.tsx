import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { ActionCentrePage } from "./pages/ActionCentrePage";
import { LogsPage } from "./pages/LogsPage";
import { OIProfilePage } from "./pages/OIProfilePage";
import { OITrackerPage } from "./pages/OITrackerPage";
import { OptionChainPage } from "./pages/OptionChainPage";
import { OrderbookPage } from "./pages/OrderbookPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { PositionsPage } from "./pages/PositionsPage";
import { StrategyBuilderPage } from "./pages/StrategyBuilderPage";
import { StrategyPortfolioPage } from "./pages/StrategyPortfolioPage";
import { TradebookPage } from "./pages/TradebookPage";
import { ToolsPage } from "./pages/ToolsPage";

const pages = [
  { path: "/dashboard", title: "Dashboard", description: "The main APTRADES dashboard now runs through backend contracts." },
  { path: "/optionchain", title: "Option Chain", description: "The core option chain grid now loads live Breeze-backed rows." },
  { path: "/positions", title: "Positions", description: "Live quote enrichment begins after QuoteService exists." },
  { path: "/strategy", title: "Strategy", description: "Strategy Builder and Strategy Portfolio stay under Tools in MVP." },
  { path: "/tools", title: "Tools", description: "Reduced six-tool grid will replace this placeholder in a later phase." },
];

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/orderbook" element={<OrderbookPage />} />
        <Route path="/tradebook" element={<TradebookPage />} />
        <Route path="/positions" element={<PositionsPage />} />
        <Route path="/action-centre" element={<ActionCentrePage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/optionchain" element={<OptionChainPage />} />
        <Route path="/oi-tracker" element={<OITrackerPage />} />
        <Route path="/oi-profile" element={<OIProfilePage />} />
        <Route path="/strategy-builder" element={<StrategyBuilderPage />} />
        <Route path="/strategy-portfolio" element={<StrategyPortfolioPage />} />
        {pages
          .filter((page) => !["/dashboard", "/orderbook", "/tradebook", "/positions", "/action-centre", "/logs", "/tools", "/optionchain"].includes(page.path))
          .map((page) => (
            <Route
              key={page.path}
              path={page.path}
              element={<PlaceholderPage title={page.title} description={page.description} />}
            />
          ))}
      </Routes>
    </AppShell>
  );
}
