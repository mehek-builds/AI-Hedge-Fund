from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import BigInteger, CheckConstraint, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Signal(Base):
    """Trading signal hypertable partitioned on `created_at`."""

    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('long', 'short', 'hold')",
            name="ck_signal_direction",
        ),
        {"info": {"hypertable": True}},
    )

    created_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())
    signal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    symbol: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    earnings_event_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    eps_gap: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    three_axis_composite: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    naive_position_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="pending")

    # FR-1.5 point-in-time column
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
