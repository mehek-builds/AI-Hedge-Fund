from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Integer, Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RlTransition(Base):
    """RL experience replay transition hypertable partitioned on `ts`."""

    __tablename__ = "rl_transitions"
    __table_args__ = ({"info": {"hypertable": True}},)

    ts: Mapped[datetime] = mapped_column(primary_key=True, server_default=func.now())
    episode_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    step: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    symbol: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state_vec: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    action: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    reward: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    next_state_vec: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    done: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    priority: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True, server_default="1.0"
    )

    # FR-1.5 point-in-time column
    ingestion_timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
