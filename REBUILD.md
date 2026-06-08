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
