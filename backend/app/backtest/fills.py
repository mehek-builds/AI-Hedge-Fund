"""Deterministic simulated fills for backtest replay.

Uses transaction_cost_bps from global CONFIG as the round-trip cost
(entry + exit combined, per Phase 5 decision). No separate slippage
model for v1.0.

FR-6.1: the close price used for fills is queried with ingestion_timestamp <= as_of.
"""

import logging
import sys
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# Add repo root to sys.path so rl.* and config.py imports work.
# fills.py lives at backend/app/backtest/fills.py, so 3 levels up is repo root.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import CONFIG  # noqa: E402 (must be after sys.path augmentation)

logger = logging.getLogger(__name__)

# Round-trip transaction cost in basis points (12.5 bps = 0.00125 as decimal)
_COST_DECIMAL = CONFIG.risk.transaction_cost_bps / 10_000.0


def get_close_as_of(
    session: Session,
    symbol: str,
    as_of: datetime,
) -> Optional[float]:
    """Return the most recent close price for symbol visible as of as_of.

    FR-6.1: filters ingestion_timestamp <= as_of (point-in-time correctness).
    Returns None if no bar is available (skips fill for this symbol/date).
    """
    row = session.execute(
        text(
            """
            SELECT close
            FROM price_bars
            WHERE symbol = :symbol
              AND time <= :as_of
              AND ingestion_timestamp <= :as_of
            ORDER BY time DESC
            LIMIT 1
            """
        ),
        {"symbol": symbol, "as_of": as_of},
    ).fetchone()
    return float(row[0]) if row else None


def simulate_fill(
    close_price: float,
    position_size_fraction: float,
    nav: float,
    direction: str = "long",
) -> dict:
    """Compute a deterministic simulated fill for a single trade.

    Args:
        close_price: execution price (last close as_of the replay date)
        position_size_fraction: fraction of NAV to allocate (e.g., 0.02)
        nav: current portfolio NAV in dollars
        direction: 'long' or 'short'

    Returns a dict with:
        shares: number of shares (fractional allowed)
        notional: dollar value of the fill
        cost: round-trip transaction cost in dollars
        net_notional: notional minus cost
    """
    if close_price <= 0:
        logger.warning("Non-positive close price %.4f, skipping fill", close_price)
        return {"shares": 0.0, "notional": 0.0, "cost": 0.0, "net_notional": 0.0}

    notional = position_size_fraction * nav
    shares = notional / close_price
    cost = notional * _COST_DECIMAL  # round-trip cost applied at entry
    sign = 1.0 if direction == "long" else -1.0

    return {
        "shares": sign * shares,
        "notional": sign * notional,
        "cost": cost,
        "net_notional": sign * (notional - cost),
    }
