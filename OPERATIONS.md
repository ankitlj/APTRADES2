# APTRADES v2 Operations Runbook

Day-to-day operational tasks for the deployed app (Railway backend + Postgres + Redis, Vercel frontend). Phase 17 production hardening.

## 1. Daily Breeze session-token refresh

The Breeze API session token expires every day. While it is expired, all live quote / order / position / option-chain / websocket calls fail, but the app stays up and REST endpoints keep returning structured errors instead of crashing.

How to refresh:

1. Generate a fresh session token from the ICICI Breeze login flow (the `api_session` value).
2. In Railway, open the **backend service -> Variables** and update:
   - `BREEZE_SESSION_TOKEN` = the new token
3. Railway redeploys automatically. No code change is needed.
4. Confirm it worked:
   - `GET /api/health/readiness` -> `checks.breeze` should be `configured`.
   - `GET /api/debug/breeze-auth` -> `status: ok` with your `user_id`.

Never commit the token. Keep `BREEZE_API_KEY`, `BREEZE_SECRET_KEY`, and `BREEZE_SESSION_TOKEN` only in Railway/local env vars.

Symptom of an expired token: dashboard quotes stop updating, the live badge shows `degraded`, and `breeze-auth` returns an auth error. Refresh the token to recover.

> Decision still open: whether to keep this manual daily refresh or build an automated login/token routine later. Until automated, treat the manual refresh above as a daily task on trading days.

## 2. Daily master-contract refresh (Railway cron)

The instrument/master-contract data should be re-imported once a day, before market open. This does not need the Breeze token (it pulls ICICI SecurityMaster + the repo CSV).

Recommended: a dedicated Railway **cron service** in the same project, separate from the web service:

- New service from the same GitHub repo.
- Start command: `cd backend && flask --app run:app master-contract import`
- Variables: `DATABASE_URL = ${{Postgres.DATABASE_URL}}` (point at the same Postgres).
- Cron schedule (UTC): `30 2 * * *` = 08:00 IST daily, before the 09:15 open.

Verify after the first run: `GET /api/master-contract/status` -> `latest_run.status: success` and `instrument_count` ~127k.

## 3. Rate limiting

A default API rate limit is applied (`flask-limiter`). High-frequency paths are exempt: `/api/health*`, `/api/market-data*`, and `/socket.io`.

Tunable via env vars on the backend service:

- `RATELIMIT_DEFAULT` (default `600 per minute`) — the per-client default limit.
- `RATELIMIT_ENABLED` (default `1`) — set to `0` to disable entirely.

Storage uses Redis automatically when `REDIS_URL` is set, otherwise in-process memory. Rate-limited responses return the standard structured error shape with HTTP 429.

## 4. Health and readiness

- `GET /api/health` — liveness (always ok if the process is up).
- `GET /api/health/readiness` — `api`, `postgres`, `redis`, `breeze` (config-only, no network), `websocket` (live market-data worker state).
- `GET /api/health/deployment` — the above plus `master_contract` status.
- `GET /api/market-data/status` — websocket worker state for the live badge.

## 5. Diagnosis protocol

Before making any code change to fix a performance or stability issue, follow the protocol in `DIAGNOSIS.md`:

1. Collect evidence from frontend, API, backend timing, Redis/cache, websocket/worker, infra, and broker.
2. Classify the problem type.
3. Measure before and after the fix.
4. Use the diagnostic API endpoints:
   - `GET /api/diagnosis/trace?route=health` — time any route end-to-end
   - `GET /api/diagnosis/cache` — inspect Redis tick cache
   - `GET /api/diagnosis/broker` — test Breeze broker responsiveness
   - `GET /api/diagnosis/worker` — check websocket worker state
   - `GET /api/diagnosis/full` — aggregate all system checks
   - `GET /api/diagnosis/timing` — view collected timing records

All error responses across `/api/*` use one structured shape:

```json
{ "status": "error", "error": { "code": 404, "message": "..." } }
```

From this point onward, the project is renamed ORIENS.
