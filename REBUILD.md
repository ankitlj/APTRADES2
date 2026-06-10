# APTRADES2 Rebuild Log

Date: 2026-06-07
Target repo: `https://github.com/ankitlj/APTRADES2.git`

## Phase 1 Skeleton

- Read and followed:
  - `APTRADES_v2_master_development_playbook.md`
  - `APTRADES_v2_MVP_scope_and_execution_plan.md`
  - `APTRADES_v2_from_scratch_architecture.md`
  - `APTRADES_v2_frontend_design_and_execution_plan.md`
  - Breeze API docs
  - `breeze-connect` PyPI package page
- Confirmed the new repo is separate from the old APTRADES/OpenAlgo codebase.
- Created a clean Flask backend skeleton with:
  - app factory
  - environment config loader
  - `/api/health`
  - `/api/health/readiness`
  - placeholder Breeze-related service modules
  - pytest health tests
- Created a React + Vite + TypeScript frontend skeleton with:
  - 224px sidebar
  - 48px topbar
  - main content spacing from the frontend plan
  - mobile bottom nav
  - Dashboard backend health/readiness panel
  - MVP route placeholders only
  - Vite dev proxy for local `/api/*` calls to Flask

## Verification

- `python -m pip install -e .[dev]` completed
- `python -m pytest` passed: `2 passed`
- `npm.cmd install` completed
- `npm.cmd run build` passed
- `http://localhost:5173/api/health` now works in local dev through the Vite proxy instead of failing in the browser with cross-origin fetch errors
- `curl http://127.0.0.1:5000/api/health` returned `status: ok`
- `curl http://127.0.0.1:5000/api/health/readiness` returned `api: online`, `postgres: not_configured`, `redis: not_configured`, `breeze: not_configured`

## Remaining Note

- The separate `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` file could not be updated from this workspace because it is outside the writable roots for this session.

## Phase 2 Deployment Foundation

- Added `flask-cors` and app-level CORS setup for local Vite plus future Vercel origin configuration.
- Added `/api/health/deployment` for a deployment-focused dashboard check.
- Added a Railway-friendly root `Procfile` using `gunicorn`.
- Updated the dashboard with a deployment status card and deployment target summary.

## Phase 2 Verification

- `python -m pip install -e .[dev]` completed with `flask-cors` and `gunicorn`
- `python -m pytest` passed: `3 passed`
- `curl http://127.0.0.1:5000/api/health/deployment` returned:
  - `api: online`
  - `postgres: unknown`
  - `redis: unknown`
  - `breeze: unknown`
- `npm.cmd run build` passed
- Railway runtime diagnosis showed `gunicorn: command not found`, so the backend now includes an explicit `requirements.txt` for Railpack dependency installation.

## Phase 3 DB/Redis Foundation

- Added SQLAlchemy engine helpers and Redis health helpers.
- Updated readiness and deployment health endpoints to report real DB/Redis status instead of fixed placeholders.
- Added Alembic scaffold files for future migrations.
- Added dashboard status pill coloring for service states.

## Phase 3 Verification

- `python -m pip install -e .[dev]` completed with SQLAlchemy, Alembic, and Redis
- `python -m pytest` passed: `3 passed`
- Inline backend checks returned:
  - SQLite database probe: `online`
  - Redis without URL: `not_configured`
- `npm.cmd run build` passed
- Follow-up deploy fix: added `psycopg[binary]` so Railway can connect SQLAlchemy to Postgres instead of reporting `offline` due to a missing driver.

## Phase 4 Breeze Diagnostics

- Re-read the official Breeze API reference for request headers, `CustomerDetails`, and `Quotes`, and used the `breeze-connect` PyPI page only as supporting reference.
- Implemented a real `BreezeGateway` with:
  - `CustomerDetails` token exchange
  - Breeze checksum/header signing
  - 3-attempt retry handling with 1 second delay
  - cached customer-session reuse during a single diagnostic run
- Added:
  - `GET /api/debug/breeze-auth`
  - `GET /api/debug/breeze-test`
- Added a temporary dashboard Breeze diagnostics panel that surfaces:
  - auth/config status
  - symbol-level status
  - returned LTP / previous close / spot / expiry when available
  - real Breeze error text when calls fail
