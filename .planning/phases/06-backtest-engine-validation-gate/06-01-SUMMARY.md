---
phase: "06"
plan: "01"
subsystem: backtest-engine
tags: [backtest, schema, alembic, orm, gate, stats, wave-0]
dependency_graph:
  requires:
    - "05-01: RL ensemble and MoEController production modules"
    - "04-01: portfolio_positions table and portfolio pipeline"
    - "03-01: signals table, compute_signal_for_event, signal pipeline"
    - "01-02: Alembic setup, ingestion_timestamp semantics, point_in_time.py"
  provides:
    - "backtest_runs table (migration 0005)"
    - "BacktestRun ORM model"
    - "backend/app/backtest/ package: runner, fills, replay, stats, gate, alerts"
    - "backend/tests/backtest/ Wave 0 test suite (55 unit tests)"
    - "backend/scripts/run_full_backtest.py CLI entrypoint"
  affects:
    - "06-02: production-code wiring (uses app/backtest/ scaffold)"
    - "06-03: stats and gate plans (uses stats.py, gate.py)"
    - "06-04: full replay + persistence (uses runner.py, alerts.py)"
    - "Phase 7: startup gate check reads backtest_runs.gate_status"
    - "Phase 8: Backtest Explorer queries backtest_runs table"
tech_stack:
  added: []
  patterns:
    - "sync SQLAlchemy session (postgresql+psycopg2) via app/flows/_base.sync_session"
    - "ingestion_timestamp <= :as_of in every DB query (FR-6.1 point-in-time)"
    - "production imports only in replay.py (FR-6.2 no parallel signal logic)"
    - "numpy-only stats: sharpe, max_drawdown, calmar, information_ratio"
    - "conjunctive gate: full_sharpe > 1.0 AND ex2020_sharpe > 0.8"
key_files:
  created:
    - backend/alembic/versions/0005_backtest_runs.py
    - backend/app/models/backtest_runs.py
    - backend/app/backtest/__init__.py
    - backend/app/backtest/runner.py
    - backend/app/backtest/fills.py
    - backend/app/backtest/replay.py
    - backend/app/backtest/stats.py
    - backend/app/backtest/gate.py
    - backend/app/backtest/alerts.py
    - backend/scripts/run_full_backtest.py
    - backend/tests/backtest/__init__.py
    - backend/tests/backtest/conftest.py
    - backend/tests/backtest/test_backtest_as_of.py
    - backend/tests/backtest/test_backtest_schema.py
    - backend/tests/backtest/test_backtest_uses_prod_engine.py
    - backend/tests/backtest/test_backtest_stats.py
    - backend/tests/backtest/test_backtest_gate.py
    - backend/tests/backtest/test_backtest_e2e.py
  modified: []
decisions:
  - "transaction_cost_bps used as round-trip cost (entry + exit), no separate slippage model (Phase 5 decision)"
  - "std < 1e-10 guard in sharpe_ratio to prevent near-zero division returning Inf on constant series"
  - "is_partial_year=True marks ex-2020 and other stress slices so gate logic skips them"
  - "gate_status CHECK constraint: pending/pass/fail (prevents invalid states at DB level)"
  - "sys.path augmented 3 levels up from backend/app/backtest/ to reach repo root for rl.* and config.py"
metrics:
  duration: "~45 minutes"
  completed_date: "2026-05-13"
  tasks_completed: 5
  files_created: 18
  tests_added: 55
---

# Phase 6 Plan 1: Backtest Harness + Schema Summary

Alembic migration 0005, BacktestRun ORM model, full backend/app/backtest/ package scaffold (runner, fills, replay, stats, gate, alerts), Wave 0 test suite (55 passing unit tests), and CLI entrypoint for the point-in-time-correct 2018-2023 backtest engine.

## What Was Built

### Migration 0005: backtest_runs table
`backend/alembic/versions/0005_backtest_runs.py` creates the `backtest_runs` table with all columns required by the Phase 8 Backtest Explorer:
- `id` (UUID PK), `start_date`, `end_date`
- `sharpe`, `max_drawdown`, `ir_vs_baseline`, `calmar` (NUMERIC)
- `monthly_returns` (JSONB), `gate_status` with CHECK constraint (pending/pass/fail)
- `is_partial_year` (Boolean), `config_snapshot` (JSONB), `created_at`
- Indexes: `ix_backtest_runs_gate_status` for Phase 7 startup check, `ix_backtest_runs_dates` for Explorer queries

### BacktestRun ORM Model
`backend/app/models/backtest_runs.py` maps to `backtest_runs` with SQLAlchemy `Mapped` columns. Gate status CHECK constraint is enforced at ORM level too.

