---
phase: 07-alpaca-execution-alerting
plan: 02
subsystem: execution
tags: [alpaca, bracket-orders, celery, fastapi, position-sync, orphan-detection]

requires:
  - phase: 07-alpaca-execution-alerting/07-01
    provides: Settings fields (ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER, ENABLE_SHORT_SIDE, STOP_LOSS_PCT, TAKE_PROFIT_PCT), Wave 0 test stubs
  - phase: 06
    provides: check_phase7_gate() in backtest/alerts.py, backtest_runs gate_status column

provides:
  - TradingClient singleton (lru_cache) in app.execution.broker
  - submit_bracket_order(): bracket order with limit=ask+0.5tick, stop=entry*0.98, tp=entry*1.04
  - reconcile_positions_with_alpaca(): INSERT-only hypertable snapshot on qty discrepancy
  - detect_and_cancel_orphans(): 60s grace period filter on orphaned sell orders
  - POST /api/v1/orders FastAPI endpoint via asyncio.to_thread wrapper
  - sync_positions_task Celery task on portfolio queue, 900s beat schedule
  - Phase 7 startup gate check in lifespan with SKIP_GATE_CHECK test guard

affects: [07-03, 07-04, signal-engine]

tech-stack:
  added: [alpaca-py==0.43.4 (already in requirements), asyncio.to_thread pattern]
  patterns:
    - "TradingClient singleton via lru_cache - one client per process lifetime"
    - "asyncio.to_thread() wrapping synchronous SDK calls in async FastAPI handlers"
    - "Hypertable append semantics - INSERT new snapshot, never UPDATE portfolio_positions"
    - "SKIP_GATE_CHECK env var guards lifespan gate check for test isolation"
    - "Lazy-import pattern avoided - module-level imports for mockable patch targets"

key-files:
  created:
    - backend/app/execution/__init__.py
    - backend/app/execution/broker.py
    - backend/app/execution/position_sync.py
    - backend/app/execution/orphan_detector.py
    - backend/app/routers/orders.py
    - backend/app/tasks/execution.py
    - backend/tests/execution/test_broker.py
    - backend/tests/execution/test_position_sync.py
    - backend/tests/execution/test_orphan_detector.py
    - backend/tests/tasks/test_execution_task.py
    - backend/tests/test_orders_router.py
  modified:
    - backend/app/worker.py
    - backend/app/main.py
    - backend/tests/conftest.py

key-decisions:
  - "Entry price = ask + 0.5 tick (TICK_SIZE=0.01, HALF_TICK=0.005) per locked decision"
  - "Stop-loss = entry * 0.98, take-profit = entry * 1.04 per locked decision"
  - "Short orders blocked by ValueError when ENABLE_SHORT_SIDE=False before any Alpaca call"
  - "Position reconciliation uses INSERT-only hypertable append, never UPDATE"
  - "Orphan grace period = 60 seconds to avoid false positives on just-submitted orders"
  - "TradingClient module-level import in tasks/execution.py (not lazy) to enable patching"
  - "SKIP_GATE_CHECK=1 in conftest.py before app import prevents gate check during tests"

patterns-established:
  - "asyncio.to_thread(sync_fn, *args): all synchronous alpaca-py calls wrapped this way"
  - "Celery beat schedule in worker.conf.update() beat_schedule dict"
  - "Test isolation: os.environ.setdefault('SKIP_GATE_CHECK', '1') at top of test files"

requirements-completed: [FR-7.1, FR-7.2, FR-7.3, FR-7.6]

duration: 35min
completed: 2026-05-13
---

# Phase 7 Plan 02: Execution Module Summary

**Alpaca paper trading execution layer: bracket order submission, position reconciliation, orphan detection, POST /api/v1/orders router, and 15-minute Celery beat sync wired into FastAPI lifespan with Phase 7 gate check.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-13T08:17:00Z
- **Completed:** 2026-05-13T08:52:00Z
- **Tasks:** 2 of 2
- **Files modified:** 13 (11 created, 2 modified + conftest update)

## Accomplishments

### Task 1: execution/ module

Created `backend/app/execution/` with three production modules:

