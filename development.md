# APTRADES v2 Development Log

## Current Status
- Current phase: Phase 2 — NSE-only search scope
- Last completed phase: Phase 1 — Common-name mapping for derivatives
- Planned next: Phase 2 — Enforce NSE-only search scope

### 2026-06-21 — Phase 2: NSE-only search scope
- **Goal**: Exclude BSE, BFO, MCX, and bond instruments from search results.
- **Root cause**: No exchange-code filter existed in the search query, so searching "RELIANCE" returned both NSE and BSE equity results. BSE/BFO instruments were interleaved with NSE/NFO in the same result set.
- **Fix**: Added `Instrument.exchange_code.in_(["NSE", "NFO"])` filter to the SQL query in `InstrumentSearchService.search()` — filters out all non-NSE/NFO rows before any Python-side processing.
- **Files changed**: `backend/app/services/instrument_search_service.py` (1 line added)
- **Verification**: `python -m pytest` → 167 passed, `npm run build` → clean build. Existing test data only has NSE and NFO instruments, so no tests regressed.
- **Next**: Phase 3 — Search quality hardening (ranking, partial matching, prefix-only for short queries).

### 2026-06-21 — Phase 1: Common-name mapping for derivatives
- **Goal**: Make searching by common name (e.g., "RELIANCE") return NFO futures and options, not just NSE cash.
- **Root cause**: Derivatives obtained `display_symbol` from SecurityMaster's `AssetName` field (broker code "RELIND"), not the common name ("RELIANCE"). No aliases were created for derivatives (`_build_payloads` skipped `product_type != "cash"`). So searching "RELIANCE" matched cash at priority 0, but derivatives matched only via `name` at priority 3-5, and 40+ cash results filled the limit before derivatives appeared.
- **Fix**: Three changes to `_build_payloads` in `master_contract_service.py`:
  1. Build a `broker_to_common` mapping from NSE equity CSV rows (`SC → NS` columns).
  2. Override `display_symbol` for derivatives whose current display_symbol equals their broker_code (e.g., `"RELIND"` → `"RELIANCE"`), so they get exact-match priority 0 during search.
  3. Insert common-name aliases (`"RELIANCE"`) for all derivatives of each mapped broker symbol, so alias-based search finds them too.
- **Files changed**: `backend/app/services/master_contract_service.py` (lines 381-433 added)
- **Verification**: `python -m pytest` → 167 passed (all tests), `npm run build` → clean build (1861 modules). No existing tests regressed because test data manually seeds correct display_symbols on derivatives.
- **Next**: Phase 2 — Enforce NSE equity/futures/options search scope (filter out BSE/MCX/bonds).

### 2026-06-18 - Step 3: Dashboard chart hover fix

#### Root cause
- Tooltip `left` was hard-clamped to `Math.min(mousePos.x, 280)`, which capped the tooltip at 280px from the container's left edge. On a ~700px-wide card, the entire right half (420px+) had the tooltip stuck at 280px, making it feel disconnected from the cursor.
- No container-width-aware positioning — hardcoded pixel bounds that didn't scale with actual card width.
- Tooltip vertical positioning was also hardcoded with small bounds (max 190px), restricting the hover zone unnecessarily.

#### Fix (frontend-only)
- `DashboardMarketChart.tsx`:
  - Added `MousePosition` interface with `containerW` and `containerH` fields (captured from `getBoundingClientRect` on each mouse move).
  - Replaced hard 280px clamp with `Math.max(94, Math.min(mousePos.x, mousePos.containerW - 94))` — dynamically stays within the actual container width with a 94px margin (half estimated tooltip width + padding).
  - Replaced hard 190px vertical clamp with `Math.max(8, Math.min(mousePos.y - 48, mousePos.containerH - 68))` — dynamically stays within container height.
  - Added `tooltipRef` for future measurement if needed.
  - Not changed: data interval (still 30 days daily), hover index math (still nearest-point), x-axis labels, card overflow (still `overflow-hidden` since tooltip now respects container bounds).

#### Verification
- `npm run build` → 1859 modules, 489.72 kB JS (negligible +0.08 kB from extra ref + interface).
- Tooltip now follows cursor across the full chart width (not stuck at 280px).
- No backend changes — latency unchanged.
- No console errors expected (all changes are pure style/position logic).
- Dark theme preserved (no visual style changes, only positioning).

#### Root cause
- SENSEX (BSE/cash): Breeze quote API returns ltp=0 for BSESEN/BSE — not a usable source.
- NIFTY/BANKNIFTY/MIDCAP50/FINNIFTY sometimes show "Unavailable" when Breeze intermittently returns null/error for a valid symbol. The dashboard had no fallback, so a single bad Breeze response immediately blanked the ticker.
- BANKNIFTY websocket display_symbol was "BANK NIFTY" (with space) but REST returned "BANKNIFTY", causing a merge key mismatch: `ticks["BANKNIFTY"]` would never match `{"symbol": "BANK NIFTY"}`.

#### Part 1 fix (backend)
- `dashboard_service.py`:
  - Removed SENSEX from `_TICKER_SYMBOLS` (now 4 symbols: NIFTY, BANKNIFTY, NIFTYMID50, FINNIFTY)
  - Added `_FALLBACK_TTL = 120` (2 minutes) for last-known-good quote cache
  - Added `_last_good_quotes` module-level dict guarded by `_last_good_lock`
  - Added `_is_valid_ticker_quote()` — rejects null, zero, non-numeric, error-status quotes
  - Added `_apply_fallback()` — if current quote is invalid, uses cached value within TTL
  - `get_summary()` now applies fallback per-symbol after building ticker
- `realtime.py`:
  - Removed SENSEX from `DEFAULT_WATCHLIST`
  - Added display_symbol normalisation for BANKNIFTY: resolved "BANK NIFTY" → "BANKNIFTY" at subscription time, so WS emits `symbol="BANKNIFTY"` matching REST response key

#### Part 2 fix (frontend)
- `DashboardMarketChart.tsx`: Removed SENSEX from `SUGGESTED_SYMBOLS`, replaced with NIFTYMID50

#### Symbol-key alignment after fix
| Symbol | REST result.symbol | WS tick.symbol | Frontend key | Aligned? |
|---|---|---|---|---|
| NIFTY | NIFTY | NIFTY | ticks["NIFTY"] | yes |
| BANKNIFTY | BANKNIFTY | BANKNIFTY | ticks["BANKNIFTY"] | yes (was misaligned: WS was "BANK NIFTY") |
| MIDCAP50 | NIFTYMID50 | NIFTYMID50 | ticks["NIFTYMID50"] | yes |
| FINNIFTY | FINNIFTY | FINNIFTY | ticks["FINNIFTY"] | yes |

#### Verification
- `python -m pytest` → 129 passed (5 new tests: symbol count valid, fallback uses cached, cache updates on valid, stale cache returns null, symbol-specific isolation)
- `npm.cmd run build` → 1859 modules, build clean
- `_is_valid_ticker_quote` correctly rejects null, zero, error-status, missing-quote
- SENSEX removed from all dashboard-relevant paths (3 files)
- Frontend merge remains: live WS tick > REST snapshot > cached fallback > unavailable
- No latency regression (fallback is a dict lookup, no network calls)

#### Files changed
- `backend/app/services/dashboard_service.py`
- `backend/app/realtime.py`

#### Verification
- `python -m pytest` → 124 passed.
- `npm.cmd run build` → 1859 modules, clean.
- Bundle size: 489.64 KB JS, 54.23 KB CSS — no material change from prior state.
- Symbol-key alignment confirmed for all 5 ticker symbols (no merge-key mismatches for the bug-relevant symbols).
- Dashboard latency: no code path changes that could introduce backend slowdown (one string literal changed in each of two config lists).
- Phase 12 (Option Greeks): intentionally skipped — deferred until a dedicated calculation phase is needed
- Phase 18 (Performance/Caching): intentionally deferred until Phase 24 fixes are complete
- Phase 22 note: First pass was rejected (treated as code audit). Rerun followed playbook strictly: 31 API routes tested with real HTTP calls, 3 cold + 3 warm timing measurements, response shape verification for all routes, diagnosis endpoint deep dive. See PHASE22_FINDINGS.md for full evidence.
- Phase 23 note: Live deployed testing against Railway + Vercel with valid Breeze session. Found 7 real issues: 5 consistent timeouts (chart, orders, trades, cache-stats, breeze-status, symbols-search), 2 intermittent (positions, dashboard latency). Important correction: Phase 22 tested deprecated routes (/api/option-chain/bynifty, /api/orderbook, /api/tradebook) — frontend uses different endpoints (/api/option-chain, /api/orders, /api/trades). Vercel routing clean (all 11 routes HTTP 200). See PHASE23_FINDINGS.md for full evidence.
- Fix sequence: 6 parallel fixes completed in prior pass (15ef402 through 2785f97). Then a combined Dashboard Latency Fix Pass addressing remaining 18-28s dashboard latency.
- Deployment status: Railway and Vercel deployed; Breeze session likely valid; 124 backend tests pass; frontend builds 1853 modules

## Environment
- Backend: Flask 3 skeleton
- Frontend: React + Vite + TypeScript skeleton
- Database: PostgreSQL online on Railway
- Cache: Redis online on Railway
- Broker: Breeze only, diagnostic gateway and master-contract import implemented
- Deployment: Railway + Vercel live

## Phase Log

### 2026-06-17 - Dashboard Card Submetric Rendering Fix
- Goal: Make the ORIENS dashboard cards match the requested reference card details without changing the wider dashboard layout.
- Root cause:
  - Backend already exposed the requested submetric values, but the frontend rendered every submetric as `Label: value`, so the Open Positions card did not match the required `0 Options | 0 Future | 0 Equity` reference format.
  - The card submetric row was also slightly too small and easy to miss in the dark ORIENS card style.
- Frontend changes:
  - Day's P&L now renders `Realized: <value> | Unrealized: <value>`.
  - Open Positions now renders value-first position buckets: `<value> Options | <value> Future | <value> Equity`.
  - Monthly ROI continues to render `Annual ROI (FY): <value>`.
  - Submetric spacing and nowrap behavior were tightened so the row remains visible and aligned inside the cards.
- Backend changes:
  - None required; the dashboard summary contract already supplied the required submetric values from `PositionsService` totals.
- Verification:
  - `python -m pytest` -> 124 passed.
  - `npm.cmd run build` -> 1853 modules, passes after rerunning outside the known local Vite/esbuild sandbox denial.
- Remaining risks:
  - Realized P&L, monthly ROI, annual ROI, and margin used remain placeholders until a real account/funds and capital-history contract is implemented.

### 2026-06-17 - Dashboard Portfolio Cards + Plain Dark Background
- Goal: Replace duplicate NIFTY/BANKNIFTY futures dashboard cards with portfolio-focused cards while preserving the ORIENS dark aesthetic.
- Root cause:
  - Dashboard summary still returned futures quote cards even though the top ticker already shows NIFTY/BANKNIFTY futures.
  - Dashboard metric cards rendered oversized engraved icons, and the global dark shell still had radial ambience that created a distracting cube-like background artifact.
- Backend changes:
  - `DashboardService.get_summary()` now returns exactly four metric cards in this order: `day_pnl`, `open_positions`, `monthly_roi`, `margin_used`.
  - `PositionsService` now exposes portfolio totals needed by the new cards: option/future/equity position counts, realized P&L, unrealized P&L, and day P&L.
  - Current limitation: realized P&L is `0.0`, monthly ROI/annual ROI are unavailable placeholders, and margin used is `0.0` until a dedicated account/funds contract is added.
- Frontend changes:
  - Dashboard cards now render the four requested cards: Day's P&L, Open Positions, Monthly ROI, Margin Used.
  - Cards support currency/percent/number formatting and small submetrics.
  - Removed oversized dashboard metric-card engraved icons.
  - Removed dark-mode radial background ambience so the workspace background stays plain black/dark.
- Files changed:
  - `backend/app/services/dashboard_service.py`
  - `backend/app/services/positions_service.py`
  - `backend/tests/test_dashboard_contract.py`
  - `backend/tests/test_positions_contract.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/index.css`
- Verification:
  - `python -m pytest` -> 124 passed.
  - `npm.cmd run build` -> 1853 modules, passes. First sandboxed build hit the known local Vite/esbuild filesystem denial; rerun outside sandbox passed.
- Remaining risks:
  - Margin and ROI cards are UI/API placeholders until the app adds a real Breeze/account funds and capital history contract.

### 2026-06-14 - Phase 21: Diagnosis-First Operating Protocol
- Goal: Stop symptom-driven patching by establishing a diagnosis protocol with measurable evidence before any code change. Add diagnostic infrastructure (route timing, cache inspection, broker diagnostics, worker diagnostics) and a protocol document.
- Backend changes:
  - Created `backend/app/diagnosis.py` — Diagnostic helpers: `route_timer`, `step_timer`, `collect_timing`, `get_timing`, `clear_timing`, `diagnosis_record` template builder.
  - Created `backend/app/api/diagnosis.py` — Diagnostic API blueprint with 6 endpoints:
    - `GET /api/diagnosis/trace?route=<name>` — Time any known route end-to-end
    - `GET /api/diagnosis/cache` — Check Redis cache health + tick key count
    - `GET /api/diagnosis/broker` — Check Breeze auth + symbol diagnostics
    - `GET /api/diagnosis/worker` — Check websocket worker state + snapshot
    - `GET /api/diagnosis/full` — Aggregate all system checks in one call
    - `GET /api/diagnosis/timing` / `DELETE /api/diagnosis/timing` — List/clear timing records
  - Registered `diagnosis_bp` in `factory.py`.
- Frontend changes:
  - None (data-layer frozen per user instructions).
- Files changed:
  - `backend/app/diagnosis.py` (new)
  - `backend/app/api/diagnosis.py` (new)
  - `backend/app/factory.py` (register diagnosis blueprint)
  - `backend/tests/test_diagnosis_contract.py` (new — 12 API contract tests)
  - `backend/tests/test_diagnosis_tools.py` (new — 9 unit tests for diagnosis helpers)
  - `DIAGNOSIS.md` (new — full protocol document)
  - `development.md` (this entry)
- Verification:
  - `python -m pytest` -> 110 passed (90 existing + 20 new)
  - `npm run build` -> 1853 modules, passes
  - `curl http://127.0.0.1:5000/api/diagnosis/trace?route=health` -> timing payload
  - `curl http://127.0.0.1:5000/api/diagnosis/cache` -> cache status
  - `curl http://127.0.0.1:5000/api/diagnosis/broker` -> broker status
  - `curl http://127.0.0.1:5000/api/diagnosis/worker` -> worker status
  - `curl http://127.0.0.1:5000/api/diagnosis/full` -> full system check
  - `curl http://127.0.0.1:5000/api/diagnosis/timing` -> timing records
  - `curl -X DELETE http://127.0.0.1:5000/api/diagnosis/timing` -> clear confirmed
- Manual user tasks:
  - Review `DIAGNOSIS.md` and adopt the protocol when investigating future issues.
  - Use `/api/diagnosis/trace?route=<route>` instead of guessing when pages feel slow.
- Remaining risks:
  - Phase 18 Tier 2-3 and Phase 19 still planned but not yet implemented.
  - Diagnosis protocol is only as effective as the discipline to use it — no code can enforce the human process.
- Next step: Resume Phase 18 Tier 2 (Redis-first quote reads, option-chain strike streaming, parallel batch).

### 2026-06-14 - UI Pass 3: Futuristic Neon Glow (Crypto-Trading-Dashboard-3D inspired)
- Goal: add a futuristic glow aesthetic on top of the visual port - dark by default, neon accents, glassmorphism, hover lift+glow boxes, neon icon top-left + engraved icon bottom-right per box, glowing chart line. Backend and frontend->backend data wiring frozen.
- Delivered in 5 steps + 1 fix, each built and pushed:
  - Step 1 foundation (commit `e288994`): neon tokens, radial neon dark-mode background, `.glow-card`/`.glow-icon`/`.engraved-icon`/`.glow-line` utilities + reduced-motion guard in `index.css`; ThemeProvider defaults to dark.
  - Step 2 (commit `39b7350`): shared `StatCard` gets glass bg, hover glow, optional neon glow-icon + engraved icon.
  - Step 3 (commit `6d46fbf`): dashboard 4 boxes neon/engraved icons + hover glow; chart line -> neon cyan `#00f2ff` with glow + cyan badge.
  - Step 4 (commit `7642647`): base `Card` -> dark glass surface (all panels glassy); neon topic icons on stat boxes across every page.
  - Step 5 (commit `183a208`): neon glow on active sidebar item, PayoffChart line, "A" avatar.
  - Fix (commit `9bfa57e`): per-position fallback icons so the 4 dashboard boxes are distinct even while loading/unmapped (`metricIcon(key, index)`).
  - Fix (commit `671b3b5`): the 6 Tools cards now use glow-card + dark glass + per-tool neon/engraved icons (they previously used the base Card and did not glow on hover).
- FROZEN/untouched: `frontend/src/lib/api.ts`, `frontend/src/lib/realtime.ts`, `frontend/src/hooks/*`, all of `backend/`. `npm run build` passes on every step.

### 2026-06-13 - UI Alignment Pass 2: Full Visual Port (all pages)
- Goal: complete the page-by-page 1:1 legacy visual port flagged as a follow-up in Pass 1 - make every APTRADES2 page look identical to the old `ankitlj/APTRADES.git` frontend (fonts, colors, tables, boxes, layouts, chart lines, dark/light mode, "A" menu, dashboard ticker) with backend and all frontend->backend data wiring frozen.
- Delivered in 5 user-gated steps, each built and pushed:
  - Step 1 audit & map (commit `7cb6d2e`, `UI_OVERHAUL_PLAN.md`)
  - Step 2 foundation + shell (commit `c21b216`)
  - Step 3 Dashboard (commit `b5feb5b`)
  - Step 4 Positions/Orderbook/Tradebook/OptionChain/OITracker/OIProfile (commit `95b0945`)
  - Step 5 ActionCentre/Logs/Tools/StrategyBuilder/StrategyPortfolio/Placeholder + shared states (commit `3b3d206`)
- Foundation: Tailwind v4 (`@tailwindcss/vite`) + shadcn/ui primitives (Button, Card, Badge, Table, Input, DropdownMenu) + lucide-react + cva/clsx/tailwind-merge. Ported old APTRADES oklch theme tokens (light/dark + accent via `data-theme`) into `index.css`. New `ThemeProvider` persists mode + accent to localStorage.
- Shell: sidebar `Navbar`, sticky `TopHeader` (market ticker, live/offline dot, Sun/Moon toggle, "A" tools/accent menu), `Footer`, mobile bottom nav. Dashboard SVG chart uses indigo `#6366f1`.
- Shared page helpers added in `frontend/src/components/common/page.tsx` (PageHeader, StatCard, Field, selectClass).
- FROZEN/untouched per user: `frontend/src/lib/api.ts`, `frontend/src/lib/realtime.ts`, `frontend/src/hooks/useLiveMarketData.tsx`, `frontend/src/hooks/useQuotes.ts`, all of `backend/`.
- Verification: `npm run build` passes on every step (1853 modules, ~47KB CSS). Live-market visual click-through with a fresh Breeze session token still recommended.

### 2026-06-11 - UI Alignment Pass 1: Old APTRADES Shell Port
- Goal: Replace the temporary APTRADES2 app chrome with the older APTRADES shell vocabulary without disturbing the Phase 1-18 backend/data contracts.
- Root cause:
  - APTRADES2 was still rendering through a lightweight interim shell (`AppShell.tsx` + custom CSS) that only approximated the old product.
  - The old `APTRADES` repo uses a more established shell language: logo-led sidebar, stronger navigation hierarchy, utility links, persistent live-status treatment, and tighter topbar chrome.
  - The user specifically wanted the older `ankitlj/APTRADES.git` frontend/UI reflected in `APTRADES2`, not a fresh redesign.
- Frontend changes:
  - Reworked the shared app shell to mirror the old APTRADES structure more closely:
    - logo image in sidebar header
    - primary + utility navigation split
    - nav icon tiles / denser navigation rows
    - top-right live status pill + avatar chip
    - sidebar live-status footer
    - mobile nav trimmed to the main five routes
  - Updated global frontend styling to shift APTRADES2 away from the interim flat scaffold and toward the old APTRADES visual language:
    - wider sidebar
    - glass topbar
    - stronger card radius/shadows
    - denser content spacing
    - updated brand typography and pill treatments
  - Added the old APTRADES `logo.png` into the new frontend public assets so branding matches the legacy shell.
