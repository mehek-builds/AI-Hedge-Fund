from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

VALID_EVENT_TYPES = (
    "order_filled",
    "order_rejected",
    "stop_triggered",
    "target_reached",
    "orphan_detected",
    "macro_gate_open",
    "macro_gate_close",
    "rl_gate_triggered",
    "system_error",
)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rate_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivered_sendgrid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivered_slack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
