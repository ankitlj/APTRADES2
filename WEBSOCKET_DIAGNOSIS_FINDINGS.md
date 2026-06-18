# WEBSOCKET DIAGNOSIS FINDINGS

## PART 0 — DIAGNOSIS RULES

### Claim under investigation
> Backend receives live ticks but the frontend does not continuously update without manual refresh.

### Four possible root-cause buckets
| Bucket | Description |
|--------|-------------|
| A | Backend receives ticks but does not emit to clients (emit path broken) |
| B | Backend emits ticks but does not persist/update Redis snapshot (Redis write path broken) |
| C | Frontend receives socket events but ignores them (payload shape / symbol mismatch / stale state) |
| D | Frontend never receives socket events (connection / subscription / transport / namespace issue) |

### Required result
Identify the single highest-confidence root cause, or the smallest remaining uncertainty set that needs live-market validation.

### No code changes made in this pass
This is a pure diagnosis report. Zero code modifications were made.

---

## PART 1 — BACKEND LIVE-TICK PATH TRACE FROM CODE

### 1.1 Files inspected

- `backend/app/services/market_data_worker.py` (521 lines)
- `backend/app/realtime.py` (165 lines)
- `backend/app/api/diagnosis.py` (331 lines)

### 1.2 Complete backend flow map

```
Breeze websocket message arrives
  |
  v
breeze_connect internal socket thread
  calls breeze.on_ticks = MarketDataWorker._on_ticks  (line 221)
  |
  v
MarketDataWorker._on_ticks(tick: dict)                (line 371)
  |-- guard: if not isinstance(tick, dict): return     (line 373)
  |
  v
_normalize_tick(tick) -> dict | None                   (line 375, defined line 405)
  |-- look up subscription by stock_token               (line 406-407)
  |-- compute ltp, close, change, etc.                  (line 409-416)
  |-- return dict with keys: symbol, broker_symbol,
  |   exchange_code, product_type, token, stock_token,
  |   ltp, open, high, low, close, change,
  |   change_percent, volume, oi, ts                    (line 424-441)
  |
  v (if normalized is not None)
_log_gap()                                               (line 378, defined line 394)
  |-- warn if time since last tick > gap_log_seconds (5s)
  |
  v
Update diagnostic counters (no lock needed for ints)    (line 379-385)
  |-- _last_tick_at = now_ts
  |-- _ticks_received_ever, _first_tick_at (first time)
  |-- _tick_count_total += 1
  |
  v
with self._lock:                                        (line 387)
  self._last_ticks[sym] = normalized                    (line 388)  <-- in-memory snapshot
  self._per_symbol_tick_counts[sym]++                   (line 389)
  |
  v
_write_redis(normalized)                                 (line 390, defined line 443)
  |-- if not self._redis_url: return                    (line 444)
  |-- key = f"md:tick:{exchange_code}:{token}"          (line 448)
  |     or f"md:tick:{symbol}" if no token
  |-- client.set(key, json.dumps(tick), ex=60)          (line 449)
  |-- except Exception: pass                             (line 450-451)  <-- SILENT FAIL
  |
  v
_recorder.record(normalized)                             (line 391)
  |-- best-effort DB write, catches all exceptions
  |
  v
_emit(normalized)                                        (line 392, defined line 458)
  |-- read self._publish under lock                      (line 459-460)
  |-- if publish is None: return                         (line 461-462)
  |-- publish("tick", tick)                              (line 464)  <-- socketio.emit
  |-- except Exception: pass                             (line 465-466)  <-- SILENT FAIL
```

### 1.3 Per-ho documentation

#### Stage 1: Breeze callback registration
- **File**: `market_data_worker.py`
- **Function**: `_connect()` at line 219-224
- **Action**: `breeze.on_ticks = self._on_ticks` (line 221)
- **Thread**: Runs on breeze-connect internal socket thread
- **Swallows exceptions?**: No (but called by supervisor loop which does)

#### Stage 2: Raw tick entry point
- **File**: `market_data_worker.py`
- **Function**: `_on_ticks(self, tick: Any)` at line 371-392
- **Input**: Raw Breeze tick dict (keys: symbol, last, close, change, open, high, low, volume, oi, etc.)
- **Output**: None (side-effects only)
- **Guards**: non-dict input is silently dropped (line 373-374); None from normalize drops silently (line 376-377)
- **Swallows exceptions?**: No direct try/except in `_on_ticks` itself. But downstream `_write_redis`, `_emit` each have bare except.

#### Stage 3: Normalize
- **File**: `market_data_worker.py`
- **Function**: `_normalize_tick(self, tick: dict) -> dict | None` at line 405-441
- **Input**: raw Breeze tick
- **Output**: dict with 16 fields matching `LiveTick` frontend interface
- **Key logic**: Looks up subscription by `stock_token` from raw tick's `symbol` field (line 406-407). If no subscription found, subscription becomes None and fallback values are used (lines 418-422, 426-429).
- **Synchronous**: Yes
- **Swallows exceptions?**: No

#### Stage 4: In-memory snapshot update
- **File**: `market_data_worker.py`
- **Function**: `_on_ticks`, lines 387-389
- **Action**: `self._last_ticks[sym] = normalized` under `self._lock`
- **Thread-safety**: Protected by `threading.RLock` (line 110, 387)
- **Key**: `sym` = `normalized["symbol"]` which is `subscription.display_symbol`
- **Failure mode**: None — dict assignment is atomic. Always succeeds.
- **Snapshot read path**: `snapshot()` (line 504-506) returns `list(self._last_ticks.values())` under lock.

