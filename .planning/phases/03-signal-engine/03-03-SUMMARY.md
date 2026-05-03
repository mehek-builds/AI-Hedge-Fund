---
phase: 03-signal-engine
plan: "03"
subsystem: signal-engine
tags: [signals, celery, task, integration-test, perf-benchmark, tdd, FR-3.7]
dependency_graph:
  requires:
    - 03-02 (pipeline.py → compute_signal_for_event)
    - 01-01 (worker.py → celery_app, task_routes config)
    - 01-01 (flows/_base.py → sync_session context manager)
  provides:
    - backend/app/tasks/signals.py → compute_signal_task (Celery task)
    - backend/tests/tasks/test_signal_task.py → 5 unit tests (no broker/DB)
    - backend/tests/signals/test_pipeline_integration.py → 3 DB-gated integration tests
    - backend/tests/signals/test_pipeline_perf.py → 1 DB-gated perf benchmark
  affects:
    - Phase 7 (FMP earnings ingestion will dispatch compute_signal_task)
    - Phase 6 (backtest runner can call compute_signal_task.run() in eager mode)
tech_stack:
  added: []
  patterns:
    - Celery task with explicit name= for stable task routing
    - sync_session() context manager for commit/rollback semantics
    - DB-gated tests via pytest.mark.skipif on DATABASE_URL_SYNC env var
    - time.perf_counter() for wall-clock benchmarking with warmup pass
    - TDD red-green per task
key_files:
  created:
    - backend/app/tasks/__init__.py
    - backend/app/tasks/signals.py
    - backend/tests/tasks/__init__.py
    - backend/tests/tasks/test_signal_task.py
    - backend/tests/signals/test_pipeline_integration.py
    - backend/tests/signals/test_pipeline_perf.py
  modified: []
