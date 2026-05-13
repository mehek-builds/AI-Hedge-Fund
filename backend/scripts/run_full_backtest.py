"""CLI entrypoint for running the full 2018-2023 backtest.

Usage:
    python backend/scripts/run_full_backtest.py
    python backend/scripts/run_full_backtest.py --start 2018-01-01 --end 2023-12-31
    python backend/scripts/run_full_backtest.py --ex2020  # also run ex-2020 stress slice

FR-6.4: prints gate_status at end (backtest_gate_pass or backtest_gate_fail).
FR-6.5: --ex2020 flag runs the exclude-March/April-2020 slice as a separate run.
"""

import argparse
import logging
import sys
import os
from datetime import date

# Add repo root and backend to sys.path
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ROOT = os.path.abspath(os.path.join(_BACKEND, ".."))
for _p in [_BACKEND, _ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("run_full_backtest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full 2018-2023 backtest")
    parser.add_argument(
        "--start",
        default="2018-01-02",
        type=str,
        help="Backtest start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        default="2023-12-29",
        type=str,
        help="Backtest end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--ex2020",
        action="store_true",
        default=False,
        help="Also run ex-March/April-2020 stress slice (FR-6.5)",
    )
    parser.add_argument(
        "--override-gate-pass",
        action="store_true",
        default=False,
        help="Force gate_status=pass regardless of Sharpe (documented bypass only)",
    )
    return parser.parse_args()


def _persist_run(result: dict, gate_result) -> str:
    """Persist a backtest run to the DB and return the run_id."""
    from app.flows._db import SyncSessionLocal
    from app.models.backtest_runs import BacktestRun
    from app.backtest.alerts import fire_gate_alert

    with SyncSessionLocal() as session:
        run = BacktestRun(
            start_date=result["start_date"],
            end_date=result["end_date"],
            sharpe=gate_result.full_sharpe,
            gate_status=gate_result.gate_status,
            is_partial_year=result.get("is_partial_year", False),
            config_snapshot=result.get("config_snapshot"),
        )
        session.add(run)
        session.flush()
        run_id = run.id
        fire_gate_alert(session, gate_result, run_id=run_id)
        session.commit()

    return run_id


def main() -> None:
    args = parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    # Validate: end date must not be in the future
    if end > date.today():
        logger.error("end date %s is in the future — aborting to prevent look-ahead bias", end)
        sys.exit(1)

    from app.backtest.runner import BacktestConfig, run_backtest
    from app.backtest.stats import compute_all_stats
    from app.backtest.gate import evaluate_gate

    logger.info("Starting full backtest: %s to %s", start, end)
    config = BacktestConfig(
        start_date=start,
        end_date=end,
        override_gate_pass=args.override_gate_pass,
        run_label="full",
    )
    result = run_backtest(config)

    stats = compute_all_stats(
        daily_returns=result["daily_returns"],
        naive_returns=None,
        start_date=start,
    )

    gate_result = evaluate_gate(
        full_sharpe=stats["sharpe"],
        override_gate_pass=args.override_gate_pass,
    )

    run_id = _persist_run({**result, **stats}, gate_result)
    logger.info(
        "[backtest_%s] run_id=%s sharpe=%.3f max_dd=%.3f",
        gate_result.gate_status,
        run_id,
        stats["sharpe"],
        stats["max_drawdown"],
    )

    # Optional ex-2020 stress slice (FR-6.5)
    if args.ex2020:
        logger.info("Running ex-March/April-2020 stress slice")
        ex2020_config = BacktestConfig(
            start_date=start,
            end_date=end,
            exclude_start=date(2020, 3, 1),
            exclude_end=date(2020, 4, 30),
            override_gate_pass=args.override_gate_pass,
            run_label="ex2020",
        )
        ex2020_result = run_backtest(ex2020_config)
        ex2020_stats = compute_all_stats(
            daily_returns=ex2020_result["daily_returns"],
            naive_returns=None,
            start_date=start,
        )
        ex2020_gate = evaluate_gate(
            full_sharpe=ex2020_stats["sharpe"],
            is_partial_year=True,
        )
        _persist_run({**ex2020_result, **ex2020_stats}, ex2020_gate)
        logger.info(
            "Ex-2020 slice: sharpe=%.3f max_dd=%.3f",
            ex2020_stats["sharpe"],
            ex2020_stats["max_drawdown"],
        )

        # Re-evaluate conjunctive gate with both slices
        final_gate = evaluate_gate(
            full_sharpe=stats["sharpe"],
            ex2020_sharpe=ex2020_stats["sharpe"],
            override_gate_pass=args.override_gate_pass,
        )
        logger.info(
            "[final_gate_%s] full=%.3f ex2020=%.3f reason: %s",
            final_gate.gate_status,
            final_gate.full_sharpe,
            final_gate.ex2020_sharpe,
            final_gate.reason,
        )

    if gate_result.gate_status != "pass":
        sys.exit(2)


if __name__ == "__main__":
    main()
