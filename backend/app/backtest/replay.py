"""Backtest replay step: calls production signal engine and SAC ensemble.

FR-6.2: this module imports from production modules only. No backtest-specific
signal logic is defined here. Any grep for backtest-only signal code should
return nothing from this file.

FR-6.1: all DB queries use ingestion_timestamp <= as_of (via production modules
that already enforce this) or explicit point-in-time filtering.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# Add repo root to sys.path so rl.* imports work.
# replay.py lives at backend/app/backtest/replay.py, so 3 levels up is repo root.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger(__name__)


def _load_active_earnings_events(session: Session, as_of: datetime) -> list[int]:
    """Return earnings event IDs announced on or just before as_of and still in window.

    Point-in-time: filters ingestion_timestamp <= as_of so events ingested after
    the as_of date are not visible to the replay (FR-6.1).
    """
    rows = session.execute(
        text(
            """
            SELECT id
            FROM earnings_events
            WHERE announced_at::date = :as_of_date
              AND ingestion_timestamp <= :as_of
            ORDER BY id
            """
        ),
        {"as_of_date": as_of.date(), "as_of": as_of},
    ).fetchall()
    return [r[0] for r in rows]


def _get_portfolio_nav(session: Session, as_of: datetime) -> float:
    """Return the most recent portfolio NAV as of the replay date.

    Fallback to 1_000_000.0 if no position rows exist (fresh portfolio).
    """
    row = session.execute(
        text(
            """
            SELECT SUM(market_value)
            FROM portfolio_positions
            WHERE ingestion_timestamp <= :as_of
            """
        ),
        {"as_of": as_of},
    ).fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return 1_000_000.0  # default starting NAV


def load_active_events_as_of(session: Session, as_of: datetime) -> list:
    """Return earnings event ORM rows (or plain objects) visible as of as_of.

    Point-in-time: filters ingestion_timestamp <= as_of so events ingested after
    the as_of date are not visible to the replay (FR-6.1).

    Returns a list of objects; each object is passed to replay_step as the `event`
    argument. Uses the EarningsEvent ORM when available, falls back to row tuples.
    """
    try:
        rows = session.execute(
            text(
                """
                SELECT id, symbol, announced_at, eps_actual, eps_estimate
                FROM earnings_events
                WHERE announced_at::date = :as_of_date
                  AND ingestion_timestamp <= :as_of
                ORDER BY id
                """
            ),
            {"as_of_date": as_of.date(), "as_of": as_of},
        ).fetchall()
        # Return lightweight namedtuple-like objects so replay_step can access .id
        from collections import namedtuple

        _EE = namedtuple("_EE", ["id", "symbol", "announced_at", "eps_actual", "eps_estimate"])
        return [_EE(*r) for r in rows]
    except Exception as exc:
        logger.warning("load_active_events_as_of failed for %s: %s", as_of.date(), exc)
        return []


def load_active_ensemble(session: Session):
    """Load the latest SACEnsemble and MoEController from the DB.

    Returns (ensemble, moe) tuple. Raises on failure so the caller can
    decide whether to abort or fall back.
    """
    from rl.sac_agent import SACEnsemble
    from rl.moe_controller import MoEController

    ensemble = SACEnsemble.load_latest_from_db(session)
    moe = MoEController()
    return ensemble, moe


def replay_step(session: Session, ensemble, moe, as_of: datetime, event) -> Optional[dict]:
    """Execute the backtest replay for a single earnings event at as_of.

    Calls production signal engine, macro loader, and SAC ensemble.
    Returns a dict with keys:
        signal_id, signal_row (Signal ORM), macro_score, macro_components,
        blended_entry_size, final_entry_size, as_of
    or None if the event cannot be processed (no signal, no price, etc.).

    FR-6.2: no signal logic is re-implemented here.
    """
    from app.signals.pipeline import compute_signal_for_event
    from app.portfolio.macro_loader import load_macro_snapshot
    from app.backtest.fills import get_close_as_of
    from sqlalchemy import text as _text

    event_id = event.id if hasattr(event, "id") else event[0]

    signal_id = compute_signal_for_event(session, event_id)
    if signal_id is None:
        return None

    # Load signal ORM row
    signal_row = session.execute(
        _text(
            """
            SELECT s.signal_id, s.symbol, s.direction, s.eps_gap,
                   s.quality_score, s.three_axis_composite, s.naive_position_size,
                   s.ingestion_timestamp, s.created_at
            FROM signals s
            WHERE s.signal_id = :signal_id
            LIMIT 1
            """
        ),
        {"signal_id": signal_id},
    ).fetchone()
    if signal_row is None:
        return None

    # Build a lightweight object with the Signal ORM field names
    from collections import namedtuple

    _SR = namedtuple(
        "_SignalRow",
        ["signal_id", "symbol", "direction", "eps_gap",
         "quality_score", "three_axis_composite", "naive_position_size",
         "ingestion_timestamp", "created_at"],
    )
    signal_obj = _SR(*signal_row)

    symbol = signal_obj.symbol
    direction = signal_obj.direction
    naive_size = float(signal_obj.naive_position_size or 0.02)

    # Get close price (point-in-time)
    close = get_close_as_of(session, symbol, as_of)
    if close is None:
        return None

    # Macro score for MoE blending
    macro_score, macro_components = load_macro_snapshot(session, as_of=as_of)

    # Build observation vector for SAC ensemble (same as step_replay)
    direction_sign = 1.0 if direction == "long" else -1.0
    obs_vec = [close / 1000.0, macro_score / 10.0, naive_size, direction_sign]

    try:
        per_agent = ensemble.select_action_per_agent(obs_vec, deterministic=True)
        moe_action = moe.blend(per_agent, macro_score=macro_score)
        final_entry_size = float(moe_action.entry_size)
        blended_entry_size = final_entry_size
    except Exception as exc:
        logger.warning("SAC ensemble action failed for %s: %s", symbol, exc)
        final_entry_size = naive_size
        blended_entry_size = naive_size

    return {
        "signal_id": signal_id,
        "signal_row": signal_obj,
        "macro_score": macro_score,
        "macro_components": macro_components,
        "blended_entry_size": blended_entry_size,
        "final_entry_size": final_entry_size,
        "as_of": as_of,
    }


def step_replay(session: Session, as_of: datetime) -> Optional[float]:
    """Execute one day of the backtest replay loop.

    Calls:
    1. Production signal engine (compute_signal_for_event) for any earnings events
    2. Production macro loader (load_macro_snapshot) for MoE macro_score
    3. Production SAC ensemble (SACEnsemble + MoEController) for position sizing

    Returns the daily portfolio return (float) or None if no signals fired.

    FR-6.2: no signal logic is re-implemented here.
    """
    # Import production modules (deferred to avoid import-time DB calls)
    from app.signals.pipeline import compute_signal_for_event
    from app.portfolio.macro_loader import load_macro_snapshot
    from app.backtest.fills import get_close_as_of, simulate_fill

    event_ids = _load_active_earnings_events(session, as_of)
    if not event_ids:
        return None  # no earnings events today, skip

    nav = _get_portfolio_nav(session, as_of)
    macro_score, _ = load_macro_snapshot(session, as_of=as_of)

    # Lazy-load RL ensemble to avoid import cost when no events fire
    try:
        from rl.sac_agent import SACEnsemble
        from rl.moe_controller import MoEController

        ensemble = SACEnsemble.load_latest_from_db(session)
        moe = MoEController()
    except Exception as exc:
        logger.warning(
            "RL ensemble load failed for as_of=%s, skipping SAC sizing: %s",
            as_of.date(),
            exc,
        )
        return None

    day_pnl = 0.0

    for event_id in event_ids:
        signal_id = compute_signal_for_event(session, event_id)
        if signal_id is None:
            continue

        # Load signal direction and symbol from DB
        row = session.execute(
            text(
                """
                SELECT s.direction, s.symbol, s.naive_position_size
                FROM signals s
                WHERE s.signal_id = :signal_id
                LIMIT 1
                """
            ),
            {"signal_id": signal_id},
        ).fetchone()
        if row is None:
            continue

        direction, symbol, naive_size = row[0], row[1], float(row[2])

        # Get close price for fill (point-in-time)
        close = get_close_as_of(session, symbol, as_of)
        if close is None:
            continue

        # Build observation vector for SAC ensemble
        # Observation: [close, macro_score_normalized, naive_size, direction_sign]
        direction_sign = 1.0 if direction == "long" else -1.0
        obs_vec = [close / 1000.0, macro_score / 10.0, naive_size, direction_sign]

        try:
            per_agent = ensemble.select_action_per_agent(obs_vec, deterministic=True)
            moe_action = moe.blend(per_agent, macro_score=macro_score)
            position_size = float(moe_action.entry_size)
        except Exception as exc:
            logger.warning("SAC ensemble action failed for %s: %s", symbol, exc)
            position_size = naive_size

        fill = simulate_fill(close, position_size, nav, direction)
        # Simplified daily return: next-day close change (replay uses same-day for now)
        # Phase 06-04 will wire the full hold-period return calculation
        day_pnl += fill["net_notional"]

    daily_return = day_pnl / nav if nav > 0 else 0.0
    return daily_return