- Added dedicated backend tests for Breeze gateway behavior.

## Phase 4 Verification

- `python -m pip install -e .[dev]` passed after rerunning with network access outside the sandbox
- `python -m pytest` passed: `11 passed`
- Local Flask test-client check returned:
  - `/api/debug/breeze-auth` -> `status: not_configured`
  - `/api/debug/breeze-test` -> structured error state without secrets
- `npm.cmd run build` passed after rerunning outside the sandbox
- User-confirmed deployed readiness now shows:
  - `api: online`
  - `postgres: online`
  - `redis: online`

## Phase 4 Note

- The user shared a fresh Breeze session token during the session. It was intentionally not written into repo files, logs, or commits. Live Breeze verification still depends on env vars for `BREEZE_API_KEY`, `BREEZE_SECRET_KEY`, and `BREEZE_SESSION_TOKEN`.

## Phase 5 Master Contract Import

- Added persistent SQLAlchemy models for:
  - `instruments`
  - `instrument_aliases`
  - `master_contract_runs`
- Implemented `MasterContractService` with:
  - SecurityMaster zip download/parsing
  - fallback/supplemental parsing of `C:\Users\Ankit\Desktop\Claude_Code\StockScriptNew.csv`
  - contract parsing for cash, futures, and options rows
  - alias extraction for display-symbol to broker-symbol mapping
  - import-run logging and status reporting
- Added:
  - `GET /api/master-contract/status`
  - `POST /api/master-contract/import`
  - `flask master-contract import`
- Added a Dashboard developer panel for:
  - instrument count
  - alias count
  - CSV availability
  - last import time
  - source/checksum
  - verified alias examples
- Cleaned up the stale topbar label so the deployed UI no longer says `Phase 1 skeleton`.

## Phase 5 Verification

- `python -m pytest` passed: `15 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox
- Real local smoke import against the supplied CSV returned:
  - `instrument_count = 33109`
  - `alias_count = 35445`
- Default endpoint behavior was verified:
  - `/api/master-contract/status` returns `not_configured` cleanly without a DB
  - `/api/master-contract/import` returns a clear DB-config-required error when `DATABASE_URL` is missing

## Phase 5 Note

- Railway will not be able to read `C:\Users\Ankit\Desktop\Claude_Code\StockScriptNew.csv` directly. Deployed imports can still use Breeze SecurityMaster, but CSV-driven alias enhancement on Railway requires a safe deployment-side copy or upload path.

## Phase 5 Deployment Fix

- Railway runtime logs showed the worker timing out while trying to download:
  - `http://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip`
- Added a Phase 5 follow-up fix so the import:
  - fails fast on unreachable SecurityMaster
  - falls back to a minimal seeded alias/instrument set instead of crashing the worker
- Added test coverage for the fallback import path.

## Phase 5 Deployment Fix Verification

- `python -m pytest` passed: `16 passed`
- The new fallback test confirms import succeeds even when:
  - SecurityMaster download fails
  - no local CSV is available

## Phase 5 Repo CSV Completion Fix

- Railway cannot read `C:\Users\Ankit\Desktop\Claude_Code\StockScriptNew.csv`, so the fallback-only import was expected once SecurityMaster timed out.
- Added the stable stock-code mapping file to the backend repo at:
  - `backend/data/StockScriptNew.csv`
- Changed the default backend CSV path to:
  - `data/StockScriptNew.csv`
- Added backend-root relative path resolution so the same config works when Railway uses `backend/` as the service root.
- Added regression coverage for repo-relative CSV availability.

## Phase 5 Repo CSV Completion Verification

- `python -m pytest` passed: `17 passed`
- Real repo-CSV smoke import with SecurityMaster disabled returned:
  - `status = ok`
  - `row_count = 33109`
  - `alias_count = 35445`
  - `source_name = stock_script_csv+seed_aliases`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial.

## Phase 5 Remaining Risk

- `http://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip` may still be unreachable from Railway.
- The repo-contained CSV now prevents the deployed import from dropping to the minimal seed-only source, but daily SecurityMaster freshness still needs a separate reachable-source solution if ICICI directlink continues timing out.

