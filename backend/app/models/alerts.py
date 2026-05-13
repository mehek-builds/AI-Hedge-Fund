import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

VALID_EVENT_TYPES = (
    "signal_generated", "order_submitted", "order_filled",
    "stop_triggered", "thesis_broken", "macro_regime_change",
    "backtest_gate_pass", "backtest_gate_fail", "rl_diversity_alert",
)


class Alert(Base):
    """Persisted alert record. One row per dispatched or rate-limited event."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    payload: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    delivered_sendgrid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivered_slack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
