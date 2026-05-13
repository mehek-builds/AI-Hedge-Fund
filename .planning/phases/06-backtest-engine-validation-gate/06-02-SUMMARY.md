---
phase: "06"
plan: "02"
subsystem: backtest-engine
tags: [backtest, fr-6.2, import-graph, production-reuse, wave-1]
dependency_graph:
  requires:
    - "06-01: backtest harness package (replay.py, fills.py, runner.py)"
    - "03-01: compute_signal_for_event in app/signals/pipeline.py"
    - "05-01: SACEnsemble and MoEController in rl/sac_agent.py and rl/moe_controller.py"
    - "04-02: compute_position_size in app/portfolio/pipeline.py"
  provides:
    - "Extended FR-6.2 test suite (11 tests, up from 6)"
    - "Must-have invariant tests: single definition, no portfolio reimplementation, no SAC reimplementation"
    - "ruff format applied to all backtest package files"
    - "06-02-PLAN.md planning artifact"
  affects:
    - "06-03: stats and gate (FR-6.2 compliance verified before stats wiring)"
    - "06-04: full replay (confirms production-code reuse holds end-to-end)"
tech_stack:
  added: []
  patterns:
    - "AST-based import-graph assertions (ast.walk over FunctionDef nodes)"
    - "pathlib.rglob for codebase-wide single-definition checks"
    - "FR-6.2 test pattern: verify no function named X in backtest/, exactly one X in production"
key_files:
  created:
    - .planning/phases/06-backtest-engine-validation-gate/06-02-PLAN.md
  modified:
    - backend/tests/backtest/test_backtest_uses_prod_engine.py
    - backend/app/backtest/alerts.py
    - backend/app/backtest/fills.py
    - backend/app/backtest/gate.py
    - backend/app/backtest/replay.py
    - backend/app/backtest/runner.py
    - backend/app/backtest/stats.py
decisions:
  - "replay.py FR-6.2 compliant as shipped by 06-01: all production imports present, no signal/RL/portfolio logic redefined"
  - "5 new must-have invariant tests added to cover portfolio sizing reuse and SAC action selection reuse"
  - "ruff format applied to all backtest package files (format-only, no logic changes)"
metrics:
  duration: "~2 minutes"
  completed_date: "2026-05-13"
  tasks_completed: 3
  files_created: 1
  tests_added: 5
---

# Phase 6 Plan 2: Production-Code Reuse Wiring Summary

FR-6.2 compliance verified and extended: `replay.py` confirmed to import exclusively from production modules with 5 new AST-based tests covering portfolio sizing, SAC action selection, and single-definition invariants. Test count grew from 6 to 11, all passing.

## What Was Built

### Plan File

`06-02-PLAN.md` created (was missing from the planning artifact set). Describes the three tasks:
1. Verify replay.py FR-6.2 compliance
2. Extend must-have invariant tests
3. Lint and full test run

### FR-6.2 Test Extensions (5 new tests)

`backend/tests/backtest/test_backtest_uses_prod_engine.py` extended with:

1. `test_no_compute_position_size_defined_in_backtest_modules` - portfolio sizing (`compute_position_size`) must not be re-implemented in any backtest module; it belongs in `app.portfolio.pipeline`
2. `test_no_portfolio_pipeline_logic_in_backtest_modules` - portfolio pipeline functions (`apply_erp_cap`, `apply_mag7_cap`, `apply_stop_loss`, `size_position`) must not appear in backtest modules
3. `test_single_definition_of_compute_signal_for_event` - codebase-wide AST search confirms exactly one definition of `compute_signal_for_event`, in `app/signals/pipeline.py`. Any duplicate would indicate a parallel reimplementation.
4. `test_replay_imports_fills_not_reimplemented` - `replay.py` imports `simulate_fill` from `app.backtest.fills` and defines no fill calculation function inline
5. `test_no_select_action_defined_in_backtest_modules` - SAC `select_action` not re-implemented in any backtest module; action selection belongs in `rl.sac_agent.SACEnsemble`

### replay.py FR-6.2 Verification

`replay.py` was already compliant from 06-01:
- Imports `compute_signal_for_event` from `app.signals.pipeline`
- Imports `load_macro_snapshot` from `app.portfolio.macro_loader`
- Imports `SACEnsemble` from `rl.sac_agent` and `MoEController` from `rl.moe_controller`
- Imports `simulate_fill` from `app.backtest.fills`
- Defines no signal, RL, or portfolio logic locally

No modifications to `replay.py` logic were needed.

### ruff Format

`ruff format` applied to all 11 backtest package files (format-only changes, no logic). The files were lint-clean (`ruff check`) before and after.

## Test Results

| File | Tests | Result |
|------|-------|--------|
| test_backtest_uses_prod_engine.py | 11 (was 6) | 11 passed |
| test_backtest_as_of.py | 5 | 5 passed |
| test_backtest_schema.py | 6 | 6 passed |
| test_backtest_stats.py | 21 | 21 passed |
| test_backtest_gate.py | 14 | 14 passed |
| test_backtest_e2e.py | 6 | 3 passed, 3 skipped (DB-gated) |
| **Total** | **63** | **60 passed, 3 skipped** |

## Deviations from Plan

None. The CONTEXT.md spec for 06-02 called for `replay.py` and `test_backtest_uses_prod_engine.py` - both existed from 06-01 and were FR-6.2 compliant. Plan 02 extended the test coverage to fully satisfy the must-have invariants documented in the CONTEXT.md.

The missing `06-02-PLAN.md` file was created as part of this plan execution (the planning phase had seeded only a CONTEXT.md with sub-plan descriptions, not individual PLAN.md files).

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| 06-02-PLAN.md created | FOUND |
| test_backtest_uses_prod_engine.py modified | FOUND |
| commit 670965d2 (plan file) | FOUND |
| commit 7312ae6a (test enhancements + format) | FOUND |
| 60 backtest tests pass | PASSED |
| ruff check on backtest package | PASSED |
| ruff format check on backtest package | PASSED |
