# Backtest Runbook (Phase 6)

The Sharpe gate (>= 1.0 main slice AND >= 0.8 ex-2020 slice) blocks Phase 7.
This runbook covers how to invoke the backtest, interpret results, and respond to a fail.

## Prerequisites

1. `DATABASE_URL_SYNC=postgresql://...` exported in the shell.
2. Alembic at head: `cd backend && alembic upgrade head` (must include migration 0006_backtest_runs_slice_columns).
3. RL checkpoints in `rl_checkpoints` table (Phase 5 output). If absent, the backtest runs with a
   randomly initialized ensemble, useful for plumbing tests, not for gate decisions.
4. ff5_factors table populated with `rf` column (Phase 2 flow output).

## Invocation

Full 2018-2023 replay (target ~4 hours on Railway production):

```bash
cd backend && python -m scripts.run_full_backtest
```

Fast development run (2022 only, ~30 minutes; not gate-eligible because partial-year):

```bash
cd backend && python -m scripts.run_full_backtest --fast
```

Custom range:

```bash
cd backend && python -m scripts.run_full_backtest --start 2019-01-01 --end 2021-12-31
```

Manual gate override (use only after deliberate review, see "Override policy" below):

```bash
cd backend && python -m scripts.run_full_backtest --override-gate
```

## Expected runtime

- Full 2018-2023: ~4 hours (soft target, not a gate).
- Fast slice (1 year): ~30 minutes.
- 1-month smoke: <5 minutes.

## Output interpretation

The CLI prints three sections:

1. `[backtest] main run_id=<UUID> sharpe=<value>` -- main slice result.
2. `[backtest] ex_2020 run_id=<UUID> sharpe=<value>` -- ex-2020 stress slice result.
3. `[backtest] gate_status=<pass|fail|pending> reason=<text>` -- conjunctive gate decision.

Exit code: 0 on pass or pending; 2 on fail.

## On fail: diagnosis steps

1. Query monthly_returns from the failing run:

   ```sql
   SELECT monthly_returns FROM backtest_runs WHERE run_id = '<uuid>';
   ```

   Identify the months with the most negative returns.

2. If a specific quarter dragged Sharpe down: check signals from that quarter (signals table) for
   quality score distribution; look for systematic mis-prediction on a sector.

3. If the ex-2020 slice failed but main passed: the strategy is over-fit to the COVID period.
   This is expected to be caught here; do NOT lower the gate threshold. Return to Phase 3-5 and
   improve signal robustness on non-crisis periods.

4. Compare `ir_vs_baseline`: if positive, the strategy beats the 2% naive baseline but not the
   absolute Sharpe target, the issue is volatility, not direction.

5. Re-run with `--fast` after any code change to iterate quickly before committing to a full
   4-hour run.

## Override policy

The `--override-gate` flag (and `BACKTEST_OVERRIDE_GATE_PASS=true` env var) forces gate_status=pass
regardless of Sharpe. This exists for one reason: a human has reviewed the failed run, accepts the
risk, and is consciously letting Phase 7 deploy. The override is logged in gate_reason as
"manual override via BACKTEST_OVERRIDE_GATE_PASS" -- that string is the audit trail.

Never use --override-gate to "make CI green". Always document why in a commit message.

## Known limitations

- **Daily return proxy uses `eps_gap * direction`, not realized P&L.** The runner does NOT have a
  cross-day position state machine in Phase 6 v1.0. The Signal ORM has no field for the realized
  or expected return on a position; we use `float(signal_row.eps_gap or 0.0) * sign(signal_row.direction)`
  (+1 long, -1 short, 0 hold) as the per-event daily return proxy, scaled by `final_entry_size`
  for the strategy series and by NAIVE_POSITION_SIZE (0.02) for the baseline. `eps_gap` is the
  standardized EPS surprise that already drives the primary obs vector feature in plan 06-02, so
  the gate measures whether the policy + sizing correctly capitalize on the signal it was shown.
  This proxy will under-state both wins and losses versus a true price-bar P&L; the Sharpe gate
  thresholds (>= 1.0 main, >= 0.8 ex-2020) are calibrated against this proxy and should be
  re-evaluated when a full portfolio state machine is added in a later phase.
- Trading calendar uses pandas business-day frequency, not NYSE-exact. The difference is a few
  extra no-data days per year; replay skips dates with no events gracefully.
- The replay does NOT retrain the RL agent walk-forward; the Phase 5 checkpoint is treated as
  fixed (per CONTEXT Non-Goals).
