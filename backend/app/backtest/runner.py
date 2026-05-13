"""Backtest runner: date iterator, as_of plumbing, and run orchestration.

FR-6.1: every DB query in this module must filter ingestion_timestamp <= as_of.
Uses synchronous SQLAlchemy session (postgresql+psycopg2) consistent with
all existing Phase 2-5 flow code.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import text

from app.flows._base import sync_session

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""

    start_date: date
    end_date: date
    # Optionally exclude a date range for stress-slice runs (FR-6.5)
    exclude_start: Optional[date] = None
    exclude_end: Optional[date] = None
    # Allow manual override of gate pass (documented bypass only)
    override_gate_pass: bool = False
    # Label for config_snapshot (e.g., "full", "ex2020")
    run_label: str = "full"
    # Extra metadata stored in config_snapshot JSONB
    extra: dict = field(default_factory=dict)


def trading_dates(start: date, end: date) -> list[date]:
    """Return business days between start and end inclusive.

    Uses pandas bdate_range (Mon-Fri). Non-NYSE holidays are included;
    the replay loop skips dates where no price bars exist.
    """
    return [d.date() for d in pd.bdate_range(start=start, end=end, freq="B")]


def sp500_members_as_of(session, as_of: date) -> list[str]:
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


def run_backtest(config: BacktestConfig) -> dict:
    """Execute a backtest run and return a results dict.

    The caller (replay.py) iterates dates and calls this to coordinate
    signal engine, SAC ensemble, and portfolio sizing. This function
    owns the date iterator and the DB session lifecycle.

    Returns a dict with keys matching BacktestRun columns:
        start_date, end_date, gate_status, is_partial_year, config_snapshot, ...
    """
    dates = trading_dates(config.start_date, config.end_date)

    # Remove excluded range for stress-slice runs (FR-6.5)
    if config.exclude_start and config.exclude_end:
        dates = [
            d
            for d in dates
            if not (config.exclude_start <= d <= config.exclude_end)
        ]
        is_partial = True
    else:
        is_partial = False

    logger.info(
        "Backtest run starting: %s to %s, %d trading days, label=%s",
        config.start_date,
        config.end_date,
        len(dates),
        config.run_label,
    )

    daily_returns: list[float] = []

    with sync_session() as session:
        for as_of in dates:
            as_of_dt = datetime.combine(as_of, datetime.min.time()).replace(
                tzinfo=timezone.utc
            )
            # Import here to defer until session is open (avoids import-time DB calls)
            from app.backtest.replay import step_replay

            day_return = step_replay(session, as_of_dt)
            if day_return is not None:
                daily_returns.append(day_return)

    config_snap = {
        "start_date": config.start_date.isoformat(),
        "end_date": config.end_date.isoformat(),
        "run_label": config.run_label,
        "override_gate_pass": config.override_gate_pass,
        **config.extra,
    }
    if config.exclude_start:
        config_snap["exclude_start"] = config.exclude_start.isoformat()
        config_snap["exclude_end"] = config.exclude_end.isoformat() if config.exclude_end else None

    return {
        "start_date": config.start_date,
        "end_date": config.end_date,
        "daily_returns": daily_returns,
        "is_partial_year": is_partial,
        "config_snapshot": config_snap,
        "gate_status": "pending",
    }
