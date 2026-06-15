# APTRADES2 — Phase 23B: Latency, Number Correctness, Live/Offline Badge Diagnosis

**Diagnosis date**: 2026-06-15 (Monday) IST ~21:30
**Market**: CLOSED
**Breeze session**: VALID (AJ510524)

---

## Part 1: Executive Summary

1. **Dashboard latency (10-30s) is caused by 3-4 sequential Breeze REST API calls per page load**, each taking 3-7s. The calls are: NIFTY quote → BANKNIFTY quote → portfolio positions (summary) → portfolio positions (alerts, duplicate).

2. **`get_batch_quotes()` iterates sequentially** over requests (for loop at `quote_service.py:60`), so NIFTY and BANKNIFTY quotes never run in parallel — doubling the Breeze wait time.

3. **Dashboard alerts calls portfolio positions AGAIN** (`dashboard_service.py:130`), duplicating the Breeze call already made in `get_summary()` (`dashboard_service.py:51`). This inflates the 30s timeout risk.

4. **NIFTY/BANKNIFTY displayed values are futures LTP from Breeze**, fetched correctly as `NFO/NIFTY/futures` and `NFO/BANKNIFTY/futures`. The values 23930 and 57211.2 are Breeze's `ltp` field. The labels read "NIFTY futures" / "BANKNIFTY futures" on dashboard cards, which is correct.

5. **Topbar ticker shows "NIFTY" (no "futures" suffix)** and uses the same futures LTP. This may mislead users expecting spot index values.

6. **The live/offline badge shows "Live" when the Breeze WebSocket connection is active**, regardless of market hours. This is technically correct (the socket is connected), but semantically confusing — users interpret "Live" as "market is open and streaming".

7. **The `_normalize_tick` method reads `_subscriptions` dict without lock** at `market_data_worker.py:355`, which is a race condition in a multi-threaded context.

8. **No endpoint timeout is set on Breeze HTTP calls** at the gateway level (breeze_gateway.py:281 uses `timeout=15`), but individual endpoints can hang up to 30s before Railway proxy timeout kills them.

9. **The chart endpoint** (`/api/dashboard/chart`) calls Breeze `/historicalcharts` for 30 days of daily data. The Breeze historical endpoint is slow or rate-limited, causing 30s timeouts.

10. **`/api/positions`, `/api/orders`, `/api/trades` endpoints also call Breeze REST synchronously** with no Redis cache fallback, so they suffer the same 3-7s per Breeze call.

---

## Part 2: Frontend Request Map

| Function | File | Component/Hook | Endpoint | Params | Interval | Type |
|---|---|---|---|---|---|---|
| `getDashboardSummary()` | `api.ts:564` | `DashboardPage` | `GET /api/dashboard/summary` | none | once on mount | HTTP fetch |
| `getDashboardAlerts()` | `api.ts:568` | `DashboardPage` | `GET /api/dashboard/alerts` | none | once on mount | HTTP fetch |
| `getDashboardChart()` | `api.ts:572` | `DashboardMarketChart` | `GET /api/dashboard/chart?symbol=NIFTY` | `symbol=NIFTY` | once on mount | HTTP fetch |
| `getDashboardSummary()` | `api.ts:564` | `MarketTicker` | `GET /api/dashboard/summary` | none | once on mount | HTTP fetch |
| Socket.IO `connect` | `realtime.ts:43` | `LiveMarketDataProvider` | `/socket.io` (WS) | none | once on mount | WebSocket |
| Socket.IO `status` event | `useLiveMarketData.tsx:94` | `LiveMarketDataProvider` | `status` (WS event) | backend-driven | on connect + state change | WebSocket event |
| Socket.IO `tick` event | `useLiveMarketData.tsx:95` | `LiveMarketDataProvider` | `tick` (WS event) | backend-driven | on each tick | WebSocket event |