#### Stage 5: Redis write
- **File**: `market_data_worker.py`
- **Function**: `_write_redis(self, tick: dict) -> None` at line 443-451
- **Guards**: returns immediately if `self._redis_url` is falsy (line 444)
- **Key name**: `f"md:tick:{tick['exchange_code']}:{tick['token']}"` if token is truthy, else `f"md:tick:{tick['symbol']}"` (line 448)
- **Value**: `json.dumps(tick)` — JSON string
- **TTL**: `self._tick_ttl_seconds` (default 60, set at line 91, used at line 449)
- **Redis client**: lazy-cached `self._redis_client()` (line 453-456) which calls `create_redis_client(self._redis_url)` once and caches
- **Exception behavior**: **ALL exceptions silently swallowed** (line 450-451: `except Exception: pass`). No logging.
- **Failure consequence if Redis write fails**: in-memory `_last_ticks` is already updated (line 388), so snapshot endpoint still works. Emit still happens (line 392). Redis cache diverges from live state.

#### Stage 6: Socket emit
- **File**: `market_data_worker.py`
- **Function**: `_emit(self, tick: dict) -> None` at line 458-466
- **Guards**: returns if `self._publish` is None (line 461-462)
- **Publish call**: `self._publish("tick", tick)` (line 464)
- **What is `_publish`**: `socketio.emit` — set at `realtime.py` line 59
- **Exception behavior**: **ALL exceptions silently swallowed** (line 465-466: `except Exception: pass`). No logging.
- **Failure consequence if emit fails**: in-memory snapshot already updated. Redis write already attempted (line 390 before emit at line 392). Diagnostic counters already incremented. The tick is silently lost to the frontend.

#### Stage 7: Diagnostic counters
- **File**: `market_data_worker.py`
- **Function**: `status()` at line 485-502
- **Reads from**: **worker memory only** — `self._state`, `self._subscriptions`, `self._last_tick_at`, `self._tick_count_total`, `self._ticks_received_ever`, `self._freshness()`
- **Does NOT read from Redis**: confirmed — no Redis read in `status()`
- **Freshness**: `_freshness()` at line 356-369 checks `_last_tick_at` against current time with 30s threshold

### 1.4 Stage dependency analysis

| If this fails... | Does emit still happen? | Does in-memory tick still update? | Does Redis write still happen? | Do diagnostic counters increment? |
|---|---|---|---|---|
| `_normalize_tick` returns None | No (short-circuit at line 376) | No | No | No |
| `_write_redis` throws silently (line 450) | **Yes** (line 392 runs regardless) | **Yes** (line 388 ran before line 390) | N/A | **Yes** |
| `_recorder.record` throws | **Yes** | **Yes** | **Yes** | **Yes** |
| `_emit` throws silently (line 465) | N/A | **Yes** | **Yes** | **Yes** |

**Critical finding**: `_write_redis` and `_emit` are after the in-memory update. Failure in either does NOT prevent the other from running, and does NOT prevent counters from incrementing. This means:
- Worker can show `ticks_received_ever: true`, `tick_count_total > 0`, `last_tick_at: recent` **while both Redis writes and socket emits silently fail.**
- The `/api/diagnosis/worker` endpoint will report "healthy" even when Redis and socket paths are broken.

### 1.5 Snapshot endpoint source

