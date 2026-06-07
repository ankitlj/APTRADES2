import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

const pages = [
  { path: "/", title: "Dashboard", description: "Resolver-backed quotes and deployment checks start here." },
  { path: "/orderbook", title: "Orderbook", description: "Compact Breeze-backed orders table lands in a later phase." },
  { path: "/tradebook", title: "Tradebook", description: "Normalized Breeze trades page starts after backend contracts." },
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
        <Route path="/" element={<DashboardPage />} />
        {pages
          .filter((page) => page.path !== "/")
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
