"""Phase 6 backtest CLI entrypoint.

Usage:
    python -m scripts.run_full_backtest [--start YYYY-MM-DD] [--end YYYY-MM-DD]
                                        [--fast] [--override-gate]

Runs main + ex-2020 slices, persists two backtest_runs rows, evaluates the
Sharpe gate (>= 1.0 main AND >= 0.8 ex-2020), and fires the gate alert.
Exit code 0 on pass/pending, 2 on fail.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date

# Add backend and repo root to sys.path for module resolution
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ROOT = os.path.abspath(os.path.join(_BACKEND, ".."))
for _p in [_BACKEND, _ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from app.backtest.runner import run_backtest, update_gate_status  # noqa: E402
from app.backtest.gate import evaluate_gate_v2 as evaluate_gate  # noqa: E402
from app.backtest.alerts import fire_gate_alert_v2 as fire_gate_alert  # noqa: E402
from app.config import settings  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Phase 6 backtest (main + ex-2020 slices).")
    p.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=date(2018, 1, 1),
        help="Backtest start date (YYYY-MM-DD, default 2018-01-01)",
    )
    p.add_argument(
        "--end",
        type=lambda s: date.fromisoformat(s),
        default=date(2023, 12, 31),
        help="Backtest end date (YYYY-MM-DD, default 2023-12-31)",
    )
    p.add_argument(
        "--fast",
        action="store_true",
        help="Run a 1-year slice (2022) for development; not gate-eligible.",
    )
    p.add_argument(
        "--override-gate",
        action="store_true",
        help="Force gate pass; equivalent to settings.BACKTEST_OVERRIDE_GATE_PASS=True.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start = args.start
    end = args.end
    if args.fast:
        start = date(2022, 1, 1)
        end = date(2022, 12, 31)

    print(f"[backtest] main slice: {start} to {end}", flush=True)
    main_run = run_backtest(start, end, slice_type="main")
    print(
        f"[backtest] main run_id={main_run['run_id']} sharpe={main_run['sharpe']:.4f}",
        flush=True,
    )

    print(
        f"[backtest] ex-2020 slice: {start} to {end} excluding 2020-03-01..2020-04-30",
        flush=True,
    )
    ex2020_run = run_backtest(
        start,
        end,
        slice_type="ex_2020",
        exclude_date_range=(date(2020, 3, 1), date(2020, 4, 30)),
    )
    print(
        f"[backtest] ex_2020 run_id={ex2020_run['run_id']} sharpe={ex2020_run['sharpe']:.4f}",
        flush=True,
    )

    override = args.override_gate or settings.BACKTEST_OVERRIDE_GATE_PASS
    gate = evaluate_gate(main_run, ex2020_run, override=override)
    print(
        f"[backtest] gate_status={gate['gate_status']} reason={gate['gate_reason']}",
        flush=True,
    )

    # Persist gate result on both rows (Phase 7 reads this)
    update_gate_status(main_run["run_id"], gate["gate_status"], gate["gate_reason"])
    update_gate_status(ex2020_run["run_id"], gate["gate_status"], gate["gate_reason"])

    event = fire_gate_alert(gate["gate_status"], gate["gate_reason"], main_run["run_id"])
    print(f"[backtest] alert fired: {json.dumps(event)}", flush=True)

    if gate["gate_status"] == "fail":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
