from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceBar(Base):
    """OHLCV price bar hypertable partitioned on `time`."""

    __tablename__ = "price_bars"
    __table_args__ = ({"info": {"hypertable": True}},)

    time: Mapped[datetime] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, primary_key=True)

    open: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    vwap: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # FR-1.5 point-in-time column — filter with `ingestion_timestamp <= as_of`
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
