"""End-to-end signal computation orchestrator (FR-3.1..FR-3.6).

Given an earnings_event_id, this module:
  1. Loads the event + the prior event for the same symbol.
  2. Computes implied EPS, eps_gap, quality, momentum, valuation, composite.
  3. Applies sector hurdle and ROIC>WACC filters.
  4. If both filters pass, writes a row to `signals` with the naive 2% baseline.
  5. Returns the signal_id (or None when suppressed).
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.earnings_events import EarningsEvent
from app.signals.composite import (
    compute_composite,
    direction_for_composite,
    valuation_score,
)
from app.signals.filters import apply_roic_wacc_filter, apply_sector_hurdle
from app.signals.implied_eps import compute_implied_eps, eps_gap
from app.signals.momentum import compute_momentum_score, twenty_day_return
from app.signals.quality import compute_quality_score
from app.signals.sectors import sector_for
from app.signals.writer import SignalPayload, write_signal

log = logging.getLogger(__name__)


def _load_event(session: Session, eid: int) -> Optional[EarningsEvent]:
    return session.get(EarningsEvent, eid)


def _load_prior_event(session: Session, symbol: str, before: datetime) -> Optional[EarningsEvent]:
    return (
        session.query(EarningsEvent)
        .filter(EarningsEvent.symbol == symbol, EarningsEvent.announced_at < before)
        .order_by(EarningsEvent.announced_at.desc())
        .first()
    )


def _last_close(session: Session, symbol: str, as_of: datetime) -> Optional[Decimal]:
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
    return Decimal(row[0]) if row and row[0] is not None else None


def compute_signal_for_event(
    session: Session,
    earnings_event_id: int,
    cohort_eps_gaps: Optional[Sequence[Decimal]] = None,
    cohort_returns: Optional[Sequence[float]] = None,
) -> Optional[str]:
    """Compute and persist a signal for one earnings event. Returns signal_id or None."""
    cohort_eps_gaps = list(cohort_eps_gaps or [])
    cohort_returns = list(cohort_returns or [])

    event = _load_event(session, earnings_event_id)
    if event is None or event.symbol is None:
        log.warning("compute_signal_for_event: missing event id=%s", earnings_event_id)
        return None

    sector = sector_for(event.symbol)
    as_of = event.announced_at or datetime.now(timezone.utc)

    # 1. Implied EPS + valuation
    last_close = _last_close(session, event.symbol, as_of)
    if last_close is None:
        log.warning(
            "compute_signal_for_event: no price_bars for %s as_of %s",
            event.symbol, as_of,
        )
        return None
    implied = compute_implied_eps(last_close, sector)
    gap = eps_gap(event.eps_actual, implied)
    max_gap = max((abs(g) for g in cohort_eps_gaps), default=Decimal("0"))
    val_score = valuation_score(gap, max_gap)

    # 2. Quality (with prior event)
    prior = _load_prior_event(session, event.symbol, as_of)
    qb = compute_quality_score(event, prior)
    quality_dec = Decimal(qb.total)

    # 3. Momentum
    sym_return = twenty_day_return(session, event.symbol, as_of)
    mom_score = compute_momentum_score(sym_return, cohort_returns)

    # 4. Filters
    passed, reason = apply_sector_hurdle(qb.total, sector)
    if not passed:
        log.warning(
            "signal suppressed (sector hurdle): %s sector=%s reason=%s",
            event.symbol, sector, reason,
        )
        return None
    passed, reason = apply_roic_wacc_filter(event, sector)
    if not passed:
        log.warning(
            "signal suppressed (ROIC<WACC): %s sector=%s reason=%s",
            event.symbol, sector, reason,
        )
        return None

    # 5. Composite + direction + write
    composite = compute_composite(val_score, quality_dec, mom_score)
    payload = SignalPayload(
        symbol=event.symbol,
        earnings_event_id=event.id,
        eps_gap=gap,
        quality_score=quality_dec,
        three_axis_composite=composite,
        direction=direction_for_composite(composite),
    )
    return write_signal(session, payload)