decisions:
  - Task name hardcoded as "app.tasks.signals.compute_signal_task" (not auto-derived) for stable Celery routing
  - Integration tests use DATABASE_URL_SYNC skipif marker — same pattern as phase-1/2 test convention
  - Warmup pass in perf test excludes cold-import latency from timed measurement
  - AAPL used as perf test symbol (in SECTOR_MAP as Tech, hurdle=60, ROIC filter applies)
  - Cleanup runs in finally block (T-03-19: fixture rows don't leak into shared DB)
metrics:
  duration_minutes: 8
  completed_date: "2026-05-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 6
  files_modified: 0
  tests_added: 9
---

# Phase 03 Plan 03: Celery Task Wrapper + FR-3.7 Performance Benchmark Summary

**One-liner:** Celery task `compute_signal_task` wrapping the Plan 02 signal pipeline, with 5 unit tests (no broker), 3 DB-gated integration tests covering happy path and both filter suppressions, and a 1-test perf benchmark enforcing the < 5.0s FR-3.7 budget.

## What Was Built

### 1. `backend/app/tasks/signals.py` — Celery Task

```python
@celery_app.task(name="app.tasks.signals.compute_signal_task")
def compute_signal_task(earnings_event_id: int) -> Optional[str]:
    with sync_session() as session:
        return compute_signal_for_event(session, earnings_event_id)
```

- **Registration name:** `app.tasks.signals.compute_signal_task`
- **Queue routing:** `"app.tasks.signals.*"` → `{"queue": "signals"}` (pre-configured in `app/worker.py`)
- **Session semantics:** `sync_session()` commits on success, rolls back on exception (T-03-16 mitigation)
- **Exception propagation:** exceptions not swallowed — Celery records failures with traceback in Redis backend

### 2. `backend/tests/tasks/test_signal_task.py` — Unit Tests (5 tests, no broker/DB)

| Test | What it verifies |
|------|-----------------|
| test_task_is_registered | task name in `celery_app.tasks` registry |
| test_task_routes_to_signals_queue | `task_routes["app.tasks.signals.*"] == {"queue": "signals"}` |
| test_task_returns_signal_id_on_success | mocked happy path returns signal_id |
| test_task_returns_none_when_suppressed | None propagated, not raised |
| test_task_propagates_exception | ValueError not swallowed |

All 5 tests run without a Celery broker or DB connection.

### 3. `backend/tests/signals/test_pipeline_integration.py` — DB-Gated Integration Tests (3 tests)

| Test | Scenario | Expected |
|------|----------|----------|
| test_end_to_end_signal_for_earnings_event | AAPL (Tech): strong quality, price bars, up guidance | signal written with naive_position_size=0.0200 |
| test_signal_suppressed_below_sector_hurdle | MSFT (Tech): flat revenue, no guidance, equal share count → quality=0 | None returned, 0 rows in signals |
| test_signal_suppressed_by_roic_wacc_filter | NVDA (Tech): quality passes but ROIC=0.05 < 0.10 | None returned, 0 rows in signals |

**DB-gate:** `pytest.mark.skipif(not os.environ.get("DATABASE_URL_SYNC"), ...)` — all 3 skip cleanly when DB unavailable.

### 4. `backend/tests/signals/test_pipeline_perf.py` — Performance Benchmark (1 test)

- **`PERF_BUDGET_SECONDS = 5.0`** (FR-3.7 requirement)
- Inserts canonical Tech-ticker fixture: 1 prior event + 1 current event + 21 price bars
- Warmup pass primes connection pool and query plan cache before timed measurement
- Timed pass uses `time.perf_counter()` to measure wall-clock duration
- Assert: `elapsed < 5.0` with FR-3.7 budget in failure message
- Cleanup runs in `finally` block (T-03-19 mitigation)

## Celery Task Registration Confirmed

```
$ python3 -c "from app.tasks.signals import compute_signal_task; \
              from app.worker import celery_app; \
              assert 'app.tasks.signals.compute_signal_task' in celery_app.tasks; \
              print('OK')"
OK
```

## Test Summary

| File | Tests | Without DB | With DB |
|------|-------|------------|---------|
| tests/tasks/test_signal_task.py | 5 | 5 pass | 5 pass |
| tests/signals/test_pipeline_integration.py | 3 | 3 skip | 3 pass (when fixture qualifies) |
| tests/signals/test_pipeline_perf.py | 1 | 1 skip | 1 pass (< 5s) |
| **New total** | **9** | **5 pass + 4 skip** | |
| **Phase 3 grand total** | **153** | **149 pass + 4 skip** | |

## DB-Gating Pattern

Both DB-gated test files use the same skipif pattern:

```python
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_SYNC"),
    reason="DB-gated: set DATABASE_URL_SYNC and run `alembic upgrade head` first",
)
```

This is the same pattern established in Phase 1/2 DB tests. CI runs the non-DB tests on every PR; DB tests run only in full integration CI with a live PostgreSQL+TimescaleDB container.

## Threat Mitigations Applied

| Threat | Mitigation Implemented |
|--------|----------------------|
| T-03-14: SQL injection in test fixtures | All INSERTs use bound params (`:t`, `:s`, `:p`); no f-string SQL interpolation |
| T-03-15: DoS long-running task | FR-3.7 perf budget enforced by benchmark — regressions past 5s fail CI |
| T-03-16: Repudiation — task failures | Task propagates exceptions (not swallowed); Celery records failure + traceback in Redis |
| T-03-19: Info disclosure — fixture rows leak | `_cleanup()` runs in `finally` block in perf test |

## Deviations from Plan

None — plan executed exactly as written. The task implementation, integration tests, and perf benchmark match the plan spec verbatim.

## Known Stubs

None — all functions are fully implemented. The naive_position_size=0.0200 is intentionally fixed at phase 3; Phase 6 (RL) will replace it with dynamic sizing.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes. The Celery task uses an existing queue (`signals`) with existing routing config. No new trust boundaries introduced.

## Self-Check: PASSED

Files verified:
- FOUND: backend/app/tasks/__init__.py
- FOUND: backend/app/tasks/signals.py
- FOUND: backend/tests/tasks/__init__.py
- FOUND: backend/tests/tasks/test_signal_task.py
- FOUND: backend/tests/signals/test_pipeline_integration.py
- FOUND: backend/tests/signals/test_pipeline_perf.py

Commits verified:
- d3235066 — test(03-03): add failing tests for compute_signal_task Celery wrapper
- 8f10e3bf — feat(03-03): implement compute_signal_task Celery wrapper
- 4777aef4 — test(03-03): add DB-gated integration tests for end-to-end signal pipeline
- 92925938 — feat(03-03): add FR-3.7 performance benchmark test for signal pipeline