**Key observation**: `DashboardPage` calls `getDashboardSummary()` and `getDashboardAlerts()` in parallel via `Promise.allSettled` (line 237). `MarketTicker` independently calls `getDashboardSummary()` again on mount (line 21). This means `/api/dashboard/summary` could be called twice on a full dashboard load, though the second call may hit before the first completes depending on timing.

---

## Part 3: Backend Call-Chain Map

### `/api/dashboard/summary` call chain

| Step | File:Line | Function | Dependency | Duration (estimated) |
|---|---|---|---|---|
| 1 | `dashboard.py:32` | `dashboard_summary()` | calls `DashboardService.get_summary()` | — |
| 2 | `dashboard_service.py:43` | `quote_service.get_batch_quotes([NIFTY, BANKNIFTY])` | Sequential loop | 2 × Breeze call |
| 3 | → `quote_service.py:62` | `self.get_quote(NIFTY)` | SymbolResolver (DB) + Breeze REST | 3-7s |
| 4 | → `breeze_gateway.py:138` | `get_quote()` | Breeze REST `/quotes` | 3-7s |
| 5 | → `quote_service.py:62` | `self.get_quote(BANKNIFTY)` | SymbolResolver (DB) + Breeze REST | 3-7s |
| 6 | → `breeze_gateway.py:138` | `get_quote()` | Breeze REST `/quotes` | 3-7s |
| 7 | `dashboard_service.py:51` | `positions_service.get_positions()` | Calls Breeze | 3-7s |
| 8 | → `positions_service.py:58` | `gateway.get_portfolio_positions()` | Breeze REST `/portfoliopositions` | 3-7s |

**Total best case (all Breeze calls 3s)**: 9s. **Worst case (all 7s)**: 28s.

### `/api/dashboard/alerts` call chain

| Step | File:Line | Function | Dependency | Duration |
|---|---|---|---|---|
| 1 | `dashboard.py:38` | `dashboard_alerts()` | calls `DashboardService.get_alerts()` | — |
| 2 | `dashboard_service.py:97` | `master_contract_service.get_status()` | DB query (cached) | <0.1s |
| 3 | `dashboard_service.py:98` | `gateway.auth_diagnostic()` | `get_customer_details()` (cached after first call) | <0.1s |
| 4 | `dashboard_service.py:130` | `positions_service.get_positions()` → `gateway.get_portfolio_positions()` | Breeze REST `/portfoliopositions` | 3-7s |

**Total**: 3-7s. **DUPLICATE** call to `get_portfolio_positions()` — `get_summary()` already called this.

### `/api/dashboard/chart` call chain

| Step | File:Line | Function | Dependency | Duration |
|---|---|---|---|---|
| 1 | `dashboard.py:43` | `dashboard_chart()` | calls `DashboardService.get_chart()` | — |
| 2 | `dashboard_service.py:165` | `self._resolve_chart_instrument(NIFTY)` | SymbolResolver DB | <0.1s |
| 3 | `dashboard_service.py:172` | `gateway.get_historical_charts()` | Breeze REST `/historicalcharts` (30 days daily) | 10-30s |

**Total**: 10-30s. Breeze historical charts endpoint is very slow or rate-limited.

### WebSocket `status` event flow

```
Socket.IO client connects
  → realtime.py:112 worker.ensure_started()
    → market_data_worker.py:180 _connect() → breeze.ws_connect()
    → on success: _set_state(STATE_LIVE)
    → on failure: _set_state(STATE_DEGRADED)
  → realtime.py:116 emit "status" with worker.status()
```

The `status` event payload is `worker.status()` which returns `{state, configured, subscriptions, symbols, last_tick_at, error}`. The frontend receives this and `deriveConnectionState()` in `useLiveMarketData.tsx:45` maps it:
- If socket not connected → "offline" (after 2s grace) or "connecting" (during grace)
- If socket connected but no status → "connecting"
- If socket connected and status exists → returns `status.state` directly