## Phase 5 HTTPS SecurityMaster Fix

- Tested the old HTTP ICICI SecurityMaster URL and confirmed it times out.
- Tested the HTTPS variant:
  - `https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip`
  - It returned `HTTP/1.1 200 OK` and a valid zip archive.
- Changed the backend default SecurityMaster URL from HTTP to HTTPS.
- Added configurable SecurityMaster connect/read timeouts:
  - `SECURITY_MASTER_CONNECT_TIMEOUT`
  - `SECURITY_MASTER_READ_TIMEOUT`
- Added parser support for ICICI SecurityMaster `.txt` files inside the zip.
- Mapped:
  - NSE/BSE cash master rows
  - NFO/BFO derivative master rows
- Removed the misleading seed fallback warning when SecurityMaster or StockScriptNew.csv data is available.

## Phase 5 HTTPS SecurityMaster Verification

- `python -m pytest` passed: `19 passed`
- Live Python `requests` probe downloaded the HTTPS SecurityMaster zip successfully.
- Live smoke import with SecurityMaster + repo CSV returned:
  - `status = ok`
  - `row_count = 127774`
  - `alias_count = 37204`
  - `source_name = security_master+stock_script_csv+seed_aliases`
  - `warnings = []`

## Phase 5 Daily Operations Note

- After this deploy, daily manual SecurityMaster download should not be required if Railway can reach the HTTPS ICICI URL.
- Breeze `BREEZE_SESSION_TOKEN` still must be refreshed in Railway when it expires.
- Master-contract import should be run by a Railway scheduled job once scheduling is configured.

## Phase 6 SymbolResolver and Quote Service

- Implemented `SymbolResolver` against `instruments` and `instrument_aliases`.
- Added:
  - cash alias resolution
  - derivative resolution for nearest futures contracts
  - shared `QuoteService` on top of `SymbolResolver` + `BreezeGateway`
- Added quote APIs:
  - `GET /api/quotes`
  - `POST /api/quotes/batch`
- Updated the old dashboard quote diagnostics path so it now uses the new quote API instead of constructing hardcoded Breeze requests directly.
- Added frontend shared hooks:
  - `useQuote`
  - `useBatchQuotes`
- Added a small quote status component and updated the dashboard to Phase 6 wording.

## Phase 6 Verification

- Read the Phase 6 section in the master playbook before implementation.
- Re-checked the official Breeze quotes API contract for mandatory request fields.
- `python -m pytest` passed: `23 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial.
- Verified mappings in tests:
  - `SBIN` resolves to `STABAN` on `NSE`
  - `BANKNIFTY` resolves to `CNXBAN` on `NFO` futures with a real expiry

## Phase 6 Current Futures Fix

- Deployed dashboard showed cash quotes working but NIFTY/BANKNIFTY NFO futures returning `No Data Found`.
- Root cause:
  - `StockScriptNew.csv` includes expired March/April/May 2026 futures rows.
  - The resolver selected the earliest expiry overall, so expired CSV futures won over current SecurityMaster futures.
- Fixed futures resolution to select the nearest non-expired expiry first.
- Kept fallback behavior for cases where only expired contracts exist.
- Quote API error responses now preserve resolved contract metadata when Breeze rejects the quote, making future broker failures easier to diagnose.
- Fixed `/api/debug/breeze-test` null handling for unresolved error rows.

## Phase 6 Current Futures Verification

- Reproduced deployed `No Data Found` for NIFTY/BANKNIFTY through `POST /api/quotes/batch`.
- Local SecurityMaster + repo CSV import reproduced the old bad selections:
  - `NIFTY~F:30-MAR-2026`
  - `CNXBAN~F:30-MAR-2026`
- After the fix, local resolver selects:
  - `NIFTY~F:30-JUN-2026`
  - `CNXBAN~F:30-JUN-2026`
- `python -m pytest` passed: `24 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial.

## Phase 7 Dashboard

- Built the first real dashboard page on top of backend contracts instead of diagnostic-only cards.
- Added backend dashboard APIs:
  - `GET /api/dashboard/summary`
  - `GET /api/dashboard/alerts`
  - `GET /api/dashboard/chart?symbol=NIFTY`