### Backtest Package (`backend/app/backtest/`)
- `runner.py`: `BacktestConfig` dataclass, `trading_dates()` (pandas bdate_range), `sp500_members_as_of()` (point-in-time), `run_backtest()` date-iterator orchestrator
- `fills.py`: `get_close_as_of()` (ingestion_timestamp point-in-time filter), `simulate_fill()` using `transaction_cost_bps`
- `replay.py`: `step_replay()` calls production signal engine, macro loader, SAC ensemble, MoEController (FR-6.2 compliant: no backtest-only signal logic)
- `stats.py`: `sharpe_ratio`, `max_drawdown`, `calmar_ratio`, `information_ratio`, `monthly_returns_breakdown`, `compute_all_stats` (FR-6.3)
- `gate.py`: `evaluate_gate()` with Sharpe > 1.0 AND ex-2020 > 0.8 conjunctive conditions (FR-6.4/6.5)
- `alerts.py`: `fire_gate_alert()` updates `backtest_runs.gate_status`, `check_phase7_gate()` for Phase 7 startup check

### Wave 0 Test Suite (55 tests, 0 failures)
- `test_backtest_as_of.py`: 5 tests verifying `ingestion_timestamp <= as_of` in SQL (FR-6.1)
- `test_backtest_schema.py`: 6 tests verifying ORM column coverage and types (FR-6.6)
- `test_backtest_uses_prod_engine.py`: 6 AST-based tests verifying no parallel signal logic (FR-6.2)
- `test_backtest_stats.py`: 21 tests with golden numbers for all FR-6.3 metrics
- `test_backtest_gate.py`: 14 tests covering all gate conditions (FR-6.4/6.5)
- `test_backtest_e2e.py`: 6 tests (3 unit, 3 DB-gated skips) for FR-6.5/6.6

### CLI Entrypoint
`backend/scripts/run_full_backtest.py`: argparse CLI with `--start`, `--end`, `--ex2020`, `--override-gate-pass`. Validates end date is not in the future. Exits with code 2 on gate fail.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sys.path wrong level in fills.py and replay.py**
- **Found during:** Task 4 (running tests)
- **Issue:** `os.path.join(dirname, "..", "..", "..", "..")` computed 4 levels up from `backend/app/backtest/`, landing at `/Users/.../worktrees` instead of repo root
- **Fix:** Changed to 3 levels up (`"..", "..", ".."`) which correctly resolves to repo root containing `config.py` and `rl/`
- **Files modified:** `backend/app/backtest/fills.py`, `backend/app/backtest/replay.py`
- **Commit:** 69f2a031

**2. [Rule 1 - Bug] Near-zero std guard in sharpe_ratio**
- **Found during:** Task 4 (test_sharpe_zero_volatility_zero failing)
- **Issue:** `if std == 0.0` exact comparison failed for constant returns due to float precision; `std(ddof=1)` on `[0.001] * 100` returned ~7e16 instead of 0
- **Fix:** Changed to `if std < 1e-10` threshold guard
- **Files modified:** `backend/app/backtest/stats.py`
- **Commit:** 69f2a031

**3. [Rule 1 - Bug] Test data with zero mean for Sharpe sign tests**
- **Found during:** Task 4 (test_sharpe_positive_for_positive_mean_returns failing)
- **Issue:** `[0.001] * 100 + [-0.002] * 50` has exactly zero mean; Sharpe was 0.0 not > 0
- **Fix:** Used `0.002 + noise` with controlled noise (seed=42) to guarantee positive mean
- **Files modified:** `backend/tests/backtest/test_backtest_stats.py`
- **Commit:** 69f2a031

## Known Stubs

None. All modules are scaffolded with working implementations. The replay loop in `replay.py` uses a simplified same-day return calculation (noted as "Phase 06-04 will wire the full hold-period return calculation") but the scaffold correctly calls production signal/RL modules and is not a data stub.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: future-end-date validation | backend/scripts/run_full_backtest.py | CLI validates end date not in future; missing this check would allow look-ahead bias via CLI |

## Self-Check: PASSED

All 18 created files found on disk. All 5 task commits verified in git log.

| Check | Result |
|-------|--------|
| 18 created files exist on disk | PASSED |
| commit 2bd9e7a4 (migration 0005) | FOUND |
| commit baf358bd (ORM model) | FOUND |
| commit 236a9922 (backtest package) | FOUND |
| commit 69f2a031 (tests + fixes) | FOUND |
| commit c718ff7a (CLI script) | FOUND |
| 55 unit tests pass | PASSED |
| 3 DB-gated tests skip cleanly | PASSED |
| ruff lint clean | PASSED |
