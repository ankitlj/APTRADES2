# APTRADES2 Rebuild Log

Date: 2026-06-07
Target repo: `https://github.com/ankitlj/APTRADES2.git`

## 2026-06-18 - Step 3: Dashboard chart hover fix

- Tooltip `left` was hard-clamped to `Math.min(mousePos.x, 280)`, making the right half of the chart feel dead (tooltip stuck at 280px).
- Vertical clamp was also tight (max 190px), restricting hover zone.
- Fix: replaced hardclamps with `mousePos.containerW` and `mousePos.containerH` dynamic bounds. Tooltip now follows cursor across the full chart width, staying 94px from edges (half estimated tooltip width + padding).
- `MousePosition` interface added with `containerW`/`containerH` captured from `getBoundingClientRect`.
- `tooltipRef` added for future measurement.
- Frontend-only change: `DashboardMarketChart.tsx`. No backend changes.
- Verification: `npm run build` clean, 1859 modules, bundle +0.08 kB.

## 2026-06-18 - Step 2b: Remove SENSEX + add ticker fallback cache

- Root cause:
  - SENSEX (BSE/cash): Breeze quote API returns ltp=0 for BSESEN/BSE — not a usable live source.
  - NIFTY/BANKNIFTY/MIDCAP50/FINNIFTY: Breeze intermittently returns null/error. No fallback existed, so a single bad refresh blanked the ticker to "Unavailable".
  - BANKNIFTY WS display_symbol ("BANK NIFTY") vs REST key ("BANKNIFTY") misaligned: `ticks["BANKNIFTY"]` would never match WS `{"symbol": "BANK NIFTY"}`.
- Part 1 fix (backend):
  - `dashboard_service.py`: Removed SENSEX from `_TICKER_SYMBOLS` (now 4). Added `_FALLBACK_TTL=120s` module-level `_last_good_quotes` cache. Added `_is_valid_ticker_quote()` and `_apply_fallback()`.
  - `realtime.py`: Removed SENSEX from `DEFAULT_WATCHLIST`. Added BANKNIFTY display_symbol normalisation ("BANK NIFTY" → "BANKNIFTY") in `resolve_subscription_items` so WS tick.symbol matches REST key.
- Part 2 fix (frontend):
  - `DashboardMarketChart.tsx`: Removed SENSEX from `SUGGESTED_SYMBOLS`, replaced with NIFTYMID50.
- Symbol-key alignment now: all 4 symbols aligned (WS tick.symbol == REST key).
- Verification: `python -m pytest` 129 passed (5 new tests); `npm.cmd run build` 1859 modules clean.
- SENSEX removed from all dashboard-relevant paths (3 files).
- Fallback TTL: 120 seconds. No latency impact.
- Part 1 fix: Changed `_TICKER_SYMBOLS` in `dashboard_service.py`:
  - MIDCAP50: request symbol changed from "MIDCAP50" to "NIFTYMID50" (DB display_symbol)
  - Label stays "MIDCAP50" for display
- Part 2 fix: Changed `DEFAULT_WATCHLIST` in `realtime.py`:
  - MIDCAP50: symbol changed from "MIDCAP50" to "NIFTYMID50"
- Symbol-key alignment verified: REST result.symbol = WS tick.symbol = "NIFTYMID50" for MIDCAP50
- Verification: `python -m pytest` → 124 passed; `npm.cmd run build` → 1859 modules; bundle size unchanged.

## 2026-06-18 - Step 2: Top ticker fixes (cash/index symbols, 2dp, BANKNIFTY fix)

## 2026-06-18 - Step 1: Connection badge move + market status

- Moved websocket connection badge from top-right (TopHeader) to bottom-left sidebar footer (Navbar):
  - Navbar now shows green dot + "Connected" when live, amber dot + "Not Connected" otherwise
  - Replaced hardcoded "ICICI Direct" text
- Added time-based market open/closed badge to top-right:
  - Asia/Kolkata timezone, open 09:15-15:30 IST
  - Green dot + "Market Open" / Red dot + "Market Closed"
  - Updates every 30s via interval, no websocket dependency
- Files: `TopHeader.tsx`, `Navbar.tsx` (frontend only)
- Verification: `npm run build` -> 1859 modules, clean

