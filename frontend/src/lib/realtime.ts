import { io, type Socket } from "socket.io-client";

// In dev the Vite proxy forwards /socket.io to the Flask backend; in prod we
// connect to the configured API origin (same origin as the REST base URL).
const SOCKET_URL = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5000");

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
}

export function createMarketDataSocket(): Socket {
  return io(SOCKET_URL, {
    path: "/socket.io",
    transports: ["websocket", "polling"],
    autoConnect: true,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });
}
