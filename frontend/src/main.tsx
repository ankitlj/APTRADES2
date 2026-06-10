import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LiveMarketDataProvider } from "./hooks/useLiveMarketData";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ErrorBoundary>
        <LiveMarketDataProvider>
          <App />
        </LiveMarketDataProvider>
      </ErrorBoundary>
    </BrowserRouter>
  </React.StrictMode>,
);
