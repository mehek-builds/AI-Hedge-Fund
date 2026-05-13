---
phase: "06"
plan: "03"
subsystem: backtest-engine
tags: [backtest, stats, gate, fr-6.3, fr-6.4, fr-6.5, vectorized, tdd, wave-2]
dependency_graph:
  requires:
    - "06-01: backtest harness package (stats.py, gate.py, alerts.py scaffold)"
    - "06-02: FR-6.2 compliance verified"
  provides:
    - "compute_sharpe, compute_max_drawdown, compute_ir_vs_baseline, compute_calmar"
    - "compute_monthly_returns, load_daily_rf_as_of, compute_all_stats (vectorized)"
    - "evaluate_gate_v2(main_run: dict, ex2020_run: dict, override=False) -> dict"
    - "fire_gate_alert_v2(gate_status, gate_reason, run_id) -> dict stub"
    - "EVENT_TYPE_PASS, EVENT_TYPE_FAIL, EVENT_TYPE_PENDING constants"
    - "MAIN_SHARPE_THRESHOLD = 1.0 constant"
    - "11 golden-number stats tests + 11 conjunctive gate tests"
  affects:
    - "06-04: full replay uses compute_all_stats and evaluate_gate_v2 for result persistence"
    - "Phase 7: startup gate reads backtest_runs.gate_status written by evaluate_gate_v2"
tech_stack:
  added: []
  patterns:
    - "numpy vectorized stats: no Python-for-loop float accumulation (RESEARCH Pitfall 5)"
    - "sd < 1e-10 guard prevents degenerate Sharpe on constant return series"
    - "ddof=0 for numpy std in compute_sharpe (population std, consistent with plan spec)"
    - "Conjunctive gate with >= comparison: main >= 1.0 AND ex-2020 >= 0.8"
    - "TDD: RED (import errors) -> GREEN (implementations) -> ruff lint"
    - "Backward compat: old API preserved alongside new compute_* and evaluate_gate_v2"
key_files:
  created: []
  modified:
    - backend/app/backtest/stats.py
    - backend/app/backtest/gate.py
    - backend/app/backtest/alerts.py
    - backend/tests/backtest/test_backtest_stats.py
    - backend/tests/backtest/test_backtest_gate.py
decisions:
  - "sd < 1e-10 threshold (not == 0.0) guards compute_sharpe against near-zero floating-point std on constant series (same fix as 06-01 sharpe_ratio)"
  - "compute_all_stats_v1 preserves old list-based signature; compute_all_stats is now the plan 06-03 vectorized version with dates/is_partial_year"
  - "evaluate_gate_v2 added alongside legacy evaluate_gate; old tests use GateResult dataclass, new tests use dict return"
  - "fire_gate_alert_v2 is a pure stub (no DB writes, no SendGrid/Slack) - Phase 7 wires these"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-05-12"
  tasks_completed: 2
  files_created: 0
  tests_added: 22
---

# Phase 6 Plan 3: Statistics + Gate Logic Summary

Vectorized numpy stats (compute_sharpe, compute_max_drawdown, compute_ir_vs_baseline, compute_calmar, compute_monthly_returns) and conjunctive Sharpe gate (main >= 1.0 AND ex-2020 >= 0.8) with dict-based API, 22 new golden-number tests covering all FR-6.3/6.4/6.5 invariants.

## What Was Built

### stats.py: Vectorized compute_* Functions (FR-6.3)

`backend/app/backtest/stats.py` extended with 8 new functions:

- `compute_sharpe(daily_returns, daily_rf)`: annualized Sharpe = mean(excess)/std(excess)*sqrt(252); sd < 1e-10 guard; accepts scalar or array rf
- `compute_max_drawdown(daily_returns)`: abs(min((cum - running_max)/running_max)); returns 0.0 for < 2 elements
- `compute_ir_vs_baseline(strategy_returns, naive_returns)`: mean(diff)/std(diff)*sqrt(252); 0.0 if std==0 or unequal lengths
- `compute_calmar(annualized_return, max_drawdown_val)`: annualized/mdd; 0.0 if mdd==0
- `compute_annualized_return(daily_returns)`: geometric (total_return^(1/years) - 1)
- `compute_monthly_returns(dates, daily_returns)`: groups by YYYY-MM, computes prod(1+r)-1 per month; returns dict
- `load_daily_rf_as_of(session, as_of)`: SELECT rf FROM ff5_factors WHERE date <= :as_of AND ingestion_timestamp <= :as_of (point-in-time)
- `compute_all_stats(dates, daily_returns, naive_returns, daily_rf_array)`: returns dict with sharpe, max_drawdown, ir_vs_baseline, calmar, annualized_return, monthly_returns, is_partial_year (True if < 200 days)

