import { io, type Socket } from "socket.io-client";

// In dev the Vite proxy forwards /socket.io to the Flask backend; in prod we
// connect to the configured API origin (same origin as the REST base URL).
function normalizeSocketUrl(value: string | undefined): string {
  if (!value || value === "/") return "";
  return value.replace(/\/+$/, "");
}

const SOCKET_URL = import.meta.env.DEV ? "" : normalizeSocketUrl(import.meta.env.VITE_API_BASE_URL);

export interface LiveTick {
  symbol: string;
  broker_symbol: string;
  exchange_code: string;
  product_type: string;
  token: string;
  stock_token: string;
  ltp: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  change: number | null;
  change_percent: number | null;
  volume: number | null;
  oi: number | null;
  bid_price?: number | null;
  bid_qty?: number | null;
  ask_price?: number | null;
  ask_qty?: number | null;
  total_buy_qty?: number | null;
  total_sell_qty?: number | null;
  ts: string;
}

export type MarketDataState = "offline" | "connecting" | "live" | "degraded";

export interface MarketDataStatus {
  state: MarketDataState;
  configured: boolean;
  subscriptions: number;
  symbols: string[];
  last_tick_at: string | null;
  error: string | null;
}

export interface SubscriptionRequest {
  symbol: string;
  exchange: string;
  product_type?: string;
  token?: string;
  broker_symbol?: string;
  expiry_date?: string;
  strike_price?: string | number;
  right?: string;
}

const INDEX_FUTURES_LIVE_SYMBOLS = new Set(["NIFTY", "BANKNIFTY", "FINNIFTY"]);

export function buildLiveSpotSubscription(symbol: string): SubscriptionRequest | null {
  const normalized = symbol.trim().toUpperCase();
  if (!normalized) return null;
  if (INDEX_FUTURES_LIVE_SYMBOLS.has(normalized)) {
    return { symbol: normalized, exchange: "NFO", product_type: "futures" };
  }
  if (normalized === "NIFTYMID50") {
    // No valid Breeze websocket token is available for this index in the current
    // master contract; REST quote fallback remains the source of truth.
    return null;
  }
  return { symbol: normalized, exchange: "NSE", product_type: "cash" };
}

export function createMarketDataSocket(): Socket {
  return io(SOCKET_URL, {
    path: "/api/socket.io",
    // Vercel rewrites proxy HTTP reliably, but websocket upgrade can fail when
    // the backend is a raw HTTP VM. Start with polling so the live feed connects
    // first, then let Socket.IO upgrade to websocket if the proxy supports it.
    transports: ["polling", "websocket"],
    upgrade: true,
    autoConnect: true,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });
}