So **"Live" means the backend worker is in STATE_LIVE**, which means the Breeze WebSocket connection was successfully established. It does NOT check:
- Whether a tick was received recently
- Whether the market is open
- Whether data is actually flowing

---

## Part 4: Latency Diagnosis

### P23B-LAT-01: Sequential Breeze quotes in `get_batch_quotes`

| Field | Value |
|---|---|
| **Route** | `GET /api/dashboard/summary` |
| **Observed timing** | 3.7s to 14.5s (intermittent) |
| **Suspected blocking stage** | `quote_service.py:60` `for request in requests:` |
| **Exact code path** | `dashboard.py:32` → `dashboard_service.py:43-48` → `quote_service.py:58-73` → `quote_service.py:62` (called twice, sequentially) |
| **Why it blocks** | NIFTY and BANKNIFTY quotes are fetched one after the other. If Breeze takes 4s per quote, the user waits 8s just for quotes |
| **Classification** | Actual backend latency issue (serial Breeze REST calls) |
| **Confidence** | HIGH |
| **Evidence** | Direct code-path: `for request in requests:` at `quote_service.py:60` with no threading/async |

### P23B-LAT-02: Duplicate `get_portfolio_positions` call

| Field | Value |
|---|---|
| **Route** | Both `GET /api/dashboard/summary` and `GET /api/dashboard/alerts` |
| **Observed timing** | 3.7s to 27.3s combined |
| **Suspected blocking stage** | `dashboard_service.py:51` AND `dashboard_service.py:130` |
| **Exact code path** | `dashboard_service.py:42-93` (get_summary calls positions at line 51) and `dashboard_service.py:95-157` (get_alerts calls positions at line 130) |
| **Why it blocks** | Both summary and alerts call `self.positions_service.get_positions()` which calls `self.gateway.get_portfolio_positions()` — a redundant Breeze REST call. When frontend calls both endpoints in parallel, two Breeze portfolio-position requests can run simultaneously in separate gthread workers |
| **Classification** | Actual backend latency issue (redundant Breeze call) |
| **Confidence** | HIGH |
| **Evidence** | Direct code: `dashboard_service.py:51` and `dashboard_service.py:130` both call `self.positions_service.get_positions()` |

### P23B-LAT-03: `get_portfolio_positions` called with no active positions

| Field | Value |
|---|---|
| **Route** | All dashboard/positions endpoints |
| **Observed timing** | 3-7s per call even when empty |
| **Suspected blocking stage** | `breeze_gateway.py:153-158` `get_portfolio_positions()` |
| **Exact code path** | `breeze_gateway.py:153` → `_request("GET", "/portfoliopositions", ...)` → `_send()` → Breeze REST |
| **Why it blocks** | Even when the user has zero positions, Breeze still returns a response in 3-7s. There is no short-circuit for empty accounts |
| **Classification** | Broker/upstream latency |
| **Confidence** | HIGH |
| **Evidence** | Verified by deployed test: `/api/positions` returned HTTP 200 in 1.1s once but timed out other times. User confirmed account is empty |

### P23B-LAT-04: Chart endpoint Breeze historical call timeout

| Field | Value |
|---|---|
| **Route** | `GET /api/dashboard/chart?symbol=NIFTY` |
| **Observed timing** | 30s timeout (consistent) |
| **Suspected blocking stage** | `breeze_gateway.py:207-230` `get_historical_charts()` |
| **Exact code path** | `dashboard_service.py:172` → `gateway.get_historical_charts()` → `_request("GET", "/historicalcharts", ...)` → `_send()` → Breeze REST |
| **Why it blocks** | Breeze `/historicalcharts` endpoint is slow on Railway. The 15s HTTP timeout in `_send()` (line 281) triggers retries (line 279: 3 attempts with 1s sleep between), totaling up to ~47s before giving up. Railway proxy may kill earlier |
| **Classification** | Actual backend latency issue (Breeze upstream) |
| **Confidence** | HIGH |
| **Evidence** | Code shows 3 retries with 15s timeout each (lines 278-293). Deployed test confirmed consistent 30s timeout |

