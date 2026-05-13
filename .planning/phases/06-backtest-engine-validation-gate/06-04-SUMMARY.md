---
phase: "06"
plan: "04"
subsystem: backtest-engine
tags: [backtest, runner, cli, e2e, gate, fr-6.5, fr-6.6, wave-4]
dependency_graph:
  requires:
    - "06-01: backtest package scaffold (runner, replay, stats, gate, alerts)"
    - "06-02: FR-6.2 production-code reuse verified"
    - "06-03: vectorized compute_* stats and evaluate_gate_v2"
  provides:
    - "run_backtest(start, end, *, slice_type, exclude_date_range) -> dict"
    - "update_gate_status(run_id, gate_status, gate_reason)"
    - "iter_business_days generator"
    - "_direction_sign helper"
    - "_serialize_config_snapshot helper"
    - "replay_step, load_active_events_as_of, load_active_ensemble in replay.py"
    - "slice_type, gate_reason, total_trades columns on BacktestRun"
    - "Migration 0006 (backtest_runs new columns)"
    - "run_full_backtest.py CLI (main + ex-2020 slices, gate, alert)"
    - "test_backtest_e2e.py FR-6.5/FR-6.6 smoke tests (5 total, 3 DB-gated)"
    - "docs/backtest-runbook.md operator guide"
  affects:
    - "Phase 7: reads backtest_runs.gate_status written by run_full_backtest.py"
    - "Phase 8: Backtest Explorer queries backtest_runs table"
tech_stack:
  added: []
  patterns:
    - "eps_gap * _direction_sign(direction) as per-event daily return proxy (no expected_return on Signal ORM)"
    - "load_active_ensemble called once before date loop (not per-day)"
    - "BacktestRun persisted with gate_status=pending; gate evaluated externally by CLI"
    - "evaluate_gate_v2 (dict API from 06-03) aliased as evaluate_gate in CLI"
    - "fire_gate_alert_v2 (stub from 06-03) aliased as fire_gate_alert in CLI"
    - "T-6-01 mitigation: ValueError raised if end > date.today()"
    - "T-6-14 mitigation: override forces gate_reason=manual override via BACKTEST_OVERRIDE_GATE_PASS"
key_files:
  created:
    - backend/alembic/versions/0006_backtest_runs_slice_columns.py
    - docs/backtest-runbook.md
  modified:
    - backend/app/backtest/runner.py
    - backend/app/backtest/replay.py
    - backend/app/models/backtest_runs.py
    - backend/app/config.py
    - backend/scripts/run_full_backtest.py
    - backend/tests/backtest/test_backtest_e2e.py
decisions:
  - "run_backtest signature changed from BacktestConfig dataclass to keyword args (start, end, slice_type, exclude_date_range) per plan 06-04 spec; BacktestConfig preserved for backward compat with 06-01/02/03 tests"
  - "run_id returned as str(row.id) since BacktestRun PK column is named id; run_id is a property alias on the model"
  - "Daily return proxy uses eps_gap * direction_sign: Signal ORM has no expected_return or realized return field; eps_gap is the same EPS surprise feature used in the obs vector (plan 06-02), so the gate measures policy capitalizing on what it was shown"
  - "gate_status=pending persisted at BacktestRun creation; CLI calls update_gate_status after evaluate_gate to write final pass/fail/pending on both main and ex_2020 rows"
  - "evaluate_gate_v2 and fire_gate_alert_v2 (from 06-03) aliased in CLI to evaluate_gate and fire_gate_alert for readability"
metrics:
  duration: "~35 minutes"
  completed_date: "2026-05-12"
  tasks_completed: 2
  files_created: 2
  files_modified: 6
  tests_added: 5
---

# Phase 6 Plan 4: Full Runner + CLI + E2E Smoke Test Summary

Full run_backtest implementation (date loop, eps_gap * direction return proxy, BacktestRun persistence), run_full_backtest.py CLI running both main and ex-2020 slices with gate + alert, FR-6.5/FR-6.6 E2E smoke tests, and operator runbook documenting the eps_gap proxy substitution.

## What Was Built

### runner.py: Full Implementation (FR-6.1, FR-6.5)