- Added read-only Breeze gateway support for:
  - `portfoliopositions`
  - `historicalcharts`
- Added a minimal `PositionsService` and a composed `DashboardService`.
- Replaced the Phase 6 dashboard UI with:
  - four metric cards
  - market chart panel
  - alerts panel
  - active positions table
- Added a dashboard-only topbar market ticker.
- Added `/dashboard` route support with `/` redirecting there.

## Phase 7 Verification

- Re-read the Phase 7 playbook section and dashboard design constraints before implementation.
- Added dashboard endpoint contract tests for:
  - summary
  - alerts
  - chart
- `python -m pytest` passed: `27 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial.

## Phase 7 Railway Runtime Fix

- Railway logs showed deployed Phase 7 was still incomplete:
  - `GET /api/dashboard/chart` returned `500`
  - Breeze `No Positions available.` surfaced as a dashboard error instead of an empty state
- Root cause:
  - chart code passed a `ResolvedInstrument` directly into the Breeze historical-chart gateway path
  - the gateway expects a normalized Breeze request instrument exposing `stock_code`
- Fixed:
  - dashboard chart now converts the resolved symbol through the shared quote-to-Breeze adapter before calling Breeze
  - positions service now treats `No Positions available.` as `status = ok` with zero totals and an empty list
  - dashboard contract tests now lock in both behaviors

## Phase 7 Railway Runtime Verification

- Reviewed Railway traceback confirming:
  - `AttributeError: 'ResolvedInstrument' object has no attribute 'stock_code'`
- `python -m pytest` passed: `28 passed`
- After deploy, expected user-visible result:
  - dashboard chart loads instead of `500`
  - alerts load normally
  - positions panel shows empty-state messaging when there are no open Breeze positions

## Phase 7 Vercel SPA Routing Fix

- Directly opening `https://aptrades-2.vercel.app/dashboard` returned a Vercel `404 NOT_FOUND` page.
- Root cause:
  - frontend uses `BrowserRouter`
  - Vercel frontend root had no rewrite sending unknown paths back to `index.html`
- Fixed:
  - added `frontend/vercel.json` with a catch-all rewrite to `index.html`

## Phase 7 Vercel SPA Routing Verification

- Confirmed `/dashboard` is a client route in `frontend/src/App.tsx`
- Confirmed the app mounts with `BrowserRouter` in `frontend/src/main.tsx`
- Frontend build re-run pending for this config-only deploy fix

## Phase 7 Chart Resolution and Panel Isolation Fix

- After the routing fix, the dashboard shell loaded but:
  - chart returned `400`
  - alerts and positions showed the same `400` even though their backend endpoints were not necessarily failing
- Root cause:
  - chart resolved `NIFTY` through `NSE cash` instead of the verified `NFO futures` live quote path
  - dashboard page used a single `Promise.all`, so one rejected request poisoned the other panel states
  - frontend error handling only surfaced generic HTTP status text
- Fixed:
  - dashboard chart now resolves `NIFTY` and `BANKNIFTY` through `NFO futures`
  - dashboard page now uses `Promise.allSettled` so each panel keeps its own success or failure state
  - API client now reads backend JSON error payloads and surfaces the real message when available

## Phase 7 Chart Resolution and Panel Isolation Verification

- `python -m pytest` passed: `28 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial

## Phase 7 Breeze Chart Interval Fix

- After the chart resolution fix, Breeze still rejected the chart request with:
  - `Interval should be either 'minute', '5minute', '30minute', or 'day'.`
- Root cause:
  - dashboard chart used `1day`
  - Breeze expects `day`
- Fixed:
  - changed dashboard chart interval to `day`
  - updated tests to lock in the Breeze interval contract

## Phase 7 Breeze Chart Interval Verification

- `python -m pytest` passed: `28 passed`

## Phase 8 Orderbook and Tradebook

- Added Breeze-backed order/trade API contracts:
  - `GET /api/orders`
  - `POST /api/orders/cancel`
  - `POST /api/orders/cancel-all`
  - `GET /api/trades`
- Extended `BreezeGateway` for:
  - order list
  - cancel order
  - trade list
- Added normalized backend services so frontend pages consume consistent rows and stats instead of raw Breeze payloads.
- Implemented `/orderbook` and `/tradebook` pages in the frontend and removed those placeholders.
- Added compact table layouts, filters, refresh, CSV export, and orderbook cancel actions.

## Phase 8 Verification

- `python -m pytest` passed: `32 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
- Added response examples to `development.md`
- Live broker cancel actions were implemented but not executed against the real account in this phase

