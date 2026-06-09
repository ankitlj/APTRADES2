import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { OrderbookPage } from "./pages/OrderbookPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { PositionsPage } from "./pages/PositionsPage";
import { TradebookPage } from "./pages/TradebookPage";

const pages = [
  { path: "/dashboard", title: "Dashboard", description: "The main APTRADES dashboard now runs through backend contracts." },
  { path: "/positions", title: "Positions", description: "Live quote enrichment begins after QuoteService exists." },
  { path: "/action-centre", title: "Action Centre", description: "Approval and review workflow comes after trading pages." },
  { path: "/strategy", title: "Strategy", description: "Strategy Builder and Strategy Portfolio stay under Tools in MVP." },
  { path: "/logs", title: "Logs", description: "Operational logs arrive after core trading flows are stable." },
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
        {pages
          .filter((page) => !["/dashboard", "/orderbook", "/tradebook", "/positions"].includes(page.path))
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