`backend/app/backtest/runner.py` replaced the skeleton with the complete body:

- `iter_business_days(start, end, *, exclude_date_range)`: generator yielding business days, optional sub-range exclusion for ex-2020 slice
- `run_backtest(start, end, *, slice_type, exclude_date_range)`: full date loop
  - Validates: raises ValueError if end > date.today() (T-6-01) or start > end
  - Loads ensemble + moe ONCE before loop via `load_active_ensemble(session)`
  - Per-day: calls `load_active_events_as_of`, `replay_step` per event
  - Daily return proxy: `float(signal_row.eps_gap or 0.0) * _direction_sign(signal_row.direction)`, scaled by `final_entry_size` (strategy) and 0.02 (naive)
  - After loop: `compute_all_stats` then `BacktestRun` ORM insert with gate_status=pending
  - Returns dict including run_id, slice_type, all stats
- `update_gate_status(run_id, gate_status, gate_reason)`: updates existing row
- `_direction_sign(direction)`: +1.0 long, -1.0 short, 0.0 otherwise
- `_serialize_config_snapshot()`: JSON-safe CONFIG signal+risk snapshot
- `BacktestConfig` dataclass preserved for backward compat with 06-01/02/03 tests

### replay.py: New Public API

`backend/app/backtest/replay.py` extended with three public functions:

- `load_active_events_as_of(session, as_of)`: returns namedtuple list of earnings events visible at as_of (point-in-time FR-6.1)
- `load_active_ensemble(session)`: loads SACEnsemble + MoEController from DB once
- `replay_step(session, ensemble, moe, as_of, event)`: per-event replay; returns dict with signal_row, final_entry_size, macro_score, etc., or None

### BacktestRun Model + Migration 0006

`backend/app/models/backtest_runs.py` extended:
- `slice_type` (TEXT, default 'main'): distinguishes main vs ex_2020 rows
- `gate_reason` (TEXT, nullable): human-readable gate evaluation reason
- `total_trades` (INTEGER, nullable): count of non-None replay_step results
- `run_id` property: alias for `id` column for application code clarity

`backend/alembic/versions/0006_backtest_runs_slice_columns.py`: ADD COLUMN IF NOT EXISTS for all three columns + ix_backtest_runs_slice_type index.

### run_full_backtest.py CLI

`backend/scripts/run_full_backtest.py` replaced the skeleton with the full operator entrypoint:
- Flags: `--start`, `--end`, `--fast` (2022 slice), `--override-gate`
- Procedure: main_run, ex2020_run, evaluate_gate, update_gate_status on both rows, fire_gate_alert
- Exit code 0 on pass/pending, 2 on fail
- Override propagated from `--override-gate` or `settings.BACKTEST_OVERRIDE_GATE_PASS`

### E2E Smoke Tests (5 tests)

`backend/tests/backtest/test_backtest_e2e.py` replaced with plan 06-04 tests:
- `test_e2e_writes_backtest_runs_row` (DB-gated): 1-month run, asserts row queryable with correct slice_type and gate_status=pending
- `test_results_persisted` (DB-gated): asserts is_partial_year=True, JSONB columns populated
- `test_ex2020_slice_persists_separate_row` (DB-gated): two runs, asserts distinct run_ids with slice_types main and ex_2020
- `test_validates_future_end_date`: T-6-01, ValueError with "future" in message
- `test_validates_inverted_range`: ValueError on start > end

### Operator Runbook

`docs/backtest-runbook.md` covers all required sections including the eps_gap * direction proxy substitution rationale, override policy audit trail, and on-fail diagnosis steps.

## Test Results

| File | Tests | Result |
|------|-------|--------|
| test_backtest_e2e.py | 5 (3 DB-gated skip, 2 pass) | 5 pass/skip |
| test_backtest_stats.py | 32 | 32 passed |
| test_backtest_gate.py | 24 | 24 passed |
| test_backtest_as_of.py | 5 | 5 passed |
| test_backtest_schema.py | 6 | 6 passed |
| test_backtest_uses_prod_engine.py | 11 | 11 passed |
| **Total** | **83** | **80 passed, 3 skipped** |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] Added replay_step, load_active_events_as_of, load_active_ensemble to replay.py**
- **Found during:** Task 1 implementation
- **Issue:** Plan 06-04 spec imports these from `app.backtest.replay` but the existing replay.py only had `step_replay` with a different signature. The new run_backtest body requires the dict-returning replay_step and the event-loading helpers.
- **Fix:** Added all three functions to replay.py. Old `step_replay` preserved for backward compat.
- **Files modified:** `backend/app/backtest/replay.py`
- **Commit:** fdf40f84

