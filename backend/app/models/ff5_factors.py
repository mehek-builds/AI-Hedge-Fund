from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FF5Factor(Base):
    """Ken French 5-factor daily returns (decimal, e.g., 0.0023 = 23 bps)."""

    __tablename__ = "ff5_factors"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    mkt_rf: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    smb: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    hml: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    rmw: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    cma: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    rf: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
