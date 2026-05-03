from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SP500Constituent(Base):
    """Point-in-time S&P 500 membership.

    A constituent is a member from `added_date` (inclusive) through
    `removed_date` (exclusive). NULL `removed_date` means still active.
    Point-in-time query: WHERE added_date <= :as_of
                           AND (removed_date IS NULL OR removed_date > :as_of)
    """

    __tablename__ = "sp500_constituents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    added_date: Mapped[date] = mapped_column(Date, nullable=False)
    removed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