## Phase 8 Runtime Fix

- Railway runtime showed live Breeze `404 Not Found` errors for:
  - `/api/orders`
  - `/api/trades`
- Root cause:
  - `BreezeGateway` used the wrong REST paths for live Breeze order/trade APIs.
  - Local Phase 8 contract tests mocked the gateway and therefore did not catch the path mismatch.
- Fixed:
  - order list -> `/order`
  - cancel order -> `DELETE /order`
  - trade list -> `/trades`
- Added gateway regression tests that assert those exact live Breeze endpoint paths.

## Phase 8 Runtime Fix Verification

- `python -m pytest` passed: `35 passed`

## Phase 9 Positions

- Added backend positions API:
  - `GET /api/positions`
- Expanded the old dashboard-only positions helper into a real positions contract service.
- Added normalization for Breeze portfolio rows and live quote enrichment through `QuoteService`.
- Kept close actions intentionally read-only for this phase:
  - frontend `Close All` and row `Close` controls are disabled
  - no close-position API endpoint has been added yet
- Replaced the `/positions` placeholder with a real page containing:
  - `Live/Paused` badge
  - toolbar with settings, refresh, export, close-all
  - stats cards
  - settings/filter panel
  - positions table with `Qty`, `Avg`, `LTP`, `P&L`, and `P&L%`
- Reused the same positions service in the dashboard so dashboard and positions stay on one live source of truth.

## Phase 9 Verification

- `curl http://127.0.0.1:5000/api/positions` returned `200` with a clean `not_configured` payload when Breeze env is absent
- `python -m pytest` passed: `39 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial

## Phase 10 Tools Reduced Scope

- Replaced the `/tools` placeholder with a real reduced-scope Tools page.
- Added only the six approved MVP tools:
  - Strategy Builder
  - Strategy Portfolio
  - Option Chain
  - Option Greeks
  - OI Tracker
  - OI Profile
- Kept the non-MVP tools out of the visible tools flow:
  - Max Pain
  - Straddle Chart
  - Straddle P&L
  - Vol Surface
  - GEX
  - IV Smile
- Added responsive grid behavior:
  - 1 column mobile
  - 2 columns medium
  - 3 columns large
- Added 40x40 icon tiles and compact cards consistent with the playbook.

## Phase 10 Verification

- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial

## Phase 11 Option Chain

- Added backend option-chain contracts:
  - `GET /api/options/expiries`
  - `GET /api/option-chain`
- Added `OptionChainService` on top of:
  - PostgreSQL master-contract expiries
  - Breeze native option-chain quotes
  - short Redis caching for repeated refreshes
- Extended `BreezeGateway` with a dedicated option-chain request path.
- Added a real frontend `/optionchain` page with:
  - exchange / underlying / expiry / strike-count controls
  - summary cards for spot, ATM strike, PCR, and total OI
  - CE/PE strike grid
  - real backend error surfacing
- Updated the Tools page so the `Option Chain` card opens the live route.

## Phase 11 Verification

- `python -m pytest backend\\tests\\test_option_chain_contract.py` passed: `2 passed`
- `python -m pytest backend` passed: `41 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial

## Phase 11 Runtime Fix

- Deployed `/optionchain` exposed a real Breeze `404` on:
  - `/optionchainquotes`
- Re-checked the official Breeze API docs and corrected the gateway path to:
  - `/optionchain`
- Added a regression test so the live option-chain endpoint path stays locked to the documented contract.

## Phase 11 Runtime Fix Verification

- `python -m pytest backend\\tests\\test_breeze_gateway.py` passed
- `python -m pytest backend` passed