**2. [Rule 2 - Missing critical] Added slice_type, gate_reason, total_trades to BacktestRun**
- **Found during:** Task 1 implementation
- **Issue:** Plan requires these columns for run_backtest to persist and for Phase 7 to distinguish slice types. The existing model from 06-01 had only id, start_date, end_date, stats, gate_status, is_partial_year.
- **Fix:** Extended model + migration 0006.
- **Files modified:** `backend/app/models/backtest_runs.py`, `backend/alembic/versions/0006_backtest_runs_slice_columns.py`
- **Commit:** fdf40f84

**3. [Rule 2 - Missing critical] Added BACKTEST_OVERRIDE_GATE_PASS to settings**
- **Found during:** Task 2 implementation
- **Issue:** CLI references `settings.BACKTEST_OVERRIDE_GATE_PASS` but the field was absent from `app/config.py`.
- **Fix:** Added `BACKTEST_OVERRIDE_GATE_PASS: bool = False` to Settings class.
- **Files modified:** `backend/app/config.py`
- **Commit:** fdf40f84

**4. [Rule 1 - Bug] Removed unused imports and nav variable from replay.py**
- **Found during:** Task 2 ruff check
- **Issue:** `EarningsEvent`, `simulate_fill`, `Session as _Session`, `nav` variable flagged by ruff F401/F841
- **Fix:** Removed unused imports; nav was vestigial from the old step_replay approach.
- **Files modified:** `backend/app/backtest/replay.py`
- **Commit:** 50349ae9

## Known Stubs

- `fire_gate_alert_v2` (aliased as `fire_gate_alert` in CLI): logs only, no SendGrid/Slack. Intentional per plan spec; Phase 7 wires the external integrations.
- `load_active_ensemble`: calls `SACEnsemble.load_latest_from_db(session)`. In environments without Phase 5 RL checkpoints, this will raise and replay_step returns None for all events, producing a 0.0 Sharpe run. The gate will then fail (correctly -- no checkpoints means no valid gate decision).

## Threat Flags

None. No new network endpoints, auth paths, or schema changes beyond the three columns added to backtest_runs (an internal-only table per T-6-16 accept disposition).

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/app/backtest/runner.py exists | FOUND |
| def run_backtest( present | FOUND |
| def update_gate_status( present | FOUND |
| def _direction_sign( present | FOUND |
| def _serialize_config_snapshot( present | FOUND |
| result["signal_row"] used (NOT result["signal"]) | FOUND |
| expected_return NOT referenced in runner.py | FOUND |
| eps_gap * _direction_sign pattern | FOUND |
| backend/alembic/versions/0006_backtest_runs_slice_columns.py exists | FOUND |
| backend/scripts/run_full_backtest.py exists | FOUND |
| slice_type="main" and slice_type="ex_2020" in CLI | FOUND |
| evaluate_gate(main_run, ex2020_run, override=override) | FOUND |
| update_gate_status called for both rows | FOUND |
| fire_gate_alert( called | FOUND |
| exit code 2 on fail | FOUND |
| backend/tests/backtest/test_backtest_e2e.py exists | FOUND |
| test_e2e_writes_backtest_runs_row present | FOUND |
| test_results_persisted present | FOUND |
| test_ex2020_slice_persists_separate_row present | FOUND |
| test_validates_future_end_date present | FOUND |
| test_validates_inverted_range present | FOUND |
| docs/backtest-runbook.md exists (103 lines > 50 min) | FOUND |
| eps_gap * direction documented in runbook | FOUND |
| commit fdf40f84 (Task 1) | FOUND |
| commit 50349ae9 (Task 2) | FOUND |
| 80 tests pass, 3 skipped (DB-gated) | PASSED |
| ruff check clean on all modified files | PASSED |