### P23B-LAT-05: Breeze `_send()` 3-retry loop on timeout

| Field | Value |
|---|---|
| **Route** | All Breeze-dependent endpoints |
| **Observed timing** | 15-47s for failed requests |
| **Suspected blocking stage** | `breeze_gateway.py:278-293` |
| **Exact code path** | `breeze_gateway.py:279-293` retry loop: 3 attempts with 15s timeout + 1s sleep between |
| **Why it blocks** | When Breeze upstream is slow or unresponsive, the gateway retries 3 times at 15s each = 45s total worst case. This is why some endpoints take 25-30s to timeout |
| **Classification** | Actual backend latency issue (aggressive retry on timeout) |
| **Confidence** | HIGH |
| **Evidence** | Code: `for attempt in range(3):` + `timeout=15` at lines 279-281 |

---

## Part 5: Number Mismatch Diagnosis

### NIFTY

| Field | Value |
|---|---|
| **Requested instrument** | `NFO / NIFTY / futures` (near-month) |
| **Data source** | Breeze REST `/quotes` → `quote.ltp` field |
| **Displayed value** | 23,930.00 |
| **Displayed label (dashboard card)** | "NIFTY futures" |
| **Displayed label (topbar ticker)** | "NIFTY" (no "futures" suffix) |
| **Reported change** | +13.4 vs prev close (23930.0 - 23916.6) |
| **Reported change %** | +0.06% |
| **NIFTY spot (from option chain)** | 23,853.9 (underlying_ltp at 16:25 UTC) |

**Diagnosis**: CORRECT futures LTP, CORRECT label on dashboard cards.

The value 23,930.0 is the NIFTY futures last traded price from the near-month expiry (2026-06-30). The previous close 23,916.6 is the futures previous close. The difference (+13.4, +0.06%) is the futures change from previous close.

**Potential confusion**: The topbar ticker displays just "NIFTY" without specifying futures. A user comparing this to the NIFTY 50 spot index (~23,854) would see a 76-point difference (futures premium). If the user expects spot values, the topbar is misleading.

### BANKNIFTY

| Field | Value |
|---|---|
| **Requested instrument** | `NFO / BANKNIFTY / futures` (near-month) |
| **Data source** | Breeze REST `/quotes` → `quote.ltp` field |
| **Displayed value** | 57,211.20 |
| **Displayed label (dashboard card)** | "BANKNIFTY futures" |
| **Displayed label (topbar ticker)** | "BANKNIFTY" (no "futures" suffix) |
| **Reported change** | -46.0 vs prev close (57211.2 - 57257.2) |
| **Reported change %** | -0.08% |

**Diagnosis**: CORRECT futures LTP, CORRECT label on dashboard cards.

Same analysis as NIFTY. The value is the BANKNIFTY futures LTP. The topbar may confuse users expecting spot values.

### Summary

| Aspect | Dashboard cards | Topbar ticker |
|---|---|---|
| Has "futures" label | YES ("NIFTY futures") | NO (just "NIFTY") |
| Value type | Futures LTP | Futures LTP |
| Change source | Futures prev close | Futures prev close |
| Verdict | CORRECT | Technically correct but ambiguous |

**No evidence of a bug in the values themselves.** The numbers match Breeze's quote response. Any perceived mismatch is likely because the user expects spot index values but sees futures values (evidenced by the ~76-point futures premium on NIFTY, matching typical near-month premium).

---

## Part 6: Live/Offline Badge Diagnosis

