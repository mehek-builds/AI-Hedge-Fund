---
phase: 06-backtest-engine-validation-gate
type: prd
status: draft
depends_on_phase: 5
gates: 7
requirements:
  - FR-6.1
  - FR-6.2
  - FR-6.3
  - FR-6.4
  - FR-6.5
  - FR-6.6
  - NFR-1
---

# Phase 6 PRD, Backtest Engine + Validation Gate

**Owner:** Mehek
**Status:** Draft v0.1
**Date:** 2026-05-12
**Phase dependency:** Phase 5 (RL training) must be complete
**Phase this gates:** Phase 7 (Alpaca paper trading) cannot start unless Sharpe > 1.0 gate passes

---

## Objective

Build a point-in-time-correct backtest engine that replays 2018 through 2023 using the **production** signal engine and SAC ensemble (not a parallel reimplementation), produces full performance statistics, and enforces a programmatic go/no-go gate. The gate is the single most important defect-prevention surface in the system: a false pass (look-ahead bias inflating Sharpe) directly causes Phase 7 to deploy a broken strategy to paper trading.

Per NFR-1, look-ahead bias is the highest-severity defect class. Phase 1 already established `ingestion_timestamp` semantics. Phase 6 proves they hold end-to-end through a full replay.

---

## Success Criteria (from ROADMAP, restated as testable invariants)

1. **Point-in-time correctness**: every query in the replay path filters on `ingestion_timestamp <= as_of`. A deliberately injected future-timestamped data point is rejected by the filter and never reaches the signal engine.
2. **No parallel implementation**: the backtest imports and calls the production signal engine and SAC ensemble. Grep for backtest-only signal code returns nothing.
3. **Full statistics persisted**: Sharpe ratio, max drawdown, IR vs. naive baseline, Calmar ratio, monthly returns breakdown, all written to the `backtest_runs` table.
4. **Programmatic gate**: a `backtest_gate_pass` or `backtest_gate_fail` alert fires at end of replay. Phase 7 startup checks for `backtest_gate_pass` and refuses to run otherwise.
5. **Ex-2020 stress slice**: a separate backtest excluding March-April 2020 reports Sharpe > 0.8.
6. **Dashboard surface**: results are queryable from `backtest_runs` and visible in the Backtest Explorer view (Phase 8 consumes this).

---

## Non-Goals

- Live paper trading (Phase 7)
- Dashboard rendering of backtest results (Phase 8 consumes the table; Phase 6 only persists)
- Walk-forward retraining of the RL agent during the replay (the RL model from Phase 5 is treated as fixed)
- Transaction cost modeling beyond the agreed slippage/commission constants (decided in Phase 5)
- Multi-strategy backtests (single-strategy SAC ensemble only)

---

## Architecture

```
backtest run
    │
    ├─► date iterator (2018-01-01 → 2023-12-31, daily)
    │      │
    │      ▼
    │   as_of = current_date
    │      │
    │      ▼
    │   point_in_time.py (from Phase 1)
    │      filters ingestion_timestamp <= as_of
    │      │
    │      ▼
    │   production signal engine (from Phase 3)
    │      │
    │      ▼
    │   production SAC ensemble (from Phase 5)
    │      │
    │      ▼
    │   portfolio sizing + position updates (from Phase 4)
    │      │
    │      ▼
    │   simulated fills (no Alpaca calls)
    │      │
    └─► daily P&L → backtest_runs row
                │
                ▼
        end-of-replay statistics
                │
                ▼
        gate check: Sharpe > 1.0?
                │
        ┌───────┴───────┐
        ▼               ▼
    pass alert      fail alert
```

**Critical design decision:** the date iterator is the *only* place `as_of` is set. Every downstream call inherits it via the existing `point_in_time` helper. This is the single point of look-ahead-bias defense.

---

## Plan Breakdown (sub-plans)

This phase decomposes into four execute-plans, run in dependency order:

### 06-01: Backtest harness skeleton + date iterator

**Files:**
- `backend/app/backtest/__init__.py`
- `backend/app/backtest/runner.py` (date iterator, as_of plumbing, top-level `run_backtest(start, end)`)
- `backend/app/backtest/fills.py` (deterministic simulated fills, slippage/commission constants from config)
- `backend/alembic/versions/00XX_backtest_runs.py` (creates `backtest_runs` table)
- `backend/app/models/backtest_runs.py`
- `backend/tests/test_backtest_as_of.py` (future-timestamped row injection test, REQUIRED for FR-6.1)

**Must-have invariants:**
- Injecting a row with `ingestion_timestamp = as_of + 1 day` into any source table results in that row being absent from every query the backtest issues for `as_of`.
- The date iterator handles market-closed days correctly (skips weekends and US holidays via existing calendar from Phase 2).
- `backtest_runs` schema captures: run_id, start_date, end_date, sharpe, max_drawdown, ir_vs_baseline, calmar, monthly_returns (jsonb), config_snapshot (jsonb), gate_status, created_at.

### 06-02: Production-code reuse wiring

**Files:**
- `backend/app/backtest/replay.py` (calls into `signals.engine.compute_signal()` and `rl.ensemble.act()` from production code paths)
- `backend/tests/test_backtest_uses_prod_engine.py` (import-graph assertion: backtest imports from production modules; no `backtest_only_*` symbols exist anywhere)

**Must-have invariants:**
- A grep for `def compute_signal` returns exactly one definition in the production module. No copy in the backtest tree.
- Same for SAC `ensemble.act`, portfolio sizing, position update logic.
- Any signal-engine bug fix automatically flows into the next backtest run without backtest-side changes.

### 06-03: Statistics + gate logic