Old `compute_all_stats` renamed to `compute_all_stats_v1` (list-based signature preserved for backward compat with existing 06-01 tests).

**Line count:** 327 lines (> 120 minimum).

### gate.py: Conjunctive Dict-based API (FR-6.4, FR-6.5)

`backend/app/backtest/gate.py` extended with:

- `MAIN_SHARPE_THRESHOLD = 1.0` constant (alongside legacy `SHARPE_THRESHOLD`)
- `evaluate_gate_v2(main_run: dict, ex2020_run: dict, override: bool=False) -> dict`:
  - Partial-year check: if `main_run["is_partial_year"]` returns `{"gate_status": "pending", ...}`
  - Override: returns `{"gate_status": "pass", "gate_reason": "manual override via BACKTEST_OVERRIDE_GATE_PASS"}`
  - Conjunctive: `main_pass = main_sharpe >= 1.0` AND `ex2020_pass = ex2020_sharpe >= 0.8`
  - Pass: reason includes both Sharpe values formatted to 4 decimal places
  - Fail: reason names which slice(s) failed with their actual Sharpe values

**Line count:** 165 lines (> 60 minimum).

### alerts.py: Phase 7 Stub Interface (FR-6.4)

`backend/app/backtest/alerts.py` extended with:

- `EVENT_TYPE_PASS = "backtest_gate_pass"`
- `EVENT_TYPE_FAIL = "backtest_gate_fail"`
- `EVENT_TYPE_PENDING = "backtest_gate_pending"`
- `fire_gate_alert_v2(gate_status, gate_reason, run_id) -> dict`: logs via stdlib logging only, returns structured event dict; Phase 7 wires SendGrid+Slack

**Line count:** 132 lines (> 30 minimum).

### Golden-Number Tests (22 new tests)

**test_backtest_stats.py** (11 new tests):
- `test_sharpe_golden_constant_return`: constant series -> 0.0 (std guard)
- `test_sharpe_golden_mixed_returns`: seed=42 normal(0.001, 0.01) -> Sharpe in (0.5, 3.5)
- `test_sharpe_empty_returns_zero`: empty and single-element arrays
- `test_max_drawdown_known_pattern`: [0.10, -0.10, 0.06061] -> mdd in (0.09, 0.11)
- `test_max_drawdown_monotone_up_is_zero`: all positive returns -> 0.0
- `test_ir_zero_when_strategy_equals_naive`: strategy == naive -> 0.0
- `test_ir_nonzero_when_strategy_beats_naive`: seed=7 with +5bp daily edge -> IR > 0
- `test_calmar_zero_drawdown_is_zero`: mdd=0 -> 0.0
- `test_calmar_basic`: 0.20/0.10 = 2.0 within 1e-9
- `test_monthly_returns_groups_by_month`: 60 days -> Jan + Feb keys, positive values
- `test_compute_all_stats_v2_keys`: 252-day array -> all 7 required keys present, is_partial_year=False

**test_backtest_gate.py** (11 new tests):
- `test_gate_conjunctive_pass`: main=1.5, ex2020=0.9 -> pass
- `test_gate_fails_when_main_below_threshold`: main=0.99 -> fail, "main slice" in reason
- `test_gate_fails_when_ex2020_below_threshold`: main=1.5, ex2020=0.79 -> fail, "ex-2020" in reason (conjunctive trap)
- `test_gate_fails_when_both_below_threshold`: both 0.5 -> fail with both names in reason
- `test_gate_pending_on_partial_year`: is_partial_year=True -> pending
- `test_gate_override_forces_pass`: even with fail inputs, override=True -> pass
- `test_gate_thresholds_are_exact`: exactly at thresholds passes (>= not >)
- `test_fire_gate_alert_v2_pass_event_type`: event_type == EVENT_TYPE_PASS
- `test_fire_gate_alert_v2_fail_event_type`: event_type == EVENT_TYPE_FAIL, run_id None preserved
- `test_ex2020_slice`: FR-6.5 explicit: main=1.2, ex2020=0.85 -> pass, both values in reason text

## Test Results