## Phase 12 Skip Note

- Phase 12 (Option Greeks) was intentionally deferred.
- Greeks will be computed inline in strategy code when needed (Black-Scholes / Heston / Monte Carlo).
- No backend endpoints, no frontend pages were added for Phase 12.
- Phase 13 has no dependency on Phase 12.

## Phase 13 OI Tracker and OI Profile

- Added `OIService` wrapping `OptionChainService` with full-chain fetch (strike_count=0).
  - `get_tracker()` returns all strikes sorted by total OI descending with max_ce_oi_strike and max_pe_oi_strike.
  - `get_profile()` returns all strikes sorted by strike_price ascending.
  - No new Breeze endpoint — both reuse `/optionchain` via the existing Phase 11 gateway call.
- Added backend endpoints:
  - `GET /api/oi/tracker`
  - `GET /api/oi/profile`
- Registered `oi_bp` in `factory.py`.
- Added 4 contract tests in `backend/tests/test_oi_contract.py`.
- Added `OITrackerPage` at `/oi-tracker` — control bar, 4 stat cards (ATM, PCR, resistance strike, support strike), table sorted by total OI descending with inline CE/PE split bar.
- Added `OIProfilePage` at `/oi-profile` — same control bar, 4 stat cards (spot, ATM, PCR, total OI), table sorted by strike ascending with ATM highlight and proportional CE/PE bars.
- Updated `ToolsPage.tsx` — OI Tracker and OI Profile cards are now live links.
- Updated `AppShell.tsx` — topbar label changed to Phase 13 OI tools, extraPages map includes new routes.

## Phase 13 Verification

- `python -m pytest` passed: `46 passed`
- `npm.cmd run build` passed: `52 modules`

## Phase 14 Strategy Builder and Strategy Portfolio

- Added `Strategy` SQLAlchemy model to `models.py` with id, name, underlying, exchange_code, expiry_date (Date), legs_json (Text), created_at, updated_at. Auto-created via existing `ensure_tables()` — no Alembic migration.
- Added `StrategyService`:
  - `list_strategies()` — all strategies ordered by created_at desc
  - `create_strategy()` — saves and returns strategy dict with computed `net_premium`
  - `delete_strategy()` — raises `StrategyServiceError` if not found
  - `compute_payoff()` — 50-point curve, CE/PE intrinsic math, linear-interpolated breakevens
- Added `strategy_bp` with 4 routes:
  - `GET /api/strategies`
  - `POST /api/strategies/payoff` (registered before `<int:id>` route)
  - `POST /api/strategies`
  - `DELETE /api/strategies/<int:strategy_id>`
- Registered `strategy_bp` in `factory.py`.
- Added 7 contract tests in `backend/tests/test_strategy_contract.py`.
- Added shared `PayoffChart` component — pure SVG, no chart library, green/red fills via clipPath, breakeven markers.
- Added `StrategyBuilderPage` at `/strategy-builder` — exchange/underlying/expiry controls, strategy name, leg builder (action/right/strike/qty/premium, max 8), legs table with remove-per-row, preview payoff (4 stat cards + SVG diagram), save strategy.
- Added `StrategyPortfolioPage` at `/strategy-portfolio` — list saved strategies, strategy cards with leg tags, net premium badge, toggle inline payoff, delete.
- Updated `ToolsPage.tsx` — Strategy Builder and Portfolio cards changed from planned to live hrefs.
- Updated `AppShell.tsx` — extraPages map includes new routes, topbar label changed to Phase 14 strategy tools.

## Phase 14 Verification

- `python -m pytest` passed: `53 passed`
- `npm.cmd run build` passed: `55 modules`

## Phase 15 Action Centre and Logs

- Added SQLAlchemy tables for:
  - `pending_actions`
  - `api_logs`
  - `app_event_logs`
- Implemented `ActionCentreService`:
  - syncs pending rows from live cancellable Breeze orders
  - persists approve/reject state changes
  - approve sends the linked Breeze cancel request
  - reject preserves the audit row without touching the broker
- Implemented `LogsService`:
  - stores API request rows
  - stores app event rows
  - filters by level / source / time
  - returns a merged live-tail payload