## 2026-06-17 - Dashboard Card Submetric Rendering Fix

- Tightened the ORIENS dashboard card submetric rendering to match the user's
  white-card reference while keeping the current dark ORIENS aesthetic.
- Day's P&L now shows `Realized` and `Unrealized`; Open Positions now shows
  value-first buckets (`0 Options | 0 Future | 0 Equity`); Monthly ROI now
  keeps `Annual ROI (FY)` visible.
- Backend already supplied these fields through the dashboard summary contract,
  so no backend changes were required in this follow-up.
- Verification: `python -m pytest` -> 124 passed; `npm.cmd run build` -> 1853
  modules passed after rerunning outside the known local Vite/esbuild sandbox
  denial.

## 2026-06-17 - Dashboard Portfolio Cards + Plain Dark Background

- Replaced duplicate dashboard futures quote metric cards with the requested
  portfolio card order: Day's P&L, Open Positions, Monthly ROI, Margin Used.
- Kept the NIFTY/BANKNIFTY futures values in the top ticker; the card grid now
  focuses on portfolio metrics instead of repeating ticker data.
- Added backend totals for option/future/equity position counts and day P&L
  breakdown. Realized P&L, ROI, and margin are safe placeholders until a real
  account/funds contract is added.
- Removed oversized engraved icons from dashboard metric cards and removed the
  dark radial page-background ambience so the workspace background stays plain.
- Verification: `python -m pytest` -> 124 passed; `npm.cmd run build` -> 1853
  modules passed after rerunning outside the known local Vite/esbuild sandbox
  denial.

## 2026-06-14 - Futuristic Neon Glow Pass (Crypto-Trading-Dashboard-3D inspired)

- Goal: layer a futuristic look on top of the APTRADES visual port, inspired by
  `omkarghare8803/Crypto-Trading-Dashboard-3D`: dark mode by default, neon accent
  glow, glassmorphism panels, hover lift+glow on stat boxes, a neon glowing icon
  top-left of each box, a faint oversized "engraved" icon bottom-right, and a
  glowing chart line. Data layer + backend still frozen.
- Delivered in 5 steps + 1 fix, each built and pushed:
  - Step 1 foundation (commit `e288994`): neon tokens (cyan `#00f2ff`, purple
    `#bc13fe`, green `#00ff88`, red `#ff0055`), radial neon page-background
    gradients in dark mode, reusable utility classes `.glow-card` (hover lift +
    neon edge glow), `.glow-icon`, `.engraved-icon`, `.glow-line`, with a
    `prefers-reduced-motion` guard, all in `index.css`. ThemeProvider now
    defaults to dark mode.
  - Step 2 (commit `39b7350`): shared `StatCard` (components/common/page.tsx)
    gains glass background (white/4% + backdrop blur), hover glow, optional neon
    glow-icon top-left, and faint engraved icon bottom-right.
  - Step 3 (commit `6d46fbf`): dashboard 4 metric boxes get neon icons (mapped
    per metric key) + engraved icons + hover glow; market chart line switches to
    neon cyan with the `.glow-line` drop-shadow + cyan latest-value badge.
  - Step 4 (commit `7642647`): base `Card` primitive gains a dark glass surface
    (white/3.5% + blur + subtle border) so every panel/table is glassy; neon
    topic icons added to the stat boxes on all pages (Positions, Orderbook,
    Tradebook, Option Chain, OI Tracker, OI Profile, Logs, Action Centre,
    Strategy Builder, Strategy Portfolio).
  - Step 5 polish (commit `183a208`): neon glow on the active sidebar nav item,
    the PayoffChart line, and the top-right "A" avatar button.
  - Fix (commit `9bfa57e`): the four dashboard boxes shared one icon while
    metrics were loading or unmapped; `metricIcon(key, index)` now falls back per
    box position (TrendingUp / Layers / Percent / Wallet) so each box (and its
    engraved sticker) is always distinct and topic-appropriate.
  - Fix (commit `671b3b5`): the 6 Tools cards used the base Card without
    `.glow-card`, so they did not glow on hover; they now use glow-card + dark
    glass, a per-tool neon glow-icon (Code2/Briefcase/Layers/Sigma/Activity/
    BarChart3), and an engraved icon bottom-right.
