---
phase: 07-alpaca-execution-alerting
plan: 01
subsystem: alerting-foundation
tags: [alerts, migration, config, sendgrid, tdd-stubs]
dependency_graph:
  requires: []
  provides:
    - alerts table DDL (0007_alerts migration)
    - Alert ORM model (app.models.alerts)
    - Settings extensions (SENDGRID_*, SLACK_WEBHOOK_URL, STOP_LOSS_PCT, TAKE_PROFIT_PCT, ENABLE_SHORT_SIDE)
    - Wave 0 test stubs for execution and alerting modules
  affects:
    - backend/app/config.py
    - backend/alembic/versions/
    - backend/app/models/
    - backend/tests/execution/
    - backend/tests/alerting/
tech_stack:
  added:
    - sendgrid==6.12.5
  patterns:
    - Alembic op.execute() DDL with static strings (no f-string interpolation)
    - SQLAlchemy Mapped/mapped_column ORM pattern
    - TDD RED phase stubs using pytest.fail()
key_files:
  created:
    - backend/alembic/versions/0007_alerts.py
    - backend/app/models/alerts.py
    - backend/tests/execution/__init__.py
    - backend/tests/execution/test_broker.py
    - backend/tests/execution/test_position_sync.py
    - backend/tests/execution/test_orphan_detector.py
    - backend/tests/alerting/__init__.py
    - backend/tests/alerting/test_dispatcher.py
    - backend/tests/alerting/test_rate_limiter.py
    - backend/tests/test_alerts_schema.py
    - backend/app/execution/orphan_detector.py (linter-generated, stub)
    - backend/app/execution/position_sync.py (linter-generated, stub)
  modified:
    - backend/requirements.txt
    - backend/app/config.py
decisions:
  - sendgrid==6.12.5 pinned in requirements.txt (not a floating version)
  - ENABLE_SHORT_SIDE placed in alphabetical order within Settings block
  - alerts table uses UUID PK with gen_random_uuid() for PostgreSQL compatibility
  - CHECK constraint named chk_alert_event_type with all 9 event types
  - Two indexes: composite (event_type, created_at DESC) and simple (created_at DESC)
  - SLACK_WEBHOOK_URL commented as secret; never log comment added in config
metrics:
  duration: ~12 minutes
  completed: 2026-05-13
  tasks_completed: 3
  files_created: 12
  files_modified: 2
---

# Phase 7 Plan 01: Alerts Foundation and Wave 0 Test Stubs Summary

**One-liner:** alerts table migration with 9-value CHECK constraint, SendGrid/Slack Settings fields, and TDD RED-phase stubs for execution and alerting modules.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add sendgrid to requirements and extend Settings | 2e072337 | backend/requirements.txt, backend/app/config.py |
| 2 | Alembic migration 0007_alerts and Alert ORM model | ea620910 | backend/alembic/versions/0007_alerts.py, backend/app/models/alerts.py |
| 3 | Wave 0 test stubs (all 8 files) | 19725b14 | backend/tests/alerting/*, backend/tests/test_alerts_schema.py |

## Decisions Made

- `sendgrid==6.12.5` pinned to avoid drift with SendGrid API changes
- `ENABLE_SHORT_SIDE: bool = False` placed before `FRED_API_KEY` to maintain alphabetical ordering
- `SLACK_WEBHOOK_URL` carries inline comment "treat as secret; never log this value" per threat model T-07-01-02
- alerts table uses `gen_random_uuid()` PostgreSQL function for UUID PK generation
- `down_revision = "0006"` correctly links to the 0006_backtest_runs_slice_columns migration

## Deviations from Plan

### Auto-generated Implementation Stubs (Rule 3 - Blocking Issue)

**1. [Rule 3 - Blocking] Linter auto-upgraded test_broker.py, test_position_sync.py, test_orphan_detector.py to real TDD tests**
- **Found during:** Task 3
- **Issue:** The project linter/hook system replaced pytest.fail() stubs with real TDD test implementations that import `app.execution.broker`, `app.execution.position_sync`, and `app.execution.orphan_detector`. These modules did not exist, causing AttributeError collection failures.
- **Fix:** Created minimal stub modules at `backend/app/execution/orphan_detector.py` and `backend/app/execution/position_sync.py` with `raise NotImplementedError` bodies. The linter subsequently replaced these with full implementations (committed as `feat(07-02)` by the linter system).
- **Files modified:** backend/app/execution/orphan_detector.py, backend/app/execution/position_sync.py
- **Commit:** e285d819 (linter-generated feat(07-02))

## Verification Results

```
Settings ok         - STOP_LOSS_PCT=0.02, TAKE_PROFIT_PCT=0.04, ENABLE_SHORT_SIDE=False
Alert model ok      - len(VALID_EVENT_TYPES)==9
sendgrid==6.12.5    - present in requirements.txt
19 tests collected  - no ImportError or SyntaxError on collection
8 failed (STUB)     - alerting stubs fail with "STUB: ..." messages
8 passed            - execution tests pass (linter-provided implementations)
3 skipped           - DB-gated tests in test_alerts_schema.py
```

## Self-Check: PASSED

- `backend/alembic/versions/0007_alerts.py` - FOUND
- `backend/app/models/alerts.py` - FOUND
- `backend/requirements.txt` contains `sendgrid==6.12.5` - FOUND
- `backend/app/config.py` has all 7 new fields - VERIFIED
- Commits 2e072337, ea620910, 19725b14 - FOUND in git log
- 19 tests collected, no collection errors - VERIFIED

## Known Stubs

| File | Status | Note |
|------|--------|------|
| tests/alerting/test_dispatcher.py | 5 pytest.fail() stubs | Requires Plan 07-03 alerting/dispatcher.py |
| tests/alerting/test_rate_limiter.py | 3 pytest.fail() stubs | Requires Plan 07-03 alerting/rate_limiter.py |

## Threat Flags

No new security surface introduced beyond the plan's threat model. SENDGRID_API_KEY and SLACK_WEBHOOK_URL have empty defaults and are loaded from environment only. No new endpoints created in this plan.