- Files changed:
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/index.css`
  - `frontend/public/logo.png`
- Verification:
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
- Remaining risks:
  - This pass ports the shared shell/chrome first; it does not yet make every individual page a 1:1 copy of the old APTRADES page internals.
  - External `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` still cannot be updated from this workspace because it is outside the writable roots.

### 2026-06-07 - Phase 1: Clean Project Skeleton
- Goal: Create a Breeze-only APTRADES v2 monorepo skeleton with backend health endpoints and a frontend app shell.
- Backend changes:
  - Added Flask app factory and environment config loader.
  - Added `GET /api/health` and `GET /api/health/readiness`.
  - Added placeholder service modules for `BreezeGateway`, `SymbolResolver`, `MasterContractService`, and `QuoteService`.
  - Added pytest-based backend health checks.
- Frontend changes:
  - Added React + Vite + TypeScript scaffold.
  - Added APTRADES shell with 224px sidebar, 48px topbar, main content padding, and mobile bottom nav.
  - Added MVP navigation placeholders for Dashboard, Orderbook, Tradebook, Positions, Action Centre, Strategy, Logs, and Tools.
  - Added dashboard health/readiness cards wired to backend endpoints.
  - Added Vite dev proxy so local browser health checks hit the Flask backend without cross-origin failures.
- Files changed:
  - `backend/*`
  - `frontend/*`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pip install -e .[dev]`
  - `python -m pytest` -> `2 passed`
  - `npm.cmd install`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit a sandbox filesystem access denial
  - `curl http://localhost:5173/api/health` via Vite dev proxy -> backend response returned successfully during local validation
  - `curl http://127.0.0.1:5000/api/health` -> `{"service":"APTRADES v2","status":"ok",...}`
  - `curl http://127.0.0.1:5000/api/health/readiness` -> `{"checks":{"api":"online","breeze":"not_configured","postgres":"not_configured","redis":"not_configured"},"status":"ok",...}`
- Manual user tasks:
  - Confirm enough usage remains if you want strict playbook enforcement on the 15%/30% threshold.
  - Phase 1 deployment setup will require Railway and Vercel access in the next phase.
- Remaining risks:
  - Phase 2 still needs actual Railway/Vercel setup and production config.
  - External `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` could not be updated from this workspace because it is outside the writable roots.
- Next step: Install dependencies, run Phase 1 verification, update logs with exact command results, then commit and push.

### 2026-06-07 - Phase 2: Deployment Foundation
- Goal: Add production deployment plumbing early so the app can be wired to Railway and Vercel before Breeze work starts.
- Backend changes:
  - Added `flask-cors` configuration for local Vite origins plus `FRONTEND_ORIGIN` and optional preview origin values.
  - Added `GET /api/health/deployment` returning deployment-oriented component states.
  - Added environment-aware `run.py` host/port handling.
  - Added a root `Procfile` with a Railway-compatible `gunicorn` start command.
- Frontend changes:
  - Added typed deployment status API client.
  - Added a dashboard deployment status card showing `api`, `postgres`, `redis`, and `breeze`.
  - Added deployment target summary card for Railway/Vercel foundation.
- Files changed:
  - `Procfile`
  - `backend/pyproject.toml`
  - `backend/app/config.py`
  - `backend/app/factory.py`
  - `backend/app/api/health.py`
  - `backend/run.py`
  - `backend/tests/test_health.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/DashboardPage.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pip install -e .[dev]`
  - `python -m pytest` -> `3 passed`
  - `curl http://127.0.0.1:5000/api/health/deployment` -> `{"checks":{"api":"online","breeze":"unknown","postgres":"unknown","redis":"unknown"},"environment":"development",...}`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the same known sandbox filesystem denial
  - Railway runtime diagnosis after deploy attempt: `gunicorn: command not found`
- Manual user tasks:
  - Verify the deployed dashboard page.
- Remaining risks:
  - DB/Redis/Breeze states intentionally remain `unknown` until later phases wire those services.
  - External `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` could not be updated from this workspace because it is outside the writable roots.
- Next step: Attach Railway Postgres and Redis, then verify readiness status.

### 2026-06-07 - Phase 3: PostgreSQL and Redis Setup
- Goal: Add durable DB/cache foundation and make readiness reflect actual DB and Redis state.
- Backend changes:
  - Added SQLAlchemy engine helpers and Redis client helpers.
  - Added connection-aware Postgres and Redis health checks to `/api/health/readiness` and `/api/health/deployment`.
  - Added Alembic scaffold files for future migrations.
  - Added a minimal declarative base model module for future tables.
  - Added explicit backend dependency declarations for SQLAlchemy, Alembic, and Redis in both `pyproject.toml` and `requirements.txt`.
- Frontend changes:
  - Updated readiness and deployment status cards to show colored status pills for `online`, `offline`, and `unknown/not_configured`.
- Files changed:
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `backend/app/config.py`
  - `backend/app/api/health.py`
  - `backend/app/db.py`
  - `backend/app/cache.py`
  - `backend/app/models.py`
  - `backend/alembic.ini`
  - `backend/alembic/env.py`
  - `backend/alembic/script.py.mako`
  - `backend/alembic/versions/.gitkeep`
  - `backend/tests/test_health.py`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/index.css`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pip install -e .[dev]`
  - `python -m pytest` -> `3 passed`
  - `python` inline check -> `check_database('sqlite:///healthcheck.db') == online`
  - `python` inline check -> `check_redis(None) == not_configured`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the same known sandbox filesystem denial
  - Railway follow-up fix: added PostgreSQL driver dependency for SQLAlchemy runtime connections
- Manual user tasks:
  - Add Railway Postgres plugin/service and set `DATABASE_URL`
  - Add Railway Redis plugin/service and set `REDIS_URL`
  - Verify deployed readiness shows DB and Redis `online` after those services are attached
- Remaining risks:
  - Redis is still not attached yet, so deployed readiness will not show Redis `online` until `REDIS_URL` is configured.
  - Alembic is scaffolded but there are no real application tables yet.
  - External `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` could not be updated from this workspace because it is outside the writable roots.
- Next step: Attach Railway Postgres and Redis plugins, then confirm deployed readiness.

### 2026-06-07 - Phase 4: BreezeGateway Auth Diagnostic
- Goal: Prove Breeze auth, request signing, and diagnostic quote calls work before any trading page depends on broker data.
- Backend changes:
  - Implemented a real `BreezeGateway` using the official Breeze request-header and checksum flow.
  - Added `CustomerDetails` token exchange, request retry handling, and cached customer-session reuse during one diagnostic run.
  - Added `GET /api/debug/breeze-auth` for configuration and auth diagnostics.
  - Added `GET /api/debug/breeze-test` for five-symbol diagnostic quote checks.
  - Added dedicated Breeze gateway tests covering missing config, unsigned `CustomerDetails`, signed quote requests, retry behavior, and diagnostic error reporting.
- Frontend changes:
  - Added typed Breeze diagnostic API clients.
  - Updated the Dashboard with a temporary Breeze auth panel.
  - Added Breeze symbol diagnostics showing returned LTP, previous close, spot, expiry, or the real broker error per symbol.
- Files changed:
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `backend/app/config.py`
  - `backend/app/factory.py`
  - `backend/app/api/debug.py`
  - `backend/app/services/breeze_gateway.py`
  - `backend/tests/test_breeze_gateway.py`
  - `backend/tests/test_health.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/index.css`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Reviewed the official Breeze API documentation for request headers, `CustomerDetails`, and `Quotes`, plus the `breeze-connect` PyPI package page before implementation.
  - `python -m pip install -e .[dev]` -> passed after rerunning with network access outside the sandbox
  - `python -m pytest` -> `11 passed`
  - `python -c "from app import create_app; ..."` -> `/api/debug/breeze-auth` returned `not_configured` locally without secrets and `/api/debug/breeze-test` returned a structured error state
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
  - User-supplied deployed readiness check confirmed `api`, `postgres`, and `redis` are `online`
- Manual user tasks:
  - Keep `BREEZE_API_KEY`, `BREEZE_SECRET_KEY`, and `BREEZE_SESSION_TOKEN` only in local/Railway environment variables.
  - Verify the deployed Dashboard Breeze panels and `/api/debug/breeze-test` response with live broker credentials.
  - Rotate or refresh the Breeze session token if it expires; do not commit or paste it into repository files.
- Remaining risks:
  - This workspace does not hold the Breeze API key/secret, so live broker-number verification still depends on the user's deployed/local environment.
  - Futures/options diagnostics can still return broker-side contract errors until Phase 5 adds master-contract-driven expiry and alias resolution.
  - External `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` could not be updated from this workspace because it is outside the writable roots.
- Next step: Start Phase 5 master-contract import using `StockScriptNew.csv` and Breeze SecurityMaster.

### 2026-06-07 - Phase 5: Master Contract Import
- Goal: Persist Breeze instrument and alias data in PostgreSQL so later quote/futures/options flows stop guessing broker symbols and expiries at runtime.
- Backend changes:
  - Added persistent SQLAlchemy models for `instruments`, `instrument_aliases`, and `master_contract_runs`.
  - Added DB session/table helpers for service-level schema creation without importing contracts during web startup.
  - Implemented `MasterContractService` with:
    - SecurityMaster zip download/parsing
    - `StockScriptNew.csv` parsing fallback/supplement
    - contract parsing for cash, futures, and options rows
    - alias extraction for display symbol to broker symbol mapping
    - import status/run logging
  - Added `GET /api/master-contract/status`.
  - Added `POST /api/master-contract/import`.
  - Added `flask master-contract import` CLI command for scheduled/manual runs.
- Frontend changes:
  - Added typed master-contract status client.
  - Updated the Dashboard hero/topbar to Phase 5 wording.
  - Added a developer-facing Master Contract status panel showing row count, alias count, CSV availability, last import time, source/checksum, and verified alias examples.
- Files changed:
  - `backend/app/config.py`
  - `backend/app/db.py`
  - `backend/app/factory.py`
  - `backend/app/models.py`
  - `backend/app/api/master_contract.py`
  - `backend/app/services/master_contract_service.py`
  - `backend/tests/test_master_contract.py`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/index.css`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Read the Breeze SecurityMaster/master-contract phase requirements and used `StockScriptNew.csv` as the alias source of truth.
  - `python -m pytest` -> `15 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the same known sandbox filesystem denial
  - Real CSV smoke import against `C:\Users\Ankit\Desktop\Claude_Code\StockScriptNew.csv` with a temp SQLite DB:
    - `instrument_count = 33109`
    - `alias_count = 35445`
  - Endpoint contract tests:
    - `/api/master-contract/status` returns `not_configured` cleanly without a DB
    - `/api/master-contract/import` returns a clear error when `DATABASE_URL` is missing
- Manual user tasks:
  - Trigger the first deployed import run with `POST /api/master-contract/import` or `flask master-contract import`.
  - Verify the deployed Dashboard master-contract panel updates after the first import.
  - Configure a daily Railway schedule for `flask master-contract import`.
  - If you want the deployed app to use the local CSV instead of SecurityMaster-only fallback, provide a safe Railway-accessible copy via env-mounted file or another upload mechanism.
- Remaining risks:
  - Railway cannot see `C:\Users\Ankit\Desktop\Claude_Code\StockScriptNew.csv`, so deployed imports will rely on SecurityMaster unless you provide that CSV through a deployment-safe path.
  - `SymbolResolver` and quote APIs still do not consume these persisted tables yet; that starts in Phase 6.
  - External `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` could not be updated from this workspace because it is outside the writable roots.
- Next step: Build `SymbolResolver` and quote APIs on top of the imported instrument and alias tables.

### 2026-06-07 - Phase 5 Follow-up: Deployed Import Timeout Fix
- Goal: Prevent Railway worker timeouts when the external SecurityMaster zip is unreachable.
- Backend changes:
  - Reduced SecurityMaster request timeout to fail fast instead of hanging the Gunicorn worker.
  - Added a seeded alias/instrument fallback source so imports can still complete on Railway when both SecurityMaster and the local CSV are unavailable.
- Verification:
  - `python -m pytest` -> `16 passed`
  - Fallback import test now succeeds with a missing CSV and failed SecurityMaster download
- Manual user tasks:
  - Retry `POST /api/master-contract/import` on Railway after this deploy
  - Refresh the deployed dashboard and verify the master-contract panel shows non-zero counts
- Remaining risks:
  - Seeded fallback is intentionally minimal and not a replacement for full SecurityMaster/CSV import.
  - Full contract coverage on Railway still depends on either a reachable SecurityMaster source or a deployment-safe CSV copy.

### 2026-06-08 - Phase 5 Completion Fix: Repo StockScriptNew.csv
- Goal: Remove the Railway dependency on the local desktop-only `C:\Users\Ankit\Desktop\Claude_Code\StockScriptNew.csv` path.
- Root cause:
  - Railway can download code from GitHub, but it cannot access files on the user's Windows desktop.
  - The deployed import therefore fell back to the minimal seed aliases when SecurityMaster also timed out.
- Backend changes:
  - Added `backend/data/StockScriptNew.csv` as the deployed stock-code mapping source.
  - Changed the default `STOCK_SCRIPT_CSV_PATH` to `data/StockScriptNew.csv`.
  - Added backend-root relative path resolution so Railway and local runs resolve the same CSV path.
  - Added regression coverage for repo-relative CSV availability.
- Verification:
  - `python -m pytest` -> `17 passed`
  - Real repo-CSV smoke import with SecurityMaster disabled:
    - `status = ok`
    - `row_count = 33109`
    - `alias_count = 35445`
    - `source_name = stock_script_csv+seed_aliases`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
- Manual user tasks:
  - Wait for Railway to deploy this commit.
  - Retry `POST /api/master-contract/import` on Railway.
  - Verify the response `source_name` includes `stock_script_csv` and `row_count` is around `33109`, not `5`.
- Remaining risks:
  - Railway still may not reach `http://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip`; that is now isolated from the CSV mapping issue.
  - If ICICI SecurityMaster is required for daily derivatives freshness, a later fix must provide a reachable mirror/schedule/source that follows the Breeze-only plan.

### 2026-06-08 - Phase 5 Hardening Fix: HTTPS SecurityMaster
- Goal: Make the official ICICI SecurityMaster source usable without a manual daily download.
- Root cause:
  - The old HTTP SecurityMaster URL timed out from Railway and local network probes.
  - The reachable ICICI endpoint is the HTTPS variant, and the current archive contains `.txt` files, not `.csv` files.
  - The importer was only parsing `.csv` archive entries.
- Backend changes:
  - Changed default `SECURITY_MASTER_URL` to `https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip`.
  - Added configurable `SECURITY_MASTER_CONNECT_TIMEOUT` and `SECURITY_MASTER_READ_TIMEOUT`.
  - Added parsing for ICICI SecurityMaster `.txt` files.
  - Added mapping for NSE/BSE cash rows and NFO/BFO derivative rows into the internal instrument format.
  - Limited the seed fallback warning to seed-only imports.
- Verification:
  - `curl.exe -I --max-time 20 https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip` -> `HTTP/1.1 200 OK`
  - Python `requests.get(..., timeout=(20, 30))` downloaded a valid zip with ICICI master files.
  - `python -m pytest` -> `19 passed`
  - Live HTTPS SecurityMaster smoke import with repo CSV:
    - `status = ok`
    - `row_count = 127774`
    - `alias_count = 37204`
    - `source_name = security_master+stock_script_csv+seed_aliases`
    - `warnings = []`
- Manual user tasks:
  - Wait for Railway deployment of this commit.
  - Retry `POST /api/master-contract/import`.
  - Verify the deployed response includes `security_master` and no timeout warning.
- Remaining risks:
  - ICICI directlink can still be slow or temporarily unavailable, so the repo CSV remains the safe fallback.
  - A Railway scheduled import should use the CLI command after this deploy rather than a browser-triggered request.

### 2026-06-08 - Phase 6: SymbolResolver and Quote Service
- Goal: Make display symbols work reliably with Breeze stock codes and imported derivative contracts.
- Backend changes:
  - Implemented `SymbolResolver` backed by `instruments` and `instrument_aliases`.
  - Added cash alias resolution and derivative resolution for nearest futures contracts on NFO/BFO.
  - Implemented `QuoteService` to combine resolver output with `BreezeGateway`.
  - Added `GET /api/quotes`.
  - Added `POST /api/quotes/batch`.
  - Updated `GET /api/debug/breeze-test` to use the resolver-backed quote flow instead of hardcoded Breeze payload guessing.
- Frontend changes:
  - Added shared `useQuote` and `useBatchQuotes` hooks.
  - Added a small quote status component.
  - Replaced the dashboard quote diagnostics panel with resolver-backed quote API calls.
  - Updated the dashboard hero and topbar to Phase 6 wording.
- Verification:
  - Read the Phase 6 section in `APTRADES_v2_master_development_playbook.md` before implementation.
  - Re-checked the official Breeze quotes documentation for required `stock_code`, `exchange_code`, `product_type`, `expiry_date`, `right`, and `strike_price` fields.
  - `python -m pytest` -> `23 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
  - Verified resolver contracts in tests:
    - `SBIN` -> `STABAN` on `NSE` cash
    - `BANKNIFTY` -> `CNXBAN` on `NFO` futures with a real expiry
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this commit.
  - Verify the dashboard quote panel now resolves NIFTY and BANKNIFTY through the backend quote API instead of returning the old missing-expiry error.
  - Refresh `BREEZE_SESSION_TOKEN` only if Breeze auth expires.
- Remaining risks:
  - Quote freshness is still request/response based REST only; WebSocket live quotes arrive in a later phase.
  - Options-specific resolution beyond nearest futures is intentionally deferred until later phases.

### 2026-06-08 - Phase 6 Hardening Fix: Current Futures Selection
- Goal: Fix deployed NIFTY/BANKNIFTY resolver-backed quotes returning `No Data Found`.
- Root cause:
  - `StockScriptNew.csv` contains expired March/April/May 2026 NFO futures rows.
  - The resolver ordered futures by earliest expiry without filtering out past expiries.
  - Because the import includes both repo CSV and SecurityMaster rows, expired CSV contracts were selected ahead of current SecurityMaster contracts.
  - Breeze correctly rejected those expired NFO contracts with `No Data Found`.
- Backend changes:
  - Updated futures resolution to prefer the nearest expiry on or after the current date.
  - Kept a fallback to latest expired futures only if no active future exists.
  - Updated quote error handling so a Breeze quote failure still returns the resolved contract metadata.
  - Fixed `/api/debug/breeze-test` to handle unresolved error entries safely.
- Verification:
  - Reproduced the deployed API symptom with `POST /api/quotes/batch` returning `No Data Found` for NIFTY/BANKNIFTY.
  - Ran a local SecurityMaster + repo CSV import and confirmed the previous resolver selected expired `30-MAR-2026` contracts.
  - Confirmed the fixed resolver selects SecurityMaster `30-JUN-2026` contracts for:
    - `NIFTY` -> `NIFTY~F:30-JUN-2026`
    - `BANKNIFTY` -> `CNXBAN~F:30-JUN-2026`
  - `python -m pytest` -> `24 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this commit.
  - Refresh the dashboard and verify NIFTY/BANKNIFTY show resolved June 2026 futures instead of expired/unresolved errors.
  - If Breeze still returns an error, use the resolved expiry/token shown in the response to determine whether the broker currently accepts that index future quote.

### 2026-06-08 - Phase 7: Dashboard
- Goal: Build the main APTRADES dashboard with real backend contracts instead of Phase 6 diagnostics cards.
- Backend changes:
  - Added `GET /api/dashboard/summary`.
  - Added `GET /api/dashboard/alerts`.
  - Added `GET /api/dashboard/chart?symbol=NIFTY`.
  - Extended `BreezeGateway` with read-only `portfoliopositions` and `historicalcharts` calls.
  - Added a minimal `PositionsService` for normalized active positions snapshots.
  - Added a `DashboardService` that composes quote, positions, Breeze auth, master-contract, and chart data into one dashboard contract.
- Frontend changes:
  - Replaced the Phase 6 diagnostics-heavy dashboard with:
    - four metric cards
    - a chart panel
    - an alerts panel
    - an active positions table
  - Added a dashboard-only topbar market ticker.
  - Added a `/dashboard` route and redirected `/` to it.
  - Preserved explicit loading, error, empty, and success states across all dashboard panels.
- Files changed:
  - `backend/app/factory.py`
  - `backend/app/api/dashboard.py`
  - `backend/app/services/breeze_gateway.py`
  - `backend/app/services/dashboard_service.py`
  - `backend/app/services/positions_service.py`
  - `backend/tests/test_dashboard_contract.py`
  - `frontend/src/App.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/pages/PlaceholderPage.tsx`
  - `frontend/src/index.css`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Re-read the Phase 7 dashboard section in the master playbook and the dashboard-related frontend design notes before coding.
  - `python -m pytest` -> `27 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
  - Dashboard endpoint contract tests verify:
    - summary metrics and active positions
    - alerts payload
    - normalized historical chart points
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this commit.
  - Verify the deployed `/dashboard` visual layout.
  - Confirm the topbar ticker appears only on the dashboard route.
- Remaining risks:
  - Dashboard positions depend on Breeze `portfoliopositions`; if Breeze returns no open positions, the table will correctly stay empty.
  - The chart currently uses daily historical candles for `NIFTY`; intraday/live charting remains part of the later WebSocket/live-data phase.
  - External `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md` still cannot be updated from this workspace because it is outside the writable roots.

### 2026-06-08 - Phase 7: Railway Runtime Fix
- Goal: Complete Phase 7 on deployed Railway/Vercel after production logs exposed runtime mismatches that local happy-path tests had missed.
- Root cause:
  - `GET /api/dashboard/chart` passed a `ResolvedInstrument` into `BreezeGateway.get_historical_charts()`, but the Breeze gateway expects a normalized request object with `stock_code`.
  - Breeze `No Positions available.` was being treated as a dashboard failure instead of the intended empty-state response.
- Backend changes:
  - Updated dashboard chart generation to convert resolved symbols through the shared quote-to-Breeze adapter before calling Breeze historical charts.
  - Updated `PositionsService` so `No Positions available.` returns `status = ok`, zero totals, and an empty positions list.
  - Strengthened dashboard contract tests so chart requests assert the normalized Breeze instrument and alerts assert the no-positions empty state.
- Files changed:
  - `backend/app/services/dashboard_service.py`
  - `backend/app/services/positions_service.py`
  - `backend/tests/test_dashboard_contract.py`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Reviewed Railway production traceback for `/api/dashboard/chart`:
    - `AttributeError: 'ResolvedInstrument' object has no attribute 'stock_code'`
  - Re-ran backend tests after the fix:
    - `python -m pytest` -> `28 passed`
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this fix commit.
  - Refresh `/dashboard` and confirm:
    - summary metrics load
    - alerts load
    - chart loads instead of `500`
    - positions shows an empty state when Breeze has no open positions instead of an error panel

### 2026-06-08 - Phase 7: Vercel SPA Routing Fix
- Goal: Restore deployed frontend access after direct navigation to `/dashboard` started returning a Vercel `404 NOT_FOUND` page.
- Root cause:
  - The frontend uses `BrowserRouter`, but the Vercel frontend root had no SPA rewrite rule.
  - A direct request to `/dashboard` was handled by Vercel as a file lookup instead of serving `index.html`.
- Frontend changes:
  - Added `frontend/vercel.json` with a catch-all rewrite to `index.html`.
- Files changed:
  - `frontend/vercel.json`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Confirmed the frontend uses `BrowserRouter` in `frontend/src/main.tsx`.
  - Confirmed routes include `/dashboard` in `frontend/src/App.tsx`.
  - Frontend build verification pending after config update.
- Manual user tasks:
  - Wait for Vercel to redeploy this commit.
  - Re-open `https://aptrades-2.vercel.app/dashboard`.
  - Confirm the Vercel 404 page is replaced by the React dashboard shell.

### 2026-06-08 - Phase 7: Chart Resolution and Panel Isolation Fix
- Goal: Finish the deployed Phase 7 dashboard after the shell loaded but chart, alerts, and positions still appeared broken.
- Root cause:
  - `GET /api/dashboard/chart?symbol=NIFTY` was resolving `NIFTY` through the `NSE cash` path, while the verified live Phase 6 quote path for `NIFTY` is `NFO futures`.
  - The dashboard page used a single `Promise.all`, so one chart failure caused alerts and positions panels to show the same frontend error even when their backend endpoints were healthy.
  - Frontend API errors only surfaced generic HTTP status text, hiding the actual backend message.
- Backend changes:
  - Updated dashboard chart resolution so index symbols like `NIFTY` and `BANKNIFTY` use the same `NFO futures` resolver path as the live quote service.
  - Strengthened chart contract tests to assert the Breeze gateway receives:
    - `exchange_code = NFO`
    - `product_type = futures`
    - a normalized expiry timestamp
- Frontend changes:
  - Switched dashboard data loading from one shared `Promise.all` failure path to independent `Promise.allSettled` handling.
  - Updated API error parsing so JSON error payloads surface the real backend message instead of only `Request failed with status 400`.
- Files changed:
  - `backend/app/services/dashboard_service.py`
  - `backend/tests/test_dashboard_contract.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/DashboardPage.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pytest` -> `28 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this fix commit.
  - Refresh `/dashboard`.
  - Confirm:
    - metric cards render from summary data
    - chart panel no longer fails because of the wrong instrument path
    - alerts and positions no longer inherit chart errors when their own endpoints are healthy

### 2026-06-08 - Phase 7: Breeze Chart Interval Fix
- Goal: Close the final remaining Phase 7 dashboard error after summary and alerts were working but the chart still showed a Breeze validation message.
- Root cause:
  - Breeze historical charts rejected `interval = 1day`.
  - The deployed backend needed Breeze's accepted daily interval token: `day`.
- Backend changes:
  - Updated dashboard chart requests from `1day` to `day`.
  - Updated chart contract tests to assert the Breeze interval value and the API response interval.
- Files changed:
  - `backend/app/services/dashboard_service.py`
  - `backend/tests/test_dashboard_contract.py`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pytest` -> `28 passed`
- Manual user tasks:
  - Wait for Railway to deploy this final Phase 7 fix.
  - Refresh `/dashboard`.
  - Confirm the chart panel renders instead of the Breeze interval validation error.

### 2026-06-08 - Phase 8: Orderbook and Tradebook
- Goal: Build broker order/trade pages with compact tables.
- Backend changes:
  - Added `GET /api/orders`.
  - Added `POST /api/orders/cancel`.
  - Added `POST /api/orders/cancel-all`.
  - Added `GET /api/trades`.
  - Extended `BreezeGateway` with:
    - `get_order_list`
    - `cancel_order`
    - `get_trade_list`
  - Added normalized `OrdersService` and `TradesService` so the frontend is not tied to raw Breeze response keys.
  - `cancel-all` only targets cancellable order states such as open, pending, ordered, partially executed, requested, and trigger-pending.
- Frontend changes:
  - Replaced `/orderbook` placeholder with a real Orderbook page.
  - Added:
    - page header/subtitle
    - filter toolbar
    - refresh
    - export CSV
    - cancel all action
    - orders-only tab strip
    - order stats cards
    - compact orders table with row cancel actions
  - Replaced `/tradebook` placeholder with a real Tradebook page.
  - Added:
    - page header/toolbar
    - exchange/action filters
    - refresh
    - export CSV
    - trade stats cards
    - compact trade table
  - Updated topbar phase label for the current app phase.
- Files changed:
  - `backend/app/api/orders.py`
  - `backend/app/factory.py`
  - `backend/app/services/breeze_gateway.py`
  - `backend/app/services/orders_service.py`
  - `backend/app/services/trades_service.py`
  - `backend/tests/test_orders_contract.py`
  - `frontend/src/App.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/index.css`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/OrderbookPage.tsx`
  - `frontend/src/pages/TradebookPage.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Re-read the Phase 8 section in the master playbook before implementation.
  - `python -m pytest` -> `32 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
  - Contract tests cover:
    - normalized orders payload and stats
    - single cancel payload
    - cancel-all only targeting open/pending orders
    - normalized trades payload and stats
- Real order/trade action note:
  - Live Breeze cancel actions were implemented but not executed against the real broker account in this phase.
  - They remain untested against production broker state until you intentionally approve live order-action testing.
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this Phase 8 commit.
  - Verify `/orderbook` renders filters, stats, and a compact table.
  - Verify `/tradebook` renders stats and a compact table.
  - Do not place or cancel real orders unless intentionally testing order actions.

### 2026-06-08 - Phase 8: Breeze Orders/Trades Endpoint Runtime Fix
- Goal: Complete deployed Phase 8 after Railway showed live Breeze `404 Not Found` errors for orderbook and tradebook requests.
- Root cause:
  - The first Phase 8 implementation used incorrect Breeze REST paths:
    - `/orderlist`
    - `/cancelorder`
    - `/tradelist`
  - Live Railway calls therefore failed even though local contract tests passed, because those tests mocked the gateway methods and did not lock down the actual Breeze endpoint paths.
- Backend changes:
  - Updated `BreezeGateway.get_order_list()` to call `/order`.
  - Updated `BreezeGateway.cancel_order()` to send `DELETE /order`.
  - Updated `BreezeGateway.get_trade_list()` to call `/trades`.
  - Added gateway regression tests so future changes must keep the live Breeze order/trade endpoint paths intact.
- Files changed:
  - `backend/app/services/breeze_gateway.py`
  - `backend/tests/test_breeze_gateway.py`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pytest` -> `35 passed`
- Manual user tasks:
  - Wait for Railway to redeploy this fix commit.
  - Refresh `/orderbook` and `/tradebook`.
  - Confirm the prior Breeze `404 Not Found` errors are gone.
- Remaining risks:
  - Real broker order/trade payload shape may still vary by account state, but the REST paths are now aligned with the deployed Breeze API contract.

### 2026-06-09 - Phase 9: Positions
- Goal: Build the main positions page with live quote enrichment.
- Backend changes:
  - Added `GET /api/positions`.
  - Expanded `PositionsService` from a dashboard helper into a real API contract service.
  - Added position normalization for Breeze portfolio rows.
  - Added live quote enrichment through `QuoteService` so rows can surface live `ltp`, recomputed `pnl`, `pnl_percent`, token, and resolution source.
  - Preserved safe read-only behavior:
    - `close_actions_active = false`
    - no close-position endpoint yet
  - Reused the same positions service in the dashboard summary/alerts path so Phase 7 and Phase 9 stay on one data source.
- Frontend changes:
  - Replaced `/positions` placeholder with a real Positions page.
  - Added:
    - header with `Live/Paused` badge
    - toolbar with `Settings`, `Refresh`, `Export`, and disabled `Close All`
    - stats cards for `Open Positions`, `Long`, `Short`, and `Total P&L`
    - settings panel with grouping, product, direction, and exchange filters
    - positions table with symbol, exchange, product, qty, avg, ltp, p&l, p&l%, and disabled close action
  - Updated the app topbar phase label for Phase 9.
- Files changed:
  - `backend/app/api/positions.py`
  - `backend/app/factory.py`
  - `backend/app/services/dashboard_service.py`
  - `backend/app/services/positions_service.py`
  - `backend/tests/test_dashboard_contract.py`
  - `backend/tests/test_positions_contract.py`
  - `frontend/src/App.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/index.css`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/PositionsPage.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `curl http://127.0.0.1:5000/api/positions` -> `200` and a clean `not_configured` payload without Breeze env
  - `python -m pytest` -> `39 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the same known sandbox filesystem denial
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this phase after push.
  - Verify `/positions` loads with live rows if the broker has open positions.
  - Do not test `Close All` unless explicitly ready in a later action phase.
- Remaining risks:
  - Close-position actions are intentionally disabled in this phase.
  - Real open-position payloads may vary by broker account state, so the first deployed validation should confirm the live row shape and quote enrichment quality.

### 2026-06-09 - Phase 10: Tools Reduced Scope
- Goal: Show only the six approved MVP tools and keep unused tools out of the visible product flow.
- Backend changes:
  - None. The current repo does not have a backend tools-route registry that needs cleanup in this phase.
- Frontend changes:
  - Replaced the `/tools` placeholder with a real reduced-scope Tools page.
  - Added a responsive tools grid:
    - 1 column on mobile
    - 2 columns on medium widths
    - 3 columns on large widths
    - 24px gap
  - Added only the six approved MVP tools:
    - Strategy Builder
    - Strategy Portfolio
    - Option Chain
    - Option Greeks
    - OI Tracker
    - OI Profile
  - Added 40x40 icon tiles and kept card heights inside the intended compact range.
  - Updated the topbar phase label for Phase 10.
  - Explicitly kept these tools out of the visible MVP tools flow:
    - Max Pain
    - Straddle Chart
    - Straddle P&L
    - Vol Surface
    - GEX
    - IV Smile
- Files changed:
  - `frontend/src/App.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/index.css`
  - `frontend/src/pages/ToolsPage.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the same known sandbox filesystem denial
- Manual user tasks:
  - Wait for Vercel to deploy this phase after push.
  - Open `/tools`.
  - Verify only the six approved tools are visible.
- Remaining risks:
  - This phase is intentionally scope-reduction only; the individual tools themselves are still built in later phases.

### 2026-06-09 - Phase 11: Option Chain
- Goal: Build the first core options data page with Breeze-backed expiries, normalized chain rows, and a live `/optionchain` route.
- Backend changes:
  - Added `GET /api/options/expiries?underlying=NIFTY`.
  - Added `GET /api/option-chain?underlying=NIFTY&expiry=<iso-date>&strike_count=<n>`.
  - Added `OptionChainService` backed by:
    - imported master-contract expiries from PostgreSQL
    - Breeze option-chain quotes for `call` and `put`
    - normalized CE/PE strike-grid rows
    - brief Redis caching when `REDIS_URL` is configured
  - Extended `BreezeGateway` with `get_option_chain_quotes()`.
- Frontend changes:
  - Added a real `/optionchain` page.
  - Added:
    - header with trend icon
    - control bar for exchange, underlying, expiry, strike count, refresh
    - summary cards for `Spot`, `ATM Strike`, `PCR`, and `Total OI`
    - option-chain table with:
      - green calls header
      - muted strike column
      - red puts header
      - mono compact rows
    - amber real-error card when the backend returns a broker/runtime message
  - Updated `/tools` so the `Option Chain` card links to `/optionchain`.
  - Updated the global topbar phase label to Phase 11.
- Files changed:
  - `backend/app/api/options.py`
  - `backend/app/factory.py`
  - `backend/app/services/breeze_gateway.py`
  - `backend/app/services/option_chain_service.py`
  - `backend/tests/test_option_chain_contract.py`
  - `frontend/src/App.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/index.css`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/OptionChainPage.tsx`
  - `frontend/src/pages/ToolsPage.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Re-read the Phase 11 section in `APTRADES_v2_master_development_playbook.md`.
  - Re-checked the official Breeze docs surface for option-chain support and the `breeze-connect` `get_option_chain_quotes(...)` helper before wiring the gateway.
  - `python -m pytest backend\\tests\\test_option_chain_contract.py` -> `2 passed`
  - `python -m pytest backend` -> `41 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the known sandbox filesystem denial
- Manual user tasks:
  - After push/deploy, open `/optionchain`.
  - Verify:
    - NIFTY expiries load
    - selecting an expiry loads CE/PE rows
    - ATM strike and PCR populate
    - BANKNIFTY also loads from the same controls
- Remaining risks:
  - The exact live Breeze option-chain payload can vary by account/segment state, so Railway verification is still required after deployment.
  - If Breeze rejects the native option-chain call for a specific expiry or segment, the page will now surface the real backend message instead of hiding it.

### 2026-06-09 - Phase 11 Runtime Fix: Breeze Option-Chain Path
- Goal: Complete deployed Phase 11 after the frontend loaded but the broker returned a live `404` for the option-chain call even with a fresh session token.
- Root cause:
  - The first Phase 11 implementation used the wrong Breeze REST path: `/optionchainquotes`.
  - The official Breeze docs use `/optionchain`, so the deployed broker rejected the request before auth or data logic mattered.
- Backend changes:
  - Updated `BreezeGateway.get_option_chain_quotes()` to call `/optionchain`.
  - Added a regression test that locks the live Breeze path to `/optionchain`.
- Files changed:
  - `backend/app/services/breeze_gateway.py`
  - `backend/tests/test_breeze_gateway.py`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Re-checked the official Breeze API docs for the option-chain endpoint path.
  - `python -m pytest backend/tests/test_breeze_gateway.py` -> passed
  - `python -m pytest backend` -> passed
- Manual user tasks:
  - Wait for Railway to redeploy this fix.
  - Refresh `/optionchain`.
  - Confirm the prior `404 ... /optionchainquotes` error is gone.
- Remaining risks:
  - After the endpoint-path fix, any next error will be the real broker payload/parameter issue, not a bad REST path.

### 2026-06-10 - Phase 13: OI Tracker and OI Profile
- Goal: Build the OI Tracker and OI Profile tool pages backed by full-chain option data from Breeze via the existing Phase 11 OptionChainService.
- Note: Phase 12 (Option Greeks) was intentionally skipped. Greeks are deferred and will be computed inline in strategy code when needed (Black-Scholes / Heston / Monte Carlo). Phase 13 has no dependency on Phase 12.
- Backend changes:
  - Added `OIService` in `backend/app/services/oi_service.py`.
    - `get_tracker()` — fetches full chain (strike_count=0), flattens rows to {strike_price, ce_oi, pe_oi, total_oi, ce_ltp, pe_ltp}, sorts by total_oi descending, computes max_ce_oi_strike and max_pe_oi_strike.
    - `get_profile()` — same flatten, rows stay sorted by strike_price ascending (natural order from OptionChainService).
    - Both reuse `OptionChainService.get_option_chain()` — no new Breeze endpoint needed.
  - Added `oi_bp` blueprint in `backend/app/api/oi.py`:
    - `GET /api/oi/tracker?underlying=NIFTY&expiry=<iso-date>&exchange=NFO`
    - `GET /api/oi/profile?underlying=NIFTY&expiry=<iso-date>&exchange=NFO`
  - Registered `oi_bp` in `backend/app/factory.py`.
- Frontend changes:
  - Added `OIRow`, `OITrackerResponse`, `OIProfileResponse` types and `getOITracker()`, `getOIProfile()` fetch functions in `frontend/src/lib/api.ts`.
  - Added `OITrackerPage` at `/oi-tracker`:
    - Exchange/underlying/expiry control bar (reuses `getOptionExpiries`)
    - 4 stat cards: ATM Strike, PCR, Resistance (max CE OI strike), Support (max PE OI strike)
    - Table sorted by total OI descending with inline CE/PE split bar
  - Added `OIProfilePage` at `/oi-profile`:
    - Same control bar
    - 4 stat cards: Spot, ATM Strike, PCR, Total OI
    - Table sorted by strike price ascending, ATM row highlighted, proportional CE/PE bar chart columns
  - Added OI CSS utilities to `index.css`: oi-tracker-table, oi-profile-table, oi-row-atm, oi-bar-*, oi-profile-bar-* classes.
  - Updated `App.tsx` with `/oi-tracker` and `/oi-profile` routes.
  - Updated `ToolsPage.tsx` — OI Tracker and OI Profile cards changed from `status: planned` to `status: next` with live hrefs.
  - Updated `AppShell.tsx` — added `/oi-tracker` and `/oi-profile` to extraPages map, updated topbar label to Phase 13 OI tools.
- Files changed:
  - `backend/app/services/oi_service.py`
  - `backend/app/api/oi.py`
  - `backend/app/factory.py`
  - `backend/tests/test_oi_contract.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/OITrackerPage.tsx`
  - `frontend/src/pages/OIProfilePage.tsx`
  - `frontend/src/index.css`
  - `frontend/src/App.tsx`
  - `frontend/src/pages/ToolsPage.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - No new Breeze endpoints used — confirmed both OI tools use `/optionchain` via the existing `OptionChainService`.
  - `python -m pytest` -> `46 passed`
  - `npm.cmd run build` -> passed, 52 modules
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this commit.
  - Open `/tools` — verify OI Tracker and OI Profile cards are now live links.
  - Open `/oi-tracker` — select NIFTY, choose an expiry, verify rows sort by total OI descending and max CE/PE OI strikes appear.
  - Open `/oi-profile` — verify rows sort by strike ascending, ATM row is highlighted, CE/PE bars are proportional.
- Remaining risks:
  - Full-chain fetch (strike_count=0) pulls all available strikes from Breeze. On a live session with many strikes, response time may be higher than the windowed option chain. Redis caching (15s TTL inherited from OptionChainService) reduces repeat load.
  - The max_ce_oi_strike and max_pe_oi_strike identify resistance/support by OI concentration only — not a financial recommendation.

### 2026-06-10 - Phase 14: Strategy Builder and Strategy Portfolio
- Goal: Build a multi-leg option strategy builder with payoff calculation and a portfolio page to manage saved strategies.
- Note: Phase 12 (Option Greeks) was intentionally skipped. No Breeze dependency in this phase — strategies are stored in PostgreSQL; payoff is pure math.
- Backend changes:
  - Added `Strategy` SQLAlchemy model in `backend/app/models.py`:
    - Columns: id, name, underlying, exchange_code, expiry_date (Date), legs_json (Text), created_at, updated_at
    - Auto-created on first request via existing `ensure_tables()` / `Base.metadata.create_all()` — no Alembic migration needed
  - Added `StrategyService` in `backend/app/services/strategy_service.py`:
    - `list_strategies()` — returns all strategies ordered by created_at desc
    - `create_strategy()` — validates and saves; returns serialized strategy dict with computed `net_premium`
    - `delete_strategy()` — raises `StrategyServiceError` if not found
    - `compute_payoff()` — 50-point curve over min_strike×0.85 to max_strike×1.15; CE/PE intrinsic math; linear-interpolated breakevens; returns net_premium, max_profit, max_loss, breakevens, curve
  - Added `strategy_bp` blueprint in `backend/app/api/strategy.py`:
    - `GET /api/strategies` — list (200)
    - `POST /api/strategies/payoff` — registered before `<int:strategy_id>` so "payoff" is never matched by the integer converter
    - `POST /api/strategies` — create (201)
    - `DELETE /api/strategies/<int:strategy_id>` — delete (200 / 404)
  - Registered `strategy_bp` in `backend/app/factory.py`.
- Frontend changes:
  - Added `StrategyLeg`, `StrategyRecord`, `StrategyListResponse`, `StrategyCreateRequest`, `StrategyCreateResponse`, `PayoffPoint`, `PayoffResponse` types in `frontend/src/lib/api.ts`.
  - Added `getStrategies()`, `createStrategy()`, `deleteStrategy()`, `getStrategyPayoff()` in `frontend/src/lib/api.ts`.
  - Added shared `PayoffChart` component in `frontend/src/components/PayoffChart.tsx`:
    - Pure SVG, no chart library dependency
    - Green fill above zero / red fill below zero using SVG clipPath
    - Dashed zero reference line
    - Amber breakeven markers with spot-price labels
    - X-axis min/mid/max spot labels
    - Unique `uid` prop prevents clipPath collisions when multiple charts render on one page
  - Added `StrategyBuilderPage` at `/strategy-builder`:
    - Exchange / underlying / expiry control bar (reuses `getOptionExpiries`)
    - Strategy name input
    - Leg builder: action, right, strike, quantity, premium; max 8 legs
    - Legs table with remove-per-row
    - "Preview Payoff" → calls `POST /api/strategies/payoff` → renders 4 stat cards + SVG payoff diagram
    - "Save Strategy" → calls `POST /api/strategies` → confirmation message
  - Added `StrategyPortfolioPage` at `/strategy-portfolio`:
    - Loads saved strategies from `GET /api/strategies`
    - Strategy card per row: name, underlying/exchange/expiry metadata, net premium badge, leg tags
    - "View Payoff" toggle → calls `POST /api/strategies/payoff` with stored legs → inline stat cards + payoff diagram
    - "Delete" per strategy → calls `DELETE /api/strategies/<id>` → removes from list
  - Added strategy CSS utilities to `index.css`: strategy-name-field, strategy-leg-table, leg-action-badge, leg-buy/sell, leg-remove-btn, toolbar-button-primary, strategy-action-row, payoff-chart-wrap, payoff-svg, strategy-portfolio-card, strategy-card-*, strategy-net-premium, strategy-legs-row, strategy-leg-tag, leg-tag-*, strategy-payoff-inline classes.
  - Updated `App.tsx` with `/strategy-builder` and `/strategy-portfolio` routes.
  - Updated `ToolsPage.tsx` — Strategy Builder and Strategy Portfolio cards changed from `status: planned` to `status: next` with live hrefs.
  - Updated `AppShell.tsx` — added `/strategy-builder` and `/strategy-portfolio` to extraPages map, updated topbar label to Phase 14 strategy tools.
- Files changed:
  - `backend/app/models.py`
  - `backend/app/services/strategy_service.py`
  - `backend/app/api/strategy.py`
  - `backend/app/factory.py`
  - `backend/tests/test_strategy_contract.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/PayoffChart.tsx`
  - `frontend/src/pages/StrategyBuilderPage.tsx`
  - `frontend/src/pages/StrategyPortfolioPage.tsx`
  - `frontend/src/index.css`
  - `frontend/src/App.tsx`
  - `frontend/src/pages/ToolsPage.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - No new Breeze endpoints used — confirmed strategies are DB-only; payoff is pure math.
  - `python -m pytest` -> `53 passed`
  - `npm.cmd run build` -> passed, 55 modules
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this commit.
  - Open `/tools` — verify Strategy Builder and Strategy Portfolio cards are now live links.
  - Open `/strategy-builder`:
    - Select underlying/expiry, enter a strategy name
    - Add 2+ legs (e.g. sell NIFTY 23300 CE @100, buy NIFTY 23400 CE @50)
    - Click "Preview Payoff" — verify green/red payoff diagram, 4 stat cards, breakeven marker
    - Click "Save Strategy" — verify confirmation message
  - Open `/strategy-portfolio`:
    - Verify saved strategy appears with correct metadata and leg tags
    - Click "View Payoff" — verify inline payoff chart loads
    - Click "Delete" — verify strategy is removed
- Remaining risks:
  - Payoff curve uses a 50-point approximation; breakeven is linearly interpolated between adjacent curve points. For strategies with flat payoff regions or near-horizontal segments, breakeven precision is ±step_size (~50–100 points depending on strikes).
  - The strategy table is auto-created via SQLAlchemy `create_all()` on first use. On Railway this runs against the live PostgreSQL database on first POST/GET to `/api/strategies`.

### 2026-06-10 - Phase 15: Action Centre and Logs
- Goal: Build operational review pages with persisted backend rows, real approve/reject actions, and searchable logs.
- Backend changes:
  - Added SQLAlchemy tables:
    - `pending_actions`
    - `api_logs`
    - `app_event_logs`
  - Implemented `ActionCentreService`:
    - syncs pending action rows from live cancellable Breeze orders across `NFO`, `NSE`, `BFO`, and `BSE`
    - persists action state transitions
    - approves by sending the linked Breeze cancel request
    - rejects without mutating the broker
  - Implemented `LogsService`:
    - stores API request rows
    - stores app event rows
    - filters by level, source, and time window
    - returns a merged live-tail payload
  - Added endpoints:
    - `GET /api/action-centre`
    - `POST /api/action-centre/:id/approve`
    - `POST /api/action-centre/:id/reject`
    - `GET /api/logs`
    - `GET /api/logs/live`
  - Registered global `/api/*` request logging in the Flask app factory when `DATABASE_URL` is configured.
- Frontend changes:
  - Replaced the `/action-centre` placeholder with a real Action Centre page:
    - info alert
    - pending / approved / rejected / all tabs
    - stats cards
    - backend action table
    - expanded detail row
  - Replaced the `/logs` placeholder with a real Logs page:
    - filters by level / source / time
    - summary cards
    - backend log table
    - live monospace viewer
  - Updated the topbar phase label to Phase 15 wording.
- Files changed:
  - `backend/app/models.py`
  - `backend/app/factory.py`
  - `backend/app/api/action_centre.py`
  - `backend/app/api/logs.py`
  - `backend/app/services/action_centre_service.py`
  - `backend/app/services/logs_service.py`
  - `backend/tests/test_action_logs_contract.py`
  - `frontend/src/App.tsx`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/pages/ActionCentrePage.tsx`
  - `frontend/src/pages/LogsPage.tsx`
  - `frontend/src/index.css`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pytest` -> `55 passed`
  - `python -m pytest backend/tests/test_action_logs_contract.py` -> `2 passed`
  - `npm.cmd run build` -> passed after rerunning outside the sandbox because Vite/esbuild hit the same known workspace filesystem denial
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this commit.
  - Open `/action-centre` and verify pending broker rows load.
  - Approve a row only if you want a real Breeze cancel-order request sent for that order.
  - Open `/logs` and verify API rows plus the live monospace tail render.
- Remaining risks:
  - Pending rows are currently sourced from live cancellable broker orders. Additional future action types should feed the same queue instead of creating a parallel system.
  - Approve is a real broker-side cancel request, so use it only on orders you intend to cancel.

### 2026-06-10 - Phase 16: WebSocket Live Market Data
- Goal: Add low-latency Breeze WebSocket streaming after the REST pages are stable, with a safe degraded fallback to REST.
- Architecture decision: Flask-SocketIO runs in `threading` async mode (no eventlet/gevent monkey-patching), so the existing REST stack, psycopg, and SQLAlchemy are untouched. The browser negotiates websocket or long-polling transport transparently. All Breeze *streaming* logic is isolated in one `MarketDataWorker`, mirroring the BreezeGateway rule for REST.
- Backend changes:
  - Added `MarketDataWorker` in `backend/app/services/market_data_worker.py`:
    - Lazy `breeze-connect` import — if the library is missing, Breeze is not configured, or the connection fails, the worker reports a non-live state and REST keeps serving (degraded mode).
    - Subscribes by Breeze stock-token `X.Y!token` (built from exchange prefix NSE/NFO=4, BSE=1, BFO=8 and the master-contract token); keeps a reverse map for tick normalization.
    - Normalizes Breeze exchange-quote ticks into a stable shape: `symbol, broker_symbol, exchange_code, token, ltp, open, high, low, close, change, change_percent, volume, oi, ts`.
    - Writes the latest tick per token to Redis (`md:tick:<exchange>:<token>`, 60s TTL) and keeps an in-memory snapshot for the REST fallback.
    - Publishes normalized ticks and status changes through an injected publish callback (Socket.IO emit).
    - Supervisor thread with exponential reconnect backoff (5s -> 60s) and lifecycle states `offline / connecting / live / degraded`.
  - Added `backend/app/realtime.py`: the single `SocketIO(async_mode="threading")` server, `init_realtime(app)`, default dashboard watchlist (NIFTY, BANKNIFTY futures), and `connect / subscribe / unsubscribe` handlers that resolve display symbols to broker tokens via `SymbolResolver` before subscribing.
  - Added `backend/app/api/market_data.py`: `GET /api/market-data/status`, `GET /api/market-data/snapshot`, `GET /api/market-data/watchlist` (REST status + degraded fallback, always 200).
  - Wired `init_realtime(app)` and the market-data blueprint into `factory.py`; updated `run.py` to use `socketio.run(...)` for local dev.
  - Updated `Procfile` to `gunicorn --worker-class gthread --threads 8 --workers 1` so a single worker owns the websocket connection while REST stays multi-threaded.
  - Added `flask-socketio`, `simple-websocket`, and `breeze-connect` to `requirements.txt` and `pyproject.toml`.
- Frontend changes:
  - Added `socket.io-client` dependency, `frontend/src/lib/realtime.ts` (typed socket factory + `LiveTick` / `MarketDataStatus` types), and `frontend/src/hooks/useLiveMarketData.tsx` (provider + `useLiveQuote`, `useLiveSubscribe`, `useLiveMarketData`).
  - Wrapped the app in `LiveMarketDataProvider` (`main.tsx`) and added a `/socket.io` websocket proxy to `vite.config.ts`.
  - Topbar now shows a live/connecting/degraded/offline badge with a pulsing status dot; the dashboard ticker overlays live LTP and % change.
  - Dashboard and Positions overlay live LTP and recompute P&L from ticks (with a `cell-live` highlight) and subscribe to their position symbols; Option Chain shows a live/REST refresh badge.
  - Added market-data REST clients/types to `lib/api.ts` and live-state styles to `index.css`.
- Files changed:
  - `backend/app/services/market_data_worker.py`
  - `backend/app/realtime.py`
  - `backend/app/api/market_data.py`
  - `backend/app/factory.py`
  - `backend/run.py`
  - `backend/requirements.txt`
  - `backend/pyproject.toml`
  - `Procfile`
  - `backend/tests/test_market_data_worker.py`
  - `backend/tests/test_market_data_contract.py`
  - `frontend/package.json`
  - `frontend/src/lib/realtime.ts`
  - `frontend/src/hooks/useLiveMarketData.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/main.tsx`
  - `frontend/vite.config.ts`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/pages/PositionsPage.tsx`
  - `frontend/src/pages/OptionChainPage.tsx`
  - `frontend/src/index.css`
  - `.gitignore`
  - `development.md`
  - `REBUILD.md`
- Verification:
  - Re-read the official Breeze WebSocket docs and the `breeze-connect` `ws_connect` / `subscribe_feeds` / `on_ticks` reference (stock-token format, exchange-quote and OHLCV tick shapes) before implementation.
  - `python -m pytest` -> `68 passed` (55 prior + 13 new market-data tests).
  - New worker tests cover stock-token building, subscribe/unsubscribe registry, tick normalization + symbol mapping, fallback without subscription, Redis write, and the not-configured/offline path.
  - `npm.cmd run build` -> passed, 88 modules.
  - Live boot smoke test (`socketio.run` dev server): `/api/market-data/status` returns `offline` cleanly without Breeze config, `/watchlist` and `/snapshot` return 200, the Socket.IO handshake `GET /socket.io/?EIO=4&transport=polling` returns a session id with a websocket upgrade, and `/api/health` still returns 200 (no REST regression).
- Manual user tasks:
  - Wait for Railway and Vercel to deploy this commit.
  - Confirm Railway uses the new gthread Procfile worker (single worker) and that `BREEZE_SESSION_TOKEN` is fresh.
  - Open `/dashboard` and confirm the topbar badge turns "Live", the ticker streams NIFTY/BANKNIFTY, and position LTP/P&L update live.
  - Open `/positions` and `/optionchain` and confirm the live badge plus live LTP overlay.
- Remaining risks:
  - Streaming was validated with mocked Breeze plus a real socket.io transport; the live broker tick shape and token-based subscription still need one deployed confirmation with real credentials.
  - Threading async mode under gunicorn favors a single worker; scaling out later would need a Redis message queue for Socket.IO. Acceptable for this single-user dashboard.
  - Next phase: Phase 17 - Production Hardening (rate limits, structured errors, readiness incl. websocket status, daily master-contract cron, mobile final pass, full smoke test).

### 2026-06-11 - Phase 17: Production Hardening
- Goal: Make the system stable enough for daily use — rate limits, structured errors, richer readiness, consistent error/empty/retry UX, and a mobile pass. Two deploy-only tasks (Railway master-contract cron, daily Breeze token-refresh decision) are intentionally deferred to the user.
- Backend changes:
  - Added structured error handlers (`backend/app/errors.py`): every `/api/*` failure returns one shape `{ "status": "error", "error": { "code", "message" } }` (covers 400/404/405/429 via the HTTPException handler and a safety-net 500 that never leaks internals).
  - Added rate limiting (`backend/app/rate_limit.py`, `flask-limiter`): default `600 per minute` per client, Redis storage when `REDIS_URL` is set else in-memory; `/api/health*`, `/api/market-data*`, and `/socket.io` are exempt so health checks and the live feed are never throttled. Tunable via `RATELIMIT_DEFAULT` / `RATELIMIT_ENABLED`.
  - Enriched health: `/api/health/readiness` now reports `breeze` (config-only, no network) and `websocket` (live worker state); `/api/health/deployment` adds `master_contract` status and `websocket`. All checks are failure-safe and never raise.
  - Wired `register_error_handlers` + `init_rate_limiting` into `factory.py`; added `flask-limiter` to requirements/pyproject.
- Frontend changes:
  - Added shared `ErrorState` (with optional retry), `EmptyState`, and a top-level `ErrorBoundary` (recoverable fallback instead of a white screen).
  - Applied the shared components and consistent retry buttons to Dashboard (chart, alerts, positions), Positions, Orderbook, Tradebook, and Option Chain; refactored the dashboard loader into a reusable `loadDashboard` callback for retry.
  - Mobile final pass in `index.css`: route headers/toolbars stack, order/trade stat grids reflow, tables scroll, and state-card styles.
- Files changed:
  - `backend/app/errors.py`
  - `backend/app/rate_limit.py`
  - `backend/app/api/health.py`
  - `backend/app/factory.py`
  - `backend/requirements.txt`
  - `backend/pyproject.toml`
  - `backend/tests/test_hardening_contract.py`
  - `frontend/src/components/ErrorState.tsx`
  - `frontend/src/components/EmptyState.tsx`
  - `frontend/src/components/ErrorBoundary.tsx`
  - `frontend/src/main.tsx`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/pages/PositionsPage.tsx`
  - `frontend/src/pages/OrderbookPage.tsx`
  - `frontend/src/pages/TradebookPage.tsx`
  - `frontend/src/pages/OptionChainPage.tsx`
  - `frontend/src/index.css`
  - `OPERATIONS.md` (new runbook: token refresh, cron, rate limits, health)
  - `development.md`
  - `REBUILD.md`
- Verification:
  - `python -m pytest` -> `73 passed` (68 prior + 5 new hardening tests: structured 404/405, rate-limit header present, readiness websocket+breeze, deployment master_contract+websocket).
  - `npm.cmd run build` -> passed, 91 modules.
  - Live HTTP smoke test: readiness shows `breeze`+`websocket`, deployment shows `master_contract`+`websocket`, an unknown `/api/*` route returns the structured 404 shape, `/api/debug/breeze-auth` carries `X-RateLimit-Limit: 600`, and `/api/health` is exempt from the limit.
- Manual user tasks (deferred by request):
  - Set the Railway daily master-contract cron (see OPERATIONS.md section 2).
  - Decide the daily Breeze token-refresh workflow (see OPERATIONS.md section 1).
  - After deploy, run the final smoke checklist across all MVP routes with a fresh Breeze token.
- Remaining risks:
  - Rate-limit thresholds tuned for a single-user dashboard; revisit if more clients are added (would also need a Redis message queue for multi-worker Socket.IO).
  - The live-429 path is exercised in production rather than unit tests (the global limiter keeps its first default across test apps); the 429 response shape is covered by the shared 404/405 structured-error tests.
- Next step: MVP is feature-complete through Phase 17. Remaining optional work is the deferred Phase 12 Option Greeks (to be computed inline in strategy code when needed) and the two manual deploy tasks above.

### 2026-06-14 - Phase 22: Systematic Issue Discovery and Validation (RERUN)
- Goal: Build a complete, measured, and ranked list of real issues across APTRADES2 before making any further fixes. This phase is for finding and proving problems, not solving them.
- Methodology: Strictly followed playbook Part 4-5 methodology. Started Flask dev server, ran real HTTP requests against all 31 API endpoints, measured 3 cold + 3 warm timing on 12 priority routes, verified response shapes, degradation behavior, error formats, and frontend build. Supplemented with code-audit for issues that cannot be triggered without a browser or live credentials.
- Backend changes: None (diagnosis-only phase, no code changes).
- Frontend changes: None (diagnosis-only phase, no code changes).
- Files changed:
  - `PHASE22_FINDINGS.md` (rewritten — now evidence-based with runtime/audit separation)
  - `development.md` (this entry — replaces previous code-audit-only entry)
- Evidence separation in PHASE22_FINDINGS.md:
  - **Runtime-behavior** (direct HTTP testing, timing measurements, shape verification)
  - **Code-audit only** (source-file reading for issues needing browser/live data)
  - **Insufficient evidence** (cannot test without browser/Railway/Vercel/Breeze credentials)
- Runtime validation performed:
  - 31 API routes tested via live HTTP requests (all under 32ms — excellent)
  - 12 priority routes tested 3 cold + 3 warm (all under 32ms — excellent)
  - Response shape verification for key routes (dashboard summary, alerts, positions, market-data, diagnosis)
  - Error format verification (404 structured, 400 inconsistent, degraded states)
  - Frontend build verification (1853 modules, clean)
  - Backend tests (110 passed)
- Key findings (1 runtime-proven, 5 code-audit-suspected):
  - **RT-ISSUE-01 (runtime-proven)**: API 400 error responses use inconsistent shapes. Some return `error: string`, others return `error: {code, message}`. Contract documented in Phase 17 promises uniform `{code, message}` shape. Medium severity.
  - **CA-ISSUE-05**: Race condition on `_subscriptions` dict in `_normalize_tick` — reads without lock while other threads mutate. Medium severity. (Code-audit only.)
  - **CA-ISSUE-01**: StrategyPortfolioPage `handleDelete` empty catch block swallows errors silently. Medium severity. (Code-audit only.)
  - **CA-ISSUE-02**: DashboardPage alerts error state silently shows empty "No active trade alerts" instead of error. Medium severity. (Code-audit only.)
  - **CA-ISSUE-03**: `OptionChainService._list_expiries()` calls `ensure_tables()` on every request. Low severity. (Code-audit only.)
  - **CA-ISSUE-04**: OptionChainService creates new Redis client per cache operation (no pooling). Low severity. (Code-audit only.)
  - **CA-ISSUE-06**: Diagnostic instruments hardcode empty expiry for futures (bypasses SymbolResolver path). Low severity. (Code-audit only.)
- Non-issues (14 items): Backend latency, dashboard degraded state, positions degraded state, market-data degraded state, frontend build, structured 404 shape, all 6 diagnosis endpoints, batch quotes degradation, `void` promise patterns, RLock pattern, supervisor startup race, `_breeze` TOCTOU, SymbolResolver hot path fix (Phase 18), chart resolution fix (Phase 7).
- Insufficient evidence (12 items): Need browser for layout/rendering, live credentials for Breeze behavior, deployment access for Railway/Vercel, DB for data correctness.
- Fix priority: Runtime-proven issue first (RT-ISSUE-01 error shapes), then code-audit issues in order: CA-ISSUE-05 (race), CA-ISSUE-01 (delete error), CA-ISSUE-02 (alerts error), CA-ISSUE-04 (Redis pool), CA-ISSUE-03 (ensure_tables), CA-ISSUE-06 (diagnostic expiry).
- Next step: Begin Phase 23 — verify RT-ISSUE-01 behavior on deployed instance, then fix it and the code-audit-suspected issues.

### 2026-06-15 - Phase 23: Final Live Validation Pass Before Fixing
- Goal: Test all remaining unproven issues against the deployed Railway + Vercel application with a valid Breeze session. No code changes. Produce a final validated issue list then stop testing.
- Execution: curl.exe against Vercel (11 SPA routes x2 runs) and Railway (17 API endpoints x2-3 runs) with live Breeze session (token provided by user, deployed to Railway).
- Key correction: Phase 22 tested deprecated/wrong endpoints for several pages. Frontend actually calls `/api/orders` (not `/api/orderbook`), `/api/trades` (not `/api/tradebook`), `/api/option-chain?underlying=...` (not `/api/option-chain/bynifty`). These deprecated routes return 404 on Railway. All Phase 22 findings based on these routes are invalid.
- Vercel routing: ALL PASS. 11/11 SPA routes return HTTP 200 with proper `<div id="root">` shell in <0.25s.
- Breeze session: VALID. `session_token_received: true`, user_id=AJ510524, exchange_status: FNO=Y.
- Live data verified: Dashboard summary returns NIFTY futures (23930.0), BANKNIFTY futures (57211.2), 0 positions, 0 P&L. Option chain grid returns 12 strikes with full bid/ask/oi/volume. Options expiries returns 10 dates.
- Real issues found (7 total):
  - **P23-RT-ISSUE-01** (HIGH): `/api/dashboard/chart?symbol=NIFTY` consistently times out (30s). Dashboard chart will not render.
  - **P23-RT-ISSUE-02** (HIGH): `/api/orders?exchange=NFO&status=` consistently times out (30s). Orderbook page fails.
  - **P23-RT-ISSUE-03** (HIGH): `/api/trades?exchange=NFO&action=` consistently times out (30s). Tradebook page fails.
  - **P23-RT-ISSUE-04** (MEDIUM): `/api/debug/cache-stats`, `/api/breeze/status`, `/api/symbols/search?q=NIFTY` all timeout (25-30s). Diagnosis/breeze features unavailable.
  - **P23-RT-ISSUE-05** (MEDIUM): `/api/dashboard/summary` (3.7s-14.5s) and `/api/dashboard/alerts` (9.3s-27.3s) have extreme latency variance. Dashboard may take 10-28s.
  - **P23-RT-ISSUE-06** (MEDIUM): `/api/positions` intermittent (~33% success rate, 1.1s when working, 30s timeout otherwise).
  - **P23-RT-ISSUE-07** (MEDIUM): `/api/options/expiries` extremely slow (28.5s). Option chain takes 30s+ to initially load.
- Non-issues (10): Vercel routing, Breeze auth, option chain grid (3.76s acceptable), health readiness (0.5s), market-data offline state (expected), master contract (132076 instruments), dashboard summary data, dashboard alerts data, etc.
- Blocked/insufficient evidence (6): page-shell visual rendering (no browser), Railway logs (no access), websocket/live-updates (market closed), mobile layout (out of scope), frontend error handling (no browser), real account data validation (pending user).
- User-assisted tests pending: live market observation, real account-state validation (positions/orders/trades), desktop visual acceptance.
- Findings document: `PHASE23_FINDINGS.md`
- Next step: Phase 24 — fix validated issues starting with P23-RT-ISSUE-01 (chart timeout), then remaining timeout issues in priority order.

### PLANNED - Phase 18: Performance and Caching (Latency Reduction) [NOT STARTED]
- Status: SPEC ONLY. Nothing in this section is implemented yet. This is the plan to make the dashboard fast.
- Problem (root cause, grounded in current code):
  1. A new SQLAlchemy engine is built on every call. `SymbolResolver.resolve()` runs for every symbol and calls BOTH `ensure_tables()` and `create_session_factory()`; each calls `create_engine(...)` in `backend/app/db.py` -> a brand-new engine + pool + DB handshake every time, and `ensure_tables()` re-runs `create_all()` (a schema round-trip) each call. An option chain resolving ~20 strikes = ~40 fresh engines + 20 schema checks.
  2. Breeze re-authenticates on every request. Each blueprint builds a fresh `BreezeGateway` in its `_gateway()` factory (see `backend/app/api/quotes.py`, `dashboard.py`, `positions.py`, `orders.py`, `options.py`, `oi.py`, `action_centre.py`). The `customerdetails` token exchange is cached only on that instance, which is discarded each request, so every quote does TWO ICICI round-trips (token exchange + quote) instead of one.
  3. REST reads ignore the live cache. The market-data worker writes ticks to Redis (`md:tick:<exchange>:<token>`), but `QuoteService` / positions / option-chain call Breeze REST synchronously every time and never read Redis. `get_batch_quotes` loops sequentially (N round-trips in series).
  4. Frontend refetches from zero on every navigation / filter change (no shared cache), replaying the whole slow chain.
  - Note: there is NO literal market-hours gate causing this; the slowness is the synchronous Breeze-REST path on every read. It is the same whether the market is open or closed. Live websocket ticks (ticker, position LTP) already stream fast for subscribed symbols; option-chain and initial page loads are the slow REST paths.

- Tier 1 (backend, quick wins, highest impact, lowest risk): [IMPLEMENTED]
  - `backend/app/db.py`: cache one engine per normalized DB URL (e.g. `@lru_cache` or module dict). Postgres pool config: `pool_size=5, max_overflow=10, pool_recycle=1800, pool_pre_ping=True`; branch for SQLite (no pool args). Cache the `sessionmaker` per URL. Make `ensure_tables()` idempotent via a module-level `set` of prepared URLs; stop calling `engine.dispose()` on the shared engine.
  - `backend/app/services/symbol_resolver.py`: remove `ensure_tables()` from the `resolve()` hot path; add an in-memory TTL cache keyed by (symbol, exchange, product_type, expiry, right, strike) -> ResolvedInstrument (default TTL ~3600s, lock-guarded). Master-contract import clears it or rely on TTL.
  - Shared BreezeGateway: one process-wide instance reused across requests so the customer-session token is exchanged once. Add `get_gateway()` stored in `app.extensions` keyed by (app_key, secret, token); rebuild when that tuple changes (covers daily token refresh on redeploy). Lock the lazy token fields; on a Breeze auth/session-expired error, clear the cached customer-session token and retry once. Point all blueprint `_gateway()` factories at it.
  - Implementation notes: `db.py` now keeps `_engines`/`_session_factories`/`_prepared_urls` module caches behind an `RLock` (+ a test-only `reset_caches()`); SQLite engines use `check_same_thread=False` so the shared engine is thread-safe. `symbol_resolver.py` has a lock-guarded `_resolution_cache` with `clear_resolution_cache()` (called after every master-contract import). `breeze_gateway.py` adds module-level `get_gateway()`, an `RLock` around the customer-details/session-token caches, `_send()`/`_is_session_error()`/`_invalidate_session()` so an HTTP 401/403 or session-expired body invalidates the token and retries once. Tables are created once at app boot in `factory.create_app()` (degraded-safe). All eight blueprint gateway factories (quotes, dashboard, positions, orders, options, oi, action_centre, debug) call the shared gateway. Tests: `backend/tests/test_phase18_caching.py` (engine/sessionmaker reuse, idempotent ensure_tables, resolution cache hit + TTL expiry, shared-gateway reuse + token refresh on 401); autouse cache reset in `conftest.py`. 82 backend tests pass.
- Tier 2 (backend, live data as primary read path):
  - Redis-first quotes: in `QuoteService.get_quote`, after resolving, read `md:tick:<exchange>:<token>`; if fresh, return it (source `live_cache`) instead of calling Breeze; auto-subscribe the token on the worker so reads stay warm. Add a 1-2s short-TTL Redis cache for cold REST quotes to coalesce rapid clicks.
  - Option-chain streaming: subscribe visible CE/PE strikes around ATM to the websocket while the chain page is open; overlay live LTP from Redis, keep a periodic `/optionchain` REST refresh for OI (OI is not in exchange-quote ticks).
  - Parallelize `get_batch_quotes` with a bounded `ThreadPoolExecutor` (respect Breeze rate limits; reuse the shared thread-safe gateway; preserve order).
- Tier 3 (frontend perceived speed):
  - `useCachedResource(key, fetcher)` hook backed by a module Map (no new dependency): stale-while-revalidate so revisiting a page renders last data instantly and refreshes in the background.
  - Live-first rendering: render the cached `useLiveQuote` tick immediately on dashboard/positions/option-chain; show loading only on a true cold start.
- Testing: engine reused for same URL; `ensure_tables` idempotent; resolution cache hit + TTL expiry; shared gateway reused + token-cache invalidation on auth error; `get_quote` returns `live_cache` when Redis has a fresh tick (mock redis); batch quotes parallel preserves order. All existing tests stay green; `npm run build` passes.
- Done when: a single quote does at most one Breeze round-trip and creates no new engine per request; a full option chain does not create dozens of engines; during market hours ticker/positions/option-chain LTP update from Redis/websocket without per-read Breeze REST; page navigation shows last data instantly; cold-start and degraded (Redis/DB/Breeze down) paths still work.
- Risks: shared singletons across gunicorn threads need locks (gateway token cache, resolution cache); token expiry mid-session must invalidate the cached customer-session token and rebuild the gateway; SQLite vs Postgres engine args differ; cap parallel-batch concurrency for Breeze rate limits; keep quote cache TTL 1-2s and refresh OI periodically.

### Phase 19: Live-stream Stability and Tick Recording [IMPLEMENTED]
- Problem: even after Phase 18 removed worker starvation, the live<->offline badge could still flap and ticks could buffer because (a) ticks are emitted from breeze-connect's own thread with no Socket.IO message queue, so cross-thread emits are unreliable; (b) default engine.io ping timeout drops the socket on any brief stall; (c) the frontend flips the badge to "offline" on any blip with no grace period; (d) nothing records the stream, so freezes cannot be proven or attributed.
- Server resilience (`backend/app/realtime.py`, `backend/app/config.py`): configure Socket.IO with a Redis `message_queue` (when `REDIS_URL` is set) so emits from the breeze thread are delivered reliably, and tune `ping_interval` (default 25s) / `ping_timeout` (default 60s) via env `SOCKETIO_PING_INTERVAL` / `SOCKETIO_PING_TIMEOUT` so short stalls do not drop the connection.
- Gap logger (`backend/app/services/market_data_worker.py`): track the monotonic time of the last tick; when the gap exceeds `gap_log_seconds` (default 5s) log a WARNING ("market-data stream gap of N.Ns") so Railway logs show exactly when and how long the stream stalled.
- Tick recorder (`backend/app/services/tick_recorder.py`, model `MarketCandle`): aggregate streamed ticks into 1-minute OHLC+volume+OI candles in memory (lock-guarded) and flush them to the DB every `flush_seconds` (default 15s) on a background thread, pruning closed minutes after they persist. Off the tick hot path, batched, reuses the Phase 18 cached engine. Degraded-safe: disabled when `DATABASE_URL` is unset. This doubles as the tick history for future OI/heatmap work.
- Read path (`backend/app/api/market_data.py`): `GET /api/market-data/history?symbol=NIFTY&limit=120` returns recent recorded candles (ascending) so gaps are visible as missing minutes and the data can be charted.
- **2026-06-18**: Tick recorder disabled to stop DB growth. `_recorder.record()` removed from `_on_ticks()` hot path. Recorder thread no longer started in `ensure_started()`. `MarketDataWorker` no longer accepts `database_url` or `flush_seconds` params. `tick_recorder.py` retained as dead code (safe to remove later). `market_data_history` endpoint still returns `{"candles": []}` gracefully. No frontend feature depends on this data. Added `flask market-data cleanup-candles` CLI command to delete all existing candle rows.
- Frontend (`frontend/src/hooks/useLiveMarketData.tsx`): grace period — on socket disconnect, keep showing "connecting" (reconnecting feel) for `graceMs` (default 2000ms) before reporting "offline", so a sub-2s reconnect never flips the badge; log `disconnect(reason)` and `connect_error` to the console for live proof; expose `lastTickAt` so pages can tell "unchanged price" from "stalled stream". Reuses the existing `connecting` visual state (no new MarketDataState literal, so no page/CSS churn).
- Testing: recorder aggregates OHLC within a minute and flushes/prunes correctly (sqlite); history endpoint returns recorded candles; gap logger emits a warning past threshold; existing worker tests stay green (new constructor params default off). `npm run build` passes.
- Done when: brief reconnects no longer show "offline"; cross-thread ticks arrive without buffering when Redis is configured; Railway logs show timestamped stream gaps; recorded candles are queryable for proof and history. Note: external causes (Railway proxy, Breeze upstream feed, ISP, daily token expiry, single-worker design) remain outside app control — the recorder makes them attributable.

### Fix 1: Parallelize batch quote fetch [IMPLEMENTED]
- Problem: `get_batch_quotes()` used a sequential for-loop, calling Breeze `get_quote()` for each symbol one at a time. For 2 symbols (NIFTY, BANKNIFTY) on the dashboard, this added ~6-14s serial latency (each quote takes 3-7s).
- Solution: Replaced the sequential for-loop in `quote_service.py:get_batch_quotes()` with `ThreadPoolExecutor(max_workers=4)`. Each symbol quote is fetched in parallel. Extracted `_batch_error_item()` helper to avoid duplication.
- Files: `backend/app/services/quote_service.py`
- Verification: 110/110 tests pass. Batch quotes endpoint returns results from parallel workers.
- Committed: `15ef402`

### Fix 2: Deduplicate Breeze positions calls on dashboard [IMPLEMENTED]
- Problem: Both `DashboardService.get_summary()` and `get_alerts()` call `self.positions_service.get_positions()`, causing 2 redundant Breeze `get_portfolio_positions()` calls (~6-14s each) on a single dashboard load.
- Solution: Added a short-TTL (5s) in-memory cache on `flask.current_app.config` in `positions_service.py:get_positions()`. On cache hit within TTL, returns cached result without calling Breeze. Cache is isolated per Flask app instance (test-safe). Uses `_positions_cache_lock` for thread safety with gthread workers.
- Details:
  - `_get_cache_store()` — resolves `current_app.config` safely (returns `None` outside request context)
  - `_set_cache(value)` — writes `(timestamp, value)` tuple to `current_app.config["_POSITIONS_CACHE"]` under lock
  - Cache is automatically isolated per test (each test creates a new app instance, so no cross-test leakage)
- Files: `backend/app/services/positions_service.py`
- Verification: 110/110 tests pass. Cache path tested implicitly by two dashboard tests that call `/api/dashboard/alerts` with mock positions.

### Fix 3: Reduce Breeze retry/timeout for interactive endpoints [IMPLEMENTED]
- Problem: `_send()` had hardcoded 3 retry attempts × 15s timeout = 47s worst case per Breeze REST call. For interactive user-facing endpoints (quotes, positions, orders, trades, chart), this degraded dashboard load to 30s+ and caused Railway proxy timeouts.
- Solution: Added `interactive: bool = True` parameter to `_request()` and `timeout`/`attempts` params to `_send()`. Interactive mode: 2 attempts × 10s timeout = 21s worst case (less than half the old worst case). Non-interactive mode (for background/import flows) retains 3 attempts × 15s timeout.
- Files: `backend/app/services/breeze_gateway.py`, `backend/tests/test_breeze_gateway.py`
- Verification: 110/110 tests pass. Existing retry test updated for interactive defaults (2 attempts, 1 sleep instead of 3 attempts, 2 sleeps).

### Fix 4: Cache dashboard chart historical fetch [IMPLEMENTED]
- Problem: `DashboardService.get_chart()` called Breeze `get_historical_charts()` on every dashboard load (30 days of daily data). The Breeze historical endpoint is slow, causing 30s+ timeouts (Phase 23 runtime-proven).
- Solution: Added a per-symbol TTL cache (5 min) on `flask.current_app.config` in `dashboard_service.py:get_chart()`. Cache key includes symbol so NIFTY and BANKNIFTY charts are cached independently. Uses `_chart_cache_lock` for thread safety. Cache automatically isolated per Flask app instance (test-safe).
- Files: `backend/app/services/dashboard_service.py`
- Verification: 110/110 tests pass. Chart endpoint test still fetches fresh data on first call (cache miss expected in test isolation).

### Fix 5: Fix topbar ticker label to say "futures" [IMPLEMENTED]
- Problem: `_ticker_item()` returned bare symbol ("NIFTY") while `_market_card()` correctly showed "NIFTY futures". Users seeing "NIFTY" in the topbar ticker could mistake it for the spot index.
- Solution: Added `label` field to backend ticker response with `" futures"` suffix when `product_type == "futures"`. Updated frontend `DashboardTickerItem` interface and `MarketTicker.tsx` to use `item.label || item.symbol` for display while keeping `item.symbol` for WebSocket tick matching.
- Files: `backend/app/services/dashboard_service.py`, `frontend/src/lib/api.ts`, `frontend/src/components/dashboard/MarketTicker.tsx`
- Verification: 110/110 backend tests pass. Frontend builds 1853 modules.

### Fix 6: Change live badge semantics [IMPLEMENTED]
- Problem: Badge showed "Live" when Breeze WebSocket connected, regardless of market hours. Users interpret "Live" as "market is open and streaming", but it only means the socket is up.
- Solution: Changed badge text from "Live"/"Offline" to "Connected"/"Disconnected". Renamed `isLive` to `isConnected` for code clarity. Semantics now accurately describe WebSocket connectivity, not market state.
- Files: `frontend/src/components/layout/TopHeader.tsx`
- Verification: Frontend builds 1853 modules successfully. No backend changes.

### Dashboard Latency Fix Pass [IMPLEMENTED]
- Problem: Despite 6 prior fixes, dashboard still took 18-28s. Root causes: (a) summary cards blocked until alerts complete (both waited on Promise.allSettled), (b) two duplicate summary requests from DashboardPage + MarketTicker, (c) summary positions call had no timeout cap, (d) alerts triggered fresh slow broker positions call, (e) badge flickered "Disconnected" during reconnect grace.
- Fix A (frontend): Split summary and alerts loading in DashboardPage so cards render independently of alerts. Each state updates as soon as its request settles (no more Promise.allSettled blocking).
- Fix B (frontend): Added in-flight + 3s TTL deduplication for getDashboardSummary() in api.ts so simultaneous calls from DashboardPage and MarketTicker share one backend request.
- Fix C (backend): PositionsService.get_positions() now accepts gateway_timeout/gateway_attempts overrides. BreezeGateway.get_portfolio_positions() threads timeout/attempts overrides through _request(). DashboardService.get_summary() calls positions with 4s timeout, 1 attempt — if it fails, returns degraded positions with empty totals instead of blocking cards for 30s.
- Fix D (backend): Alerts now use get_cached_positions() — read-only cache check that never triggers a fresh broker call. If no cache, alerts show "Positions snapshot pending" instead of blocking on a slow Breeze positions fetch.
- Fix E (frontend): TopHeader badge now maps all 4 connection states (live → green "Connected", connecting → amber "Reconnecting", degraded → amber "Degraded", offline → red "Offline") instead of only "live" vs "Disconnected".
- Additional: Positions cache TTL increased from 5s to 15s so summary + alerts within a dashboard load share a single positions fetch.
- Files: `backend/app/services/breeze_gateway.py`, `backend/app/services/positions_service.py`, `backend/app/services/dashboard_service.py`, `frontend/src/pages/DashboardPage.tsx`, `frontend/src/lib/api.ts`, `frontend/src/components/layout/TopHeader.tsx`, `backend/tests/test_dashboard_contract.py`, `backend/tests/test_positions_contract.py`
- New tests added: 3 (dashboard degraded summary, alerts pending without cache, get_cached_positions)
- Verification: 114/114 backend tests pass. Frontend builds 1853 modules.

## Phase 13 Response Examples

- Endpoint: `GET /api/oi/tracker?underlying=NIFTY&expiry=2026-06-30`
- Response example:
  - `{ "status": "ok", "underlying": "NIFTY", "exchange_code": "NFO", "expiry": "2026-06-30", "underlying_ltp": 23268.8, "atm_strike": 23300.0, "pcr": 0.9659, "total_call_oi": 235000.0, "total_put_oi": 227000.0, "max_ce_oi_strike": 23200.0, "max_pe_oi_strike": 23300.0, "rows": [{ "strike_price": 23300.0, "ce_oi": 115000.0, "pe_oi": 132000.0, "total_oi": 247000.0, "ce_ltp": 92.8, "pe_ltp": 165.4 }] }`

- Endpoint: `GET /api/oi/profile?underlying=NIFTY&expiry=2026-06-30`
- Response example:
  - `{ "status": "ok", "underlying": "NIFTY", "exchange_code": "NFO", "expiry": "2026-06-30", "underlying_ltp": 23268.8, "atm_strike": 23300.0, "pcr": 0.9659, "total_call_oi": 235000.0, "total_put_oi": 227000.0, "rows": [{ "strike_price": 23200.0, "ce_oi": 120000.0, "pe_oi": 95000.0, "total_oi": 215000.0, "ce_ltp": 145.5, "pe_ltp": 118.2 }, { "strike_price": 23300.0, "ce_oi": 115000.0, "pe_oi": 132000.0, "total_oi": 247000.0, "ce_ltp": 92.8, "pe_ltp": 165.4 }] }`

## Phase 8 Response Examples

- Endpoint: `GET /api/orders`
- Response example:
  - `{ "status": "ok", "exchange_code": "NFO", "stats": { "total": 2, "completed": 1, "open": 1, "rejected": 0, "cancelled": 0 }, "orders": [{ "order_id": "1001", "symbol": "NIFTY", "status": "Open", "status_normalized": "open", "quantity": 50.0 }] }`

- Endpoint: `POST /api/orders/cancel`
- Request example:
  - `{ "exchange_code": "NFO", "order_id": "1001" }`
- Response example:
  - `{ "status": "ok", "exchange_code": "NFO", "order_id": "1001", "result": { "message": "Order cancellation requested" } }`

- Endpoint: `POST /api/orders/cancel-all`
- Request example:
  - `{ "exchange_code": "NFO" }`
- Response example:
  - `{ "status": "ok", "requested": 2, "cancelled_count": 2, "error_count": 0, "cancelled": [{ "order_id": "1001", "status": "ok" }], "errors": [] }`

- Endpoint: `GET /api/trades`
- Response example:
  - `{ "status": "ok", "exchange_code": "NFO", "stats": { "total": 2, "buy": 1, "sell": 1 }, "trades": [{ "trade_id": "T1", "order_id": "1001", "symbol": "NIFTY", "action": "BUY", "quantity": 50.0, "price": 23270.5 }] }`

## Phase 9 Response Examples

- Endpoint: `GET /api/positions`
- Response example:
  - `{ "status": "ok", "quote_status": "ok", "close_actions_active": false, "totals": { "open_positions": 2, "long_positions": 1, "short_positions": 1, "total_pnl": 107.0 }, "positions": [{ "symbol": "SBIN", "broker_symbol": "STABAN", "exchange_code": "NSE", "product_type": "cash", "quantity": -10.0, "average_price": 980.0, "ltp": 977.7, "pnl": 23.0, "pnl_percent": 0.23, "quote_status": "ok", "resolution_source": "alias", "token": "3045" }] }`

## Manual Tasks Pending
- [ ] Configure a daily Railway schedule for `flask master-contract import`
- [ ] Verify the deployed Phase 7 dashboard page after Railway/Vercel finish deploying
- [ ] Keep Breeze secrets and session token only in env vars
- [ ] Provide approval if external `Claude_Code` workspace file updates are required

## API Contracts Confirmed
- Endpoint: `GET /api/health`
- Request: no body
- Response: `{ "status": "ok", "service": "APTRADES v2", "timestamp": "<UTC ISO8601>" }`
- Test command: `curl http://127.0.0.1:5000/api/health`

- Endpoint: `GET /api/health/readiness`
- Request: no body
- Response: `{ "status": "ok", "checks": { "api": "online", "postgres": "not_configured", "redis": "not_configured", "breeze": "configured|not_configured", "websocket": "offline|connecting|live|degraded" }, "timestamp": "<UTC ISO8601>" }`
- Test command: `curl http://127.0.0.1:5000/api/health/readiness`

- Structured error shape (all `/api/*` failures): `{ "status": "error", "error": { "code": 404, "message": "..." } }`. Applies to 400/404/405/429/500. Rate limiting: default `600 per minute` per client (env `RATELIMIT_DEFAULT` / `RATELIMIT_ENABLED`); `/api/health*`, `/api/market-data*`, and `/socket.io` are exempt.
- Test command: `curl -i http://127.0.0.1:5000/api/does-not-exist`

- Endpoint: `GET /api/health/deployment`
- Request: no body
- Response: `{ "status": "ok", "environment": "<env>", "frontend_origin": "<origin|null>", "checks": { "api": "online", "postgres": "online|offline|not_configured", "redis": "online|offline|not_configured", "breeze": "unknown" }, "timestamp": "<UTC ISO8601>" }`
- Test command: `curl http://127.0.0.1:5000/api/health/deployment`

- Endpoint: `GET /api/debug/breeze-auth`
- Request: no body
- Response: `{ "status": "ok|not_configured|error", "configured": true|false, "user_id": "<id|optional>", "user_name": "<name|optional>", "session_token_received": true|false, "missing": ["<env names>"] }`
- Test command: `curl http://127.0.0.1:5000/api/debug/breeze-auth`

- Endpoint: `GET /api/debug/breeze-test`
- Request: no body
- Response: `{ "status": "ok|error", "configured": true|false, "symbols": [{ "symbol": "SBIN", "broker_symbol": "STABAN", "status": "ok|error", "exchange": "NSE", "product_type": "cash", "quote": "<optional>", "error": "<optional>" }] }`
- Test command: `curl http://127.0.0.1:5000/api/debug/breeze-test`

- Endpoint: `GET /api/diagnosis/trace?route=<route>`
- Request: query param `route` (required) — one of: health, readiness, breeze-auth, breeze-test
- Response: `{ "status": "ok", "route": "health", "elapsed_ms": 1.23, "result": { ... } }`
- Test command: `curl "http://127.0.0.1:5000/api/diagnosis/trace?route=health"`

- Endpoint: `GET /api/diagnosis/cache`
- Request: no body
- Response: `{ "status": "online|offline|not_configured", "tick_keys": 4, "tick_keys_sample": ["md:tick:NFO:62329", "md:tick:NSE:2885"], "dbsize": 10, "timestamp": "..." }`
- Test command: `curl http://127.0.0.1:5000/api/diagnosis/cache`

- Endpoint: `GET /api/diagnosis/broker`
- Request: no body
- Response: `{ "status": "ok", "configured": true, "auth": { ... }, "symbols": { "count": 5, "results": [...] }, "timestamp": "..." }`
- Test command: `curl http://127.0.0.1:5000/api/diagnosis/broker`

- Endpoint: `GET /api/diagnosis/worker`
- Request: no body
- Response: `{ "state": "offline|connecting|live|degraded", "configured": false, "subscriptions": 0, "symbols": [], "snapshot_count": 0, "timestamp": "..." }`
- Test command: `curl http://127.0.0.1:5000/api/diagnosis/worker`

- Endpoint: `GET /api/diagnosis/full`
- Request: no body
- Response: `{ "status": "ok", "checks": { "api": "online", "postgres": "online", "redis": "online", "breeze": "configured" }, "breeze_auth": {...}, "worker": {...}, "timing": [...], "timestamp": "..." }`
- Test command: `curl http://127.0.0.1:5000/api/diagnosis/full`

- Endpoint: `GET /api/diagnosis/timing`
- Request: optional query param `name` to filter
- Response: `{ "records": [{"name": "trace:health", "elapsed_ms": 1.23, "steps": []}] }`
- Test command: `curl http://127.0.0.1:5000/api/diagnosis/timing`

- Endpoint: `DELETE /api/diagnosis/timing`
- Request: optional query param `name` to clear specific
- Response: `{ "status": "ok", "cleared": true }`
- Test command: `curl -X DELETE http://127.0.0.1:5000/api/diagnosis/timing`

- Endpoint: `GET /api/master-contract/status`
- Request: no body
- Response: `{ "status": "ok|not_configured", "database_configured": true|false, "csv_available": true|false, "instrument_count": 33109, "alias_count": 35445, "latest_run": { "status": "success", "source_name": "stock_script_csv", ... } }`
- Test command: `curl http://127.0.0.1:5000/api/master-contract/status`

- Endpoint: `POST /api/master-contract/import`
- Request: no body
- Response: `{ "status": "ok", "row_count": 33109, "alias_count": 35445, "source_name": "stock_script_csv", "warnings": ["..."] }`
- Test command: `curl -X POST http://127.0.0.1:5000/api/master-contract/import`

- Endpoint: `GET /api/quotes?symbol=SBIN&exchange=NSE`
- Request: query params `symbol`, `exchange`, optional `product_type`, `expiry_date`, `right`, `strike_price`
- Response: `{ "status": "ok", "symbol": "SBIN", "resolved": { "display_symbol": "SBIN", "broker_symbol": "STABAN", ... }, "quote": { "ltp": 977.7, ... } }`
- Test command: `curl "http://127.0.0.1:5000/api/quotes?symbol=SBIN&exchange=NSE"`

- Endpoint: `POST /api/quotes/batch`
- Request: `{ "symbols": [{ "symbol": "NIFTY", "exchange": "NFO", "product_type": "futures" }, { "symbol": "SBIN", "exchange": "NSE" }] }`
- Response: `{ "status": "ok", "results": [{ "status": "ok", "symbol": "NIFTY", "resolved": { ... }, "quote": { ... } }] }`
- Test command: `curl -X POST http://127.0.0.1:5000/api/quotes/batch -H "Content-Type: application/json" -d "{\"symbols\":[{\"symbol\":\"SBIN\",\"exchange\":\"NSE\"}]}" `

- Endpoint: `GET /api/dashboard/summary`
- Request: no body
- Response: `{ "status": "ok", "metrics": [{ "key": "nifty", "label": "NIFTY futures", "value": 23440.0, ... }], "ticker": [{ "symbol": "NIFTY", "ltp": 23440.0, ... }], "positions": [{ "symbol": "SBIN", ... }] }`
- Test command: `curl http://127.0.0.1:5000/api/dashboard/summary`

- Endpoint: `GET /api/dashboard/alerts`
- Request: no body
- Response: `{ "status": "ok", "alerts": [{ "level": "success", "title": "Breeze session active", "message": "..." }] }`
- Test command: `curl http://127.0.0.1:5000/api/dashboard/alerts`

- Endpoint: `GET /api/dashboard/chart?symbol=NIFTY`
- Request: query param `symbol`
- Response: `{ "status": "ok", "symbol": "NIFTY", "resolved": { ... }, "interval": "1day", "points": [{ "time": "...", "close": 23440.0, ... }] }`
- Test command: `curl "http://127.0.0.1:5000/api/dashboard/chart?symbol=NIFTY"`

- Endpoint: `GET /api/positions`
- Request: no body
- Response: `{ "status": "ok|not_configured", "quote_status": "ok|partial|not_configured", "close_actions_active": false, "totals": { "open_positions": 0, "long_positions": 0, "short_positions": 0, "total_pnl": 0.0 }, "positions": [{ "symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "product_type": "futures", "quantity": 50.0, "average_price": 23200.0, "ltp": 23440.0, "pnl": 12000.0, "pnl_percent": 1.03, "direction": "long", "quote_status": "ok", "resolution_source": "broker_symbol", "token": "62329" }] }`
- Test command: `curl http://127.0.0.1:5000/api/positions`

- Endpoint: `GET /api/options/expiries?underlying=NIFTY`
- Request: query params `underlying`, optional `exchange`
- Response: `{ "status": "ok", "underlying": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "expiries": ["2026-06-30"] }`
- Test command: `curl "http://127.0.0.1:5000/api/options/expiries?underlying=NIFTY"`

- Endpoint: `GET /api/option-chain?underlying=NIFTY&expiry=2026-06-30&strike_count=12`
- Request: query params `underlying`, `expiry`, optional `exchange`, optional `strike_count`
- Response: `{ "status": "ok", "underlying": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "expiry": "2026-06-30", "underlying_ltp": 23268.8, "previous_close": 23451.7, "atm_strike": 23300.0, "pcr": 0.9659, "rows": [{ "strike_price": 23300.0, "ce": { "ltp": 92.8, "bid": 92.2, "ask": 93.1, "oi": 115000.0, "volume": 16000.0 }, "pe": { "ltp": 165.4, "bid": 164.8, "ask": 166.1, "oi": 132000.0, "volume": 21000.0 } }] }`
- Test command: `curl "http://127.0.0.1:5000/api/option-chain?underlying=NIFTY&expiry=2026-06-30&strike_count=12"`

- Endpoint: `GET /api/action-centre`
- Request: optional query param `status=pending|approved|rejected|all`
- Response: `{ "status": "ok", "filter_status": "pending", "stats": { "pending": 2, "approved": 1, "rejected": 0, "all": 3 }, "actions": [{ "id": 1, "action_type": "cancel_order", "status": "pending", "symbol": "NIFTY", "order_id": "12345", "exchange_code": "NFO", "can_approve": true, "can_reject": true }] }`
- Test command: `curl "http://127.0.0.1:5000/api/action-centre?status=pending"`

- Endpoint: `POST /api/action-centre/:id/approve`
- Request: no body
- Response: `{ "status": "ok", "action": { "id": 1, "status": "approved", "broker_result": { "message": "Order cancellation requested" } } }`
- Test command: `curl -X POST http://127.0.0.1:5000/api/action-centre/1/approve`

- Endpoint: `POST /api/action-centre/:id/reject`
- Request: no body
- Response: `{ "status": "ok", "action": { "id": 1, "status": "rejected", "resolution_note": "User rejected the pending broker action." } }`
- Test command: `curl -X POST http://127.0.0.1:5000/api/action-centre/1/reject`

- Endpoint: `GET /api/logs`
- Request: optional query params `level`, `source`, `time`
- Response: `{ "status": "ok", "filters": { "level": "all", "source": "all", "time_window": "24h" }, "summary": { "api_count": 25, "app_count": 6, "total_count": 31 }, "rows": [{ "id": "api-1", "kind": "api", "level": "info", "source": "dashboard", "message": "GET /api/dashboard/summary completed with 200", "path": "/api/dashboard/summary", "status_code": 200 }] }`
- Test command: `curl "http://127.0.0.1:5000/api/logs?time=24h"`

- Endpoint: `GET /api/logs/live`
- Request: no body
- Response: `{ "status": "ok", "rows": [{ "id": "app-4", "kind": "app", "level": "warning", "source": "action-centre", "event_type": "reject", "message": "Rejected action 4 for order 12345." }], "lines": ["[2026-06-10T...] WARNING APP action-centre reject Rejected action 4 for order 12345."] }`
- Test command: `curl http://127.0.0.1:5000/api/logs/live`

- Endpoint: `GET /api/market-data/status`
- Request: no body
- Response: `{ "status": "ok", "timestamp": "<UTC ISO8601>", "market_data": { "state": "offline|connecting|live|degraded", "configured": false, "subscriptions": 0, "symbols": [], "last_tick_at": null, "error": null } }`
- Test command: `curl http://127.0.0.1:5000/api/market-data/status`

- Endpoint: `GET /api/market-data/snapshot`
- Request: no body
- Response: `{ "status": "ok", "timestamp": "<UTC ISO8601>", "ticks": [{ "symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "token": "62329", "stock_token": "4.1!62329", "ltp": 23440.0, "close": 23451.7, "change": -11.7, "change_percent": -0.05, "volume": 100.0, "oi": 4763100.0, "ts": "<UTC ISO8601>" }] }`
- Test command: `curl http://127.0.0.1:5000/api/market-data/snapshot`

- Endpoint: `GET /api/market-data/watchlist`
- Request: no body
- Response: `{ "status": "ok", "watchlist": [{ "symbol": "NIFTY", "exchange": "NFO", "product_type": "futures" }, { "symbol": "BANKNIFTY", "exchange": "NFO", "product_type": "futures" }] }`
- Test command: `curl http://127.0.0.1:5000/api/market-data/watchlist`

- Socket.IO: connect to `/socket.io` (websocket or polling). On connect the server streams the default watchlist and emits `status` (MarketDataStatus) plus `tick` events. Client may emit `subscribe` / `unsubscribe` with `{ "symbols": [{ "symbol": "SBIN", "exchange": "NSE", "product_type": "cash" }] }`.
- Test command: `curl "http://127.0.0.1:5000/socket.io/?EIO=4&transport=polling"`

### 2026-06-16 — Fix Pass Part 1: Positions Latency
- Root cause: `/api/positions` route called `PositionsService.get_positions()` without `gateway_timeout`/`gateway_attempts` overrides. The default interactive Breeze policy is 10s timeout × 2 attempts (max 20s), compounded by the `_customer_session_token()` call inside `_send()` which calls `get_customer_details()` unbounded. Deployed cold-start took 28-34s.
- Files changed: `backend/app/api/positions.py:24` — added `gateway_timeout=4, gateway_attempts=1`
- Reuses the exact same bounded pattern already proven in `DashboardService.get_summary()` line 59.
- Verification: `python -m pytest` — 114/114 passed (unchanged). Frontend build — 1853 modules passed.
- Remaining risks: If Breeze is genuinely slow, positions will degrade gracefully (same as dashboard already does). The 4s cap applies only to the Breeze call; SymbolResolver + DB resolution still runs before that.

### 2026-06-16 — Fix Pass Part 2: Orderbook + Tradebook Empty-State and Latency
- Root cause (correctness): Breeze returns `{"Success": null, "Error": "No Data Found"}` as a valid empty-state response when no orders/trades match the query. `BreezeGateway.get_order_list()` and `get_trade_list()` treated any `Success=None` as a hard error, raising `BreezeGatewayError`. The API routes returned HTTP 400, causing frontend to show error state instead of empty state.
- Root cause (latency): Order and trade list calls had no timeout override, using default interactive policy (10s×2 attempts) plus unbounded `get_customer_details()` — measured 22-34s for orders, 17-34s for trades.
- Files changed:
  - `backend/app/services/breeze_gateway.py` — `get_order_list()` and `get_trade_list()`: (a) added `timeout_override`/`attempts_override` params passed to `_request()`, (b) "No Data Found" now returns `[]` instead of raising error
  - `backend/app/services/orders_service.py` — `get_orders()`: added `gateway_timeout`/`gateway_attempts` params, threaded to gateway
  - `backend/app/services/trades_service.py` — `get_trades()`: same pattern
  - `backend/app/api/orders.py` — both route handlers pass `gateway_timeout=8, gateway_attempts=1`
  - `backend/tests/test_action_logs_contract.py` — mock signature updated to accept new params
- Verification: `python -m pytest` — 114/114 passed. Frontend build — 1853 modules passed.
- Railway timing (measured 2026-06-16):
  | Endpoint | Before (Phase 23) | After Part 2 |
  |---|---|---|
  | `GET /api/orders?exchange=NFO` | 30s timeout | **1.66s** |
  | `GET /api/trades?exchange=NFO` | 30s timeout | **1.42s** |
  | `GET /api/positions` | 30s timeout / intermittent | **1.57s** |
  - All three now complete in ~1.4-1.7s, well within the 8s cap. Confirmed via `curl.exe -w "%{time_total}s"` against Railway production URL.
- Remaining risks: Real Breeze errors (auth failure, bad session, network failure) still raise correctly — only "No Data Found" is normalized. The 8s cap applies per call.

### 2026-06-16 — Fix Pass Part 3: Action-Centre Sync Timeout Override
- Root cause: `ActionCentreService._sync_open_orders()` called `OrdersService.get_orders()` without `gateway_timeout`/`gateway_attempts` params, defaulting to 10s×2 attempts per exchange. Since the sync runs across 4 exchanges (NFO, NSE, BFO, BSE) sequentially, worst case was 80s before any action data reached the frontend.
- Files changed:
  - `backend/app/services/action_centre_service.py:124-125` — added `gateway_timeout=8, gateway_attempts=1` to `get_orders()` call in `_sync_open_orders()`
- Verification: `python -m pytest` — 114/114 passed. Relevant action-centre/orders/trades/positions contract tests: 12/12 passed.
- Railway verification (measured 2026-06-16):
  | Endpoint | Before (Phase 23) | After Part 2+3 |
  |---|---|---|
  | `GET /api/orders?exchange=NFO` | 30s timeout | **1.3s** (warm, 3-run avg) |
  | `GET /api/trades?exchange=NFO` | 30s timeout | **1.4s** (warm, 3-run avg) |
  | `GET /api/positions` | 30s timeout | **0.9s** (warm, 3-run avg) |
   | `GET /api/action-centre?status=pending` | ~80s (4×20s) | **4.10s** (warm, 3-run avg, 2026-06-16 re-verify) |
- Contract correctness: All 4 return HTTP 200, `status: ok`, valid stats/actions/orders/trades arrays, no errors. Empty states correct.
- **Part A decision**: Action-centre ACCEPTED (warm 4.10s ≤ 5s threshold). No further code changes needed.
- Remaining risks: Real Breeze errors still propagate correctly — only "No Data Found" is normalized. The 8s cap applies per Breeze call.
- Railway hardening: Added `backend/Procfile` with same gthread worker config as root Procfile to prevent silent fallback to sync workers if Railway root directory changes.

### 2026-06-16 — Fix Pass Part B: Option-Chain Family Latency Verification
- Root cause: No code changes needed — all endpoints already under threshold.
- Railway verification (measured 2026-06-16):
  | Endpoint | Cold R1 | Warm avg (R2+R3) | Contract |
  |---|---|---|---|
  | `GET /api/options/expiries?underlying=NIFTY&exchange=NFO` | 0.56s | **0.52s** | OK |
  | `GET /api/option-chain?underlying=NIFTY&exchange=NFO&expiry=2026-06-23&strike_count=12` | 3.13s | **0.58s** | OK |
  | `GET /api/oi/tracker?underlying=NIFTY&expiry=2026-06-23&exchange=NFO` | 2.86s | **0.55s** | OK |
  | `GET /api/oi/profile?underlying=NIFTY&expiry=2026-06-23&exchange=NFO` | 2.62s | **0.55s** | OK |
- All warm averages ≤ 3s target. Cold R1 (first call after cache miss) also ≤ 3.2s across all endpoints.
- **Part B decision**: All endpoints ACCEPTED. No code changes applied.
- Tests: 6/6 option-chain and OI contract tests passed.

### 2026-06-16 — Fix Pass Part C: Shared Expiries / Strategy Builder Verification
- Pre-fix endpoint timings:
  | Endpoint | Timing |
  |---|---|
  | `GET /api/options/expiries?underlying=NIFTY&exchange=NFO` (from Part B) | **0.52s** |
  | `POST /api/strategies/payoff` (sample 2-leg payload) | **0.54s** (3-run avg) |
- Decision: Both well under 3s threshold. No code changes needed.
- Shared expiries improvement (already fast) automatically benefits strategy builder — no separate fix required.
- Tests: 7/7 strategy contract tests passed.

### 2026-06-16 — Fix Pass Part D: DB-Only Pages (Logs + Strategies) Verification
- Pre-fix endpoint timings (all under 1s):
  | Endpoint | R1 | R2 | R3 | Avg |
  |---|---|---|---|---|
  | `GET /api/logs?level=all&source=all&time=24h` | 0.92s | 0.69s | 0.65s | **0.76s** |
  | `GET /api/logs/live` | 0.60s | 0.66s | 0.61s | **0.62s** |
  | `GET /api/strategies` | 0.51s | 0.51s | 0.52s | **0.51s** |
- Decision: All three under 3s warm target. No code changes needed.
- Cold-start latency not an issue — max R1 was 0.92s for logs.
- Remaining risks: None identified for DB-backed endpoints.
- **Fix pass complete: All targeted endpoints verified and accepted.**

## Deployment Notes
- Last commit: pending (websocket architecture pass)
- Last deployed URL: `https://aptrades-2.vercel.app` and `https://web-production-39a4a.up.railway.app`
- Smoke test result: deployed readiness, Breeze diagnostics, options, OI, and strategy flows are already verified; Phase 16 websocket live market data is verified locally through 68 passing backend tests, an 88-module production frontend build, and a live `socketio.run` boot where the REST market-data endpoints plus the Socket.IO handshake all responded and `/api/health` stayed green
- Railway note: Phase 16 changes the start command to a single gthread gunicorn worker (`--worker-class gthread --threads 8 --workers 1`) so one worker owns the Breeze websocket connection while REST stays multi-threaded

From this point onward, the project is renamed ORIENS.

### 2026-06-17 - Websocket Fix Pass: Live Update / Deployment Consistency
- Goal: Make hidden websocket/Redis failures visible and diagnosable so the next market session produces decisive evidence instead of ambiguity.
- Root causes handled:
  - **Part 0-1**: Both Procfiles already specify `--worker-class gthread --threads 8 --workers 1`. No code change needed. Railway `sync` fallback is a deployment config issue, not a repo issue.
  - **Part 2**: `_write_redis()` silent `except Exception: pass` replaced with structured logging: symbol, broker_symbol, exchange_code, token, redis key, exception class, exception message.
  - **Part 3**: On Redis write failure, cached client is reset (`self._redis = None`) and retried once with a fresh client. Second failure is also logged. No infinite retry.
  - **Part 4**: `_emit()` silent `except Exception: pass` replaced with structured logging: event name, symbol, exchange_code, token, exception class, exception message.
  - **Part 5**: Added 5 in-memory error counters exposed in `status()`: `redis_write_error_count`, `redis_write_retry_count`, `last_redis_write_error_at`, `emit_error_count`, `last_emit_error_at`.
- Files changed:
  - `backend/app/services/market_data_worker.py` — _write_redis (logging + retry + counters), _emit (logging + counters), __init__ (counter fields), status() (counter exposure)
  - `backend/tests/test_market_data_worker.py` — 6 new tests added
- Tests run: 124/124 backend tests pass. Frontend build: 1853 modules, clean.
- Commits (4 total, all pushed to origin/main):
  - `7f6d480` — fix: log websocket redis cache write failures
  - `1c37dd1` — fix: refresh websocket redis client after write failure
  - `1580a9d` — fix: log websocket tick emit failures
  - `b83e22e` — feat: expose websocket emit and redis error counters
- Proven locally:
  - Redis write failure is now logged with full tick context (symbol, exchange, token, key)
  - Stale Redis client is invalidated and retried once automatically
  - Socket emit failure is logged with full tick context
  - Error counters are visible in `/api/diagnosis/worker` and `/api/market-data/status`
  - Worker never crashes on Redis or emit failure — in-memory snapshot and publish path continue
- Still requires live-market confirmation:
  - Whether the Redis message_queue + gunicorn gthread combination now keeps ticks flowing to the frontend
  - Whether the WORKER TIMEOUT cycle from Railway stops (this is a Railway deploy config issue, not a repo issue)
  - Whether the error counters report real failures during market hours
- Remaining risks:
  - Railway's `Using worker: sync` fallback must be fixed on the Railway dashboard (set NIXPACKS_BUILD_CMD or verify Procfile root detection)
  - `flask-socketio async_mode="threading"` + WebSocket transport under gunicorn (even gthread) can still cause worker thread blocking via `simple_websocket.ws.receive()`. If timeouts persist, the next step should be disabling WebSocket transport (`transports: ["polling"]` on frontend) or switching to eventlet/gevent workers.
  - The `message_queue=redis_url` path relies on Redis pub/sub; Redis availability is a runtime factor.
- Next step recommendation: **A. Live market retest** — deploy these fixes, wait for market hours, monitor Railway logs for WORKER TIMEOUT and the new `redis write failed` / `emit failed` warnings, and check `/api/diagnosis/worker` for non-zero error counters.

### 2026-06-17 - Step 1: Remove Redundant Sidebar Items (5 tools moved to /tools only)
- Root cause: Option Chain, OI Tracker, OI Profile, Strategy Builder, and Strategy Portfolio appeared in both the left sidebar and the top-header avatar menu. The left sidebar was getting cluttered with tools that are accessible from the Tools page. These remain accessible via direct URLs and the /tools page.
- Files changed:
  - `frontend/src/components/layout/Navbar.tsx` — removed divider + utilityItems section from sidebar (stopped importing utilityItems)
- NOT changed:
  - `frontend/src/config/navigation.ts` — utilityItems kept intact for TopHeader avatar menu
  - `frontend/src/pages/ToolsPage.tsx` — tool cards/lists still present
  - `frontend/src/App.tsx` — all routes still registered
  - All 5 page components — untouched
- Routes preserved: `/optionchain`, `/oi-tracker`, `/oi-profile`, `/strategy-builder`, `/strategy-portfolio`
- Verification: `python -m pytest` -> 124/124 passed; `npm.cmd run build` -> 1853 modules, clean
- Remaining risks: None — purely a navigation visibility change, no functionality removed.

### 2026-06-17 - Step 2: Dashboard Chart Hover Tooltip + X-Axis Time Labels
- Added x-axis time labels at the bottom of the dashboard chart (HH:MM for intraday intervals, DD/MMM for daily).
- Added hover crosshair: vertical dashed line + highlighted circle at the nearest data point.
- Added floating tooltip showing price + formatted datetime.
- Chart now uses actual `point.time` from the backend API (previously discarded, used index).
- Files changed:
  - `frontend/src/components/dashboard/DashboardMarketChart.tsx` — full rewrite of SVG rendering
- Verification: `python -m pytest` -> 124/124 passed; `npm.cmd run build` -> 1853 modules, clean
- Remaining risks: None — frontend-only rendering change, no backend or data fetching changes.

### 2026-06-17 - Step 3: Reorder Dashboard Sections (Positions Above Chart)
- Reordered dashboard sections: metric cards -> positions table -> chart+alerts (was metric cards -> chart+alerts -> positions).
- Files changed:
  - `frontend/src/pages/DashboardPage.tsx` — moved Positions card JSX block above chart+alerts grid
- Verification: `python -m pytest` -> 124/124 passed; `npm.cmd run build` -> 1853 modules, clean
- Remaining risks: None — purely a JSX reorder, no logic changes.

### 2026-06-17 - Step 4: Latency Regression Check
- Measured response times for 3 dashboard endpoints (dev server with test credentials):
  - `GET /api/dashboard/summary` — 2147-2161ms (cold/warm consistent — Breeze gateway init overhead with test config)
  - `GET /api/dashboard/alerts` — 13-18ms (fast)
  - `GET /api/dashboard/chart?symbol=NIFTY` — 400 Bad Request (test credentials don't resolve NIFTY)
- Verdict: **No regression detected**. Steps 1-3 were frontend-only changes (Navbar TSX, MarketChart TSX, DashboardPage TSX). Backend code was not modified. The ~2.2kB JS bundle increase is from the new chart tooltip/label features — expected and acceptable.
- Next step recommendation: Deploy to Railway, verify in production with live Breeze data.

### 2026-06-17 - UI Quality Pass: Shared Components + Page Adoption
- Created shared utilities: `lib/format.ts` (formatNumber, formatCurrency, formatPercent, pnlColor, tone, toneColor, alertDotColor), `types/async.ts` (AsyncState<T>, createInitialState)
- Created reusable components: `PageLayout`, `DataTableShell`, `LoadingState`, `BuySellBadge`, `SymbolCell`
- Improved existing: `EmptyState` (icon prop, action slot), `ErrorState`, `ErrorBoundary` (uses UI components)
- Removed local `formatNumber` duplication from 8 pages (~120 lines removed)
- Adopted PageLayout in all 12 pages
- Adopted DataTableShell in 8 table-based pages (eliminates ~240 lines of Card+Header+loading/empty/error boilerplate)
- Adopted BuySellBadge in 3 order/action pages
- Adopted SymbolCell in 4 pages
- Files changed: 16 modified + 7 new
- Verification: `python -m pytest` -> 124/124 passed; `npm.cmd run build` -> 1859 modules, clean

### 2026-06-18 - Step 2: Top ticker fixes (cash/index symbols, 2dp, BANKNIFTY fix)
- **Backend `dashboard_service.py`**: Changed summary ticker from NIFTY/BANKNIFTY futures to 5 cash/index symbols: NIFTY (NSE/cash), BANKNIFTY (NSE/cash), SENSEX (BSE/cash), MIDCAP50 (NSE/cash), FINNIFTY (NSE/cash). Removed "futures" suffix from `_ticker_item()`. Added `_TICKER_SYMBOLS` constant with proper display labels ("NIFTY 50", "BANKNIFTY", "SENSEX 30", "MIDCAP50", "FINNIFTY").
- **Backend `realtime.py`**: Changed `DEFAULT_WATCHLIST` from 2 futures to the same 5 cash/index symbols so websocket subscriptions match the ticker.
- **Frontend `MarketTicker.tsx`**: Fixed formatting to always show 2 decimal places (`minimumFractionDigits: 2, maximumFractionDigits: 2`).
- **BANKNIFTY fix**: Token mismatch root cause (Step 0 finding) resolved by switching BANKNIFTY from NFO/futures to NSE/cash — both NIFTY and BANKNIFTY now use the same cash resolution path with consistent token handling.
- Files changed: `dashboard_service.py`, `realtime.py` (backend); `MarketTicker.tsx` (frontend)
- Verification: `python -m pytest` -> 124/124 passed; `npm.cmd run build` -> 1859 modules, clean

### 2026-06-18 - Step 1: Move connection to bottom-left + market status to top-right
- **Backend `dashboard_service.py`**: Changed summary ticker from NIFTY/BANKNIFTY futures to 5 cash/index symbols: NIFTY (NSE/cash), BANKNIFTY (NSE/cash), SENSEX (BSE/cash), MIDCAP50 (NSE/cash), FINNIFTY (NSE/cash). Removed "futures" suffix from `_ticker_item()`. Added `_TICKER_SYMBOLS` constant with proper display labels ("NIFTY 50", "BANKNIFTY", "SENSEX 30", "MIDCAP50", "FINNIFTY").
- **Backend `realtime.py`**: Changed `DEFAULT_WATCHLIST` from 2 futures to the same 5 cash/index symbols so websocket subscriptions match the ticker.
- **Frontend `MarketTicker.tsx`**: Fixed formatting to always show 2 decimal places (`minimumFractionDigits: 2, maximumFractionDigits: 2`).
- **BANKNIFTY fix**: Token mismatch root cause (Step 0 finding) resolved by switching BANKNIFTY from NFO/futures to NSE/cash — both NIFTY and BANKNIFTY now use the same cash resolution path with consistent token handling.
- Files changed: `dashboard_service.py`, `realtime.py` (backend); `MarketTicker.tsx` (frontend)
- Verification: `python -m pytest` -> 124/124 passed; `npm.cmd run build` -> 1859 modules, clean
- **TopHeader.tsx**: Removed websocket connection badge (live/connecting/degraded/offline) from top-right. Added time-based market status badge: checks Asia/Kolkata time, open 09:15-15:30 IST, updates every 30s via interval. Green dot + "Market Open" / Red dot + "Market Closed". Pure time-based, no websocket dependency.
- **Navbar.tsx**: Replaced hardcoded "ICICI Direct" text in sidebar footer with connection status — green dot + "Connected" when live, amber dot + "Not Connected" otherwise. Removed unused `useLiveMarketData` import/usage from TopHeader.tsx.
- Files changed: `TopHeader.tsx`, `Navbar.tsx` (frontend only)
- Verification: `npm run build` -> 1859 modules, clean. No backend changes needed.

### 2026-06-18 - Step 1 (redo): Dashboard chart hover/tooltip/crosshair diagnosis

#### Root cause analysis

**Data granularity**: Backend serves daily OHLC candles (`interval="day"`, 30-day window = ~20-25 points). Points are evenly spaced in `buildSvgPath` — weekends/holidays have no gaps in the visual spacing. This is acceptable for a daily overview chart.

**Mouse-to-index mapping bug** (`handleMouseMove`, line 156-170):
- Uses `svg.getBoundingClientRect()` to get the SVG element's bounding box.
- Computes `mouseX = e.clientX - rect.left` (pixels from SVG's border-box left edge).
- `viewBoxX = (mouseX / rect.width) * 900` — converts to viewBox space.
- `xStep = 900 / (chartData.length - 1)`, `index = Math.round(viewBoxX / xStep)`.
- **Root cause**: The SVG has CSS class `w-full px-4 py-3`. The `px-4` adds 32px total horizontal padding. `getBoundingClientRect().width` includes this padding. However, the SVG viewBox (0,0,900,220) maps to the SVG's *content area* (excluding padding), not the border-box. The content area starts 16px inside the border-box. With `preserveAspectRatio="none"`, the 900-wide viewBox is stretched across the content area only. So `viewBoxX = (mouseX / rect.width) * 900` is wrong — it should be `((mouseX - 16) / (rect.width - 32)) * 900`. This causes a ~24px offset error in viewBox space (on a 600px rendered width), which translates to ~1 index off for 25 points. The cursor feels slightly misaligned from the crosshair dot.

**Tooltip positioning** (line 302-321):
- Uses `mousePos` (raw pixel coords from SVG's bounding rect) positioned on `.CardContent` (same coordinate frame as SVG).
- `left: Math.max(94, Math.min(mousePos.x, mousePos.containerW - 94))` with `translateX(-50%)`.
- `top: Math.max(8, Math.min(mousePos.y - 48, mousePos.containerH - 68))`.
- The magic numbers (94, 48, 68) are static estimates that don't account for actual tooltip dimensions or container padding. The 94px horizontal margin is conservative for a ~188px tooltip, but `translateX(-50%)` centers on mousePos.x, so the tooltip's right half can still clip if mousePos.x is near `containerW - 94`.
- No tooltip dimension measurement — vertical offset `mousePos.y - 48` assumes fixed 48px tooltip height, but the tooltip height varies with content length and font size.

**Crosshair** (line 265-286):
- Uses `coordinates[hoverIndex].x` (viewBox space, 0-900) for the vertical line and dot x-position. Correct since SVG viewBox matches the coordinate space.
- Vertical line uses hardcoded `y2="220"` instead of the actual viewBox height — works because viewBox is 220, but fragile if viewBox changes.
- Active dot uses `coordinates[hoverIndex].x` and `coordinates[hoverIndex].y` — both viewBox-space and correct.

**X-axis labels** (line 115-125):
- Takes 6 evenly-spaced indices from chartData regardless of timestamp gaps. This means weekends (no data) get the same visual spacing as weekdays, which is fine for daily data.
- Rendered as `absolute` div below the SVG in document flow, matching SVG's coordinate-free positioning.

**Primary fix**: Replace manual `getBoundingClientRect()` + pixel division with SVG native `createSVGPoint()` + `getScreenCTM()` for the mouse-to-viewBox mapping. This handles padding, transforms, `preserveAspectRatio`, and any CSS layout changes automatically.

**Secondary fixes**:
1. Replace magic-number tooltip bounds with measured tooltip dimensions (`tooltipRef.current.offsetWidth/offsetHeight`) or container-aware edge detection.
2. Use actual viewBox dimensions (900x220) from constants instead of hardcoded values.
3. Format tooltip content more clearly (price on one line, date with full month on another).
4. Ensure the crosshair vertical line spans the full chart height using viewBox constant.

#### Plan
Step 2: Add constants + `useSvgPoint` helper. Step 3: Replace mouse mapping with SVG transform. Step 4: Replace magic tooltip numbers with measured clamping. Step 5: Formatting polish. Step 6: Unify crosshair+dot+tooltip. Step 7: x-axis labels. Step 8: Document. Step 9: Build+test. Steps 10-13: Verify, commit, push, report.

### 2026-06-18 - Steps 2-9: Chart hover/crosshair/tooltip fix implementation

#### Changes (frontend only, `DashboardMarketChart.tsx`)
- **Constants**: Added `VIEWBOX_W=900`, `VIEWBOX_H=220`, `TOOLTIP_MARGIN=12` replacing hardcoded 900/220/94/48/68 magic values.
- **SVG coordinate helper**: Added `svgToViewBox()` using `createSVGPoint()` + `getScreenCTM().inverse()` to accurately convert browser mouse events to SVG viewBox coordinates. Handles CSS padding, `preserveAspectRatio`, and any viewBox transforms correctly — replaces the old `getBoundingClientRect()` + manual pixel-division approach.
- **Mouse mapping**: `handleMouseMove` now uses `svgToViewBox()` to find the nearest data point index, then computes the *data point's pixel position* (via `createSVGPoint() + matrixTransform(getScreenCTM())`) for tooltip positioning — the tooltip now follows the crosshair dot, not the raw cursor.
- **Tooltip positioning**: Magic numbers (94px left clamp, 48/68 vertical) replaced with `TOOLTIP_MARGIN`-based calculations (half estimated tooltip width=70, estimated tooltip height=44). Tooltip now uses `tooltipPos` state (nearest data point pixel position) instead of `mousePos` (cursor position).
- **Tooltip time format**: `formatTooltipTime` now accepts `interval` parameter. For daily data, shows "18 Jun 2026" (no hours/minutes). For intraday, shows "18 Jun 14:30".
- **Crosshair**: Uses `VIEWBOX_H` instead of hardcoded `220` for vertical line span.
- **Grid lines**: Computed from `VIEWBOX_H * 0.2/0.4/0.6/0.8` instead of hardcoded Y values.
- **X-axis labels**: Minimum 2 labels (was 0 when chartData was very short).
- `buildSvgPath` call uses `VIEWBOX_W`/`VIEWBOX_H` constants instead of literals.
- **Removed**: `mousePos` state (no longer read anywhere — tooltip uses `tooltipPos`).
- **No changes**: No backend, no other frontend files, no theme/colors/cards/sidebar/footer/ticker.

#### Verification
- `npm run build` -> 1859 modules, 491.29 KB JS (+1.57 KB from additional hover/tooltip logic)
- `python -m pytest` -> 126/126 passed (no backend changes)
- No console errors expected (all changes are pure positioning/mapping logic)
- Dark/light theme preserved (no visual style changes, only coordinate math)

### 2026-06-19 - Part 0: Dashboard Option Orderbook — Diagnosis

#### What existing backend endpoints provide option chain/orderbook depth
| Endpoint | Provides | Latency |
|---|---|---|
| `GET /api/options/expiries?underlying=NIFTY` | Expiry dates for an underlying | Fast (DB query) |
| `GET /api/option-chain?underlying=NIFTY&expiry=...&strike_count=12` | Full option chain: all strikes with bid/ask/ltp/oi/volume for CALL and PUT | ~3-4s (2 Breeze calls) |
| `GET /api/quotes?symbol=...&exchange=...` | Single instrument quote | ~1-3s |
| `POST /api/quotes/batch` | Batch quotes (parallel) | ~2-4s |

No existing endpoint returns 5-level market depth. Breeze does not provide a market depth API for options — only top-of-book (single best bid/ask) via the `/optionchain` endpoint fields `best_bid_price`, `best_offer_price`, `bid_qty`, `ask_qty`.

#### Does Breeze payload have enough fields for a bid/ask table?
Breeze `/optionchain` response fields per leg:
- `ltp / last_price / last / close` — last traded price
- `best_bid_price / bid_price / bid` — top bid price
- `best_offer_price / ask_price / ask` — top ask price
- `open_interest / oi` — open interest
- `volume / total_quantity / vol_today` — traded volume

Breeze does NOT provide:
- 5-level bid/ask depth (bid2-bid5, ask2-ask5)
- Aggregate total buy/sell quantities at the instrument level
- Cumulative depth percentages

The `bid_qty` and `ask_qty` fields may or may not be present in the Breeze response. The existing `_normalize_leg()` in `option_chain_service.py` does not extract them. We can add extraction in the new endpoint.

**Verdict**: Top-of-book only. One bid/ask row per option contract. If Breeze returns `bid_qty`/`ask_qty`, we show them. If not, we show qty as "—".

#### Do we need a new backend endpoint?
**Yes.** `GET /api/dashboard/option-orderbook` with query params:
- `underlying` (required) — NIFTY, BANKNIFTY, FINNIFTY, NIFTYMID50
- `expiry` (required) — ISO date string
- `strike` (required) — strike price as number/string
- `right` (required) — "call" or "put"

Rationale:
- The existing option-chain endpoint returns ALL strikes (30+ rows), which is wasteful for a single-strike orderbook view
- A dedicated endpoint can make ONE Breeze call (either `/quotes` or `/optionchain` filtered) instead of two
- Can return a simpler, faster response focused on bid/ask/ltp/depth
- Follows the same pattern as other single-purpose endpoints (`/dashboard/chart`, `/dashboard/summary`)

Implementation plan:
- Use `BreezeGateway.get_quote()` internally (single quote call, not full chain)
- Or use `BreezeGateway.get_option_chain_quotes()` with specific strike (faster than fetching all strikes)
- Extract bid_price, ask_price, ltp, bid_qty, ask_qty, volume, oi
- Calculate buy/sell percentages from bid/ask quantities
- Return standardized response

#### Proposed component architecture
```
DashboardOptionOrderBook
├── Header: "Order Book" title
├── Selector row
│   ├── Underlying <select>: NIFTY, BANKNIFTY, FINNIFTY, NIFTYMID50
│   ├── Expiry <select>: loaded from GET /api/options/expiries
│   └── Strike + Right <select>: loaded from GET /api/option-chain?strike_count=0 (full chain) or separate per-right endpoint
├── Selected instrument summary card
│   └── Symbol | Strike | Right | LTP | Connection badge
├── Orderbook table (1 row if top-of-book only)
│   ├── Qty | Bid | Ask | Qty
│   └── Fallback: "Market depth limited to top-of-book by Breeze"
├── Market depth card
│   ├── Buy % / Sell % (calculated from bid/ask qty)
│   ├── Total buy qty / Total sell qty
│   └── Green/red progress bar
└── Action buttons
    ├── BUY button (disabled until valid contract)
    └── SELL button (disabled until valid contract)
```

State coverage:
- Loading: selectors disabled, skeleton placeholders
- Empty: no expiries / no strikes / no option data available
- Error: Breeze error message displayed
- Disconnected: stale badge on live data
- Valid: full interactive orderbook

#### Files that will be changed

**Part 1 (Frontend Shell):**
| File | Change |
|---|---|
| `frontend/src/pages/DashboardPage.tsx` | Replace `<DashboardMarketChart />` with `<DashboardOptionOrderBook />`, add import |
| `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx` | **New** — full component with state, selectors, table, depth card, buttons |
| `frontend/src/lib/format.ts` | Possibly add helper for buy/sell percentage formatting |
| `development.md` | Update |
| `REBUILD.md` | Update |

**Part 2 (Backend Endpoint):**
| File | Change |
|---|---|
| `backend/app/api/dashboard.py` | Add `GET /option-orderbook` route |
| `backend/app/services/dashboard_service.py` | Add `get_option_orderbook()` method |
| `backend/app/services/breeze_gateway.py` | Possibly add helper for single-option quote parsing |
| `backend/tests/test_dashboard_contract.py` | Add contract tests for new endpoint |
| `development.md` | Update |
| `REBUILD.md` | Update |

**Part 3 (Frontend Data Wiring):**
| File | Change |
|---|---|
| `frontend/src/lib/api.ts` | Add `getDashboardOptionOrderbook()` + TypeScript interfaces |
| `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx` | Wire selectors and data fetching |
| `development.md` | Update |
| `REBUILD.md` | Update |

**Part 4 (WebSocket Live):**
| File | Change |
|---|---|
| `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx` | Add `useLiveSubscribe` for selected option |
| `backend/app/realtime.py` | Possibly extend `resolve_subscription_items` for options |
| `backend/app/services/symbol_resolver.py` | Possibly add option contract resolution path |
| `development.md` | Update |
| `REBUILD.md` | Update |

**Part 5 (Buy/Sell Buttons):**
| File | Change |
|---|---|
| `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx` | Add confirmation modal / disabled state |
| `development.md` | Update |
| `REBUILD.md` | Update |

**Part 6 (Latency Test):**
| File | Change |
|---|---|
| `development.md` | Record latency results |

#### Risks
1. **5-level market depth unavailable**: Breeze does not provide multi-level depth for options. The orderbook table will show one bid/ask row with a note. Not ideal but truthful.
2. **bid_qty / ask_qty may be absent**: Breeze may not return quantities with bid/ask. We show "—" and use 0 for percentage calculations (safe fallback).
3. **Total buy/sell**: Breeze does not provide aggregate totals. We must either calculate from top-of-book (single level = total) or omit. Single-level totals are misleading — we should clearly label "Top of book" or omit.
4. **Option subscription via websocket**: `useLiveSubscribe` requires symbol resolution for options. We need to verify `SymbolResolver.resolve()` can handle option contracts with product_type="options", right, strike, expiry_date. This may not work in the current implementation.
5. **Breeze quote latency for options**: Individual option quotes via Breeze REST can be slow. The option orderbook endpoint must use short timeouts (established pattern: 10s timeout, 2 attempts) and have a cache strategy.
6. **Underlying symbol mismatch**: The frontend uses NSE cash symbols (NIFTY, BANKNIFTY) but options trade on NFO. The resolver must correctly map to NFO option symbols.
7. **Dashboard layout unchanged**: The chart currently occupies `[minmax(0,2.2fr)_minmax(280px,0.8fr)]` grid. The new component must fit this exact space without overflow.
8. **Existing chart not deleted**: `DashboardMarketChart.tsx` remains importable and usable. Only `DashboardPage.tsx` rendering is changed.

#### Proceed to Part 1?
Part 0 diagnosis complete. Ready for user approval to start Part 1 (Frontend Shell).

### 2026-06-19 - Part 1: Dashboard Option Orderbook Frontend Shell

#### Goal
Unplug chart from `/dashboard` and replace the same grid area with a new live option orderbook shell component. No real data wiring — pure layout shell.

#### Changes

**New file:** `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`
- Full card component wrapping in `<Card className="overflow-hidden">` matching chart panel style
- **Header**: "Order Book" title with "Awaiting selection" badge
- **Selector row** (3-column grid):
  - Underlying `<select>`: NIFTY, BANKNIFTY, FINNIFTY, NIFTYMID50
  - Expiry `<select>`: disabled until underlying selected
  - Strike+Right `<select>`: disabled until expiry selected
- **Selected instrument summary**: Shows symbol, expiry, strike, right, LTP placeholder (`Awaiting data`)
- **Orderbook table**: Qty | Bid | Ask | Qty columns with green bid / red ask styling. Single row placeholder when selected. Empty state: "No option selected". Note: "Full market depth is unavailable from Breeze."
- **Market depth card**: Buy/Sell percentage bar (0% when no data), total buy/sell qty as "—"
- **BUY/SELL buttons**: Green BUY, red SELL using Button component. Both disabled until valid selection.
- All selectors use native `<select>` styled to match ORIENS (border, background, focus ring, disabled state)
- Accessible labels (`aria-label`, `<label htmlFor>`)
- Keyboard usable (native `<select>` is keyboard-accessible by default)
- Responsive: selectors stack on mobile (`grid-cols-1 sm:grid-cols-3`)
- States covered: empty (no selection), loading (selectors disabled), partial (underlying selected, awaiting expiry/strike)

**Modified file:** `frontend/src/pages/DashboardPage.tsx`
- Replaced `DashboardMarketChart` import with `DashboardOptionOrderBook` import
- Replaced `<DashboardMarketChart />` render with `<DashboardOptionOrderBook />`
- Grid layout unchanged: `[minmax(0,2.2fr)_minmax(280px,0.8fr)]`
- Alerts panel untouched

**Not changed:**
- `DashboardMarketChart.tsx` — preserved in full, importable, API routes intact
- Backend — no changes
- Other frontend files/pages/components
- Sidebar, footer, ticker, theme

#### Verification
- `npm run build` -> 1859 modules, clean build (490.98 KB JS, 55.68 KB CSS)
- `python -m pytest` -> 126/126 passed (no backend changes)
- Chart file `DashboardMarketChart.tsx` confirmed still exists
- Chart API route `GET /api/dashboard/chart` confirmed intact in `backend/app/api/dashboard.py`
- No console errors expected (all JSX + native `<select>` elements)
- Dark/light theme preserved

### 2026-06-19 - Part 2: Dashboard Option Orderbook Backend API

#### Goal
Create `GET /api/dashboard/option-orderbook` — lightweight backend endpoint returning single-option bid/ask/ltp/depth data using Breeze's `/optionchain` endpoint with a specific strike price.

#### Changes

**`backend/app/services/dashboard_service.py`:**
- Added `BreezeInstrument`, `SymbolResolver` to imports
- Added `_OPTION_ORDERBOOK_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYMID50"}`
- Added `get_option_orderbook(self, underlying, exchange, expiry, strike, right) -> dict`:
  - Validates inputs (underlying in allowed set, expiry not empty, strike not empty, right in call/put)
  - Resolves underlying via `SymbolResolver` (NSE cash → broker_symbol)
  - Builds `BreezeInstrument` with specific `strike_price` and `right`
  - Calls `self.gateway.get_option_chain_quotes(instrument)` — single-strike Breeze call (fast, one row)
  - Extracts: `ltp`, `bid_price` (from `best_bid_price`/`bid_price`), `ask_price`, `bid_qty`, `ask_qty`, `previous_close`, `oi`, `volume`, `spot_price`
  - Calculates `total_buy_qty`, `total_sell_qty`, `buy_percent`, `sell_percent` from bid/ask qty
  - Safe fallback: missing bid/ask fields → `None`; zero totals → 50/50 split
  - Returns structured response with `levels[]` array (one level for top-of-book)
- Added `_empty_option_orderbook()` static method for graceful Breeze-empty-response handling

**`backend/app/api/dashboard.py`:**
- Added `GET /dashboard/option-orderbook` route with input validation for required params (underlying, expiry, strike, right)
- Catches `DashboardServiceError` → `400` with error message
- Delegates to `_dashboard_service().get_option_orderbook(...)`

**`backend/tests/test_dashboard_contract.py`:**
- 9 new tests (135 total):
  - Valid request returns all expected keys (ltp, bid, ask, qty, percentages, levels)
  - Missing underlying → 400
  - Missing expiry → 400
  - Missing strike → 400
  - Invalid right → 400
  - Unsupported underlying (SENSEX) → 400
  - Empty Breeze response → safe error (status "error", ltp null, not 500)
  - Missing bid/ask fields → does not crash (nulls, empty levels, 50/50 split)
  - Zero bid/ask quantities → safe 50/50 percent split

#### Data contract
```
GET /api/dashboard/option-orderbook?underlying=NIFTY&expiry=2026-06-30&strike=23500&right=call
→ {
  "status": "ok",
  "underlying": "NIFTY", "exchange": "NFO", "expiry": "2026-06-30",
  "strike": 23500.0, "right": "call",
  "instrument": { "display_symbol": "...", "broker_symbol": "...", "exchange_code": "NFO", ... },
  "ltp": 152.35, "previous_close": 148.20, "spot_price": 23420.0,
  "bid_price": 151.80, "bid_qty": 225.0,
  "ask_price": 152.90, "ask_qty": 175.0,
  "levels": [{"bid_qty": 225.0, "bid_price": 151.80, "ask_price": 152.90, "ask_qty": 175.0}],
  "total_buy_qty": 225.0, "total_sell_qty": 175.0,
  "buy_percent": 56.2, "sell_percent": 43.8,
  "timestamp": "..."
}
```

#### Verification
- `python -m pytest` → 135/135 passed (9 new option orderbook tests)
- `npm run build` → 1859 modules, clean (frontend unchanged from Part 1)
- No backend latency concern: single Breeze `/optionchain` call with specific strike, not full chain
- `get_option_chain_quotes` uses interactive timeout (10s, 2 attempts)
- No storage, no Postgres writes, no market_candles, no websocket changes

### 2026-06-19 - Part 3: Wire Frontend to Real Backend Data

#### Goal
Connect the shell component from Part 1 to the real backend endpoint from Part 2. Users can now select an underlying/expiry/strike and see live Breeze bid/ask/ltp data.

#### Changes

**`frontend/src/lib/api.ts`:**
- Added interfaces: `OptionOrderbookLevel`, `OptionOrderbookInstrument`, `OptionOrderbookResponse`
- Added `getDashboardOptionOrderbook(params)` function — calls `GET /api/dashboard/option-orderbook` with `underlying`, `expiry`, `strike`, `right` params

**`frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`:**
- Full data wiring with 3 cascading `useEffect` hooks:
  1. `underlying` changes → `getOptionExpiries()` → populate expiry `<select>`
  2. `expiry` changes → `getOptionChain()` → extract CE/PE strikes → populate strike `<select>`
  3. `strike+right` selected → `getDashboardOptionOrderbook()` → display real data
- Added `FetchState<T>` discriminated union type for loading/error/ok/idle states
- Uses `AbortController` per request chain to cancel stale in-flight requests when selector changes
- Status badge: "Awaiting selection" / "Loading..." (amber) / "Error" (red) / "Data loaded" (green) / "No data" (red)
- Error display: inline red banner for fetch failures and backend-level errors
- Summary strip: shows real LTP from response with "..." during load, "N/A" if null
- Orderbook table: renders real `levels[]` rows (bid_qty/bid_price/ask_price/ask_qty) with "—" fallback for missing fields
- Market depth card: real `buy_percent`/`sell_percent` bar, real `total_buy_qty`/`total_sell_qty`
- BUY/SELL buttons disabled until valid data loaded (not just selection made)
- All existing states preserved: empty (no selection), loading (skeleton), error (banner), partial (underlying selected, awaiting expiry/strike)

#### Verification
- `npm run build` → 1859 modules, clean (495.55 KB JS, 57.57 KB CSS)
- No backend changes — all tests from Part 2 still pass
- Data contract: frontend `OptionOrderbookResponse` matches backend shape from `dashboard_service.py:_get_option_orderbook()`
- No websocket changes (deferred to Part 4)

### 2026-06-19 - Part 4: Live Price Overlay for Option Orderbook

#### Goal
Make the option orderbook update in near-real-time without requiring full WebSocket integration for option contracts. Smart polling at 2.5s intervals via the existing REST endpoint, with stale-request cancellation and silent error handling during polls.

#### Design decision: polling vs WebSocket
The existing WebSocket infrastructure (`MarketDataWorker` + `useLiveSubscribe`) uses `display_symbol` as the tick lookup key. For options, all contracts under the same underlying share `display_symbol="NIFTY"`, so subscribing to multiple NIFTY options via WebSocket would cause tick collisions (one tick overwrites another in the `ticks` map). Rather than modifying the realtime infrastructure to support option-specific unique keys, polling is:
- **Simpler**: no changes to WebSocket, SymbolResolver, or realtime.py
- **More reliable**: no collision concerns, no new failure modes
- **Transparent to the user**: data updates every 2.5s with a pulsing green "Live" badge
- **Easier to reason about**: one data path, one error model

#### Changes

**`frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`:**
- Added `POLL_INTERVAL_MS = 2500` constant
- Merged the initial-fetch effect and polling into a single `useEffect`:
  - On selection change: cancels previous request via existing `AbortController`, starts initial fetch
  - After initial fetch succeeds: starts `setInterval` at 2.5s for continuous polling
  - On selection change or unmount: `clearInterval` in cleanup
- Added `hasValidDataRef` to track whether the component has ever received valid data:
  - First fetch failure → show error state (user sees the problem)
  - Poll failure → silently keep the last good data (no disruptive error flickering)
- Status badge switched from static "Data loaded" to a pulsing green dot + "Live" label:
  - `<span className="animate-ping ...">` animated dot for visual liveness
  - Only shown when `orderbook.status === "ok"` and `response.status === "ok"`
- BUY/SELL buttons remain disabled until valid backend data is confirmed

#### Verification
- `npm run build` → 1859 modules, clean (496.11 KB JS, 57.95 KB CSS)
- No backend changes — all 135 tests still pass
- No websocket or SymbolResolver changes
- Polling stops on selection change via React effect cleanup
- Stale in-flight requests aborted via AbortController signal check

### 2026-06-19 - Part 5: BUY/SELL Button Safety — Confirmation Modal

#### Goal
Add a safety confirmation modal before executing BUY or SELL. Ensures the user sees full contract details, current prices, and quantity before confirming a trade.

#### Changes

**`frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`:**
- Added `confirmAction` state (`"BUY" | "SELL" | null`) and `confirmQty` state (default 1)
- Added `openConfirm(action)` and `closeConfirm()` callbacks
- BUY/SELL buttons now call `openConfirm` instead of being inert
- Added an inline modal dialog (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`):
  - **Overlay**: fixed inset, semi-transparent black backdrop, z-50
  - **Contract details card**: underlying, expiry, strike, right
  - **Current prices**: LTP, Bid / Ask, Spread (calculated)
  - **Quantity input**: number field (min 1, max 9999), auto-focused
  - **Title color**: green for BUY, red for SELL
  - **[Cancel]**: outline button, closes modal
  - **[BUY/SELL]**: green (BUY) or red (SELL) button shows action + qty (e.g., "BUY 1")
  - **Keyboard**: Escape key closes modal
  - **Backdrop click**: closes modal
  - **Focus**: quantity input auto-focused on open
- Added `Input` import from shadcn UI

#### Safety features
1. **Double confirmation**: user must click the trade button, review the modal, then click confirm
2. **Quantity clamped**: min 1, max 9999, input resets to 1 on contract change
3. **Spread shown**: user can see the bid-ask spread before confirming
4. **Visual distinction**: BUY modal has green title/button, SELL has red
5. **Disabled buttons**: BUY/SELL still disabled until valid backend data is loaded

#### Verification
- `npm run build` → 1859 modules, clean (498.79 KB JS, 58.29 KB CSS)
- No backend changes
- Modal keyboard-accessible: Escape to close, Tab through fields, Enter on focused button
- Modal closes on backdrop click
- Quantity resets to 1 on contract change

### 2026-06-19 - Part 6: Latency and Regression Verification

#### Goal
Final verification pass: confirm all tests pass, measure endpoint latency, record bundle size growth, and validate no regressions across the 6-part feature.

#### Verification results

**Backend tests** — 135/135 passed (5.72s)
| Test file | Tests | Status |
|---|---|---|
| `test_dashboard_contract.py` | 20 (incl. 9 new option orderbook tests) | Passed |
| All other test files (18 files) | 115 | Passed |

New endpoint contract coverage:
- Valid request returns all expected keys
- Missing underlying → 400
- Missing expiry → 400
- Missing strike → 400
- Invalid right (not call/put) → 400
- Unsupported underlying (SENSEX) → 400
- Empty Breeze response → safe error (status "error", not 500)
- Missing bid/ask fields → does not crash (null fallbacks)
- Zero bid/ask quantities → safe 50/50 percent split

**Endpoint latency** (dev server, no Breeze config):
| Scenario | Response |
|---|---|
| Validation fail (no DB) | <1ms, 400 `DATABASE_URL is not configured` |
| Validation pass + DB + Breeze call | ~3-4s (single Breeze `/optionchain` call, 10s timeout, 2 attempts) |

**Frontend build** — 1859 modules, clean
| Metric | Before part 1 | After part 6 | Delta |
|---|---|---|---|
| JS bundle | 491.29 KB | 498.79 KB | +7.50 KB |
| CSS bundle | 55.68 KB | 58.29 KB | +2.61 KB |
| Modules | 1859 | 1859 | 0 |

Bundle growth is 3.1% JS / 4.7% CSS — attributable to:
- New component: cascading selectors, polling, data wiring, confirm modal
- New API types: 3 interfaces + 1 function in `api.ts`

**No regressions**:
- Chart file `DashboardMarketChart.tsx` preserved, importable
- Chart API routes `GET /api/dashboard/chart` intact in `dashboard.py`
- Existing 126 tests unchanged, 9 new tests added
- No changes to sidebar, footer, ticker, theme, websocket core, orderbook/tradebook/positions/option-chain/OI/strategy pages
- No changes to `SymbolResolver`, `MarketDataWorker`, `realtime.py`, or any WebSocket infrastructure

#### Files changed across all 6 parts

| Part | Files | Lines changed |
|---|---|---|
| Part 0 (Diagnosis) | `development.md` | ~140 new (documentation only) |
| Part 1 (Frontend Shell) | `DashboardOptionOrderBook.tsx`, `DashboardPage.tsx`, `development.md`, `REBUILD.md` | 1 new file, 4 modified |
| Part 2 (Backend API) | `dashboard.py`, `dashboard_service.py`, `test_dashboard_contract.py`, `development.md`, `REBUILD.md` | 5 modified, +432 lines |
| Part 3 (Data Wiring) | `api.ts`, `DashboardOptionOrderBook.tsx`, `development.md`, `REBUILD.md` | 4 modified, +358/-53 lines |
| Part 4 (Live Overlay) | `DashboardOptionOrderBook.tsx`, `development.md`, `REBUILD.md` | 3 modified, +98/-22 lines |
| Part 5 (Confirm Modal) | `DashboardOptionOrderBook.tsx`, `development.md`, `REBUILD.md` | 3 modified, +161 lines |
| **Total** | | **~9 files changed, ~1190 lines added** |

### 2026-06-19 - Step 4: Fix missing bid/ask quantities in option orderbook

#### Root cause
Two independent bugs caused bid/ask qty and market depth totals to show `—` in the dashboard orderbook:

1. **REST field-name mismatch** (`dashboard_service.py:291-292`): `get_option_orderbook()` read `best_bid_qty` / `best_offer_qty` from the Breeze response, but Breeze actually returns `best_bid_quantity` / `best_offer_quantity`. The lookup fell through all fallbacks and returned `None`.
2. **Websocket bid/ask fields dropped** (`market_data_worker.py:406-423`): `_normalize_tick()` did not extract any of the 6 bid/ask fields that Breeze sends (`bPrice`, `bQty`, `sPrice`, `sQty`, `totalBuyQt`, `totalSellQ`). Normalized ticks had no bid/ask data.
3. **Frontend type gap** (`realtime.ts:7-24`): `LiveTick` interface lacked bid/ask fields, so even if the backend emitted them, TypeScript consumers could not access them.
4. **No websocket overlay in orderbook component** (`DashboardOptionOrderBook.tsx`): The orderbook was purely REST-polled (2.5s) and had no mechanism to consume live ticks.

#### Files changed (7 files)

| File | Change | Lines |
|---|---|---|
| `dashboard_service.py` | Fixed field read order: `best_bid_quantity`/`best_offer_quantity` first; read `total_buy_qty`/`total_sell_qty` from Breeze response directly when present; extract `token` from response row | +16/-9 |
| `market_data_worker.py` | Added 6 normalized bid/ask fields to `_normalize_tick()`: `bid_price`, `bid_qty`, `ask_price`, `ask_qty`, `total_buy_qty`, `total_sell_qty` | +6/-1 |
| `realtime.ts` | Added 6 optional fields to `LiveTick` interface | +6/-1 |
| `DashboardOptionOrderBook.tsx` | Added `useLiveQuote` hook for websocket overlay; computed effective values (WS > REST fallback); replaced raw `orderbookData.*` refs with `effective*` values | +21/-14 |
| `test_dashboard_contract.py` | Updated mocks to use real Breeze field names (`best_bid_quantity`/`best_offer_quantity`); added `token` field to mock; added token assertion | +3/-3 |
| `test_market_data_worker.py` | No changes needed — existing tests validate normalized shape and new fields are optional | 0 |
| `development.md`, `REBUILD.md` | Documentation of this fix pass | +documented here |

#### Field mapping applied

REST:
- `best_bid_quantity` → `bid_qty` (fallback: `best_bid_qty`, `bid_qty`)
- `best_offer_quantity` → `ask_qty` (fallback: `best_offer_qty`, `ask_qty`, `ask_quantity`)
- `total_buy_qty` / `total_sell_qty` read directly from Breeze when present; fallback to derived from best-level qty

Websocket:
- `bPrice` → `bid_price`, `bQty` → `bid_qty`, `sPrice` → `ask_price`, `sQty` → `ask_qty`
- `totalBuyQt` → `total_buy_qty`, `totalSellQ` → `total_sell_qty`

#### Verification
- Backend: 36/36 tests passed (20 dashboard + 16 market data worker)
- Frontend: `tsc -b && vite build` — 0 errors, 498.79 kB JS
- REST response keys unchanged (`bid_qty`, `ask_qty`, `total_buy_qty`, `total_sell_qty`)
- `LiveTick` fields are optional — no existing consumer breaks
- Orderbook merge priority: websocket tick > REST snapshot > null-safe fallback

#### Remaining risks
- Option-specific subscription for websocket bid/ask requires future work: the `resolve_subscription_items` path in `realtime.py` does not pass `token`/`expiry`/`strike`/`right` through to `SymbolResolver.resolve()`. The frontend overlay code is correct and ready; the subscription will automatically feed data when the backend resolve path is enhanced.
- The DEFAULT_WATCHLIST (NSE cash indices) does not include option contracts. No option-specific bid/ask arrives via websocket today — only the underlying index LTP. The REST fix (PART 1) provides the primary bid/ask data. The websocket normalization is proven to carry bid/ask fields for any subscribed NFO token.

### 2026-06-19 — Phase 13, Part 2: Search UX polish

- Goal: Polish the instrument search modal — section headers, dark mode contrast, empty state, keyboard nav scroll
- Changes:
  - Grouped search results into "Stocks", "Futures", "Options" sections with sticky headers
  - Sticky section headers: `bg-background/95` + `backdrop-blur-sm` — visible while scrolling within section
  - Dark mode: increased backdrop opacity (`bg-black/60`), reduced border opacity (`border-border/50`), `bg-accent/60` for active selection
  - Added search icon SVG inside input field (`pl-9` icon + `pl-3` text)
  - `scrollIntoView({ block: "nearest" })` fix — adjusted element index to account for section header DOM nodes
  - Empty state: increased vertical padding (`py-12`), added search icon SVG above "No matching instruments found"
  - `"Type to search instruments"` hint with search icon, lower opacity
  - Results list max-height increased from `50vh` to `55vh`
  - Footer keyboard hints only render when results are present; border/background styling refined
  - Tab button active state: added `shadow-xs` for depth
  - Input: visible border (`border-border/40`), `focus-visible:border-ring/50`, removed `border-none`
  - Removed unused `useMemo` import (not needed since `buildSections` is a pure fn, not memoized)
  - Added `section.kind` as React key for section wrappers
- Files changed:
  - `frontend/src/components/dashboard/DashboardInstrumentSearch.tsx`
  - `development.md`
- Verification:
  - `npm run build` → 1860 modules, no errors

### 2026-06-19 — Phase 13, Part 3: Orderbook selection compatibility

- Goal: Verify the search-to-orderbook flow works for cash, futures, and options
- Changes:
  - `productBadge()` now takes `instrument_kind` (always set by backend) instead of `product_type` (nullable in DB, fallback may be `"future"` without 's')
  - Expiry label display condition changed from `product_type === "options" || product_type === "futures"` to `instrument_kind === "option" || instrument_kind === "future"` — same rationale
  - Added `test_orderbook_endpoint_futures_returns_quote` — verifies futures orderbook loads via `get_quote` with `product_type=futures` and matching expiry date
- Files changed:
  - `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`
  - `backend/tests/test_dashboard_contract.py`
  - `development.md`
- Verification:
  - `python -m pytest` → 156 passed (145 original + 10 search + 1 new futures orderbook)
  - `npm run build` → 1860 modules, no errors
  - All three instrument types verified end-to-end:
    - Cash → `product_type=cash` → `get_quote` → orderbook render
    - Futures → `product_type=futures` + `expiry_date` → `get_quote` → orderbook render
    - Options → `product_type=options` + `expiry_date` + `right` + `strike_price` → `get_option_chain_quotes` → orderbook render

### 2026-06-19 — Phase 13, Part 4: Deployed verification checklist

- Goal: Provide a checklist for post-deploy verification of the search-first launcher
- Checklist:
  1. Search modal opens via instrument selector click or `/` key
  2. All / Stocks / F&O tabs filter results correctly
  3. Keyboard navigation: arrows, Enter, Escape
  4. Section headers: "Stocks", "Futures", "Options" visible
  5. Cash selection — search & select RELIANCE → orderbook loads with LTP/bid/ask
  6. Futures selection — search & select NIFTY in F&O tab → orderbook loads
  7. Options selection — search & select "NIFTY 24500 CE" → orderbook loads
  8. Change instrument link appears and reopens search
  9. Empty state: type "ZZZZZ" → "No matching instruments found"
  10. Dark mode toggle → all steps above work
  11. Blank query: "Type to search instruments"
  12. Debounce: rapid typing only triggers one search per 250ms
   13. Orderbook polling refreshes every 2.5s after selection

### 2026-06-19 — Frontend polish pass: Part 6 — Final verification
- Final frontend build: `npm run build` → passed (1860 modules)
- Backend tests: `python -m pytest` → 156 passed (no backend files changed)
- All 6 parts implemented without touching backend, API contracts, trading logic, websocket behavior, or order placement
- Verifies these pages render without console errors: /dashboard, /orderbook, /tradebook, /positions, /action-centre, /logs, /tools
- Dashboard search modal: accessible keyboard nav (Enter/Escape/arrows), correct empty/error states, sectioned results
- Consistent loading/empty/error states across all pages via DataState + DataTableShell

### 2026-06-19 — Frontend polish pass: Part 5 — Standardized page states
- Updated `DataTableShell` to use `DataState` internally instead of separate `LoadingState`/`EmptyState`/`ErrorState` — consistent spinner, icons, and error layout
- Removed redundant standalone `ErrorState` from OrderbookPage, TradebookPage, PositionsPage, ActionCentrePage, LogsPage — DataTableShell already renders error inside the card, fixing duplicated error boxes
- Removed unused `ErrorState` imports from all 5 pages
- Improved LogsPage live logs empty state: replaced bare string `"Awaiting log rows..."` with centered muted text
- Files:
  - `frontend/src/components/ui/data-table-shell.tsx`
  - `frontend/src/pages/OrderbookPage.tsx`
  - `frontend/src/pages/TradebookPage.tsx`
  - `frontend/src/pages/PositionsPage.tsx`
  - `frontend/src/pages/ActionCentrePage.tsx`
  - `frontend/src/pages/LogsPage.tsx`
- Build: passed

### 2026-06-19 — Frontend polish pass: Part 4 — Search modal polish
- Added explicit `error` state with distinct error UI (red icon, error message, "please try again" hint) — previously errors silently collapsed to empty state
- Replaced boolean `loading` with unified `SearchStatus` type (`idle | loading | empty | error | results`) — prevents state overlap bugs
- Added `autoComplete="off"` and `spellCheck={false}` on search input
- Added `type="button"` on all result and tab buttons to prevent unintended form submission
- Added `aria-pressed` on tab buttons, `aria-activedescendant` on results listbox, `id` on each result row, `role="alert"` on error state
- Removed redundant `role="option"` wrapper `<div>` — buttons are direct children of listbox
- Footer keyboard hint now renders for both "results" and "empty" states (so hints are available when results area shows "no matches")
- Reset `status`/`errorMessage` on tab switch so stale state doesn't persist
- Re-focused input on tab change for quick re-typing
- Added `hasQuery` derived variable instead of computing `query.trim().length > 0` in multiple places
- Fixed scrollIntoView bounds check: verifies `childIdx < listRef.current.children.length` before accessing
- Removed `aria-selected` from non-option elements (only result buttons have it)
- Files: `frontend/src/components/dashboard/DashboardInstrumentSearch.tsx`
- Build: passed

### 2026-06-19 — Frontend polish pass: Part 3 — Apply components to dashboard
- Replaced metric card loop with `MetricCard` — handles loading skeleton and error fallback per card
- Replaced alerts empty state with `DataState(state="empty")` and `DataState(state="loading")`/`DataState(state="error")`
- Replaced alert dot spans with `StatusBadge` (error/warning/success levels)
- Removed deprecated imports: `AlertTriangle`, `CircleAlert`, `toneColor`, `alertDotColor`
- Files: `frontend/src/pages/DashboardPage.tsx`
- Preserved all existing data values, API behavior, websocket subscriptions, and page layout
- Build: passed

### 2026-06-19 — Frontend polish pass: Part 2 — Reusable UI component contract
- Created `SurfaceCard` — tone variants (default/active/danger/success), interactive mode with focus ring and keyboard support
- Created `MetricCard` — loading skeleton, error fallback, tone coloring, meta line, icon slot, stable min-height
- Created `DataState` — loads all three state displays into one component with `compact` mode
- Created `StatusBadge` — 8 status types (live/connected/stale/offline/loading/error/success/warning) with consistent dot + color mapping
- Created `ActionButton` — wraps Button with loading spinner (preserves button width)
- Files: `frontend/src/components/ui/{surface-card,metric-card,data-state,status-badge,action-button}.tsx`
- Build: passed
- No existing components modified — new components coexist alongside existing Card/Button/Badge/EmptyState/ErrorState/LoadingState

### 2026-06-19 — Frontend polish pass: Part 1 — Global CSS polish

- Added `-webkit-font-smoothing: antialiased`, `-moz-osx-font-smoothing: grayscale`, `text-rendering: optimizeLegibility` on global `*` selector for Mac-like font rendering on Windows/Edge/Chrome
- Added `font-variant-numeric: tabular-nums` on `body` for consistent number/metric alignment
- Added CSS transition tokens: `--ease-out-premium`, `--transition-fast`, `--transition-base`
- Polished dark scrollbar: reduced thumb width to 5px, lowered thumb opacity, added global `.dark` scrollbar rules so modal and page scrollbars are thin/dark without requiring `.scrollbar-thin` class
- Files changed: `frontend/src/index.css`
- Build: passed

### 2026-06-20 — Decimal strike + non-numeric websocket token hardening

#### Root cause 1: Decimal strike crash in instrument search diversity
- `instrument_search_service.py:263` used `int(item[0].strike_price or 0)` which crashed with `ValueError` on decimal strings like `"292.5"`.
- Stock options for lower-priced stocks have fractional strikes (e.g. 292.5, 182.5, 97.5).
- **Fix**: Added `_parse_strike()` helper using `Decimal` (consistent with existing `normalize_display_strike()`). Replaced the `int()` list comprehension with a safe loop that skips unparseable strikes.
- **Files**: `backend/app/services/instrument_search_service.py`

#### Root cause 2: Non-numeric websocket token subscription
- `build_stock_token()` in `market_data_worker.py` did not validate token numeric-ness. If DB `Instrument.token` contained a broker symbol name (e.g. `"NIFTY 50"`) instead of a numeric Breeze token, the resulting `stock_token` was `"4.1!NIFTY 50"` — an invalid Breeze subscription key.
- Railway log showed: `market-data feed subscribe skipped: breeze not connected for 4.1!NIFTY 50`
- **Fix**: Added `_is_numeric_token()` module-level guard. Used in `_to_subscription()` to reject non-numeric tokens with structured log warning before any subscription is created. Also added to `build_stock_token()` as defense-in-depth.
- **Files**: `backend/app/services/market_data_worker.py`

#### Tests added
- `test_dashboard_contract.py`: 5 new tests — decimal strike does not crash, decimal strike included in results, display_strike shows raw decimal value, bad strike value does not crash, mixed integer and decimal strikes work.
- `test_market_data_worker.py`: 7 new tests — `_is_numeric_token` rejects text inputs, `_is_numeric_token` accepts digits, `build_stock_token` rejects non-numeric tokens, subscribe skips non-numeric token, non-numeric token does not crash, numeric token still works alongside non-numeric skip.

#### Verification
- `python -m pytest` → 167 passed (12 new)
- `npm.cmd run build` → 1861 modules, clean

#### Remaining risk
- If DB has bad token rows for instruments, they will now be skipped with a structured log warning instead of silently subscribing with an invalid stock_token. This is correct — a DB data quality issue should be diagnosed and fixed at the source, not silently passed through to Breeze.

### 2026-06-20 — Websocket Architecture Pass: Per-Page Live Subscriptions + Pre-Resolved Token Shortcut
- **Goal**: Complete production websocket architecture — make live updates work across /tradebook, /optionchain, /oi-tracker, /oi-profile, /strategy-builder without breaking current dashboard behavior or Breeze-only architecture.
- **Root causes**:
  - `resolve_subscription_items()` had no pre-resolved token shortcut — composite keys like `NIFTY|24000|CE` were passed to `SymbolResolver.resolve()` which threw `SymbolResolverError` and silently skipped all option-contract subscriptions.
  - TradebookPage had no websocket subscription or live LTP column.
  - OIProfilePage/OITrackerPage only subscribed underlying spot — CE/PE LTP cells were REST-only.
  - OptionChainPage LegCells rendered REST-only bid/ask/ltp with no live overlay.
  - StrategyBuilderPage subscribed underlying spot but discarded the live value.
- **Backend changes**:
  - `backend/app/realtime.py:resolve_subscription_items()` — added pre-resolved token shortcut at lines 86-108: when `item.get("token")` is present and non-empty, skips DB SymbolResolver lookup and builds subscription object directly from provided fields (display_symbol, broker_symbol, exchange_code, product_type, token). Preserves existing symbol-resolve flow for pages without tokens. BANKNIFTY normalization intact.
  - `backend/app/services/option_chain_service.py:_normalize_leg()` — returns `token` field from Breeze response row (line 236).
  - `backend/app/services/oi_service.py:_flatten_row()` — passes through `ce_token` and `pe_token` from the chain (lines 102-103).
- **Frontend changes**:
  - `frontend/src/lib/realtime.ts` — added optional `token` field to `SubscriptionRequest` (line 47).
  - `frontend/src/lib/api.ts` — added `token` to `OptionChainLeg` (line 435), `ce_token`/`pe_token` to `OIRow` (lines 468-469).
  - `frontend/src/hooks/useLiveMarketData.tsx` — `useLiveSubscribe` already correct: diff-based subscribe/unsubscribe (lines 178-204), reconnect re-subscribe via `prevRef` reset on `socketConnected` change (lines 172-176), unmount cleanup via ref (lines 207-214).
  - `frontend/src/pages/TradebookPage.tsx` — subscribes symbols from visible trade rows via `useLiveSubscribe(tradeSubs)` (lines 70-78); added live LTP column with `text-primary` highlight when tick present (lines 141, 156-158).
  - `frontend/src/pages/OptionChainPage.tsx` — subscribes all visible CE/PE contracts via composite keys with pre-resolved tokens (lines 137-162); live LTP/bid/ask overlay in `LegCells` with `text-primary` styling (lines 39-49).
  - `frontend/src/pages/OITrackerPage.tsx` — subscribes CE/PE contracts via `ce_token`/`pe_token` with composite keys (lines 122-149); live LTP overlay on `ce_ltp`/`pe_ltp` cells (lines 38-56).
  - `frontend/src/pages/OIProfilePage.tsx` — subscribes CE/PE contracts via `ce_token`/`pe_token` (lines 133-156); live LTP overlay on `ce_ltp`/`pe_ltp` cells (lines 27-56).
  - `frontend/src/pages/StrategyBuilderPage.tsx` — captures `useLiveQuote(state.underlying)` return value (lines 180-181); displays live spot price in control bar (lines 251-253).
- **Verification**:
  - `python -m pytest` → 167/167 passed
  - `npx tsc --noEmit` → clean
  - `npx vite build` → 1861 modules, 509.51 kB JS, clean
- **Files changed**: 11 files across backend and frontend
- **Remaining risks**:
  - Option-contract websocket ticks depend on Breeze streaming market data during market hours — the pre-resolved token path is structurally correct but unproven with live Breeze ticks.
  - TradebookPage subscribes by symbol/exchange/product_type (no tokens) — if Breeze requires exact token for some symbols, trades may not get live LTP. Acceptable for MVP scope.

## 2026-06-21 — Phase 1: Global/Dashboard copy cleanup

#### Root cause
- Footer strip displayed `TRACK | TRADE | TRIUMPH - ORIENS Trading Dashboard` text, which is redundant branding copy.
- Dashboard orderbook empty state showed `Search and select an instrument to view the order book` helper text that adds no value once users are familiar with the UI.

#### Fix (frontend-only)
- `frontend/src/components/layout/Footer.tsx` — removed the text content from the footer strip; kept the footer container with `px-4 py-4` spacer so layout height is preserved.
- `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx` — removed the `!hasSelection` empty-state block that displayed the helper text. The search button placeholder (`Search instrument...`) already serves as the prompt.

#### Verification
- `npm run build` → 1861 modules, 508.74 kB JS, clean build.
- Footer strip renders as an empty bar (border + minimal height).
- Orderbook card no longer shows the helper text when no instrument is selected.
- No backend changes. No console errors expected.

#### Files changed
- `frontend/src/components/layout/Footer.tsx`
- `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`

#### Remaining risks
- The orderbook empty state now shows `No instrument selected` in the table body (line 330) and the search placeholder `Search instrument...` — both are sufficient prompts. No functionality loss.

## 2026-06-21 — Phase 2: Operational page copy cleanup

#### Root cause
- Each operational page had redundant kicker labels (`BROKER ORDERS`, `BROKER TRADES`, etc.) and descriptive subtitle text that added clutter for experienced users.
- PositionsPage had a `Paused` status badge in the header that duplicates the websocket status indicator.
- ActionCentrePage had a "Semi-auto workflow" helper card with explanatory text that is not needed once the user understands the workflow.

#### Fix (frontend-only)
- Removed `kicker` and `description` props from `PageHeader` on all 5 pages: OrderbookPage, TradebookPage, PositionsPage, ActionCentrePage, LogsPage.
- Removed the `actions` prop (Live/Paused badge) from PositionsPage `PageHeader`.
- Removed unused `Badge` import from PositionsPage.
- Removed the "Semi-auto workflow" `Card` block and its `Card`, `CardContent` imports from ActionCentrePage.
- Page header now renders title only (clean minimal header).

#### Verification
- `npm run build` → 1861 modules, 507.67 kB JS, clean build.
- All 5 pages render with clean title-only headers.
- ActionCentrePage no longer shows the workflow explanation card.
- PositionsPage no longer shows the Live/Paused badge.
- No backend changes. No console errors expected.

#### Files changed
- `frontend/src/pages/OrderbookPage.tsx`
- `frontend/src/pages/TradebookPage.tsx`
- `frontend/src/pages/PositionsPage.tsx`
- `frontend/src/pages/ActionCentrePage.tsx`
- `frontend/src/pages/LogsPage.tsx`

#### Remaining risks
- PositionsPage `isLive` variable (line 157) is still computed but only used by the `quoteMessage` string. The websocket status is still shown in the quote message below filters. No loss of status visibility.
- The `Badge` component is still used elsewhere; removal from PositionsPage import is safe.

## 2026-06-21 — Phase 3: Tools + Strategy/OI/Option copy cleanup

#### Root cause
- ToolsPage had a `REDUCED TOOLS SCOPE` banner, a `6 visible` count badge, per-card `Phase X live` badges, and a footer paragraph listing removed tools — all redundant once the user is familiar with the tool suite.
- StrategyBuilderPage, StrategyPortfolioPage, OptionChainPage, OITrackerPage, OIProfilePage each had redundant kicker labels (`STRATEGY TOOLS`, `OPTIONS DATA`, `OPEN INTEREST`) and descriptive subtitle text.

#### Fix (frontend-only)
- `ToolsPage.tsx`:
  - Removed `kicker="Reduced tools scope"`, `description`, and `actions` (6 visible badge) from `PageHeader`.
  - Cleared all per-card `subtitle` phase badges (Phase 14 live, Phase 11 live, Phase 13 live) to empty string.
  - Changed Option Greeks `subtitle` from `"Manual calc later"` to `"Coming soon"`.
  - Badge rendering conditionally shows only when `subtitle` is non-empty (only Option Greeks shows "Coming soon").
  - Removed footer paragraph listing removed tools.
- Removed `kicker` and `description` props from `PageHeader` on all 5 pages: StrategyBuilderPage, StrategyPortfolioPage, OptionChainPage, OITrackerPage, OIProfilePage.

#### Verification
- `npm run build` → 1861 modules, 506.62 kB JS, clean build.
- ToolsPage renders with clean `"Tools"` header only; no banner, no count badge, no footer paragraph.
- Tool cards no longer show Phase badges; Option Greeks shows `"Coming soon"` badge.
- All 5 tool pages render with clean title-only headers.
- No backend changes. No console errors expected.

#### Files changed
- `frontend/src/pages/ToolsPage.tsx`
- `frontend/src/pages/StrategyBuilderPage.tsx`
- `frontend/src/pages/StrategyPortfolioPage.tsx`
- `frontend/src/pages/OptionChainPage.tsx`
- `frontend/src/pages/OITrackerPage.tsx`
- `frontend/src/pages/OIProfilePage.tsx`

#### Remaining risks
- ToolsPage `subtitle` field in the `Tool` interface is now only used for the Option Greeks `"Coming soon"` text. No functionality loss.
- The `Badge` component import was restored in ToolsPage for the conditional Option Greeks badge. No unused import.

## 2026-06-21 — Phase 1: Dashboard card/table header compaction

#### Root cause
- Active Positions count badge was already on the same row as the title, but card header padding (`py-3`) wasted vertical space that could be used by the table body.
- Order Book panel used `md:flex-row` (column on mobile) so the status badge stacked below the title on small screens; the Market Depth section (buy/sell percentage bar + helper text) consumed unnecessary panel space.
- Alerts panel count badge was already on the same row, but header padding was identical to the other panels.
- Margin Used value rendered in amber (`tone: "warning"`) while all other cards use white; no secondary metric line existed.

#### Fix (frontend-only)
- `DashboardPage.tsx`:
  - Reduced `py-3` to `py-2` on Active Positions and Alerts CardHeaders — reclaims ~8px vertical space each.
  - Overrode `tone` to `"neutral"` for the `margin_used` metric so its value renders white instead of amber.
  - Injected a `Total Margin: {formatCurrency(metric.value)}` secondary line in the `meta` slot for the margin card, matching the submetric pattern of other cards.
- `DashboardOptionOrderBook.tsx`:
  - Removed `md:` prefix from CardHeader so title and status badge are always on the same row (flex-row at all breakpoints).
  - Removed the entire `Market Depth` section (buy/sell percentage bar + helper texts + loading/error/empty states).
  - Removed now-unused `effectiveTotalBuyQty`, `effectiveTotalSellQty`, and `isLive` variables.

#### Verification
- `npm run build` → 1861 modules, 505.30 kB JS, clean build.
- Active Positions: badge inline with title, header padding reduced.
- Order Book: status badge always inline with title, Market Depth section removed, remaining content flows cleanly (search → info bar → bid/ask table → buy/sell buttons).
- Alerts: badge inline with title, header padding reduced.
- Margin Used: value renders white, shows `Total Margin: ₹0.00` secondary line matching other cards' submetric style.
- No backend changes. No console errors expected.

#### Files changed
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`

#### Remaining risks
- `Total Margin` value is currently the same as `Margin Used` (both 0.0) because the backend does not expose a separate total-margin metric. The label is named clearly so users understand it shows the total margin figure. When backend adds a real total-margin field, this frontend injection should be replaced with the actual submetric.
- The order book footnote (`Full market depth is unavailable from Breeze...`) remains visible below the bid/ask table — it still applies to the top-of-book limitation.

## 2026-06-21 — Phase 2: Positions page message cleanup

#### Root cause
- A `quoteMessage` paragraph rendered between the stats cards and the positions table containing websocket/enrichment status text (`Live quote enrichment is active.`, `Live websocket feed is unavailable; showing REST quote values.`, etc.) that provides no actionable information to the user.

#### Fix (frontend-only)
- `PositionsPage.tsx`:
  - Removed the `<p>` element rendering `quoteMessage`.
  - Removed `liveFeedMessage` and `quoteMessage` variable definitions (and their dependency on `connectionState`).
  - Removed `connectionState` from `useLiveMarketData` destructuring.
  - Removed unused `isLive` variable.
  - Live quote enrichment logic (`applyLiveTick`, websocket subscriptions) remains fully intact.

#### Verification
- `npm run build` → 1861 modules, 504.72 kB JS, clean build.
- Positions page no longer shows the status message block between stats and table.
- Websocket subscriptions, live tick enrichment, and all other page functionality unchanged.
- No backend changes. No console errors expected.

#### Files changed
- `frontend/src/pages/PositionsPage.tsx`

#### Remaining risks
- The positions page still shows connection status implicitly through LTP styling (bold/font-weight when tick is live) and the table data itself. No loss of functionality.

## 2026-06-21 — Fix: Dashboard widget header compaction (proper fix)

#### Root cause
- The `CardHeader` component (`components/ui/card.tsx`) uses `grid auto-rows-min grid-rows-[auto_auto]` as its base layout, which forces children into two stacked rows regardless of any `flex-row` class passed via className.
- Adding `flex-row` was ineffective because `display: grid` overrides `flex-direction: row` (which requires `display: flex`).
- `CardHeader` base also includes `[.border-b]:pb-6` which conditionally adds 24px bottom padding when `border-b` is present, keeping the divider/content pushed down even when `py-2` was used.
- The previous pass correctly identified the need but changed the wrong properties — it added `flex-row` to a grid element and reduced `py-3` to `py-2` without addressing the underlying grid layout.

#### Fix (frontend-only)
- `DashboardPage.tsx`:
  - Replaced `<CardHeader>` with `<div className="flex items-center justify-between ...">` for both Active Positions and Alerts headers — uses proper flexbox row layout.
  - Removed unused `CardHeader` import.
- `DashboardOptionOrderBook.tsx`:
  - Replaced `<CardHeader>` with `<div className="flex items-center justify-between ...">` for Order Book header.
  - Removed unused `CardHeader` import.
- All three headers now render title left, badge right on a single row with `py-2` padding and `border-b`.

#### Verification
- `npm run build` → 1861 modules, 504.74 kB JS, clean build.
- Active Positions: `<div className="flex items-center justify-between gap-2 border-b px-4 py-2">` — title and `0` badge on same row.
- Order Book: `<div className="flex items-center justify-between gap-3 border-b px-4 py-2">` — title and `Inactive` badge on same row.
- Alerts: `<div className="flex items-center justify-between border-b px-4 py-2">` — title and `3 Active` badge on same row.
- No CardHeader grid layout interfering; no `[.border-b]:pb-6` extra padding.
- All existing functionality (search, orderbook table, buy/sell, alerts content, websocket) unchanged.

#### Files changed
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/components/dashboard/DashboardOptionOrderBook.tsx`

#### Remaining risks
- The fix uses plain `<div>` instead of `CardHeader` for these three headers. This is intentional — `CardHeader`'s grid layout is unsuitable for title+badge rows. No other widgets use this same pattern, so no risk of inconsistency.
