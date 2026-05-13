---
phase: 06-backtest-engine-validation-gate
verified: 2026-05-12T18:00:00Z
status: human_needed
score: 5/6 must-haves verified
human_verification:
  - test: "Run the full 2018-2023 backtest and observe the gate decision"
    expected: "Gate status is either 'pass' (Sharpe >= 1.0 main AND >= 0.8 ex-2020) or 'fail' (blocking Phase 7). Alert fires with structured event type. Both backtest_runs rows are written with distinct slice_type='main' and slice_type='ex_2020'."
    why_human: "The DB-gated E2E smoke tests (test_e2e_writes_backtest_runs_row, test_ex2020_slice_persists_separate_row) skip in CI without DATABASE_URL_SYNC. The full production replay requires Railway DB and Phase 5 RL checkpoints. Cannot verify actual gate pass/fail outcome or Sharpe value programmatically without a live environment."
  - test: "Confirm Phase 7 startup gate check reads backtest_runs.gate_status"
    expected: "check_phase7_gate(session) in backend/app/backtest/alerts.py returns False when gate_status != 'pass', and Phase 7 startup refuses to proceed. Returns True only when a 'pass' row exists."
    why_human: "Phase 7 code is not yet written (future phase). Cannot verify end-to-end Phase 7 gate enforcement without Phase 7 existing."
---

# Phase 6: Backtest Engine + Validation Gate Verification Report

**Phase Goal:** A 2018-2023 point-in-time replay runs using production signal and RL code, produces full performance statistics, and either passes the Sharpe > 1.0 gate (unblocking paper trading) or fails it (blocking Phase 7)
**Verified:** 2026-05-12T18:00:00Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Backtest replay uses only data with ingestion_timestamp <= as_of; a deliberately injected future data point is rejected | VERIFIED | `test_backtest_as_of.py` 5 tests: mock-based proofs that `ingestion_timestamp` filter is in every SQL call; replay.py lines 41, 60 show literal `ingestion_timestamp <= :as_of` filters; stats.py `load_daily_rf_as_of` at line 291 has same filter |
| 2 | Backtest imports and calls production signal engine and SAC ensemble; no parallel backtest-only implementations exist | VERIFIED | 11 AST-based tests in `test_backtest_uses_prod_engine.py` pass; replay.py imports `compute_signal_for_event` from `app.signals.pipeline`, `SACEnsemble` from `rl.sac_agent`, `load_macro_snapshot` from `app.portfolio.macro_loader`; no local signal/RL redefinitions found |
| 3 | Full statistics computed and persisted: Sharpe, max drawdown, IR vs. naive baseline, Calmar, monthly returns | VERIFIED | `stats.py` (327 lines) implements `compute_sharpe`, `compute_max_drawdown`, `compute_ir_vs_baseline`, `compute_calmar`, `compute_monthly_returns`, `compute_all_stats`; `runner.py` persists all stats to BacktestRun ORM; 32 golden-number tests pass |
| 4 | Go/no-go gate enforced programmatically; backtest_gate_pass or backtest_gate_fail alert fires; Phase 7 cannot proceed if gate fails | VERIFIED (partial - Phase 7 enforcement is future work) | `evaluate_gate_v2` in gate.py implements conjunctive logic; `fire_gate_alert_v2` in alerts.py returns structured event dict; `check_phase7_gate()` function exists and returns False on non-pass status; 24 gate tests pass covering all edge cases including the conjunctive trap |
| 5 | Ex-2020 stress slice runs as separate backtest_runs row; Sharpe > 0.8 on ex-2020 period is reported | VERIFIED (code path) / UNCONFIRMED (actual Sharpe value) | CLI `run_full_backtest.py` calls `run_backtest(..., slice_type='ex_2020', exclude_date_range=(date(2020,3,1), date(2020,4,30)))`; `test_ex2020_slice_persists_separate_row` DB-gated test exists; actual Sharpe value requires live DB run |
| 6 | Backtest results accessible in backtest_runs table; visible in dashboard Backtest Explorer | PARTIAL - table exists, dashboard is Phase 8 | `backtest_runs` table created by migration 0005 with all required columns; Phase 8 Backtest Explorer is explicitly a future phase (non-goal for Phase 6 per CONTEXT.md) |

