from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MacroIndicator(Base):
    """Macro-economic indicator hypertable partitioned on `date`.

    `vintage_date` captures the ALFRED point-in-time release date so queries
    can reconstruct which values would have been visible on any past date.
    """

    __tablename__ = "macro_indicators"
    __table_args__ = ({"info": {"hypertable": True}},)

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    series_id: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 6), nullable=True)
    vintage_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # FR-1.5 point-in-time column
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
