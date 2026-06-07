# APTRADES v2 Development Log

## Current Status
- Current phase: Phase 5 - Master Contract Import completion fix
- Last completed phase: Phase 5 - Master Contract Import
- Deployment status: Railway and Vercel deployed; DB/Redis/Breeze verified; master-contract import now uses the repo-contained StockScriptNew.csv plus seeded fallback when SecurityMaster is unreachable
- Known blockers:
  - Codex workspace permissions do not yet cover updating `C:\Users\Ankit\Desktop\Claude_Code\REBUILD.md`

## Environment
- Backend: Flask 3 skeleton
- Frontend: React + Vite + TypeScript skeleton
- Database: PostgreSQL online on Railway
- Cache: Redis online on Railway
- Broker: Breeze only, diagnostic gateway and master-contract import implemented
- Deployment: Railway + Vercel live

## Phase Log

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

## Manual Tasks Pending
- [ ] Retry the deployed master-contract import run after the repo-CSV deploy
- [ ] Verify the deployed master-contract panel after import
- [ ] Configure a daily Railway schedule for `flask master-contract import`
- [ ] Keep Breeze secrets and session token only in env vars
- [ ] Provide approval if external `Claude_Code` workspace file updates are required

## API Contracts Confirmed
- Endpoint: `GET /api/health`
- Request: no body
- Response: `{ "status": "ok", "service": "APTRADES v2", "timestamp": "<UTC ISO8601>" }`
- Test command: `curl http://127.0.0.1:5000/api/health`

- Endpoint: `GET /api/health/readiness`
- Request: no body
- Response: `{ "status": "ok", "checks": { "api": "online", "postgres": "not_configured", "redis": "not_configured", "breeze": "not_configured" }, "timestamp": "<UTC ISO8601>" }`
- Test command: `curl http://127.0.0.1:5000/api/health/readiness`

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

- Endpoint: `GET /api/master-contract/status`
- Request: no body
- Response: `{ "status": "ok|not_configured", "database_configured": true|false, "csv_available": true|false, "instrument_count": 33109, "alias_count": 35445, "latest_run": { "status": "success", "source_name": "stock_script_csv", ... } }`
- Test command: `curl http://127.0.0.1:5000/api/master-contract/status`

- Endpoint: `POST /api/master-contract/import`
- Request: no body
- Response: `{ "status": "ok", "row_count": 33109, "alias_count": 35445, "source_name": "stock_script_csv", "warnings": ["..."] }`
- Test command: `curl -X POST http://127.0.0.1:5000/api/master-contract/import`

## Deployment Notes
- Last commit: pending phase 5 repo-CSV fix commit
- Last deployed URL: `https://aptrades-2.vercel.app` and `https://web-production-39a4a.up.railway.app`
- Smoke test result: deployed readiness and Breeze diagnostics are verified; Phase 5 import now has a committed StockScriptNew.csv path plus fast-fail SecurityMaster handling
