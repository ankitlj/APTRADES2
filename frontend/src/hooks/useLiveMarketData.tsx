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
  /** ISO timestamp of the last tick the worker saw, or null. */
  lastTickAt: string | null;
  /** Latest tick per display symbol. */
  ticks: Record<string, LiveTick>;
  /** Request additional symbols to be streamed. */
  subscribe: (items: SubscriptionRequest[]) => void;
  /** Request symbols to be removed from the stream. */
  unsubscribe: (items: SubscriptionRequest[]) => void;
}

const LiveMarketDataContext = createContext<LiveMarketDataContextValue | null>(null);

// Phase 19: a brief reconnect should not flip the badge to "offline". During the
// grace window after a disconnect we keep reporting "connecting" (reconnecting
// feel) and only fall back to "offline" once the grace period has elapsed.
const RECONNECT_GRACE_MS = 2000;

function deriveConnectionState(
  socketConnected: boolean,
  status: MarketDataStatus | null,
  graceElapsed: boolean,
): ConnectionState {
  if (!socketConnected) {
    return graceElapsed ? "offline" : "connecting";
  }
  if (!status) {
    return "connecting";
  }
  return status.state;
}

export function LiveMarketDataProvider({ children }: PropsWithChildren) {
  const socketRef = useRef<Socket | null>(null);
  const graceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [socketConnected, setSocketConnected] = useState(false);
  const [graceElapsed, setGraceElapsed] = useState(false);
  const [ticks, setTicks] = useState<Record<string, LiveTick>>({});

  useEffect(() => {
    const socket = createMarketDataSocket();
    socketRef.current = socket;

    const clearGraceTimer = () => {
      if (graceTimerRef.current) {
        clearTimeout(graceTimerRef.current);
        graceTimerRef.current = null;
      }
    };

    socket.on("connect", () => {
      clearGraceTimer();
      setGraceElapsed(false);
      setSocketConnected(true);
    });
    socket.on("disconnect", (reason: string) => {
      // Phase 19: log the reason so a live session shows whether it was a ping
      // timeout, transport close, or server disconnect.
      console.warn("[market-data] socket disconnect:", reason);
      setSocketConnected(false);
      clearGraceTimer();
      graceTimerRef.current = setTimeout(() => setGraceElapsed(true), RECONNECT_GRACE_MS);
    });
    socket.on("connect_error", (error: Error) => {
      console.warn("[market-data] connect_error:", error?.message ?? error);
    });
    socket.on("status", (payload: MarketDataStatus) => setStatus(payload));
    socket.on("tick", (tick: LiveTick) => {
      if (!tick || !tick.symbol) {
        return;
      }
      setTicks((current) => ({ ...current, [tick.symbol]: tick }));
    });

    return () => {
      clearGraceTimer();
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

  const unsubscribe = useCallback((items: SubscriptionRequest[]) => {
    const socket = socketRef.current;
    if (!socket || !items.length) {
      return;
    }
    socket.emit("unsubscribe", { symbols: items });
  }, []);

  const connectionState = deriveConnectionState(socketConnected, status, graceElapsed);
  const lastTickAt = status?.last_tick_at ?? null;

  const value = useMemo<LiveMarketDataContextValue>(
    () => ({ status, socketConnected, connectionState, lastTickAt, ticks, subscribe, unsubscribe }),
    [status, socketConnected, connectionState, lastTickAt, ticks, subscribe, unsubscribe],
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

/** Subscribe to a set of symbols for the lifetime of the calling component.
 *
 * On mount and on `items` change, computes a diff against the previous set and
 * emits subscribe/unsubscribe socket events for the delta. On unmount,
 * unsubscribes every tracked item. On socket reconnect, re-subscribes all
 * current items.
 */
export function useLiveSubscribe(items: SubscriptionRequest[]): void {
  const { subscribe, unsubscribe, socketConnected } = useLiveMarketData();
  const prevRef = useRef<string>("");
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const serialized = JSON.stringify(items);

  // Reset prev tracking on reconnect so all items are re-subscribed.
  useEffect(() => {
    if (socketConnected) {
      prevRef.current = "";
    }
  }, [socketConnected]);

  // Compute diff against prev and emit subscribe / unsubscribe for the delta.
  useEffect(() => {
    if (!socketConnected) {
      return;
    }
    const parsed = JSON.parse(serialized) as SubscriptionRequest[];
    if (!parsed.length) {
      return;
    }

    const prevJson = prevRef.current;
    prevRef.current = serialized;

    const prev: SubscriptionRequest[] = prevJson ? JSON.parse(prevJson) : [];
    const prevKeys = new Set(prev.map((k) => JSON.stringify(k)));
    const currKeys = new Set(parsed.map((k) => JSON.stringify(k)));

    const removed = prev.filter((k) => !currKeys.has(JSON.stringify(k)));
    const added = parsed.filter((k) => !prevKeys.has(JSON.stringify(k)));

    if (removed.length) {
      unsubscribe(removed);
    }
    if (added.length) {
      subscribe(added);
    }
  }, [serialized, socketConnected, subscribe, unsubscribe]);

  // Cleanup on unmount — unsubscribe all tracked items.
  useEffect(() => {
    return () => {
      const current = itemsRef.current;
      if (current.length) {
        unsubscribe(current);
      }
    };
  }, [unsubscribe]);
}
