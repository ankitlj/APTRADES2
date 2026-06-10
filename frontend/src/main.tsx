import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { LiveMarketDataProvider } from "./hooks/useLiveMarketData";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <LiveMarketDataProvider>
        <App />
      </LiveMarketDataProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