**broker.py**: `get_trading_client()` singleton using `lru_cache(maxsize=1)`. `submit_bracket_order(symbol, qty, side, ask_price)` computes entry price as `ask + 0.005` (0.5 tick), stop as `entry * 0.98`, take-profit as `entry * 1.04`, all via `Decimal` arithmetic with `.quantize(TICK_SIZE)`. Returns dict including `filled_qty` from order response (partial fill support). Raises `ValueError("short orders disabled")` when `side="sell"` and `ENABLE_SHORT_SIDE=False`.

**position_sync.py**: `reconcile_positions_with_alpaca(session)` fetches all Alpaca positions, compares qty against DB `MAX(snapshot_at)` row per symbol, and INSERTs a new snapshot row when discrepancy exists. Returns discrepancy count. All SQL uses `sqlalchemy.text()` with bound params.

**orphan_detector.py**: `detect_and_cancel_orphans(session)` fetches open orders from Alpaca, filters to SELL side only, skips orders newer than 60 seconds (grace period), queries active DB positions using `DISTINCT ON (symbol)`, and calls `cancel_order_by_id()` for each orphan. Handles both naive and tz-aware datetimes from the SDK.

### Task 2: router, task, and infrastructure wiring

**backend/app/routers/orders.py**: `POST /api/v1/orders` with `OrderRequest` pydantic model (symbol, qty, side, ask_price). Calls `asyncio.to_thread(submit_bracket_order, ...)`. Returns 400 on `ValueError` (short side blocked), 502 on any other Alpaca failure.

**backend/app/tasks/execution.py**: `sync_positions_task` Celery task registered as `app.tasks.execution.sync_positions_task`. Uses `sync_session()` context manager from `app.flows._base`.

**worker.py**: Added `beat_schedule` with `sync-positions-every-15min` at 900.0 seconds. Added `app.tasks.execution.*` to `task_routes` with `portfolio` queue.

**main.py**: Gate check in lifespan using `SyncSessionLocal` + `check_phase7_gate()`. Guarded by `SKIP_GATE_CHECK` env var. `orders.router` registered with prefix `/api/v1`.

**conftest.py**: `os.environ.setdefault("SKIP_GATE_CHECK", "1")` added before `from app.main import app` to prevent gate check from failing tests.

## Test Results

All 15 new tests pass (8 execution module + 4 task + 3 orders router):

```
tests/execution/test_broker.py - 4 passed
tests/execution/test_position_sync.py - 2 passed
tests/execution/test_orphan_detector.py - 2 passed
tests/tasks/test_execution_task.py - 4 passed
tests/test_orders_router.py - 3 passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lazy import in tasks/execution.py prevented mock patching**
- **Found during:** Task 2 test run
- **Issue:** `reconcile_positions_with_alpaca` was imported inside the task function body (lazy), making `@patch("app.tasks.execution.reconcile_positions_with_alpaca")` fail with AttributeError
- **Fix:** Moved import to module level in `tasks/execution.py`
- **Files modified:** `backend/app/tasks/execution.py`
- **Commit:** 193c95df

**2. [Rule 2 - Missing functionality] Orphan detector timezone handling**
- **Found during:** Task 1 implementation
- **Issue:** Alpaca SDK can return both naive and tz-aware `submitted_at` datetimes; comparing with tz-aware `cutoff` would raise TypeError
- **Fix:** Added explicit tzinfo check: naive datetimes are treated as UTC before comparison
- **Files modified:** `backend/app/execution/orphan_detector.py`
- **Commit:** e285d819

## Known Stubs

None. All exported functions are fully implemented with real logic.

## Threat Surface Scan

All threat mitigations from the plan's `<threat_model>` are implemented:

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-07-02-01 | Mitigated | OrderRequest pydantic model: qty>0, side pattern, symbol 1-10 chars, ask_price>0 |
| T-07-02-02 | Mitigated | ValueError raised in submit_bracket_order() before any Alpaca call |
| T-07-02-03 | Mitigated | RuntimeError in lifespan blocks startup; SKIP_GATE_CHECK only in test mode |
| T-07-02-04 | Mitigated | asyncio.to_thread() in create_order handler |
| T-07-02-05 | Accepted | ALPACA_API_KEY never passed to logger |

No new trust boundaries introduced beyond those in the plan's threat model.

## Self-Check: PASSED

All 6 production files confirmed present. All 3 task commits confirmed in git log.