- FROZEN/untouched: `frontend/src/lib/api.ts`, `frontend/src/lib/realtime.ts`,
  `frontend/src/hooks/*`, all of `backend/`.
- Verification: `npm run build` passes on every step.
- Note: light mode still available via the Sun/Moon toggle (glow toned down in
  light). The dashboard "Failed to fetch / Offline" seen during testing is the
  Breeze data layer needing a fresh `BREEZE_SESSION_TOKEN` on Railway, not the UI.

## 2026-06-13 - Full Visual Port: APTRADES2 frontend matches APTRADES 100%

- Goal: make every APTRADES2 page look identical to the old `ankitlj/APTRADES.git`
  frontend (fonts, colors, tables, boxes, layouts, chart lines, dark/light mode,
  top-right "A" menu, dashboard ticker) without touching backend or any
  frontend->backend data wiring.
- Approach: 5 gated steps, each built and pushed, with user approval between steps:
  1. Audit & map (commit `7cb6d2e`) - see `UI_OVERHAUL_PLAN.md`
  2. Foundation + layout shell (commit `c21b216`)
  3. Dashboard (commit `b5feb5b`)
  4. Pages batch 1 - Positions, Orderbook, Tradebook, Option Chain, OI Tracker,
     OI Profile (commit `95b0945`)
  5. Pages batch 2 + polish - Action Centre, Logs, Tools, Strategy Builder,
     Strategy Portfolio, Placeholder, shared states (commit `3b3d206`)
- Foundation added: Tailwind v4 (`@tailwindcss/vite`) + shadcn/ui primitives
  (Button, Card, Badge, Table, Input, DropdownMenu) + lucide-react +
  class-variance-authority/clsx/tailwind-merge. Ported the old APTRADES oklch
  theme tokens (light/dark + accent themes via `data-theme`) into `index.css`.
  Custom `ThemeProvider` persists mode + accent to localStorage.
- Shell rebuilt: sidebar `Navbar` (logo, TRACK|TRADE|TRIUMPH, lucide nav, ICICI
  Direct status), sticky `TopHeader` (dashboard market ticker scrolling
  right->left, live/offline dot, Sun/Moon dark-light toggle, "A" tools/accent
  menu), `Footer`, mobile bottom nav.
- Pages (all 13) restyled with shared helpers in `components/common/page.tsx`
  (PageHeader, StatCard, Field, selectClass). Dashboard uses an SVG market chart
  (indigo `#6366f1` line + gradient + grid + symbol search). Option chain keeps a
  colored Calls/Strike/Puts two-tier header + ATM highlight; OI Tracker/Profile
  use Tailwind CE/PE OI bars. `PayoffChart` reused unchanged (inline SVG colors).
- FROZEN (never edited, per user): `frontend/src/lib/api.ts`,
  `frontend/src/lib/realtime.ts`, `frontend/src/hooks/useLiveMarketData.tsx`,
  `frontend/src/hooks/useQuotes.ts`, all of `backend/`. Every live websocket feed,
  filter, mutation, and CSV export is unchanged.
- Verification: `npm run build` passes on every step (1853 modules, ~47KB CSS).
- Remaining: a live-market visual click-through with a fresh Breeze session token
  is recommended (pure UI change, data wiring is identical to before).

## 2026-06-11 - Old APTRADES UI Alignment Pass 1

- User clarified that APTRADES2 should use the older `ankitlj/APTRADES.git` frontend/UI directly as the visual source, not a new redesign.
- Root cause:
  - APTRADES2 still used the temporary rebuild shell, so even though the Phase 1-18 pages were functional, the app did not look like the older APTRADES product.
- Changes made:
  - Ported the old APTRADES shell cues into APTRADES2:
    - logo-led sidebar
    - denser navigation hierarchy
    - utility navigation block
    - top-right live-status chip
    - sidebar footer live badge
  - Updated the global CSS so cards, topbar, spacing, sidebar width, pills, and brand treatment move closer to the old APTRADES frontend.
  - Added legacy `logo.png` to the frontend public assets.
