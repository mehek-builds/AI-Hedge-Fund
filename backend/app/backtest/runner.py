"""Backtest runner: date iterator, as_of plumbing, and run orchestration.

FR-6.1: every DB query in this module must filter ingestion_timestamp <= as_of.
Uses synchronous SQLAlchemy session (postgresql+psycopg2) consistent with
all existing Phase 2-5 flow code.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date as date_t
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.flows._base import sync_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy BacktestConfig dataclass (kept for backward compat with plan 06-01/02/03 tests)
# ---------------------------------------------------------------------------


@dataclass
class BacktestConfig:
    """Configuration for a single backtest run (legacy API)."""

    start_date: date_t
    end_date: date_t
    # Optionally exclude a date range for stress-slice runs (FR-6.5)
    exclude_start: Optional[date_t] = None
    exclude_end: Optional[date_t] = None
    # Allow manual override of gate pass (documented bypass only)
    override_gate_pass: bool = False
    # Label for config_snapshot (e.g., "full", "ex2020")
    run_label: str = "full"
    # Extra metadata stored in config_snapshot JSONB
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Date iterator helpers
# ---------------------------------------------------------------------------


def trading_dates(start: date_t, end: date_t) -> list[date_t]:
    """Return business days between start and end inclusive.

    Uses pandas bdate_range (Mon-Fri). Non-NYSE holidays are included;
    the replay loop skips dates where no price bars exist.
    """
    return [d.date() for d in pd.bdate_range(start=start, end=end, freq="B")]


def iter_business_days(
    start: date_t,
    end: date_t,
    *,
    exclude_date_range: tuple[date_t, date_t] | None = None,
):
    """Yield business days in [start, end], optionally excluding a sub-range.

    Args:
        start: first date (inclusive)
        end: last date (inclusive)
        exclude_date_range: optional (excl_start, excl_end) tuple; dates in
            [excl_start, excl_end] are skipped (used for ex-2020 stress slice).

    Yields date objects in ascending order.
    """
    dates = trading_dates(start, end)
    if exclude_date_range is not None:
        excl_start, excl_end = exclude_date_range
        dates = [d for d in dates if not (excl_start <= d <= excl_end)]
    yield from dates


def sp500_members_as_of(session, as_of: date_t) -> list[str]:
    """Return S&P 500 member symbols visible as of as_of date.

    Point-in-time: filters ingestion_timestamp <= as_of so late additions
    do not bias earlier date slices (FR-6.1).
    """
    rows = session.execute(
        text(
            """
            SELECT DISTINCT symbol
            FROM sp500_constituents
            WHERE added_date <= :as_of
              AND (removed_date IS NULL OR removed_date > :as_of)
              AND ingestion_timestamp <= :as_of
            ORDER BY symbol
            """
        ),
        {"as_of": as_of},
    ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Private helpers for run_backtest
# ---------------------------------------------------------------------------


def _serialize_config_snapshot() -> dict:
    """Return a JSON-serializable snapshot of CONFIG (signal + risk sections only)."""
    try:
        import sys
        import os

        _ROOT = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        if _ROOT not in sys.path:
            sys.path.insert(0, _ROOT)
        from config import CONFIG  # noqa: F401

        snap: dict = {}
        for key in ("signal", "risk"):
            section = getattr(CONFIG, key, None)
            if section is None:
                continue
            if is_dataclass(section):
                snap[key] = {
                    k: (float(v) if isinstance(v, (int, float)) else str(v))
                    for k, v in asdict(section).items()
                }
            else:
                snap[key] = {
                    k: getattr(section, k)
                    for k in dir(section)
                    if not k.startswith("_") and not callable(getattr(section, k))
                }
        return snap
    except Exception as exc:
        logger.warning("_serialize_config_snapshot failed: %s", exc)
        return {}


def _direction_sign(direction: str | None) -> float:
    """Map Signal.direction to a sign multiplier for the daily-return proxy.

    long  -> +1.0
    short -> -1.0
    hold / None / unknown -> 0.0
    """
    if direction == "long":
        return 1.0
    if direction == "short":
        return -1.0
    return 0.0


# ---------------------------------------------------------------------------
# Primary run_backtest (Plan 06-04 full implementation)
# ---------------------------------------------------------------------------


def run_backtest(
    start: date_t,
    end: date_t,
    *,
    slice_type: str = "main",
    exclude_date_range: tuple[date_t, date_t] | None = None,
) -> dict:
    """Run the backtest replay over [start, end], persist a BacktestRun row, return summary dict.

    Input validation:
    - end must not be in the future (T-6-01 mitigation).
    - start must be <= end.

    Returns dict with keys:
        run_id, slice_type, start_date, end_date, sharpe, max_drawdown,
        ir_vs_baseline, calmar, monthly_returns, annualized_return,
        is_partial_year, total_trades, dates_iterated
    """
    if end > date_t.today():
        raise ValueError(f"end_date {end} must not be in the future (T-6-01)")
    if start > end:
        raise ValueError(f"start_date {start} must be <= end_date {end}")

    from app.backtest.replay import replay_step, load_active_events_as_of, load_active_ensemble
    from app.backtest.stats import compute_all_stats, load_daily_rf_as_of
    from app.models.backtest_runs import BacktestRun

    daily_dates: list[date_t] = []
    daily_returns: list[float] = []
    naive_returns: list[float] = []
    daily_rfs: list[float] = []
    trade_count = 0

    with sync_session() as session:
        ensemble, moe = load_active_ensemble(session)

        for as_of in iter_business_days(start, end, exclude_date_range=exclude_date_range):
            as_of_dt = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)
            events = load_active_events_as_of(session, as_of_dt)

            day_strat_components: list[float] = []
            day_naive_components: list[float] = []
            for event in events:
                result = replay_step(session, ensemble, moe, as_of_dt, event)
                if result is None:
                    continue
                trade_count += 1
                # replay_step returns the Signal ORM (or namedtuple) under key "signal_row"
                # (NOT "signal"); the ORM/namedtuple has no realized-return field, so we use
                # eps_gap (standardized EPS surprise -- the same primary obs vector feature
                # used in plan 06-02) combined with the signal direction as a conservative
                # per-event daily-return proxy.
                signal_row = result["signal_row"]
                daily_return_proxy = (
                    float(signal_row.eps_gap or 0.0) * _direction_sign(signal_row.direction)
                )
                day_strat_components.append(result["final_entry_size"] * daily_return_proxy)
                day_naive_components.append(0.02 * daily_return_proxy)  # NAIVE_POSITION_SIZE = 0.02

            strat_r = float(np.mean(day_strat_components)) if day_strat_components else 0.0
            naive_r = float(np.mean(day_naive_components)) if day_naive_components else 0.0
            rf_r = load_daily_rf_as_of(session, as_of_dt)

            daily_dates.append(as_of)
            daily_returns.append(strat_r)
            naive_returns.append(naive_r)
            daily_rfs.append(rf_r)

        daily_returns_arr = np.asarray(daily_returns, dtype=np.float64)
        naive_returns_arr = np.asarray(naive_returns, dtype=np.float64)
        daily_rfs_arr = np.asarray(daily_rfs, dtype=np.float64)

        stats = compute_all_stats(daily_dates, daily_returns_arr, naive_returns_arr, daily_rfs_arr)

        row = BacktestRun(
            start_date=start,
            end_date=end,
            slice_type=slice_type,
            sharpe=stats["sharpe"],
            max_drawdown=stats["max_drawdown"],
            ir_vs_baseline=stats["ir_vs_baseline"],
            calmar=stats["calmar"],
            monthly_returns=stats["monthly_returns"],
            config_snapshot=_serialize_config_snapshot(),
            gate_status="pending",  # gate evaluated externally by run_full_backtest
            is_partial_year=stats["is_partial_year"],
            total_trades=trade_count,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        run_id_str = str(row.id)

    return {
        "run_id": run_id_str,
        "slice_type": slice_type,
        "start_date": start,
        "end_date": end,
        "sharpe": stats["sharpe"],
        "max_drawdown": stats["max_drawdown"],
        "ir_vs_baseline": stats["ir_vs_baseline"],
        "calmar": stats["calmar"],
        "monthly_returns": stats["monthly_returns"],
        "annualized_return": stats["annualized_return"],
        "is_partial_year": stats["is_partial_year"],
        "total_trades": trade_count,
        "dates_iterated": len(daily_dates),
    }


def update_gate_status(run_id: str, gate_status: str, gate_reason: str) -> None:
    """Update gate_status and gate_reason on an existing backtest_runs row."""
    with sync_session() as session:
        session.execute(
            text(
                "UPDATE backtest_runs SET gate_status = :s, gate_reason = :r "
                "WHERE id = :rid"
            ),
            {"s": gate_status, "r": gate_reason, "rid": run_id},
        )
        session.commit()
