---
phase: 09-hardening-deploy
plan: "02"
subsystem: testing
tags: [pytest, performance, nfr, sse, redis, asyncio, time-measurement]

# Dependency graph
requires:
  - phase: 08-frontend-dashboard
    provides: FastAPI SSE stream endpoint (/api/v1/events)
  - phase: 03-signal-engine
    provides: compute_signal_for_event() pipeline function
provides:
  - Performance regression guard for NFR-2 (signal < 5s) in CI
  - Performance regression guard for NFR-3 (SSE < 500ms) in CI
  - DB-gated test infrastructure for timing-based assertions
affects: [ci, 09-hardening-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Performance timing via plain time.time() wrap (no pytest-benchmark)"
    - "DB-gated performance tests with @requires_db skip behavior"
    - "SSE latency test via httpx ASGI streaming + aioredis publish"
    - "Synthetic test data cleanup in finally blocks (try/finally DELETE)"

key-files:
  created:
    - backend/tests/test_performance.py
  modified: []

key-decisions:
  - "Plain time.time() used instead of pytest-benchmark to avoid new test dependency"
  - "SSE latency measured from Redis publish moment, not before stream opens, to get accurate pub/sub delivery time"
  - "Signal test asserts on timing only (not return value) since filters may suppress signal"
  - "asyncio.wait_for(2.0s) on SSE read loop satisfies T-09-02-01 DoS threat mitigation"

patterns-established:
  - "Performance hard-assert pattern: start=time.time(); <work>; assert elapsed < N.N, f'took {elapsed:.2f}s'"
  - "SSE test pattern: open stream -> publish -> iterate aiter_lines() filtering data: prefix"

requirements-completed: [NFR-2, NFR-3]

# Metrics
duration: 15min
completed: 2026-05-13
---

# Phase 9 Plan 02: Performance Regression Tests Summary

**DB-gated pytest performance tests enforcing NFR-2 (signal computation < 5s) and NFR-3 (SSE delivery < 500ms) as hard CI assertions using plain time.time()**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-13T18:10:00Z
- **Completed:** 2026-05-13T18:25:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `test_signal_computation_under_5s`: inserts synthetic EarningsEvent + price_bars, calls compute_signal_for_event() via run_sync(), hard-asserts elapsed < 5.0s (NFR-2)
- `test_sse_latency_under_500ms`: opens httpx ASGI stream to /api/v1/events, publishes to Redis signals channel, hard-asserts time-to-first-data < 0.5s (NFR-3)
- Both tests skip cleanly with `@requires_db` when DATABASE_URL is unset (verified locally)
- No pytest-benchmark dependency added; plain time.time() consistent with project conventions

## Task Commits

Each task was committed atomically:

1. **Task 1: Write test_performance.py - signal computation and SSE latency tests** - `d3bd89d8` (feat)

## Files Created/Modified

- `backend/tests/test_performance.py` - Two DB-gated performance regression tests: NFR-2 signal timing and NFR-3 SSE latency, with synthetic data setup and try/finally cleanup

## Decisions Made

- Used named constants `SIGNAL_COMPUTE_THRESHOLD = 5.0` and `SSE_LATENCY_THRESHOLD = 0.5` for readability while keeping literal values in assert statements to satisfy CI grep verification
- SSE test measures latency from publish moment (not stream open) to capture actual pub/sub delivery time rather than connection overhead
- Signal test accepts None return from compute_signal_for_event() since sector hurdle filters may suppress the signal; test validates timing only

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for this test file. Tests skip automatically without DATABASE_URL set.

## Next Phase Readiness

- Performance regression tests are in place for NFR-2 and NFR-3
- Tests will run in CI when DATABASE_URL is set (Railway integration environment)
- No blockers for 09-01 (E2E integration test) or 09-03 (deploy gate static assertions)

---
*Phase: 09-hardening-deploy*
*Completed: 2026-05-13*