| Field | Value |
|---|---|
| **Frontend component** | `TopHeader.tsx:35` — `isLive = connectionState === "live"` |
| **Hook** | `useLiveMarketData.tsx` — `deriveConnectionState()` |
| **Socket status** | Whether Socket.IO transport is connected |
| **Backend state** | `worker.status().state` from `MarketDataWorker` |
| **Worker state "live" means** | Breeze WebSocket connection was successfully established |
| **Worker state "offline" means** | Breeze is not configured, or worker not started |
| **Worker state "degraded" means** | Breeze WebSocket connection failed/exception |
| **Worker state "connecting" means** | Worker is attempting to connect |

**The badge shows "Live" when**: Socket.IO is connected AND the backend worker reports state=`"live"`. The worker reaches state `"live"` when `breeze.ws_connect()` succeeds. Breeze's `ws_connect()` establishes a WebSocket connection to ICICI servers, which succeeds even when the market is closed (the socket connects to Breeze's streaming infrastructure, not directly to exchange feeds).

**Is "Live" a bug?** 

The behavior is:
- **Socket connected** + **worker state = "live"** → badge shows "Live" (green dot)
- This happens whenever Breeze WebSocket connects successfully, regardless of market hours
- The worker does NOT check: is market open? was a tick received recently? is the data flowing?

**Verdict**: This is a **wrong labeling / UX semantics** issue, not a backend bug. The system is correctly reporting "websocket connection is alive", but users interpret "Live" as "market is open and prices are updating". The badge should either:
1. Change label to "Connected" (technically accurate, less confusing)
2. Add a market-hours check (requires market open/close logic)
3. Check `last_tick_at` freshness (if no tick in N minutes, show "Stale" or "Offline")

---

## Part 7: Final Issue Register

### P23B-ISS-01: Sequential Breeze quote fetches in batch

| Field | Value |
|---|---|
| **Severity** | HIGH |
| **User impact** | Dashboard takes 6-14s just to load NIFTY + BANKNIFTY quotes |
| **Root cause** | `quote_service.py:60` `for request in requests:` — N calls run sequentially |
| **Files/functions** | `quote_service.py:58-73` `get_batch_quotes()`, `quote_service.py:32-56` `get_quote()` |
| **Fix type** | Parallelize with `concurrent.futures.ThreadPoolExecutor` or `asyncio` |

### P23B-ISS-02: Duplicate `get_portfolio_positions()` call in dashboard

| Field | Value |
|---|---|
| **Severity** | MEDIUM |
| **User impact** | Adds 3-7s extra latency when loading dashboard, doubles the chance of timeout |
| **Root cause** | Both `get_summary()` and `get_alerts()` independently call `positions_service.get_positions()` → Breeze |
| **Files/functions** | `dashboard_service.py:51` (get_summary → positions), `dashboard_service.py:130` (get_alerts → positions) |
| **Fix type** | Accept optional cached positions parameter in `get_alerts()`, or deduplicate on the service level |

### P23B-ISS-03: Chart historical data timeout

| Field | Value |
|---|---|
| **Severity** | HIGH |
| **User impact** | Dashboard chart never loads (30s timeout) |
| **Root cause** | Breeze `/historicalcharts` endpoint is slow; combined with 3-retry × 15s timeout pattern, requests can take 45s+ |
| **Files/functions** | `dashboard_service.py:172` → `breeze_gateway.py:207-230` `get_historical_charts()` → `_send()` retry loop `breeze_gateway.py:279-293` |
| **Fix type** | Cache historical chart data in Redis/DB with TTL; reduce retries; add timeout |

### P23B-ISS-04: 3-retry × 15s timeout on all Breeze REST calls

| Field | Value |
|---|---|
| **Severity** | HIGH |
| **User impact** | Breeze-dependent endpoints can hang up to 45s before giving up |
| **Root cause** | `breeze_gateway.py:279` `for attempt in range(3):` with `timeout=15` per attempt + 1s sleep between. 3 × (15+1) = 48s worst case |
| **Files/functions** | `breeze_gateway.py:278-293` `_send()` |
| **Fix type** | Reduce retries to 1 or 2; reduce timeout; differentiate between timeout and other errors |