**Files:**
- `backend/app/backtest/stats.py` (Sharpe, max drawdown, IR vs naive equal-weight baseline, Calmar, monthly returns)
- `backend/app/backtest/gate.py` (programmatic gate: Sharpe > 1.0 main slice AND Sharpe > 0.8 ex-2020 slice)
- `backend/app/backtest/alerts.py` (fires `backtest_gate_pass` or `backtest_gate_fail` via the alerting interface from Phase 7's spec, stubbed for now so Phase 7 can wire it)
- `backend/tests/test_backtest_stats.py` (golden numbers on a synthetic 2-year deterministic run)
- `backend/tests/test_backtest_gate.py` (gate logic: pass conditions, fail conditions, edge case where main passes but ex-2020 fails → overall fail)

**Must-have invariants:**
- Sharpe computation uses daily returns, 252 trading-day annualization, risk-free rate from config.
- Gate is conjunctive: BOTH slices must pass, not either-or.
- A fail at the gate writes `gate_status = 'fail'` and the reason to `backtest_runs`. Phase 7 reads this row at startup.
- Ex-2020 stress slice is implemented by passing `exclude_date_range=('2020-03-01', '2020-04-30')` to the runner; it does not require a separate code path.

### 06-04: Full 2018-2023 replay execution + result persistence

**Files:**
- `backend/scripts/run_full_backtest.py` (entrypoint, takes config, calls runner for main + ex-2020 slices, writes both rows, fires gate alert)
- `backend/tests/test_backtest_e2e.py` (smoke test on a 1-month slice with fake data, asserts end-to-end pipeline produces a row in `backtest_runs`)
- `docs/backtest-runbook.md` (how to invoke, expected runtime, what to do on fail)

**Must-have invariants:**
- Full replay completes in a documented time budget (target: under 4 hours on Railway production sizing; this is a soft target, not a gate).
- Run is idempotent: rerunning with the same config and data state produces identical Sharpe (within floating-point tolerance).
- On fail, the runbook tells the user how to diagnose (which year/quarter dragged Sharpe down, look at monthly returns breakdown).

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Look-ahead bias slips through despite as_of filtering | Critical | Mandatory future-row injection test in 06-01. CI fails if test fails. Manual code review of every query in the signal engine path. |
| Production engine has a subtle bug that only manifests at scale | High | Phase 5 should have caught this; if backtest reveals it, FIX the production engine (do not patch the backtest). |
| Sharpe is borderline (between 0.9 and 1.1) and gate decision feels arbitrary | Medium | Document the gate threshold rationale. If borderline, do NOT lower the threshold. Instead, return to Phase 3-5 and improve the signal or policy. |
| Ex-2020 slice exposes COVID-period over-fitting | Medium (this is the point of the slice) | Expected outcome. If ex-2020 Sharpe drops below 0.8, the strategy fails the gate and Phase 7 is blocked. Treat as feature, not bug. |
| Replay runtime is too long to iterate on | Medium | Add a `--fast` mode that runs a 1-year slice for development. Full replay only required for gate decisions, not for every commit. |
| Backtest tests pass on synthetic data but real-data run reveals integration bugs | High | 06-04 includes E2E test on 1-month real-data slice before full replay. Catch integration issues before the 4-hour run. |

---

## Open Questions

1. **Risk-free rate source**: configurable constant, or pull T-bill rate from macro indicators table point-in-time? Proposal: pull from macro indicators (Phase 4 work product) for realism. Confirm before 06-03 locks.
2. **Naive baseline definition**: equal-weight portfolio over the same universe, or SPY benchmark? Proposal: equal-weight over the same earnings universe (apples to apples). SPY can be reported as a secondary number.
3. **Sharpe annualization edge case**: when the replay has fewer than 252 days (development mode), how is Sharpe computed? Proposal: annualize anyway, flag in result row as `is_partial_year: true`. Gate only runs on full replays.
4. **Gate retry policy**: if a gate fails, does Phase 7 startup poll for a new pass, or require a manual override? Proposal: require manual override flag in config (`override_gate_pass: false` by default). Forces a human decision.
5. **Walk-forward retraining**: explicitly out of scope, but document the decision. If we ever want it, it is a new phase, not a Phase 6 extension.

---

## Acceptance Checklist (for phase verification)

- [ ] FR-6.1: future-row injection test passes (look-ahead bias rejected)
- [ ] FR-6.2: import-graph test passes (no backtest-only signal code)
- [ ] FR-6.3: `backtest_runs` row contains Sharpe, max drawdown, IR vs baseline, Calmar, monthly returns
- [ ] FR-6.4: `backtest_gate_pass` or `backtest_gate_fail` alert fires; Phase 7 startup check reads this
- [ ] FR-6.5: ex-2020 slice runs as separate `backtest_runs` row with Sharpe > 0.8 reported
- [ ] FR-6.6: row queryable from `backtest_runs` table; schema matches what Phase 8 Backtest Explorer expects
- [ ] NFR-1: zero look-ahead bias defects (validated by 06-01 injection test + manual review of signal engine query paths)

---

## Links

- [ROADMAP](../../ROADMAP.md)
- [Phase 1 plan, point-in-time foundation](../01-infrastructure-data-foundation/01-02-PLAN.md)
- [STATE](../../STATE.md)

---

## Next Steps

1. Confirm open question #1 (risk-free rate source) before 06-03 starts.
2. Run `/gsd-plan-phase 6` to expand each sub-plan (06-01 through 06-04) into full execute-plans with file-level must-haves, mirroring the Phase 1 structure.
3. Or, if proceeding manually, start with 06-01 (harness skeleton) since 06-02, 06-03, 06-04 all depend on it.
