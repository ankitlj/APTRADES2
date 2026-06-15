# APTRADES v2 Diagnosis-First Operating Protocol

## Principle

Stop symptom-driven patching. Before changing code, prove whether a real problem exists, measure its size, identify the owning layer, and only then choose the smallest fix that directly attacks the verified root cause.

## When to use this protocol

1. A page feels slow.
2. A live value feels stale.
3. A websocket appears unstable.
4. A user says "this should be better" but the code path is not yet proven wrong.
5. Multiple possible causes exist and random patching would waste time.

## Mandatory workflow: do not skip steps

Every serious issue must go through Steps A-H before any code change. Collect evidence, classify the root cause, then fix.

### Step A: Confirm the problem is real

1. Open the affected page.
2. Note what the user visually sees.
3. Refresh once.
4. Wait a fixed amount of time.
5. Check whether the symptom repeats.
6. If the symptom does not repeat, do not patch yet; mark it as intermittent and continue diagnostics.

### Step B: Capture the frontend evidence

1. Open browser devtools.
2. Check console errors.
3. Check network requests for the affected page.
4. Note:
   - request URL
   - response code
   - response time
   - response payload shape
5. If the frontend shows an error but the API returned valid data, classify as frontend/UI-state candidate.
6. If the API itself is slow or broken, continue to backend diagnosis.

### Step C: Capture the API evidence

1. Re-run the exact API route directly (use curl, browser, or `/api/diagnosis/trace`).
2. Measure:
   - start time
   - end time
   - total duration
   - status code
3. Compare API behavior across:
   - cold request
   - immediate second request
   - page revisit
4. If the second request is much faster, caching may be the real issue.
5. If both are slow, backend or upstream is the stronger candidate.

### Step D: Capture backend route timing

1. Add route timing logs if they do not already exist (use `diagnosis.RouteTimer`).
2. Log total route duration for the affected route.
3. Log each major internal step:
   - DB read
   - Redis read
   - Breeze REST call
   - websocket snapshot read
   - serialization
4. Compare which step takes the most time.
5. Only the slowest verified step should be treated as the primary bottleneck.

### Step E: Capture Redis / cache behavior

1. Check whether the route reads Redis.
2. Check whether the expected cache key exists.
3. Log:
   - cache hit
   - cache miss
   - age of cached data
   - fallback path used
4. If Redis had fresh data but route still called Breeze REST, root cause is likely service-path design.
5. If Redis had no useful data, continue to websocket or upstream diagnosis.

### Step F: Capture websocket / live-worker evidence

1. Check worker state from `/api/market-data/status`:
   - offline
   - connecting
   - live
   - degraded
2. Log:
   - connect count
   - reconnect count
   - disconnect reason
   - last tick timestamp
   - gap duration
   - active subscriptions
3. Verify whether the live worker is receiving ticks during the complaint window.
4. If ticks are arriving but UI is stale, frontend/state path is wrong.
5. If ticks are not arriving, runtime or upstream is wrong.

### Step G: Capture infrastructure evidence

1. Check Railway deployment logs.
2. Check for:
   - worker restart
   - worker timeout
   - memory pressure
   - `/socket.io` errors
   - boot loop
3. If infra errors line up with user-facing errors, classify as runtime/infra primary.
4. Do not patch business logic first when runtime is clearly failing.

### Step H: Capture broker / upstream evidence

1. Log every Breeze request duration (use `/api/diagnosis/broker`).
2. Log request outcome:
   - success
   - timeout
   - auth failure
   - malformed payload
   - empty data
3. Compare:
   - broker response time
   - backend route time
4. If broker time dominates, do not blame frontend.
5. If broker data is missing but route is fast, surface degraded state instead of adding retries blindly.

## Decision rule after evidence collection

1. Write one sentence for the confirmed primary bottleneck.
2. List secondary contributing factors, if any.
3. Reject any fix that does not directly target the primary bottleneck.
4. Prefer the smallest fix that:
   - reduces latency
   - reduces uncertainty
   - preserves correctness
   - minimizes infra/broker cost

## Fix-selection order

1. Runtime fix first if workers or sockets are unstable.
2. Read-path fix second if Redis/live data exists but is not being used.
3. Concurrency / caching fix third if upstream calls are serial and expensive.
4. Frontend render-state fix fourth if data is already correct but the page presents it badly.
5. UX labeling fix fifth if the system is correct but user interpretation is unclear.

## Mandatory post-fix verification

1. Reproduce the original issue again.
2. Re-measure the same metrics collected before the fix.
3. Compare:
   - before duration
   - after duration
   - before error rate
   - after error rate
   - before user-visible state
   - after user-visible state
4. If the measured result did not improve materially, the fix is not complete.
5. Only then update docs and move to the next issue.

## Diagnosis record template

For each serious issue, create a record in `development.md` using this template:

```
1. Issue:
2. Expected behavior:
3. Observed behavior:
4. Environment:
5. Reproduction steps:
6. API evidence:
7. Backend timing evidence:
8. Redis/cache evidence:
9. Websocket evidence:
10. Infra evidence:
11. Broker evidence:
12. Confirmed root cause:
13. Chosen fix:
14. Post-fix verification:
15. Remaining risk:
```

## Diagnostic API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/diagnosis/trace?route=<path>` | Time a specific route end-to-end |
| `GET /api/diagnosis/cache` | Check Redis cache health and keys |
| `GET /api/diagnosis/broker` | Check Breeze broker response times |
| `GET /api/diagnosis/worker` | Check websocket worker state |
| `GET /api/debug/breeze-auth` | Verify Breeze authentication |
| `GET /api/debug/breeze-test` | Test Breeze symbol quotes |

## Common symptom-to-layer mapping

| Symptom | Primary layer to check |
|---|---|
| Page loads slowly (>3s) | Backend timing (Step D) |
| Prices not updating | Frontend state (Step B) or worker (Step F) |
| Live/degraded flicker | Websocket runtime (Step F, Step G) |
| Error message not useful | API contract (Step C) |
| Historical data missing | Broker/upstream (Step H) |
| Chart rendering issue | Frontend render (Step B) |
| Order not appearing | Broker (Step H) or cache (Step E) |
