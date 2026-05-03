from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortfolioPosition(Base):
    """Portfolio position snapshot hypertable partitioned on `snapshot_at`."""

    __tablename__ = "portfolio_positions"
    __table_args__ = ({"info": {"hypertable": True}},)

    snapshot_at: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    avg_entry_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    unrealized_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    stop_loss_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True, server_default="open")

    # FR-1.5 point-in-time column
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
