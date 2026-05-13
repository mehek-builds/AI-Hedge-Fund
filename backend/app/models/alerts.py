from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Alert(Base):
    """Alert log table for system and trading alerts."""

    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    level: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, server_default="info"
    )  # info | warning | error | critical
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # FR-1.5 point-in-time column
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
