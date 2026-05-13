from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestRun(Base):
    """Backtest run record storing results and macro gate status."""

    __tablename__ = "backtest_runs"

    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, server_default="pending"
    )  # pending | running | completed | failed
    macro_gate_open: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    sharpe_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    total_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    max_drawdown: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # FR-1.5 point-in-time column
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