- Files changed:
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/index.css`
  - `frontend/public/logo.png`
- Verification:
  - `npm.cmd run build` passed after rerunning outside the sandbox due to the known Vite/esbuild filesystem restriction.
- Remaining note:
  - This is the shared-shell migration pass. If a stricter page-by-page 1:1 legacy visual port is still needed, that should continue as a focused follow-up on the page internals.

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

## Phase 17 Production Hardening

- Structured error handlers (`backend/app/errors.py`): every `/api/*` failure returns `{ "status": "error", "error": { "code", "message" } }` (400/404/405/429 via the HTTPException handler, plus a safety-net 500 that logs server-side and never leaks internals).
- Rate limiting (`backend/app/rate_limit.py`, `flask-limiter`): default `600 per minute` per client, Redis storage when `REDIS_URL` is set else memory; `/api/health*`, `/api/market-data*`, and `/socket.io` exempt so health and the live feed are never throttled. Tunable via `RATELIMIT_DEFAULT` / `RATELIMIT_ENABLED`.
- Enriched health: readiness adds `breeze` (config-only, no network) and `websocket` (live worker state); deployment adds `master_contract` and `websocket`. All checks failure-safe.
- Wired `register_error_handlers` + `init_rate_limiting` into `factory.py`; added `flask-limiter` to requirements/pyproject.
- Frontend: shared `ErrorState` (with retry), `EmptyState`, top-level `ErrorBoundary`; applied with consistent retry buttons to Dashboard, Positions, Orderbook, Tradebook, Option Chain; dashboard loader refactored into a reusable callback; mobile final pass in `index.css`.
- Added `OPERATIONS.md` runbook (Breeze token refresh, master-contract cron, rate-limit env vars, health endpoints).
- Deferred to user (manual deploy tasks): Railway daily master-contract cron, and the daily Breeze token-refresh workflow decision.

## Phase 17 Verification

- `python -m pytest` passed: `73 passed` (68 prior + 5 new hardening tests)
- `npm.cmd run build` passed: `91 modules`
- Live HTTP smoke test: enriched readiness/deployment fields present, structured 404 shape, `X-RateLimit-Limit: 600` on a limited route, `/api/health` exempt from the limit.

From this point onward, the project is renamed ORIENS.

## 2026-06-17 - UI Quality Pass: Shared Components + Page Adoption

- Created shared utilities: `lib/format.ts` (formatNumber, formatCurrency, formatPercent, pnlColor, tone, toneColor, alertDotColor), `types/async.ts` (AsyncState<T>, createInitialState)
- Created reusable components: PageLayout (page wrapper), DataTableShell (table card with loading/error/empty), LoadingState, BuySellBadge, SymbolCell
- Improved EmptyState (icon prop, action slot), ErrorState, ErrorBoundary (uses UI components)
- Adopted PageLayout in all 12 pages, DataTableShell in 8 pages, BuySellBadge in 3 pages, SymbolCell in 4 pages
- Removed duplicated formatNumber from 8 pages (~120 lines)
- Files changed: 16 modified + 7 new
- Verification: `python -m pytest` -> 124 passed; `npm.cmd run build` -> 1859 modules.

## 2026-06-17 - Step 4: Latency Regression Check

- Measured dev-server response times (test credentials, non-market hours):
  - `/api/dashboard/summary` ~2150ms (Breeze gateway init, cold start)
  - `/api/dashboard/alerts` ~15ms (fast)
  - `/api/dashboard/chart` 400 (expected — test creds don't resolve NIFTY)
- Verdict: No backend regression — all 4 steps were frontend-only.
- Frontend bundle growth: +2.2kB JS +1kB CSS — expected from new chart features.
- No code changes in this step.

## 2026-06-17 - Step 3: Reorder Dashboard Sections (Positions Above Chart)

- Reordered the "Active Positions" table above the chart + alerts section.
- New order: metric cards -> positions -> chart + alerts.
- Files changed: `frontend/src/pages/DashboardPage.tsx`
- Verification: `python -m pytest` -> 124 passed; `npm.cmd run build` -> 1853 modules.

## 2026-06-17 - Step 2: Dashboard Chart Hover Tooltip + X-Axis Time Labels

- Added x-axis time labels (HH:MM / DD MMM) along the chart bottom.
- Added hover crosshair with vertical dashed line, circle highlight at nearest point, and floating tooltip (price + datetime).
- Chart now uses actual `point.time` from the API instead of index.
- Files changed: `frontend/src/components/dashboard/DashboardMarketChart.tsx`
- Verification: `python -m pytest` -> 124 passed; `npm.cmd run build` -> 1853 modules.

## 2026-06-17 - Step 1: Remove Redundant Sidebar Items

- Moved Option Chain, OI Tracker, OI Profile, Strategy Builder, and Strategy Portfolio out of the left sidebar. These tools remain accessible via the Tools page and direct URLs.
- Sidebar now shows only: Dashboard, Orderbook, Tradebook, Positions, Action Centre, Logs, Tools.
- Top-header avatar menu still lists the 5 tools.
- Files changed: `frontend/src/components/layout/Navbar.tsx`
- Verification: `python -m pytest` -> 124 passed; `npm.cmd run build` -> 1853 modules.

## 2026-06-19 - Part 1: Dashboard Option Orderbook Shell

- Created `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx` — new card component replacing chart in dashboard grid.
- Unplugged chart from `DashboardPage.tsx`: replaced `<DashboardMarketChart />` with `<DashboardOptionOrderBook />`.
- Chart file `DashboardMarketChart.tsx` preserved (not deleted), chart API route preserved.
- Component features (shell only, no real data):
  - Underlying / Expiry / Strike selectors with cascading enable/disable
  - Selected instrument summary strip
  - Orderbook table (bid/ask top-of-book only, Breeze limitation noted)
  - Market depth card with buy/sell percentage bar
  - BUY/SELL buttons (disabled until valid selection)
- Files changed: 1 new + 1 modified (frontend only).
- Verification: `npm run build` -> 1859 modules; `python -m pytest` -> 126 passed.

## 2026-06-19 - Part 2: Dashboard Option Orderbook Backend API

- Added `GET /api/dashboard/option-orderbook` endpoint in `dashboard.py`.
- Added `get_option_orderbook()` in `dashboard_service.py` — validates inputs, calls Breeze `/optionchain` with specific strike, returns structured bid/ask/ltp/depth response.
- 9 new contract tests in `test_dashboard_contract.py`: valid request, missing params, invalid right, unsupported underlying, empty response, missing fields, zero qty.
- Backend only (frontend unchanged from Part 1).
- Verification: `python -m pytest` -> 135/135 passed; `npm run build` -> 1859 modules.

## 2026-06-19 - Part 3: Wire Frontend to Real Backend Data

- Added `OptionOrderbookLevel`, `OptionOrderbookInstrument`, `OptionOrderbookResponse` interfaces and `getDashboardOptionOrderbook()` API function to `api.ts`.
- Rewired `DashboardOptionOrderBook.tsx` with 3 cascading effects:
  - Underlying → fetch expiries via `getOptionExpiries()`
  - Expiry → fetch option chain via `getOptionChain()` → extract CE/PE strikes
  - Strike+right → fetch orderbook via `getDashboardOptionOrderbook()` → display real LTP/bid/ask/depth
- Added `FetchState<T>` discriminated union for loading/error/ok/idle states.
- Added `AbortController` per request chain to cancel stale in-flight requests.
- Real status badge (Loading/Error/Data loaded/No data), error banners, real data in table and depth card.
- BUY/SELL buttons disabled until valid data loaded.
- Files changed: `api.ts`, `DashboardOptionOrderBook.tsx` (frontend only).
- Verification: `npm run build` -> 1859 modules; backend unchanged.

## 2026-06-19 - Part 4: Live Price Overlay for Option Orderbook

- Added smart polling (2.5s interval) to `DashboardOptionOrderBook.tsx` for near-real-time price updates.
- Polling merged into the existing data-fetch effect: initial fetch + `setInterval` for subsequent polls.
- Added `hasValidDataRef` — poll failures keep last good data (no disruptive error flickering).
- Status badge changed to pulsing green dot + "Live" when data is active.
- AbortController cancels stale poll requests on selection change.
- Chose polling over WebSocket: option contracts share `display_symbol="NIFTY"` which would cause tick collisions in the existing `ticks` map. Avoiding realtime infrastructure changes.
- Files changed: `DashboardOptionOrderBook.tsx` (frontend only).
- Verification: `npm run build` -> 1859 modules; backend unchanged.

## 2026-06-19 - Part 5: BUY/SELL Button Safety — Confirmation Modal

- Added inline confirmation modal to `DashboardOptionOrderBook.tsx` with `role="dialog"`, `aria-modal="true"`, `aria-labelledby`.
- BUY/SELL buttons now open the modal instead of being inert.
- Modal shows: contract details, LTP, Bid/Ask, spread, quantity input (1-9999).
- Green title/button for BUY, red for SELL.
- Escape key and backdrop click to close.
- Quantity auto-focuses on open, resets to 1 on contract change.
- Files changed: `DashboardOptionOrderBook.tsx` (frontend only).
- Verification: `npm run build` -> 1859 modules; backend unchanged.

## 2026-06-19 - Part 6: Latency and Regression Verification

- 135/135 backend tests passed (5.72s), including 9 new option orderbook tests.
- Frontend build clean: 498.79 KB JS, 58.29 KB CSS (+7.5 KB JS, +2.61 KB CSS from baseline).
- Endpoint latency: <1ms validation path, ~3-4s with Breeze call (single `/optionchain` request, 10s timeout).
- All 6 parts complete: shell -> API -> data wiring -> live overlay -> confirm modal -> verification.
- No regressions in any existing functionality.
- Total: ~1190 lines added across 9 files.

## 2026-06-19 - Step 4: Fix missing bid/ask quantities in option orderbook

### Root cause (two independent bugs)

1. **REST field-name mismatch** (`dashboard_service.py`): `get_option_orderbook()` read `best_bid_qty` / `best_offer_qty` from Breeze response, but Breeze returns `best_bid_quantity` / `best_offer_quantity`.
2. **Websocket normalization gap** (`market_data_worker.py`): `_normalize_tick()` dropped all 6 bid/ask fields that Breeze sends (`bPrice`, `bQty`, `sPrice`, `sQty`, `totalBuyQt`, `totalSellQ`).
3. **Frontend type gap** (`realtime.ts`): `LiveTick` lacked bid/ask fields.
4. **No websocket overlay** (`DashboardOptionOrderBook.tsx`): Purely REST-polled.

### Changes

| File | Change |
|---|---|
| `dashboard_service.py` | `best_bid_qty` -> `best_bid_quantity` (correct Breeze field); `total_buy_qty`/`total_sell_qty` read from Breeze directly when present; `token` extracted from response |
| `market_data_worker.py` | Added 6 normalized fields: `bid_price`, `bid_qty`, `ask_price`, `ask_qty`, `total_buy_qty`, `total_sell_qty` |
| `realtime.ts` | Added 6 optional fields to `LiveTick` |
| `DashboardOptionOrderBook.tsx` | Added `useLiveQuote` hook; computed `effective*` values (WS > REST > null); replaced all raw refs |
| `test_dashboard_contract.py` | Updated mocks to use real Breeze field names; added `token` to mock |

### Verification

- Backend: 36/36 tests (20 dashboard contract + 16 market data worker)
- Frontend: `tsc -b && vite build` — 0 errors
- REST response shape unchanged; LiveTick fields optional (no regressions)
- Merge priority: websocket tick > REST snapshot > null-safe fallback

### Remaining risk

- Option-specific websocket subscription requires `realtime.py` enhancements (passing `token`/`expiry`/`strike`/`right` through to `SymbolResolver`). REST fix provides the primary bid/ask data.

## 2026-06-19 — Phase 13: Groww-style search-first instrument launcher

Replaced the 3-step dropdown (underlying → expiry → strike) with a search-first modal. Backend: ranked search service with normalization, alias resolution, expiry filtering, and option diversity (5 ATM strikes × 2 nearest expiries). Frontend: keyboard-nav search, tab filters (All/Stocks/F&O), section headers, dark mode polish. Orderbook loads for cash, futures, and options on selection.

### Part 1 — Backend search service + frontend wiring

- New `backend/app/services/instrument_search_service.py` — 288 lines:
  - `normalize_query()`: uppercases, strips, maps aliases (BANKNIFTY, FINNIFTY, MIDCAP, SENSEX)
  - `normalize_display_strike()`: divides raw strike >=100000 by 100 for display
  - `classify_instrument()`: cash/future/option from exchange + product + right + expiry
  - `_rank_key()`: 6-level priority (exact > alias > prefix symbol > prefix name > contains symbol > contains name), cash before futures before options, near-expiry first for options
  - `_apply_option_diversity()`: groups options by underlying+expiry, selects 5 central (ATM-near) strikes, limits to 2 nearest expiries
  - `.search()`: expiry filtering (past derivatives excluded), tab filtering, 40-result limit
- Wired into `DashboardService.search_instruments()` and search route (added `tab` param)
- Frontend `api.ts`: `InstrumentSearchResult` extended with `id`, `symbol`, `instrument_kind`, `display_strike`, `right`, `label`, `sublabel`, `badges`, `rank`
- `searchInstruments()` sends `tab` param to backend
- `DashboardInstrumentSearch.tsx` rewritten: sends `tab`, uses backend `label`/`sublabel`/`badges`, keyboard nav (arrows/Enter/Escape), fixed empty state (only when results === 0 AND not loading)
- `DashboardOptionOrderBook.tsx`: uses `instrument.right`, `instrument.instrument_kind`, `instrument.label`
- 10 new search tests (ranking, alias, expiry filter, strike normalization, ADANI, etc.)

### Part 2 — Frontend search UX polish

- Sectioned results: "Stocks", "Futures", "Options" headers (sticky, `bg-background/95`, `backdrop-blur-sm`)
- Dark mode: `bg-black/60` backdrop, reduced border opacity, `bg-accent/60` active selection, search icon SVG in input
- `scrollIntoView({ block: "nearest" })` adjusted for section header DOM nodes
- Empty state: search icon SVG, `py-12`, "Try a different search term" subtext
- "Type to search instruments" hint with icon
- Tab buttons: `shadow-xs` on active, visible border on input
- Footer keyboard hints only render with results

### Part 3 — Orderbook selection compatibility

- `productBadge()` uses `instrument_kind` (always set) not `product_type` (nullable in DB)
- Expiry display condition uses `instrument_kind` instead of `product_type`
- Added `test_orderbook_endpoint_futures_returns_quote` — futures orderbook via `get_quote`

### Part 4 — Deployed verification checklist

See `development.md` for 13-step post-deploy checklist.

### Files changed (Phase 13)

| File | Change |
|---|---|
| `backend/app/services/instrument_search_service.py` | NEW — ranked search, aliases, strike normalization, option diversity |
| `backend/app/services/dashboard_service.py` | Delegates `search_instruments()` to `InstrumentSearchService`; cleaned unused imports |
| `backend/app/api/dashboard.py` | Search route accepts `tab` param |
| `frontend/src/lib/api.ts` | Extended `InstrumentSearchResult` type; `searchInstruments()` sends `tab` |
| `frontend/src/components/dashboard/DashboardInstrumentSearch.tsx` | Rewritten: search-first UX, section headers, keyboard nav, dark polish |
| `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx` | Uses `instrument_kind` for badge/expiry display; consumes new search result fields |
| `backend/tests/test_dashboard_contract.py` | 11 new tests (10 search + 1 futures orderbook) |
| `development.md` | Phase 13 parts 1-4 entries |
| `REBUILD.md` | Phase 13 summary entry |

### Verification

- Backend: `python -m pytest` → 156 passed
- Frontend: `npm run build` → 1860 modules, no errors

## 2026-06-19 — Frontend polish pass, Part 1: Global CSS polish

- Font rendering: `-webkit-font-smoothing: antialiased`, `-moz-osx-font-smoothing: grayscale`, `text-rendering: optimizeLegibility`
- Number rendering: `font-variant-numeric: tabular-nums` on `body` for consistent metric alignment
- Added CSS transition tokens: `--ease-out-premium (cubic-bezier(0.16, 1, 0.3, 1)`, `--transition-fast (140ms)`, `--transition-base (220ms)`
- Dark scrollbar: reduced thumb width to 5px, lowered opacity, added global `.dark` scrollbar rules without requiring `.scrollbar-thin` class
- Files: `frontend/src/index.css`
- Build: passed

## 2026-06-19 — Frontend polish pass, Part 2: Reusable UI components

- `SurfaceCard`: ORIENS card with tone (default/active/danger/success), interactive mode (focus ring + keyboard), accessible `role="button"` + tabIndex
- `MetricCard`: loading skeleton, error fallback, tone-colored value, meta line, icon slot, 110px min-height
- `DataState`: unified loading/empty/error component with compact mode — replaces inline LoadingState/EmptyState/ErrorState patterns
- `StatusBadge`: 8 consistent status types (live/connected/stale/offline/loading/error/success/warning) with dot indicator
- `ActionButton`: wraps `ui/button` with inline loading spinner that preserves width
- 5 new files in `frontend/src/components/ui/`
- Build: passed

## 2026-06-19 — Frontend polish pass, Part 5: Standardized page states

- Updated `DataTableShell` to use `DataState` internally (spinner, icon, error layout) instead of separate `LoadingState`/`EmptyState`/`ErrorState`
- Removed redundant standalone `ErrorState` from OrderbookPage, TradebookPage, PositionsPage, ActionCentrePage, LogsPage — fixes duplicated error boxes on every async page
- Improved LogsPage live logs empty state (bare string → centered muted text)
- Removed unused `ErrorState` imports from 5 pages
- Build: passed

## 2026-06-19 — Frontend polish pass, Part 4: Search modal polish

- Unified `SearchStatus` type (`idle | loading | empty | error | results`) replaces boolean `loading` — prevents state overlap
- Added explicit error state with distinct UI (red icon, error message, "please try again") — previously errors silently collapsed to empty state
- Added `autoComplete="off"`, `spellCheck={false}` on search input
- Added `type="button"` on all buttons to prevent unintended form submission
- Accessibility: `aria-pressed` on tabs, `aria-activedescendant` on listbox, `role="alert"` on error, `id` on each result
- Footer keyboard hints now show for both "results" and "empty" states
- Reset status/error on tab switch; re-focus input on tab switch
- Files: `frontend/src/components/dashboard/DashboardInstrumentSearch.tsx`
- Build: passed

## 2026-06-19 — Frontend polish pass, Part 3: Dashboard component adoption

- Replaced 4 manual metric cards with `MetricCard` (loading skeleton, error fallback, submetrics via `meta`)
- Replaced alerts empty/loading/error states with `DataState`
- Replaced alert dot colors with `StatusBadge` (error/warning/success)
- Removed unused imports (`AlertTriangle`, `CircleAlert`, `toneColor`, `alertDotColor`)
- Files: `frontend/src/pages/DashboardPage.tsx`
- Build: passed

- `SurfaceCard`: ORIENS card with tone (default/active/danger/success), interactive mode (focus ring + keyboard), accessible `role="button"` + tabIndex
- `MetricCard`: loading skeleton, error fallback, tone-colored value, meta line, icon slot, 110px min-height
- `DataState`: unified loading/empty/error component with compact mode — replaces inline LoadingState/EmptyState/ErrorState patterns
- `StatusBadge`: 8 consistent status types (live/connected/stale/offline/loading/error/success/warning) with dot indicator
- `ActionButton`: wraps `ui/button` with inline loading spinner that preserves width
- 5 new files in `frontend/src/components/ui/`
- Build: passed

- Font rendering: `-webkit-font-smoothing: antialiased`, `-moz-osx-font-smoothing: grayscale`, `text-rendering: optimizeLegibility`
- Number rendering: `font-variant-numeric: tabular-nums` on `body` for consistent metric alignment
- Added CSS transition tokens: `--ease-out-premium (cubic-bezier(0.16, 1, 0.3, 1)`, `--transition-fast (140ms)`, `--transition-base (220ms)`
- Dark scrollbar: reduced thumb width to 5px, lowered opacity, added global `.dark` scrollbar rules without requiring `.scrollbar-thin` class
- Files: `frontend/src/index.css`
- Build: passed
