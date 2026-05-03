"""Momentum component of the three-axis composite (FR-3.5).

Definition: 20-trading-day price return, cohort-normalized to a percentile rank
in [0, 100]. The cohort is the set of tickers with completed earnings events
in the same window (passed in by the pipeline orchestrator, not queried here).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session


def twenty_day_return(session: Session, symbol: str, as_of: datetime) -> Optional[float]:
    """Return (close_today - close_20bd_ago) / close_20bd_ago using point-in-time
    rows (`ingestion_timestamp <= :as_of`). Returns None when < 21 bars are visible.
    """
    rows = session.execute(
        text(
            """
            SELECT close
            FROM price_bars
            WHERE symbol = :symbol
              AND time <= :as_of
              AND ingestion_timestamp <= :as_of
            ORDER BY time DESC
            LIMIT 21
            """
        ),
        {"symbol": symbol, "as_of": as_of},
    ).fetchall()
    if len(rows) < 21 or rows[0][0] is None or rows[20][0] is None:
        return None
    today = float(rows[0][0])
    twenty_back = float(rows[20][0])
    if twenty_back == 0:
        return None
    return (today - twenty_back) / twenty_back


def compute_momentum_score(
    symbol_return: Optional[float],
    cohort_returns: Sequence[float],
) -> Decimal:
    """Return a percentile rank in [0, 100] of `symbol_return` within `cohort_returns`.

    Neutral default (Decimal('50.0')) when:
      - symbol_return is None
      - cohort_returns is empty
    """
    if symbol_return is None or len(cohort_returns) == 0:
        return Decimal("50.0")
    sorted_cohort = sorted(cohort_returns)
    n = len(sorted_cohort)
    if n == 1:
        # Single-element cohort — neutral middle
        return Decimal("50.0")
    # Count how many are strictly less than symbol_return.
    below = sum(1 for r in sorted_cohort if r < symbol_return)
    # Use (below / (n - 1)) * 100 so that:
    #   min of cohort → 0/n-1 = 0.0
    #   max of cohort → (n-1)/(n-1) = 100.0
    #   median of odd cohort → (n//2)/(n-1) ≈ 50
    # For ties: average the position of the tied group.
    equal = sum(1 for r in sorted_cohort if r == symbol_return)
    # mid-point of the tied group in [0, n-1] range
    rank = below + (equal - 1) / 2.0
    pct = (rank / (n - 1)) * 100.0
    # Clamp to [0, 100] for safety
    pct = max(0.0, min(100.0, pct))
    return Decimal(str(round(pct, 2)))
