"""Persist computed signals to the signals hypertable."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.flows._base import upsert_rows
from app.models.signals import Signal


# Naive baseline per FR-3.6 — fixed 2% NAV for any signal that survives filters.
NAIVE_POSITION_SIZE = Decimal("0.0200")


@dataclass(frozen=True)
class SignalPayload:
    symbol: str
    earnings_event_id: int
    eps_gap: Optional[Decimal]
    quality_score: Decimal
    three_axis_composite: Decimal
    direction: str
    naive_position_size: Decimal = NAIVE_POSITION_SIZE
    status: str = "pending"


def write_signal(session: Session, payload: SignalPayload) -> str:
    """Insert one signal row and return the generated signal_id."""
    signal_id = str(uuid4())
    now = datetime.now(timezone.utc)
    row = {
        "created_at": now,
        "signal_id": signal_id,
        "symbol": payload.symbol,
        "earnings_event_id": payload.earnings_event_id,
        "eps_gap": payload.eps_gap,
        "quality_score": payload.quality_score,
        "three_axis_composite": payload.three_axis_composite,
        "naive_position_size": payload.naive_position_size,
        "direction": payload.direction,
        "status": payload.status,
    }
    upsert_rows(
        session,
        Signal.__table__,
        [row],
        conflict_cols=["created_at", "signal_id"],
        update_cols=[
            "symbol", "earnings_event_id", "eps_gap", "quality_score",
            "three_axis_composite", "naive_position_size", "direction", "status",
        ],
    )
    return signal_id