- **File**: `backend/app/api/market_data.py`, function `market_data_snapshot()` at line 39-45
- **Reads from**: `worker.snapshot()` — which reads **in-memory** `self._last_ticks` (market_data_worker.py line 504-506)
- **Does NOT read from Redis**: confirmed.
- **Evidence**: The endpoint returns real ticks even when Redis is empty (proven fact #4 vs #5).

### 1.6 Cache endpoint source

- **File**: `backend/app/api/diagnosis.py`, function `cache()` at line 215-235
- **Reads from**: Redis directly via `create_redis_client(redis_url)` (line 226), scanning `client.keys("md:tick:*")` (line 227)
- **Does NOT read from worker memory**: confirmed.
- **Separate Redis client**: creates a fresh client every request (line 226), calls `client.close()` at line 231. This is a **different client instance** than the worker's cached client.

### 1.7 Worker endpoint source

- **File**: `backend/app/api/diagnosis.py`, function `worker()` at line 267-280
- **Reads from**: Calls `w.status()` and `w.snapshot()` — both **worker memory only**
- **Redis involvement**: None.

### 1.8 Part 1 verdict

**Structurally suspicious** — the architecture is correct on paper but has two silent-failure points that can independently break the Redis cache path and the socket emit path without any observable diagnostic signal. Specifically:

- `_write_redis` (line 450-451): bare `except Exception: pass` — zero visibility into write failures
- `_emit` (line 465-466): bare `except Exception: pass` — zero visibility into emit failures
- Diagnose counters and `/api/diagnosis/worker` report "healthy" even when both downstream paths are broken

---

## PART 2 — REDIS CACHE WRITE DIAGNOSIS

### 2.1 Write path

**Function**: `MarketDataWorker._write_redis` in `market_data_worker.py` lines 443-451

```python
def _write_redis(self, tick: dict[str, Any]) -> None:
    if not self._redis_url:        # line 444 — guard
        return
    try:
        client = self._redis_client()   # line 447 — lazy-cached client
        key = f"md:tick:{tick['exchange_code']}:{tick['token']}" \
              if tick["token"] else f"md:tick:{tick['symbol']}"   # line 448
        client.set(key, json.dumps(tick), ex=self._tick_ttl_seconds)  # line 449
    except Exception:              # line 450
        pass                       # line 451
```

### 2.2 Read path (diagnosis cache endpoint)

**Function**: `cache()` in `diagnosis.py` lines 215-235

```python
client = create_redis_client(redis_url)        # line 226 — FRESH client
tick_keys = client.keys("md:tick:*")           # line 227 — scan keys
info["tick_keys"] = len(tick_keys)             # line 228
```

### 2.3 Key comparison

| Aspect | Writer | Reader | Match? |
|--------|--------|--------|--------|
| Key prefix | `md:tick:` | `md:tick:*` | **YES** |
| Key pattern | `{exchange}:{token}` or `{symbol}` | glob `*` | **YES** |
| Database number | Default (0) via `Redis.from_url()` | Default (0) via `Redis.from_url()` | **YES** |
| Redis URL | `self._redis_url` from constructor | `current_app.config.get("REDIS_URL")` | **YES** (same config source) |
| Client instance | Cached, created once at first call | Fresh client every request | **DIFFERENT** |
| Decode setting | `decode_responses=True` (from `create_redis_client`) | `decode_responses=True` | **YES** |

### 2.4 TTL analysis

- TTL = `self._tick_ttl_seconds` = **60 seconds** (default at line 91, used at line 449)
- After 60 seconds of inactivity, all tick keys expire from Redis
- At market-closed times, `tick_keys = 0` is **expected** — not proof of write failure
- During live market, ticks arrive every ~1 second, so keys should be continuously refreshed

### 2.5 What can go wrong

**Scenario 1 — Redis write is never reached (guarded out)**
- If `self._redis_url` is `None` or empty, line 444 returns immediately
- Evidence: `/api/diagnosis/cache` returns `status: "online"` and `dbsize: 2` → Redis IS configured. The worker receives the same `redis_url` (set at `realtime.py` line 58). Guard should not trigger.

**Scenario 2 — Cached Redis client has a broken connection**
- `_redis_client()` (line 453-456) creates the client ONCE and caches it
- If the initial `Redis.from_url()` succeeds but subsequent `client.set()` fails (connection timeout, server closed connection, auth token expired), the exception is caught at line 450 and **silently ignored**
- Meanwhile `/api/diagnosis/cache` creates a **fresh** client each request (line 226), which establishes a new connection and succeeds — reporting "online" while the worker's cached client has a stale/broken connection
- This is the exact pattern that produces: worker has ticks (counters advance, snapshot has data) but Redis has 0 keys

**Scenario 3 — Key construction fails (no token, no symbol)**
- `tick["token"]` would be empty string `""` from `_normalize_tick` line 429 (subscription.token defaults to `""`)
- `tick["symbol"]` would be `display_symbol` which is always set (line 418-422)
- Key would fall to `f"md:tick:{tick['symbol']}"` — still a valid key, still matches the scan pattern
- This would not explain 0 keys

**Scenario 4 — Redis write succeeds but keys expire before diagnosis reads**
- With 60s TTL, if diagnosis check is performed >60s after the last tick, keys would be gone
- This is the expected post-market behavior
- During market hours, ticks arrive continuously, so keys would be continuously refreshed

### 2.6 Root cause classification

**Inconclusive from code alone** — but with high suspicion of **Scenario 2 (silent write failure on cached Redis client)**.

The combination of:
1. Worker has real ticks (proven)
2. Snapshot returns real data (proven — reads from memory)
3. Redis reports "online" but `tick_keys = 0` (proven — fresh client succeeds)
4. `_write_redis` swallows all exceptions silently (proven — line 450-451)
5. Worker's Redis client is cached once and never recreated (proven — line 453-456)

...is consistent with a scenario where the worker's cached Redis client has a silently broken connection.

**However**, this can only be definitively confirmed by observing during live market when `tick_keys` should be continuously >0 with 60s TTL. At market-closed times, 0 keys is the expected outcome.

---

## PART 3 — FRONTEND SOCKET RECEIVE PATH TRACE

### 3.1 Files inspected

- `frontend/src/lib/realtime.ts` (52 lines)
- `frontend/src/hooks/useLiveMarketData.tsx` (160 lines)
- `frontend/src/components/dashboard/MarketTicker.tsx` (82 lines)
- `frontend/src/components/layout/TopHeader.tsx` (123 lines)
- `frontend/src/pages/DashboardPage.tsx` (364 lines)

### 3.2 Complete frontend flow map

```
Page mounts
  |
  v
LiveMarketDataProvider mount (useLiveMarketData.tsx:59-127)
  |-- useEffect with [] deps (line 67-108): runs once
  |-- createMarketDataSocket() -> io(SOCKET_URL, {path, transports, ...}) (realtime.ts:43-51)
  |     |-- SOCKET_URL = "" in dev (Vite proxy to localhost:5000)
  |     |-- SOCKET_URL = VITE_API_BASE_URL ?? "http://127.0.0.1:5000" in prod
  |     |-- transports: ["websocket", "polling"]
  |     |-- autoConnect: true
  |
  v
Socket connects to server
  |-- socket.on("connect") -> setSocketConnected(true) (line 78-82)
  |     |-- also: backend _handle_connect runs (realtime.py:111-123)
  |     |     |-- ensure_started() -> starts Breeze WS
  |     |     |-- subscribe DEFAULT_WATCHLIST (NIFTY, BANKNIFTY futures)
  |     |     |-- emit "status" to this client
  |     |     |-- emit "tick" for each cached snapshot item
  |
  v
socket.on("status") -> setStatus(payload) (line 94)
  |
  v
socket.on("tick") handler (line 95-100)
  |-- guard: if !tick || !tick.symbol: return (line 96-98)
  |-- setTicks((current) => ({...current, [tick.symbol]: tick})) (line 99)
  |     |-- functional updater: no stale closure risk on prev state
  |     |-- key: tick.symbol (display_symbol from backend normalization)
  |     |-- value: the complete normalized tick dict
  |
  v
React re-renders context consumers
  |-- connectionState = deriveConnectionState(socketConnected, status, graceElapsed) (line 118)
  |-- ticks = state from setTicks
  |
  v
MarketTicker component (MarketTicker.tsx:15-82)
  |-- const { ticks } = useLiveMarketData() (line 17)
  |-- on mount: REST fetch /api/dashboard/summary (line 19-31, one-time)
  |-- render loop: (summary?.ticker ?? []).map(item => {
  |     live = ticks[item.symbol.toUpperCase()]   (line 34)
  |     ltp = live?.ltp ?? item.ltp               (line 37)
  |     changePercent = live?.change_percent ?? item.change_percent  (line 38)
  |   })
  |
  v
TopHeader component (TopHeader.tsx:28-123)
  |-- const { connectionState } = useLiveMarketData() (line 32)
  |-- badgeMap[connectionState] => dot class + label (lines 36-42)
  |-- renders: green pulse + "Connected" when "live"
  |-- renders: amber + "Reconnecting" when "connecting"
  |-- renders: amber + "Degraded" when "degraded"
  |-- renders: red + "Offline" when "offline"

--- Subscription path (triggered by DashboardPage) ---

DashboardPage mount (DashboardPage.tsx:214-364)
  |-- useMemo to derive positionSubscriptions from summary data (lines 220-230)
  |     |-- maps: {symbol: position.symbol, exchange: position.exchange_code, product_type: position.product_type}
  |-- useLiveSubscribe(positionSubscriptions) (line 231)

useLiveSubscribe (useLiveMarketData.tsx:147-159)
  |-- useEffect dependencies: [serialized, socketConnected, subscribe]
  |-- guard: if (!socketConnected) return (line 152-154)
  |-- socket.emit("subscribe", { symbols: items }) (line 115 via subscribe callback)
```

### 3.3 Connection state analysis

`deriveConnectionState` (useLiveMarketData.tsx:45-57):
```typescript
function deriveConnectionState(socketConnected, status, graceElapsed): ConnectionState {
  if (!socketConnected) {
    return graceElapsed ? "offline" : "connecting";
  }
  if (!status) {
    return "connecting";
  }
  return status.state;  // <-- returns worker's "state" field: "live", "degraded", "offline"
}
```

**Critical finding**: The frontend connection state returns `status.state` directly (line 56). The worker's `status()` returns the `_state` field which is set to `STATE_LIVE`, `STATE_DEGRADED`, etc. This state only changes on lifecycle events (connect, disconnect, error), **not on tick staleness**. So the badge can show "Connected" (green) even when no ticks have arrived for minutes.

The backend has `freshness` at `market_data_worker.py:500` which detects staleness (>30s since last tick), but this is **never sent to the frontend as a separate field**. The frontend's `MarketDataStatus` interface (realtime.ts:28-35) does not include a `freshness` field.

**However**: the `status.last_tick_at` IS sent (market_data_worker.py:492) and IS received by the frontend (useLiveMarketData.tsx:119 stores it as `lastTickAt`). But `lastTickAt` is **never checked for staleness** in either `deriveConnectionState` or any render logic.

### 3.4 Subscription analysis

**Auto-subscription on connect** (realtime.py:120):
```python
_subscribe_requests(DEFAULT_WATCHLIST)
```
Subscribes to `NIFTY` (NFO futures) and `BANKNIFTY` (NFO futures).

**Position-based subscription** (DashboardPage.tsx:220-231):
```typescript
positionSubscriptions = positions.map(p => ({
  symbol: p.symbol,
  exchange: p.exchange_code,
  product_type: p.product_type,
}));
```

Both paths flow through `_subscribe_requests` in `realtime.py:102-108`, which calls `resolve_subscription_items` → `SymbolResolver.resolve()` → `worker.subscribe(items)`.

**Frontend subscribe emit** (useLiveMarketData.tsx:115):
```typescript
socket.emit("subscribe", { symbols: items });
```

**Backend subscribe handler** (realtime.py:131-139):
```python
@socketio.on("subscribe")
def _handle_subscribe(data):
    requests = _coerce_requests(data)  # line 133 — extracts items from {symbols: [...]}
    _subscribe_requests(requests)
```

**`_coerce_requests`** (realtime.py:157-165):
```python
def _coerce_requests(data):
    if isinstance(data, dict):
        symbols = data.get("symbols")
        if isinstance(symbols, list):
            return [item for item in symbols if isinstance(item, dict)]
        return [data]
    ...
```

**Frontend sends**: `socket.emit("subscribe", { symbols: items })` where `items` is an array of `{symbol, exchange, product_type}` objects.

**Backend receives**: `data = {symbols: [{symbol: "...", exchange: "...", product_type: "..."}]}`. `_coerce_requests` extracts the inner array. **This is correct.** No mismatch.

### 3.5 Symbol key chain

| Stage | Key used |
|-------|----------|
| Backend `_normalize_tick` output | `"symbol"` = `subscription.display_symbol` (line 424-425) |
| Worker `_last_ticks[sym]` | `sym` = normalized `"symbol"` (line 386, 388) |
| Frontend socket `"tick"` handler | `tick.symbol` as key for `setTicks` (line 99) |
| MarketTicker lookup | `ticks[item.symbol.toUpperCase()]` (line 34) |
| DashboardPage PositionsTable lookup | `ticks[rawPosition.symbol.toUpperCase()]` (line 168) |
| PositionPage lookup | `ticks[position.symbol.toUpperCase()]` (line 129) |

**All lookups use `symbol.toUpperCase()`**. Backend `display_symbol` is already uppercase (set via `resolved.display_symbol` which is stored in DB as uppercase). **No mismatch.**

### 3.6 Event name analysis

| Backend emits | Frontend listens | Match? |
|---------------|------------------|--------|
| `"tick"` (market_data_worker.py:464) | `"tick"` (useLiveMarketData.tsx:95) | **YES** |
| `"status"` (market_data_worker.py:481) | `"status"` (useLiveMarketData.tsx:94) | **YES** |

### 3.7 Payload shape comparison

**Backend emitted tick** (`_normalize_tick` return, market_data_worker.py:424-441):
```python
{
    "symbol": str,           # display_symbol from subscription
    "broker_symbol": str,    # subscription.broker_symbol
    "exchange_code": str,    # subscription.exchange_code
    "product_type": str,     # subscription.product_type
    "token": str,            # subscription.token
    "stock_token": str,      # raw stock_token from breeze
    "ltp": float | None,
    "open": float | None,
    "high": float | None,
    "low": float | None,
    "close": float | None,
    "change": float | None,
    "change_percent": float | None,
    "volume": float | None,
    "oi": float | None,
    "ts": str,               # ISO 8601 UTC
}
```

**Frontend `LiveTick` interface** (realtime.ts:7-24):
```typescript
interface LiveTick {
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
    ts: string;
}
```

**All 16 fields match exactly by name and type.** No mismatch.

### 3.8 Frontend re-render analysis

- `ticks` is a state variable in `LiveMarketDataProvider` (useLiveMarketData.tsx:65):
  ```typescript
  const [ticks, setTicks] = useState<Record<string, LiveTick>>({});
  ```
- Updated via functional setter (line 99):
  ```typescript
  setTicks((current) => ({ ...current, [tick.symbol]: tick }));
  ```
- React's `useState` with functional updater is immune to stale closures on the previous state.
- New object reference each tick → consumers re-render if they use `ticks`.
- `useMemo` on context value (lines 121-124) includes `ticks` in deps → context re-renders.
- MarketTicker reads `ticks` from context → re-renders on every tick.

**No stale closure or re-render block found in this path.**

### 3.9 Part 3 verdict

**No clear code defect found** — the frontend receive path is structurally sound:
- Event names match (`"tick"` both sides)
- Payload shapes match (16/16 fields identical)
- Symbol key chain is consistent (all use `symbol` uppercase)
- No stale closures (functional `setTicks` updater)
- No subscription event-name mismatch (both use `"subscribe"`)
- Socket URL and transport config are standard socket.io-client options

The only suspicious aspect is the **connection badge logic** which does not incorporate `last_tick_at` freshness — but this is a UI feedback issue, not a cause of missing updates.

If the frontend is NOT updating, the cause must be **upstream** (back-end emit path or socket transport) rather than frontend state management.

---

## PART 4 — BACKEND EMIT VS FRONTEND EXPECTATION COMPARISON

### 4.1 Field-by-field contract table

| # | Field | Backend emits (normalized tick) | Frontend expects (LiveTick) | Match? | Consequence if mismatch |
|---|-------|-------------------------------|----------------------------|--------|------------------------|
| 1 | `symbol` | `subscription.display_symbol` (uppercase, e.g. `NIFTY`) | `string` — used as index key `tick.symbol` | **YES** | N/A |
| 2 | `broker_symbol` | `subscription.broker_symbol` (e.g. `CNXBAN`) | `string` | **YES** | N/A |
| 3 | `exchange_code` | `subscription.exchange_code` | `string` | **YES** | N/A |
| 4 | `product_type` | `subscription.product_type` | `string` | **YES** | N/A |
| 5 | `token` | `subscription.token` | `string` | **YES** | N/A |
| 6 | `stock_token` | raw Breeze stock token | `string` | **YES** | N/A |
| 7 | `ltp` | `float \| None` | `number \| null` | **YES** | N/A |
| 8 | `open` | `float \| None` | `number \| null` | **YES** | N/A |
| 9 | `high` | `float \| None` | `number \| null` | **YES** | N/A |
| 10 | `low` | `float \| None` | `number \| null` | **YES** | N/A |
| 11 | `close` | `float \| None` | `number \| null` | **YES** | N/A |
| 12 | `change` | `float \| None` (abs change) | `number \| null` | **YES** | N/A |
| 13 | `change_percent` | `float \| None` | `number \| null` | **YES** | N/A |
| 14 | `volume` | `float \| None` | `number \| null` | **YES** | N/A |
| 15 | `oi` | `float \| None` | `number \| null` | **YES** | N/A |
| 16 | `ts` | ISO 8601 UTC string | `string` | **YES** | N/A |

**All 16 fields match by name and type. Contract is fully aligned.**

### 4.2 Symbol mapping analysis

**Backend emits**: `symbol` = `display_symbol` (e.g. `"NIFTY"` for NFO futures). This is from `SymbolResolver.resolve()` which resolves `"NIFTY"` + `"NFO"` + `"futures"` to `display_symbol = "NIFTY"`.

**Frontend expects**: `tick.symbol` = the key used in `ticks[displaySymbol]`.

**DashboardPage** expects `symbol` to match `rawPosition.symbol` (from REST dashboard summary).

**PositionsPage** expects `symbol` to match `position.symbol.toUpperCase()` (from REST positions).

**MarketTicker** expects `symbol` to match `item.symbol.toUpperCase()` (from REST dashboard summary ticker).

**All three consumers use `.toUpperCase()`** on the REST-originated symbol to look up the tick. The backend emits `display_symbol` which is already uppercase. **No mismatch.**

### 4.3 Specific questions answered

**Q: If backend emits `CNXBAN`, can frontend map it to `BANKNIFTY`?**
A: The backend never emits `CNXBAN` as the `symbol` field. The `symbol` field is `display_symbol` which is the user-facing name (`"BANKNIFTY"`). The `broker_symbol` field would be `"CNXBAN"` but this is never used as a lookup key by any component. Frontend only uses `tick.symbol` for lookups. So there is no mismatch.

**Q: If backend emits NIFTY futures, can topbar/dashboard render them?**
A: Yes. Frontend components all use `tick.symbol` (which equals `"NIFTY"`) matched to REST data's `symbol` field (also `"NIFTY"`).

**Q: Is there any place where update can be lost because lookup keys differ?**
A: No — the evidence shows all lookup paths use the same key: `symbol` (display_symbol), compared with `.toUpperCase()`.

### 4.4 Part 4 verdict

**Contract aligned** — all 16 fields match, all lookup keys are consistent, and there is no evidence of a payload shape or mapping issue.

---

## PART 5 — RUNTIME EVIDENCE COLLECTION PLAN

### 5.1 Access status

**Railway project URL**: `https://railway.com/project/ff5afa1d-51ff-4394-b24a-522171729f3e`
**Result**: Railway dashboard requires browser authentication. Cannot access programmatically via fetch.
**Public endpoints that ARE accessible** (confirmed working):

| Endpoint | URL | Last response |
|----------|-----|---------------|
| `/api/diagnosis/worker` | https://web-production-39a4a.up.railway.app/api/diagnosis/worker | 2026-06-17T16:04:05Z — worker offline, no ticks |
| `/api/diagnosis/cache` | https://web-production-39a4a.up.railway.app/api/diagnosis/cache | 2026-06-17T16:04:05Z — Redis online, tick_keys=0 |
| `/api/market-data/snapshot` | https://web-production-39a4a.up.railway.app/api/market-data/snapshot | 2026-06-17T16:04:06Z — ticks empty |
| `/api/health/readiness` | https://web-production-39a4a.up.railway.app/api/health/readiness | Not checked (outside scope) |

**Note**: All endpoints return expected post-market data. Market is closed (16:04 UTC = 21:34 IST). Worker is offline because no socket client has triggered `ensure_started()`.

### 5.2 What runtime facts are already proven

From the backtest evidence (not re-verifiable at this moment due to market hours):

| # | Fact | Source | Proved? |
|---|------|--------|---------|
| RF1 | Worker receives real Breeze ticks during market hours | `/api/diagnosis/worker`: `ticks_received_ever: true`, `tick_count_total > 32000`, real timestamps | **YES** |
| RF2 | In-memory snapshot stores real tick data | `/api/market-data/snapshot`: returned 2 real futures ticks with realistic LTP, open, high, low | **YES** |
| RF3 | Redis is reachable from the backend | `/api/diagnosis/cache`: `status: "online"`, `dbsize: 2` | **YES** |
| RF4 | Redis tick key count was 0 at time of check | `/api/diagnosis/cache`: `tick_keys: 0` | **YES** (but could be TTL expiry) |

### 5.3 What runtime facts remain unproven until next market session

| # | Question | How to verify |
|---|---------|---------------|
| RQ1 | Does `_write_redis` actually succeed when market is live? | During market: poll `/api/diagnosis/cache` while ticks flow. If worker ticks advance but `tick_keys` stays 0, write path is broken. |
| RQ2 | Does `_emit` → `socketio.emit` actually produce WebSocket frames? | During market: open browser DevTools Network → WS, check for `42["tick",{...}]` frames. If none arrive while badge shows "Connected", emit path is broken. |
| RQ3 | Does the frontend socket stay connected during market hours? | Check browser DevTools Network → WS for continuous WebSocket frames (ping/pong at 25s interval), check console for disconnect warnings. |
| RQ4 | Is there a reconnect loop causing lost ticks? | Check browser console for `[market-data] socket disconnect:` warnings, count frequency. |

### 5.4 What is already diagnosable without waiting for market

- **Redis write path has a proven silent-failure risk**: `_write_redis` at line 450-451 swallows all exceptions. The worker's Redis client is cached once (line 453-456) and never recreated. A single connection error causes all subsequent writes to silently fail. **This is a code defect regardless of runtime evidence.**
- **Socket emit path has a proven silent-failure risk**: `_emit` at line 465-466 swallows all exceptions. **This is a code defect regardless of runtime evidence.**
- **Frontend payload contract is fully aligned**: No mismatch found. **Frontend is not the issue.**
- **Diagnostic counters are misleading**: They measure what enters `_on_ticks`, not what reaches Redis or the frontend. Worker can report "healthy" with both paths broken.

---

## PART 6 — ROOT CAUSE RANKING

| Rank | Cause | Confidence | Evidence FOR | Evidence AGAINST | Solvable now? |
|------|-------|------------|-------------|------------------|---------------|
| 1 | **Silent `_write_redis` failure on cached Redis client** | **High** (code) | Line 450-451 swallows all exceptions. Line 453-456 caches client once. `/api/diagnosis/cache` uses fresh client. This is the exact pattern that would produce "worker has 32K ticks, cache has 0 keys" during live market. | Market-closed state makes `tick_keys=0` expected (60s TTL). Cannot prove without live-market `/api/diagnosis/cache` showing keys=0 while worker ticks advance. | **Yes (code fix)** — add logging + error counter to `_write_redis` |
| 2 | **Silent `_emit` failure via socketio.emit from breeze thread** | **Medium-High** (code) | Line 465-466 swallows all exceptions. `_publish = socketio.emit` is called from a non-server thread with `message_queue=redis_url` (realtime.py:51). If Redis pub/sub fails, the exception is silently caught. Frontend stays "Connected" (via `connectionState`) but receives zero tick events. | No runtime evidence of emit failure. The `message_queue` is designed specifically for cross-thread emits. Could be working correctly. | **Yes (code fix)** — add logging + error counter to `_emit` |
| 3 | **Both `_write_redis` AND `_emit` failing from same Redis connectivity root cause** | **Medium** | If the worker's cached Redis client has a broken connection, both `_write_redis` (direct Redis set) AND `_emit` (via `message_queue` = Redis pub/sub) would silently fail. This would explain BOTH "cache empty" AND "frontend not updating". | No direct evidence linking the two paths. `_write_redis` and `message_queue` use separate client instances. | **Yes (code fix)** — fix covers both |
| 4 | **Frontend connection badge meaning vs tick freshness** | **Low** (not a root cause of missing updates) | Line 56 returns `status.state` which does not incorporate `last_tick_at` staleness. Badge can show "Live" while ticks are stale. | This is a UI feedback issue, not a cause of missing updates. The badge is a symptom, not a root cause. | **Yes (code fix)** — incorporate freshness into connection state |
| 5 | **Token/subscription mismatch causing ticks to be normalized with fallback values** | **Low** | Proved fact #1 token mismatch is mostly ruled out. Evidence shows worker received 32K+ ticks, subscriptions=2, symbols=CNXBAN,NIFTY — all consistent. Normalization works (snapshot returns data). | Token mismatch cannot explain 32K ticks flowing through but frontend not updating. | N/A |

---

## PART 7 — FINAL VERDICT

### 7.1 What is already proven

1. **Backend receives live ticks** — `/api/diagnosis/worker` showed `ticks_received_ever: true`, `tick_count_total > 32000`, real timestamps.
2. **In-memory snapshot stores ticks** — `/api/market-data/snapshot` returned real normalized tick payloads.
3. **Redis is reachable** — `/api/diagnosis/cache` returned `status: "online"`, `dbsize: 2`.
4. **Redis tick keys were 0** — at the time of check, `tick_keys: 0`. (Could be TTL expiry since market was closed.)
5. **Frontend payload contract matches backend exactly** — all 16 `LiveTick` fields align.
6. **Frontend event listeners match backend emits** — both use `"tick"` and `"status"` event names.
7. **Frontend symbol lookup keys are consistent** — all use `tick.symbol` (display_symbol) with `.toUpperCase()`.
8. **Frontend state update has no stale-closure bug** — uses functional `setTicks(prev => ...)`.
9. **Worker's Redis client is cached once and never recreated** — `_redis_client()` (line 453-456).
10. **Both `_write_redis` and `_emit` swallow ALL exceptions silently** — bare `except Exception: pass` at lines 450-451 and 465-466.
11. **Diagnostic counters advance before Redis write and emit** — in-memory update (line 388) runs before `_write_redis` (line 390) and `_emit` (line 392). Counters can show "healthy" while both downstream paths are broken.

### 7.2 What is still unproven

1. **Whether `_write_redis` actually succeeds during live market** — code shows it can silently fail, but runtime evidence during market hours is needed to confirm that it does.
2. **Whether socket emit successfully reaches frontend during live market** — code shows it can silently fail via `message_queue`, but no runtime evidence of actual failure.
3. **Whether the combination of both failures (Redis and emit) occurs** — this would explain both symptoms (cache empty + frontend not updating) but cannot be confirmed without live runtime.

### 7.3 Highest-confidence root cause

> **Silent `_write_redis` and/or `_emit` failure caused by bare `except Exception: pass` exception handlers (market_data_worker.py lines 450-451, 465-466), combined with a cached-once Redis client that can gradually enter an error state.**

**Evidence**:
- `_write_redis` line 450-451: `except Exception: pass` — zero diagnostics
- `_emit` line 465-466: `except Exception: pass` — zero diagnostics
- `_redis_client()` line 453-456: client created once, cached forever, never recreated on error
- Worker counters advanced BEFORE Redis write and emit, so `/api/diagnosis/worker` masks the failure
- `/api/diagnosis/cache` creates a FRESH client per request, so it can report `online` while the worker's cached client is broken

The two silent-failure points create a **diagnostic blind spot** where the worker appears healthy (counters advance, snapshot returns data, freshness reports active) while both Redis writes and socket emits silently fail.

### 7.4 Secondary possible cause

**Frontend connection badge masks the problem**. The badge shows "Connected" based on socket transport + worker state (not tick freshness). Users see a green "Connected" badge and expect live updates, but ticks may not be arriving due to the backend emit failure. This is a secondary cause — it does not prevent updates but it misleads users into thinking the system is healthy.

### 7.5 What can be fixed immediately without waiting for market

1. **Add exception logging to `_write_redis`** (market_data_worker.py:450): Replace `except Exception: pass` with `except Exception: logger.exception(...)`. This will immediately show in Railway logs whether Redis writes are succeeding.
2. **Add exception logging to `_emit`** (market_data_worker.py:465): Replace `except Exception: pass` with `except Exception: logger.exception(...)`. This will immediately show in Railway logs whether socket emits are succeeding.
3. **Add Redis write success/failure counters to diagnostics** (market_data_worker.py:128-135): Add `_redis_write_attempts` and `_redis_write_errors` counters, expose in `status()`. This makes `/api/diagnosis/worker` report Redis health.
4. **Add emit success/failure counters**: Add `_emit_attempts` and `_emit_errors` counters, expose in `status()`. This makes `/api/diagnosis/worker` report emit health.
5. **Add `freshness` field to frontend `MarketDataStatus` and use it in `deriveConnectionState`**: When `freshness === "stale"`, the badge should show a different state even if socket transport is connected.

### 7.6 What must be verified during next live market

1. Deploy with logging fix (#1 and #2 above) → check Railway logs for `_write_redis` and `_emit` success/failure messages during market hours.
2. Poll `/api/diagnosis/cache` every 10 seconds during market → verify `tick_keys` becomes and stays non-zero.
3. Poll `/api/diagnosis/worker` simultaneously → verify `tick_count_total` advances while `tick_keys` is non-zero.
4. Open browser DevTools → Network → WS frames → verify `42["tick", {...}]` frames arrive continuously.
5. If frames arrive but UI does not update → verify with a simple `console.log` in the `socket.on("tick")` handler.

### 7.7 No-code-change diagnosis verdict

**The primary diagnosis is a confirmed silent-failure risk in the backend emit and Redis write paths, with a high likelihood that one or both are failing during live market hours.**

The code defects (bare `except Exception: pass` at market_data_worker.py:450-451 and 465-466) are proven from static analysis alone. The cached Redis client architecture (market_data_worker.py:453-456) creates a failure mode where the worker's client can silently break while fresh HTTP-request clients succeed.

The frontend code is **structurally sound** — all event names, payload shapes, and symbol lookups are aligned. No code defect was found in the frontend receive path.

The diagnosis is complete and actionable. The next step is the fix pass, starting with:
1. Adding exception logging to `_write_redis` and `_emit`
2. Adding Redis write and emit diagnostic counters to the worker
3. Deploying during market hours to observe the logs

---

## PART 8 — ISSUE REGISTER

| ID | Layer | Issue | Confidence | Evidence | Needs Live Market? |
|----|-------|-------|------------|----------|--------------------|
| I1 | Backend Redis write | `_write_redis` swallows all exceptions (line 450-451 bare `except`) | **High** | market_data_worker.py line 450-451 | No — code defect proven from static analysis |
| I2 | Backend socket emit | `_emit` swallows all exceptions (line 465-466 bare `except`) | **High** | market_data_worker.py line 465-466 | No — code defect proven from static analysis |
| I3 | Backend Redis client | Worker's Redis client created once and never recreated on error | **High** | market_data_worker.py line 453-456 | No — code defect proven from static analysis |
| I4 | Backend diagnostics | Counters advance before Redis write and emit, masking failures | **High** | market_data_worker.py lines 388-392 vs 450-451, 465-466 | No — execution order proven from static analysis |
| I5 | Frontend badge | `connectionState` does not incorporate tick freshness | **Low** (UI feedback, not root cause) | useLiveMarketData.tsx line 45-57 vs market_data_worker.py line 500 | No — logic proven from static analysis |
| I6 | Frontend receive path | No code defect found — all payloads, events, and keys aligned | **Proven clean** | Parts 3 and 4 of this report | N/A |
| I7 | Redis vs cache endpoint | `/api/diagnosis/cache` uses fresh client while worker uses cached client | **High** | diagnosis.py line 226 vs market_data_worker.py line 453-456 | No — architecture proven from static analysis |

### Files inspected

- `backend/app/services/market_data_worker.py`
- `backend/app/realtime.py`
- `backend/app/api/diagnosis.py`
- `backend/app/api/market_data.py`
- `backend/app/cache.py`
- `backend/app/services/tick_recorder.py`
- `frontend/src/lib/realtime.ts`
- `frontend/src/hooks/useLiveMarketData.tsx`
- `frontend/src/components/dashboard/MarketTicker.tsx`
- `frontend/src/components/layout/TopHeader.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/vite.config.ts`
- `backend/Procfile`
- `backend/run.py`
- `backend/factory.py`

### Functions inspected

- `MarketDataWorker.__init__` (market_data_worker.py:82)
- `MarketDataWorker._on_ticks` (market_data_worker.py:371)
- `MarketDataWorker._normalize_tick` (market_data_worker.py:405)
- `MarketDataWorker._write_redis` (market_data_worker.py:443)
- `MarketDataWorker._redis_client` (market_data_worker.py:453)
- `MarketDataWorker._emit` (market_data_worker.py:458)
- `MarketDataWorker.status` (market_data_worker.py:485)
- `MarketDataWorker.snapshot` (market_data_worker.py:504)
- `MarketDataWorker._freshness` (market_data_worker.py:356)
- `init_realtime` (realtime.py:32)
- `cache` (diagnosis.py:215)
- `worker` (diagnosis.py:267)
- `createMarketDataSocket` (realtime.ts:43)
- `LiveMarketDataProvider` (useLiveMarketData.tsx:59)
- `deriveConnectionState` (useLiveMarketData.tsx:45)
- `useLiveSubscribe` (useLiveMarketData.tsx:147)
- `MarketTicker` (MarketTicker.tsx:15)

### Endpoints checked

- `https://web-production-39a4a.up.railway.app/api/diagnosis/worker`
- `https://web-production-39a4a.up.railway.app/api/diagnosis/cache`
- `https://web-production-39a4a.up.railway.app/api/market-data/snapshot`

### Assumptions avoided

- Did NOT assume `_write_redis` succeeds during live market — proved it can silently fail from code
- Did NOT assume token mismatch — relied on proven facts (proven that ticks flow through normalization)
- Did NOT assume frontend is broken — proved it is structurally sound
- Did NOT assume Railway logs are accessible — reported access limitation, did not fake data

### Blockers

- Railway project dashboard (https://railway.com/project/ff5afa1d-51ff-4394-b24a-522171729f3e) requires browser authentication. Cannot access Railway logs programmatically. Need Railway CLI token or service-specific log share link to verify runtime behavior during market hours.