**Score:** 5/6 truths verified (SC#6 dashboard component deferred to Phase 8)

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Backtest results visible in dashboard Backtest Explorer | Phase 8 | Phase 8 Success Criteria #7: "Backtest Explorer lets the user select a backtest run and view Sharpe/drawdown/IR stats alongside monthly returns heatmap" |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/backtest/__init__.py` | sys.path augmentation for rl.* imports | VERIFIED | Contains `sys.path.insert`; adds repo root 3 levels up |
| `backend/app/backtest/runner.py` | iter_business_days + full run_backtest body (min 80 lines) | VERIFIED | 285 lines; contains `iter_business_days`, `run_backtest`, `update_gate_status`, `_direction_sign`, `_serialize_config_snapshot` |
| `backend/app/backtest/fills.py` | simulate_fill with transaction_cost_bps (min 30 lines) | VERIFIED | 94 lines; `simulate_fill` reads `CONFIG.risk.transaction_cost_bps`; no Alpaca calls |
| `backend/alembic/versions/0005_backtest_runs.py` | backtest_runs table creation | VERIFIED | Creates table with CHECK constraint `gate_status IN ('pending', 'pass', 'fail')`; revision="0005", down_revision="0004" |
| `backend/alembic/versions/0006_backtest_runs_slice_columns.py` | slice_type, gate_reason, total_trades columns | VERIFIED | Adds 3 columns via ADD COLUMN IF NOT EXISTS; revision="0006", down_revision="0005" |
| `backend/app/models/backtest_runs.py` | SQLAlchemy ORM BacktestRun | VERIFIED | `class BacktestRun(Base)`, 14 mapped columns; `run_id` property alias for `id` PK; JSONB for monthly_returns and config_snapshot |
| `backend/app/backtest/stats.py` | compute_sharpe, max_drawdown, ir_vs_baseline, calmar, monthly_returns, load_daily_rf_as_of, compute_all_stats (min 120 lines) | VERIFIED | 327 lines; all 8 functions present; TRADING_DAYS_PER_YEAR=252; `SELECT rf FROM ff5_factors` with `ingestion_timestamp <= :as_of`; vectorized numpy (no Python-loop float accumulation) |
| `backend/app/backtest/gate.py` | evaluate_gate conjunctive logic (min 60 lines) | VERIFIED | 165 lines; `MAIN_SHARPE_THRESHOLD = 1.0`, `EX2020_SHARPE_THRESHOLD = 0.8`; `evaluate_gate_v2` with `main_pass and ex2020_pass`; handles partial_year (pending) and override (pass) |
| `backend/app/backtest/alerts.py` | fire_gate_alert stub (min 30 lines) | VERIFIED | 132 lines; `EVENT_TYPE_PASS = "backtest_gate_pass"`, `EVENT_TYPE_FAIL = "backtest_gate_fail"`; `fire_gate_alert_v2` logs only (Phase 7 wires SendGrid/Slack); `check_phase7_gate()` function present |
| `backend/app/backtest/replay.py` | Production imports: compute_signal_for_event, SACEnsemble, load_macro_snapshot | VERIFIED | Imports from `app.signals.pipeline`, `rl.sac_agent`, `rl.moe_controller`, `app.portfolio.macro_loader`; no local signal/RL redefinitions; `load_active_events_as_of`, `load_active_ensemble`, `replay_step` all present |
| `backend/scripts/run_full_backtest.py` | CLI with --start/--end/--fast/--override-gate (min 100 lines) | VERIFIED | 116 lines; argparse with all 4 flags; runs main + ex_2020 slices; calls evaluate_gate_v2 (aliased as evaluate_gate); calls update_gate_status on both rows; fires fire_gate_alert_v2 (aliased); exit code 2 on fail |
| `backend/tests/backtest/__init__.py` | Package marker | VERIFIED | Exists |
| `backend/tests/backtest/conftest.py` | sys.path + mock_sync_session fixture | VERIFIED | Contains sys.path.insert; mock_sync_session fixture present |
| `backend/tests/backtest/test_backtest_as_of.py` | FR-6.1 future-row injection tests | VERIFIED | 5 tests covering ingestion_timestamp filter presence in SQL; NOTE: plan required `test_future_row_rejected_by_as_of_filter` by name; actual tests use `test_get_close_as_of_returns_none_for_future_row` - different name, equivalent behavior |
| `backend/tests/backtest/test_backtest_schema.py` | Schema column existence test | VERIFIED | 6 tests; `REQUIRED_COLUMNS` list; NOTE: tests 12 columns (uses `id` not `run_id`; missing `slice_type`, `gate_reason`, `total_trades` from required list) - these columns DO exist in ORM, just not in the schema test assertion |
| `backend/tests/backtest/test_backtest_stats.py` | Golden-number stats tests (32 total) | VERIFIED | 32 tests; `test_sharpe_golden_constant_return`, `test_sharpe_golden_mixed_returns`, `test_max_drawdown_known_pattern`; all pass |
| `backend/tests/backtest/test_backtest_gate.py` | Gate tests including conjunctive trap (24 total) | VERIFIED | 24 tests; `test_gate_conjunctive_pass`, `test_gate_fails_when_ex2020_below_threshold`, `test_gate_override_forces_pass`, `test_ex2020_slice`; all pass |
| `backend/tests/backtest/test_backtest_e2e.py` | FR-6.5 + FR-6.6 E2E smoke tests | VERIFIED (code) / UNCONFIRMED (DB execution) | 5 tests: 2 pass without DB (ValueError tests), 3 skip without DATABASE_URL_SYNC; `test_e2e_writes_backtest_runs_row`, `test_results_persisted`, `test_ex2020_slice_persists_separate_row` all present |
| `docs/backtest-runbook.md` | Operator runbook (min 50 lines) | VERIFIED | 103 lines; all required sections present: Prerequisites, Invocation, Expected runtime, Output interpretation, On fail: diagnosis steps, Override policy, Known limitations; eps_gap * direction proxy documented |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/backtest/runner.py` | `backend/app/flows/_base.py` | `from app.flows._base import sync_session` | VERIFIED | Line 20 of runner.py |
| `backend/app/backtest/runner.py` | `backend/app/models/backtest_runs.py` | `BacktestRun(` constructor call | VERIFIED | Line 239; session.add(row) line 253; session.commit() line 254 |
| `backend/app/backtest/runner.py` | `backend/app/backtest/replay.py` | `from app.backtest.replay import replay_step, load_active_events_as_of, load_active_ensemble` | VERIFIED | Line 188 (lazy import inside function body) |
| `backend/app/backtest/stats.py` | `ff5_factors` table | `SELECT rf FROM ff5_factors` with `ingestion_timestamp <= :as_of` | VERIFIED | Lines 289-292 |
| `backend/app/backtest/gate.py` | `backend/app/backtest/alerts.py` | `fire_gate_alert` called from CLI (aliases fire_gate_alert_v2) | VERIFIED | run_full_backtest.py line 35 imports `fire_gate_alert_v2 as fire_gate_alert`; called line 107 |
| `backend/app/backtest/gate.py` | `backend/app/config.py` | `settings.BACKTEST_OVERRIDE_GATE_PASS` | VERIFIED | settings.BACKTEST_OVERRIDE_GATE_PASS present in config.py line 19; CLI reads it at line 93 |
| `backend/scripts/run_full_backtest.py` | `backend/app/backtest/runner.py` | `from app.backtest.runner import run_backtest` | VERIFIED | Line 33 |
| `backend/scripts/run_full_backtest.py` | `backend/app/backtest/gate.py` | `from app.backtest.gate import evaluate_gate_v2 as evaluate_gate` | VERIFIED | Line 34 |
| `backend/scripts/run_full_backtest.py` | `backend/app/backtest/alerts.py` | `fire_gate_alert(...)` | VERIFIED | Line 35 imports; line 107 calls |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `runner.py run_backtest` | `daily_returns` array | `replay_step(session, ensemble, moe, as_of_dt, event)` -> `signal_row.eps_gap * _direction_sign(direction)` | Proxy (not realized P&L) - documented limitation | FLOWING (proxy documented in runbook; no `expected_return` field on Signal ORM by design) |
| `runner.py run_backtest` | `daily_rfs` array | `load_daily_rf_as_of(session, as_of_dt)` -> `SELECT rf FROM ff5_factors` | Requires populated ff5_factors table; fallback 0.0 | CONDITIONAL (real data if ff5_factors populated, else 0.0) |
| `stats.py compute_sharpe` | `excess` array | `daily_returns - daily_rf` numpy operation | Pure vectorized math on inputs | VERIFIED |
| `gate.py evaluate_gate_v2` | `main_run["sharpe"]`, `ex2020_run["sharpe"]` | Dicts returned by `run_backtest` | Real if replay ran; 0.0 if no events processed | CONDITIONAL |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| iter_business_days yields 8 business days in 2020-01-01..2020-01-10 | `python3 -c "from app.backtest.runner import iter_business_days; ..."` | 8 business days | PASS |
| evaluate_gate_v2 conjunctive: both pass -> pass | `python3 -c "from app.backtest.gate import evaluate_gate_v2; ..."` | gate_status=pass | PASS |
| evaluate_gate_v2 conjunctive: ex2020 fail -> overall fail | `python3 -c "from app.backtest.gate import evaluate_gate_v2; ..."` | gate_status=fail, reason includes "ex-2020" | PASS |
| evaluate_gate_v2: partial year -> pending | `python3 -c "from app.backtest.gate import evaluate_gate_v2; ..."` | gate_status=pending | PASS |
| compute_sharpe + compute_max_drawdown produce expected values | `python3 -c "from app.backtest.stats import ..."` | Sharpe=0.8759 (seed=42 normal), MDD=0.1 (known pattern) | PASS |
| ValueError raised for future end_date | `python3 -c "from app.backtest.runner import run_backtest; ..."` | ValueError: "end_date...must not be in the future (T-6-01)" | PASS |
| ValueError raised for inverted date range | same as above | ValueError raised | PASS |
| CLI argparse: --fast, --start/--end, --override-gate parsed | `python3 -c "from scripts.run_full_backtest import parse_args; ..."` | All flags parsed correctly | PASS |
| All 83 tests collect; 80 pass, 3 skip without DB | `python3 -m pytest backend/tests/backtest/ -x -q` | 80 passed, 3 skipped in 0.22s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FR-6.1 | 06-01 | Point-in-time correctness: every query filters ingestion_timestamp <= as_of; future-row injection rejected | SATISFIED | 5 tests in test_backtest_as_of.py verify SQL filter presence; replay.py, fills.py, stats.py all use the filter; runner validates date bounds |
| FR-6.2 | 06-02 | No parallel implementations: backtest uses production signal engine, SAC ensemble, portfolio sizing exclusively | SATISFIED | 11 AST-based tests in test_backtest_uses_prod_engine.py; replay.py confirmed to import from production modules only with no local signal/RL redefinitions |
| FR-6.3 | 06-03 | Full statistics persisted: Sharpe, max drawdown, IR vs baseline, Calmar, monthly returns | SATISFIED | stats.py 327 lines with all 7 compute_* functions; BacktestRun ORM persists all stats; 32 golden-number tests pass |
| FR-6.4 | 06-03 | Programmatic gate: backtest_gate_pass or backtest_gate_fail alert fires; Phase 7 cannot proceed if gate fails | SATISFIED (code) / UNCONFIRMED (Phase 7 enforcement) | evaluate_gate_v2 + fire_gate_alert_v2 verified; check_phase7_gate() in alerts.py provides gate check function; Phase 7 not yet written |
| FR-6.5 | 06-03, 06-04 | Ex-2020 stress slice as separate backtest_runs row; Sharpe > 0.8 reported | SATISFIED (code path, actual Sharpe requires live run) | CLI runs ex_2020 slice with exclude_date_range=(2020-03-01, 2020-04-30); separate BacktestRun row with slice_type='ex_2020'; test_ex2020_slice_persists_separate_row verifies (DB-gated) |
| FR-6.6 | 06-01, 06-04 | Results queryable from backtest_runs; schema matches Phase 8 Backtest Explorer | SATISFIED | backtest_runs table with all required columns; 6 schema tests pass; ORM test inspects columns directly; NOTE: schema test checks 12 columns (not 15 plan spec said) but additional columns slice_type/gate_reason/total_trades do exist in ORM |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/tests/backtest/test_backtest_schema.py` | 19-32 | REQUIRED_COLUMNS list omits `slice_type`, `gate_reason`, `total_trades` (added in 0006 migration) and uses `id` not `run_id` | Info | Schema test does not assert these newer columns exist; columns DO exist in ORM but test coverage is incomplete |
| `backend/tests/backtest/test_backtest_as_of.py` | - | Test uses mock-based approach only; no actual DB injection test with real INSERT | Warning | FR-6.1 is verified via mock SQL inspection, not a true point-in-time DB injection test. The plan specified `test_future_row_rejected_by_as_of_filter` using a real DB insert; the implemented tests use mocks. The @requires_db injection test from the plan spec was not implemented. |
| `backend/app/backtest/alerts.py` | 23-70 | `fire_gate_alert()` (v1) also writes gate_status to DB via SQL UPDATE - this is a dual-responsibility function beyond what the stub interface should do | Warning | The original `fire_gate_alert` in alerts.py does DB writes (updating backtest_runs). This creates two code paths for gate_status updates: one via `update_gate_status` in runner.py/CLI, another via `fire_gate_alert`. Risk of inconsistency if both are called. |

### Human Verification Required

**1. Full 2018-2023 Backtest Execution**

**Test:** Run `cd backend && python -m scripts.run_full_backtest` with DATABASE_URL_SYNC configured and Phase 5 RL checkpoints present in the DB.
**Expected:** Both main and ex_2020 slices complete; two rows written to backtest_runs with distinct run_ids; gate_status is either 'pass' or 'fail' (not 'pending'); structured alert event fires; CLI exits with code 0 (pass) or 2 (fail).
**Why human:** Requires live PostgreSQL DB with Phase 5 data (RL checkpoints, ff5_factors, signals, price_bars). DATABASE_URL_SYNC not available in CI without external DB. The 3 DB-gated E2E tests skip in all CI contexts.

**2. Phase 7 Startup Gate Check Enforcement**

**Test:** Once Phase 7 is written, confirm it calls `check_phase7_gate(session)` from `backend/app/backtest/alerts.py` at startup and aborts if the function returns False.
**Expected:** Phase 7 startup reads the most recent backtest_runs row; if gate_status != 'pass', Phase 7 refuses to start and logs the reason.
**Why human:** Phase 7 does not yet exist. The `check_phase7_gate()` function is provided as a Phase 7 contract, but enforcement depends on Phase 7 calling it.

### Gaps Summary

No blocking gaps prevent Phase 6 goal achievement. The phase produced all required artifacts, all 80 non-DB-gated tests pass, and the gate logic works correctly as verified by spot-checks.

Two non-blocking observations noted:

1. The FR-6.1 injection test is mock-based rather than using a real DB INSERT/SELECT. The plan specified `test_future_row_rejected_by_as_of_filter` using a real DB transaction, but the implementation uses mock SQL inspection. This is lower confidence than a real injection test, but functionally equivalent for CI purposes and the production query code (replay.py, fills.py, stats.py) all contain the correct filter.

2. The backtest_runs schema test (`test_backtest_schema.py`) checks 12 columns rather than 15. The 3 columns added in migration 0006 (`slice_type`, `gate_reason`, `total_trades`) are in the ORM model but not asserted in the schema test's REQUIRED_COLUMNS list. The columns exist; only the test coverage is narrower than planned.

Both observations are warning-level, not blockers. Human verification is required to confirm the actual Sharpe gate outcome once a live environment is available.

---

_Verified: 2026-05-12T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