### P23B-ISS-05: Live/offline badge shows "Live" when market is closed

| Field | Value |
|---|---|
| **Severity** | LOW |
| **User impact** | User sees "Live" outside market hours and may think data is stale or system is broken |
| **Root cause** | "Live" means Breeze WebSocket connected, not market open or data flowing |
| **Files/functions** | `topbar:35` `isLive = connectionState === "live"`; `useLiveMarketData.tsx:56` returns `status.state` directly; `market_data_worker.py:183` sets `STATE_LIVE` on websocket connect |
| **Fix type** | Add `last_tick_at` freshness check; change label to "Connected"; show stale indicator when no recent tick |

### P23B-ISS-06: Topbar ticker shows futures LTP without "futures" label

| Field | Value |
|---|---|
| **Severity** | LOW |
| **User impact** | User sees "NIFTY: 23,930" and expects NIFTY 50 spot index value (~23,854), causing confusion about the 76-point difference |
| **Root cause** | `MarketTicker.tsx:59` displays `quote.label` which is `item.symbol` (just "NIFTY") from the ticker array. The ticker data comes from `_ticker_item()` which doesn't include "futures" in the label |
| **Files/functions** | `MarketTicker.tsx:33-40` (uses `item.symbol` as label), `dashboard_service.py:223-224` (`_ticker_item()` sets `symbol: result["symbol"]`) |
| **Fix type** | Add "Futures" suffix to topbar ticker label, or show spot values in topbar |

### P23B-ISS-07: `get_portfolio_positions()` called even for empty accounts

| Field | Value |
|---|---|
| **Severity** | LOW |
| **User impact** | Unnecessary 3-7s Breeze REST call on every dashboard load when user has no positions |
| **Root cause** | No short-circuit: positions service always calls Breeze |
| **Files/functions** | `positions_service.py:58` → `breeze_gateway.py:153` |
| **Fix type** | Cache empty position response for short TTL; skip call when session is known empty |

---

## Part 8: Non-Issues

| Apparent issue | Verdict | Reason |
|---|---|---|
| NIFTY value 23,930 seems wrong | NOT AN ISSUE | It's the futures LTP, not spot. Label says "NIFTY futures" on dashboard. The futures premium (~76 pts over spot 23,854) is normal for near-month expiry |
| BANKNIFTY value 57,211 seems wrong | NOT AN ISSUE | Same as NIFTY — correct futures LTP |
| Change +13.4 on NIFTY seems small | NOT AN ISSUE | It's the change from futures previous close (23,916.6 to 23,930.0), correct |
| "Live" badge shows green when market closed | UX LABEL ISSUE | Badge means "Breeze WebSocket connected", not "market open". Technically correct but ambiguous wording |

---

## Part 9: Immediate Next Coding Order

After diagnosis, these fixes should be implemented in order:

1. **P23B-ISS-01** (HIGH): Parallelize `get_batch_quotes()` — wrap the for loop in `ThreadPoolExecutor` to fetch NIFTY/BANKNIFTY quotes concurrently
2. **P23B-ISS-03** (HIGH): Fix chart timeout — cache historical daily candles in DB with TTL; reduce retries in `_send()`
3. **P23B-ISS-04** (HIGH): Reduce Breeze retry aggressiveness — limit to 1 retry for timeouts, use shorter timeout
4. **P23B-ISS-02** (MEDIUM): Eliminate duplicate portfolio positions call in dashboard alerts — pass cached positions from summary
5. **P23B-ISS-07** (LOW): Cache empty positions response — skip Breeze call when account known empty
6. **P23B-ISS-05** (LOW): Improve live/offline badge semantics — add freshness check
7. **P23B-ISS-06** (LOW): Clarify topbar ticker label — add "Futures" suffix or switch to spot values
