---
phase: 07-alpaca-execution-alerting
plan: 04
subsystem: alerting
tags: [fastapi, sendgrid, slack, redis, celery, alerting, orders, backtest]

# Dependency graph
requires:
  - phase: 07-alpaca-execution-alerting/07-01
    provides: Alert ORM model, alerts DB migration, SendGrid dependency
  - phase: 07-alpaca-execution-alerting/07-02
    provides: orders router (POST /api/v1/orders), Celery beat task
  - phase: 07-alpaca-execution-alerting/07-03
    provides: dispatch_alert(), rate_limiter, templates (SendGrid+Slack delivery)
provides:
  - POST /api/v1/orders wired to dispatch_alert for order_submitted event (fire-and-forget via asyncio.create_task)
  - fire_gate_alert_v2() in backtest/alerts.py wired to real SendGrid+Slack dispatch
  - Complete Phase 7 end-to-end alerting integration
affects: [phase-08-dashboard, phase-09-production]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fire-and-forget async alerts from sync order handler via asyncio.create_task with own AsyncSessionLocal"
    - "Sync-to-async bridge in Celery context using asyncio.run() with lazy imports to avoid circular deps"

key-files:
  created: []
  modified:
    - backend/app/routers/orders.py
    - backend/app/backtest/alerts.py

key-decisions:
  - "Background alert task in orders router opens its own AsyncSessionLocal session (not request-scoped db) to ensure session is alive after handler returns"
  - "fire_gate_alert_v2 uses asyncio.run() with lazy imports inside try/except - preserves function signature/return value and avoids circular imports at module load time"
  - "All delivery failures are caught and logged but never re-raised (fire-and-forget semantics enforced at both call sites)"

patterns-established:
  - "Fire-and-forget alert pattern: asyncio.create_task(_fire_alert()) where _fire_alert opens own AsyncSessionLocal"
  - "Sync-context async dispatch: asyncio.run() wrapping dispatch_alert inside Celery task, lazy imports in try block"

requirements-completed: [FR-7.1, FR-7.2, FR-7.3, FR-7.4, FR-7.5, FR-7.6, FR-8.1, FR-8.2, FR-8.3, FR-8.4]

# Metrics
duration: 8min
completed: 2026-05-13
---

# Phase 7 Plan 04: Alert Wiring Summary

**POST /api/v1/orders and fire_gate_alert_v2 wired end-to-end to dispatch_alert for SendGrid+Slack+Redis delivery, completing Phase 7 alerting integration.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-13T08:54:00Z
- **Completed:** 2026-05-13T09:02:33Z
- **Tasks:** 1 completed (+ checkpoint)
- **Files modified:** 2

## Accomplishments

### Task 1: Wire dispatch_alert into orders router and gate alert

Updated `backend/app/routers/orders.py`:
- Added `dispatch_alert` import and `get_db` dependency injection
- Added `_get_redis()` helper returning sync Redis client from `settings.REDIS_PUB_URL`
- After successful `asyncio.to_thread(submit_bracket_order, ...)`, constructs `alert_payload` dict with order fields
- Fires fire-and-forget alert via `asyncio.create_task(_fire_alert())` where `_fire_alert` opens its own `AsyncSessionLocal` session (critical: not the request-scoped `db` which closes when handler returns)

Updated `backend/app/backtest/alerts.py`:
- `fire_gate_alert_v2()` function signature and return value unchanged
- Added delivery block after `logger.info("BACKTEST GATE EVENT: ...")` and before `return event`
- Uses lazy imports inside `try/except` block to avoid circular imports at module load time
- Calls `asyncio.run(_deliver())` to bridge sync Celery context to async `dispatch_alert`
- All exceptions caught and logged, never re-raised (backtest runner never crashes on alert failure)

## Verification Results

All 7 checkpoint checks passed:

1. Full unit test suite: 352 passed, 33 skipped (20 pre-existing RL phase failures unrelated to Phase 7)
2. Module import chain: all Phase 7 imports OK, `len(VALID_EVENT_TYPES) == 9`
3. Settings fields: `STOP_LOSS_PCT=0.02`, `TAKE_PROFIT_PCT=0.04`, `ENABLE_SHORT_SIDE=False`
4. Celery beat schedule: `sync-positions-every-15min` at 900.0 seconds registered
5. Alert wiring: both `create_order` and `fire_gate_alert_v2` contain `dispatch_alert` in source
6. Migration file: `alembic/versions/0007_alerts.py` exists
7. SendGrid pin: `sendgrid==6.12.5` in requirements.txt

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - `fire_gate_alert_v2` is now fully wired to real delivery.

## Threat Flags

No new trust boundaries or security-relevant surfaces introduced beyond what the plan's threat model covers. Alert payload fields (symbol, qty, side, order_id, filled_qty, limit_price) come entirely from validated `OrderRequest` pydantic model and broker result dict - no raw user string interpolation.

## Self-Check: PASSED

- `/Users/Mehek1/Documents/Second Brain/building/.claude/worktrees/angry-jepsen-18ff27/backend/app/routers/orders.py` - exists, contains dispatch_alert wiring
- `/Users/Mehek1/Documents/Second Brain/building/.claude/worktrees/angry-jepsen-18ff27/backend/app/backtest/alerts.py` - exists, contains dispatch_alert delivery block
- Commit `c266b70c` - feat(07-04): wire dispatch_alert into orders router and gate alert