| File | Tests | Result |
|------|-------|--------|
| test_backtest_stats.py | 32 (21 existing + 11 new) | 32 passed |
| test_backtest_gate.py | 24 (13 existing + 11 new) | 24 passed |
| test_backtest_as_of.py | 5 | 5 passed |
| test_backtest_schema.py | 6 | 6 passed |
| test_backtest_uses_prod_engine.py | 11 | 11 passed |
| test_backtest_e2e.py | 6 | 3 passed, 3 skipped (DB-gated) |
| **Total** | **84** | **81 passed, 3 skipped** |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] sd < 1e-10 threshold guard in compute_sharpe**
- **Found during:** Task 1 GREEN phase (test_sharpe_golden_constant_return failed)
- **Issue:** `sd == 0.0` exact check failed for constant returns array; numpy ddof=0 std of [0.001]*252 returns ~7e-16 (not exactly 0), producing an astronomically large Sharpe ratio
- **Fix:** Changed `if sd == 0.0` to `if sd < 1e-10` - same fix as 06-01's `sharpe_ratio` function
- **Files modified:** `backend/app/backtest/stats.py`
- **Commit:** 0dca24de

**2. [Rule 1 - Bug] compute_all_stats name collision with old legacy function**
- **Found during:** Task 1 GREEN phase (TestComputeAllStats tests failed with unexpected keyword argument)
- **Issue:** Old `compute_all_stats(daily_returns, naive_returns, start_date, daily_rf)` and new `compute_all_stats(dates, daily_returns, naive_returns, daily_rf_array)` have incompatible signatures; Python cannot dispatch on argument types at import time
- **Fix:** Renamed old function to `compute_all_stats_v1` and updated old test import to `compute_all_stats_v1 as compute_all_stats`; new plan 06-03 function is the canonical `compute_all_stats`
- **Files modified:** `backend/app/backtest/stats.py`, `backend/tests/backtest/test_backtest_stats.py`
- **Commit:** 0dca24de

**3. [Rule 1 - Bug] Test import used non-existent `evaluate_gate as evaluate_gate_v2` alias**
- **Found during:** Task 2 RED phase design
- **Issue:** New test code used `from app.backtest.gate import evaluate_gate as evaluate_gate_v2` but old `evaluate_gate` takes float args, not dict args; aliasing would break on first dict call
- **Fix:** Added distinct function `evaluate_gate_v2` to gate.py and updated test import to use it directly; same pattern for `fire_gate_alert_v2` in alerts.py
- **Files modified:** `backend/app/backtest/gate.py`, `backend/app/backtest/alerts.py`, `backend/tests/backtest/test_backtest_gate.py`
- **Commit:** 8ad6a219

## Known Stubs

- `fire_gate_alert_v2` in `alerts.py`: logs only, no SendGrid/Slack calls. This is intentional per plan spec. Phase 7 wires the external integrations.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. SQL in `load_daily_rf_as_of` uses `text()` with bound `:as_of` parameter (T-6-12 mitigated). Gate conjunctive logic confirmed by `test_gate_fails_when_ex2020_below_threshold` (T-6-09 mitigated).

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/app/backtest/stats.py exists (327 lines > 120 min) | PASSED |
| compute_sharpe, compute_max_drawdown, compute_ir_vs_baseline defined | PASSED |
| compute_calmar, compute_monthly_returns, load_daily_rf_as_of, compute_all_stats defined | PASSED |
| TRADING_DAYS_PER_YEAR constant present | PASSED |
| SELECT rf FROM ff5_factors present | PASSED |
| ingestion_timestamp <= :as_of present | PASSED |
| backend/app/backtest/gate.py exists (165 lines > 60 min) | PASSED |
| MAIN_SHARPE_THRESHOLD = 1.0 present | PASSED |
| evaluate_gate_v2 with conjunctive `and` logic | PASSED |
| backend/app/backtest/alerts.py exists (132 lines > 30 min) | PASSED |
| EVENT_TYPE_PASS = "backtest_gate_pass" present | PASSED |
| EVENT_TYPE_FAIL = "backtest_gate_fail" present | PASSED |
| test_backtest_stats.py contains test_sharpe_golden | PASSED |
| test_backtest_gate.py contains test_gate_conjunctive | PASSED |
| test_gate_fails_when_ex2020_below_threshold present | PASSED |
| test_ex2020_slice present | PASSED |
| 56 stats+gate tests pass | PASSED |
| 81 total backtest tests pass (3 skipped DB-gated) | PASSED |
| ruff check on all 3 modified modules | PASSED |
| commit 0dca24de (stats.py) | FOUND |
| commit 8ad6a219 (gate.py + alerts.py + tests) | FOUND |