- Added backend endpoints:
  - `GET /api/action-centre`
  - `POST /api/action-centre/:id/approve`
  - `POST /api/action-centre/:id/reject`
  - `GET /api/logs`
  - `GET /api/logs/live`
- Registered global API request logging in `factory.py` for `/api/*` responses when `DATABASE_URL` is configured.
- Replaced frontend placeholders with real pages:
  - `/action-centre`
  - `/logs`
- Added:
  - status tabs
  - stats cards
  - action table with expanded detail row
  - live monospace log viewer
- Updated `AppShell.tsx` topbar label to Phase 15 wording.

## Phase 15 Verification

- `python -m pytest backend\\tests\\test_action_logs_contract.py` passed: `2 passed`
- `python -m pytest` passed: `55 passed`
- `npm.cmd run build` passed after rerunning outside the sandbox because Vite/esbuild hit the known workspace filesystem denial

## Phase 16 WebSocket Live Market Data

- Re-read the official Breeze WebSocket docs and the `breeze-connect` `ws_connect` / `subscribe_feeds` / `on_ticks` reference before implementation (stock-token `X.Y!token` format, exchange-quote and OHLCV tick shapes).
- Architecture: Flask-SocketIO in `threading` async mode (no eventlet/gevent monkey-patching) so the existing REST stack, psycopg, and SQLAlchemy are untouched; the browser negotiates websocket or long-polling transport. All Breeze streaming logic is isolated in one `MarketDataWorker`, mirroring the BreezeGateway rule for REST.
- Added `MarketDataWorker` (`backend/app/services/market_data_worker.py`):
  - Lazy `breeze-connect` import; degrades safely (non-live state, REST keeps serving) if the library is missing, Breeze is unconfigured, or the connection fails.
  - Subscribes by Breeze stock-token built from exchange prefix (NSE/NFO=4, BSE=1, BFO=8) plus the master-contract token; reverse map drives tick normalization.
  - Normalizes ticks to `symbol/broker_symbol/exchange_code/token/ltp/open/high/low/close/change/change_percent/volume/oi/ts`.
  - Writes latest tick per token to Redis (`md:tick:<exchange>:<token>`, 60s TTL) and keeps an in-memory snapshot for the REST fallback.
  - Supervisor thread with exponential reconnect backoff and states `offline / connecting / live / degraded`; publishes ticks and status through an injected Socket.IO emit callback.
- Added `backend/app/realtime.py` (single `SocketIO(async_mode="threading")` server, `init_realtime`, default NIFTY/BANKNIFTY watchlist, `connect/subscribe/unsubscribe` handlers resolving symbols to tokens via `SymbolResolver`).
- Added `backend/app/api/market_data.py` REST endpoints: `/api/market-data/status`, `/api/market-data/snapshot`, `/api/market-data/watchlist` (always 200, REST degraded fallback).
- Wired `init_realtime` + blueprint into `factory.py`; `run.py` uses `socketio.run`; `Procfile` switched to single gthread gunicorn worker; added `flask-socketio`, `simple-websocket`, `breeze-connect` to requirements/pyproject.
- Frontend: added `socket.io-client`, `lib/realtime.ts`, `hooks/useLiveMarketData.tsx` (provider + `useLiveQuote` / `useLiveSubscribe`), wrapped `main.tsx`, added `/socket.io` vite proxy, topbar live/degraded/offline badge, live ticker + live LTP/P&L overlay on Dashboard and Positions, live badge on Option Chain, market-data REST clients/types, and live-state CSS.

## Phase 16 Verification

- `python -m pytest` passed: `68 passed` (55 prior + 13 new market-data tests)
- `npm.cmd run build` passed: `88 modules`
- Live `socketio.run` boot smoke test: `/api/market-data/status` returns `offline` cleanly without Breeze config, `/watchlist` and `/snapshot` return 200, the Socket.IO handshake `GET /socket.io/?EIO=4&transport=polling` returns a session id with a websocket upgrade, and `/api/health` still returns 200 (no REST regression).
- Remaining: live broker tick shape and token-based subscription still need one deployed confirmation with a fresh Breeze session token (this workspace holds no Breeze secrets).
