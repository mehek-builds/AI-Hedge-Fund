from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EarningsEvent(Base):
    """Earnings event hypertable partitioned on `announced_at`."""

    __tablename__ = "earnings_events"
    __table_args__ = (
        UniqueConstraint("symbol", "fiscal_quarter", name="uq_earnings_symbol_quarter"),
        CheckConstraint(
            "guidance_direction IN ('up', 'down', 'flat', 'none', 'withdrawn')",
            name="ck_guidance_direction",
        ),
        {"info": {"hypertable": True}},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    announced_at: Mapped[datetime] = mapped_column(nullable=False)
    fiscal_quarter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eps_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    eps_estimate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    revenue_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    revenue_estimate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    operating_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    share_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    guidance_direction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # FR-1.5 point-in-time column
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
