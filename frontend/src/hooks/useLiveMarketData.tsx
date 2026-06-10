import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import type { Socket } from "socket.io-client";

import {
  createMarketDataSocket,
  type LiveTick,
  type MarketDataState,
  type MarketDataStatus,
  type SubscriptionRequest,
} from "../lib/realtime";

type ConnectionState = MarketDataState;

interface LiveMarketDataContextValue {
  /** Worker state reported by the backend (live / degraded / offline). */
  status: MarketDataStatus | null;
  /** Whether the socket transport itself is currently connected. */
  socketConnected: boolean;
  /** Effective badge state combining socket transport and worker state. */
  connectionState: ConnectionState;
  /** Latest tick per display symbol. */
  ticks: Record<string, LiveTick>;
  /** Request additional symbols to be streamed. */
  subscribe: (items: SubscriptionRequest[]) => void;
}

const LiveMarketDataContext = createContext<LiveMarketDataContextValue | null>(null);

function deriveConnectionState(socketConnected: boolean, status: MarketDataStatus | null): ConnectionState {
  if (!socketConnected) {
    return "offline";
  }
  if (!status) {
    return "connecting";
  }
  return status.state;
}

export function LiveMarketDataProvider({ children }: PropsWithChildren) {
  const socketRef = useRef<Socket | null>(null);
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [socketConnected, setSocketConnected] = useState(false);
  const [ticks, setTicks] = useState<Record<string, LiveTick>>({});

  useEffect(() => {
    const socket = createMarketDataSocket();
    socketRef.current = socket;

    socket.on("connect", () => setSocketConnected(true));
    socket.on("disconnect", () => setSocketConnected(false));
    socket.on("status", (payload: MarketDataStatus) => setStatus(payload));
    socket.on("tick", (tick: LiveTick) => {
      if (!tick || !tick.symbol) {
        return;
      }
      setTicks((current) => ({ ...current, [tick.symbol]: tick }));
    });

    return () => {
      socket.removeAllListeners();
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  const subscribe = useCallback((items: SubscriptionRequest[]) => {
    const socket = socketRef.current;
    if (!socket || !items.length) {
      return;
    }
    socket.emit("subscribe", { symbols: items });
  }, []);

  const connectionState = deriveConnectionState(socketConnected, status);

  const value = useMemo<LiveMarketDataContextValue>(
    () => ({ status, socketConnected, connectionState, ticks, subscribe }),
    [status, socketConnected, connectionState, ticks, subscribe],
  );

  return <LiveMarketDataContext.Provider value={value}>{children}</LiveMarketDataContext.Provider>;
}

export function useLiveMarketData(): LiveMarketDataContextValue {
  const context = useContext(LiveMarketDataContext);
  if (!context) {
    throw new Error("useLiveMarketData must be used within a LiveMarketDataProvider");
  }
  return context;
}

/** Latest live tick for one display symbol, or undefined if none yet. */
export function useLiveQuote(symbol: string | null | undefined): LiveTick | undefined {
  const { ticks } = useLiveMarketData();
  if (!symbol) {
    return undefined;
  }
  return ticks[symbol.toUpperCase()];
}

/** Subscribe to a set of symbols for the lifetime of the calling component. */
export function useLiveSubscribe(items: SubscriptionRequest[]): void {
  const { subscribe, socketConnected } = useLiveMarketData();
  const serialized = JSON.stringify(items);

  useEffect(() => {
    if (!socketConnected) {
      return;
    }
    const parsed = JSON.parse(serialized) as SubscriptionRequest[];
    if (parsed.length) {
      subscribe(parsed);
    }
  }, [serialized, socketConnected, subscribe]);
}
