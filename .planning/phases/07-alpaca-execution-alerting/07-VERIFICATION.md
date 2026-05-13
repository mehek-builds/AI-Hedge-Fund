---
phase: 07-alpaca-execution-alerting
verified: 2026-05-13T00:00:00Z
status: passed
score: 8/8 must-haves verified
---

# Phase 7: Alpaca Execution and Alerting Verification Report

**Phase Goal:** Wire Alpaca paper trading execution (bracket orders, position sync, orphan detection) and system-wide alerting (SendGrid + Slack, Redis rate limiting, alerts table) into the PEAD backend.
**Verified:** 2026-05-13
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Bracket order (limit entry + stop-loss + take-profit) via alpaca-py | VERIFIED | `broker.py` uses `LimitOrderRequest` with `OrderClass.BRACKET`, `StopLossRequest`, and `TakeProfitRequest`; entry = ask + 0.5 tick, stop = entry * (1 - STOP_LOSS_PCT), tp = entry * (1 + TAKE_PROFIT_PCT) |
| 2 | Position reconciliation on startup and via 15-minute Celery beat | VERIFIED | `position_sync.py` implements `reconcile_positions_with_alpaca`; `worker.py` beat_schedule at 900s; `main.py` lifespan calls reconcile on startup |
| 3 | Orphan exit order detection with 60s grace period | VERIFIED | `orphan_detector.py` defines `ORPHAN_GRACE_SECONDS = 60`; skips orders submitted within grace window; cancels open SELL orders with no matching DB position |
| 4 | 9 event types delivered via SendGrid + Slack (fire-and-forget) | VERIFIED | `VALID_EVENT_TYPES` in `models/alerts.py` lists all 9; `dispatcher.py` calls `SendGridAPIClient.send()` and Slack webhook POST; failures logged not raised |
| 5 | Rate limiting: max 3/hr per event type (fixed window with epoch_hour key) | VERIFIED | `rate_limiter.py`: key format `alert_rate:{event_type}:{epoch_hour}` using `int(time.time()) // 3600`; `MAX_PER_HOUR = 3`; INCR + conditional EXPIRE |
| 6 | All alerts persisted to `alerts` table (rate-limited ones with rate_limited=True) | VERIFIED | `dispatcher.py` creates `Alert` row with `rate_limited=limited` before delivery check; `db.add(alert)` then `db.flush()` happens unconditionally; migration `0007_alerts.py` creates table |
| 7 | Phase 7 hard-blocks on startup if no `backtest_gate_pass` row | VERIFIED | `main.py` lifespan calls `check_phase7_gate(session)`; raises `RuntimeError` if result is False; `check_phase7_gate` in `backtest/alerts.py` queries `backtest_runs` for non-partial rows with `gate_status = 'pass'` |
| 8 | `ENABLE_SHORT_SIDE=False` blocks short orders | VERIFIED | `broker.py` line 65: `if side.lower() == "sell" and not settings.ENABLE_SHORT_SIDE: raise ValueError(...)`; config default is `False`; `orders.py` returns HTTP 400 on ValueError |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/app/execution/broker.py` | VERIFIED | 113 lines; full bracket order implementation with alpaca-py; short-side guard; lru_cache singleton |
| `backend/app/execution/position_sync.py` | VERIFIED | 82 lines; Alpaca `get_all_positions()` called; SELECT then conditional INSERT per symbol |
| `backend/app/execution/orphan_detector.py` | VERIFIED | 89 lines; 60s grace constant; `cancel_order_by_id` called for unmatched SELL orders |
| `backend/app/alerting/rate_limiter.py` | VERIFIED | 61 lines; fixed-window INCR/EXPIRE; epoch_hour key; MAX_PER_HOUR=3 |
| `backend/app/alerting/dispatcher.py` | VERIFIED | 172 lines; persists Alert row always; rate-checks; SendGrid + Slack fire-and-forget; Redis publish |
| `backend/app/alerting/templates.py` | VERIFIED | 32 lines; `render_email_html` and `render_slack_text` for all event types |
| `backend/app/routers/orders.py` | VERIFIED | 88 lines; POST /api/v1/orders; `asyncio.to_thread` for sync broker call; `asyncio.create_task` for fire-and-forget alert |
| `backend/app/backtest/alerts.py` | VERIFIED | `check_phase7_gate` reads `backtest_runs`; `fire_gate_alert_v2` wired to `dispatch_alert` via `asyncio.run` |
| `backend/app/tasks/execution.py` | VERIFIED | Celery task `sync_positions_task` wraps `reconcile_positions_with_alpaca` |
| `backend/app/worker.py` | VERIFIED | `beat_schedule` entry at `schedule: 900.0` for `sync_positions_task` |
| `backend/app/main.py` | VERIFIED | Gate check in lifespan; orders router registered at `/api/v1` |
| `backend/app/config.py` | VERIFIED | All fields present: ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER, ENABLE_SHORT_SIDE, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, SENDGRID_TO_EMAIL, SLACK_WEBHOOK_URL, STOP_LOSS_PCT, TAKE_PROFIT_PCT |
| `backend/alembic/versions/0007_alerts.py` | VERIFIED | Creates `alerts` table with UUID PK, JSONB payload, 9-type CHECK constraint, 2 indexes; down_revision=0006 |
| `backend/app/models/alerts.py` | VERIFIED | `Alert` ORM with all columns; `VALID_EVENT_TYPES` tuple with 9 event types |
| `backend/requirements.txt` | VERIFIED | `sendgrid==6.12.5` pinned; `alpaca-py==0.43.4` pinned |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `orders.py` POST handler | `broker.submit_bracket_order` | `asyncio.to_thread` | WIRED | Sync call wrapped correctly to avoid blocking event loop |
| `orders.py` POST handler | `dispatcher.dispatch_alert` | `asyncio.create_task(_fire_alert())` | WIRED | Fire-and-forget with own AsyncSession |
| `dispatcher.py` | `rate_limiter.is_rate_limited` | direct call | WIRED | Called before conditional delivery |
| `dispatcher.py` | `SendGridAPIClient` | `sg.send(message)` | WIRED | Renders HTML via `render_email_html`, sends via sendgrid client |
| `dispatcher.py` | Slack webhook | `httpx.AsyncClient.post` | WIRED | JSON body `{"text": render_slack_text(...)}` |
| `dispatcher.py` | Redis pub/sub | `r.publish("alerts", ...)` | WIRED | Always publishes, even for rate-limited alerts |
| `main.py` lifespan | `check_phase7_gate` | direct call with `SyncSessionLocal` | WIRED | Raises RuntimeError on failure |
| `worker.py` beat | `sync_positions_task` | `schedule: 900.0` | WIRED | Task routed to `portfolio` queue |
| `tasks/execution.py` | `reconcile_positions_with_alpaca` | `sync_session()` context manager | WIRED | Passes session directly |
| `backtest/alerts.py` fire_gate_alert_v2 | `dispatcher.dispatch_alert` | `asyncio.run(_deliver())` | WIRED | Async delivery from sync Celery context |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| FR-7.1 | Bracket order submission via alpaca-py | SATISFIED | `broker.py` full implementation; 4 passing tests |
| FR-7.2 | Position reconciliation on startup + 15-min beat | SATISFIED | `position_sync.py` + `worker.py` 900s schedule; 2 passing tests |
| FR-7.3 | Orphan detection with 60s grace | SATISFIED | `orphan_detector.py`; 2 passing tests covering grace period skip and cancel |
| FR-7.4 | 9 event types via SendGrid + Slack fire-and-forget | SATISFIED | `dispatcher.py`; tests iterate all 9 types for both channels |
| FR-7.5 | Rate limiting max 3/hr fixed window | SATISFIED | `rate_limiter.py`; 3 passing tests including burst and hourly reset |
| FR-7.6 | ENABLE_SHORT_SIDE=False blocks shorts | SATISFIED | `broker.py` guard; `orders.py` HTTP 400; 2 passing tests |
| FR-8.1 | Alerts persisted to alerts table | SATISFIED | `dispatcher.py` adds row unconditionally; `0007_alerts.py` migration |
| FR-8.2 | Rate-limited alerts stored with rate_limited=True | SATISFIED | `Alert(rate_limited=limited)` set before db.flush() |
| FR-8.3/8.4 | Redis pub/sub publish for SSE dashboard | SATISFIED | `_publish_redis` always called; test verifies channel='alerts' |

### Anti-Patterns Found

No blockers or substantive stubs detected.

`fire_gate_alert_v2` in `backtest/alerts.py` contains a stub comment ("Phase 7: wire to real SendGrid+Slack delivery") but the code below it IS the real implementation - asyncio.run delivers via dispatcher. The comment is historical documentation of the plan, not an unimplemented TODO.

`BACKTEST_OVERRIDE_GATE_PASS: bool = False` in config.py is present but not referenced in main.py lifespan gate check - this is a non-issue (the field is defensive/runbook-only).

### Test Suite Results

All 16 tests pass (0 failures, 0 errors):

- `tests/alerting/test_dispatcher.py`: 5 passed - SendGrid called for all 9 types, Slack called for all 9 types, DB persistence, Redis publish, fire-and-forget error handling
- `tests/alerting/test_rate_limiter.py`: 3 passed - burst 10 yields 3 deliveries, hourly reset, key format includes epoch_hour
- `tests/execution/test_broker.py`: 4 passed - BUY bracket prices correct, partial fill qty, short blocked by flag, short allowed when enabled
- `tests/execution/test_orphan_detector.py`: 2 passed - cancel called for old unmatched order, skip for order within 60s grace
- `tests/execution/test_position_sync.py`: 2 passed - INSERT on discrepancy, no-op when in sync

### Human Verification Required

None. All success criteria are verifiable programmatically.

---

## Gaps Summary

No gaps. All 8 success criteria are fully implemented and wired.

---

_Verified: 2026-05-13_
_Verifier: Claude (gsd-verifier)_
