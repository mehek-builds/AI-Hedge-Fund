from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BacktestRun(Base):
    """Persisted results and gate status for a single backtest run.

    FR-6.4: gate_status is the go/no-go pivot for Phase 7 startup.
    FR-6.6: columns match Phase 8 Backtest Explorer query needs.
    """

    __tablename__ = "backtest_runs"
    __table_args__ = (
        CheckConstraint(
            "gate_status IN ('pending', 'pass', 'fail')",
            name="chk_gate_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Performance statistics (FR-6.3)
    sharpe: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    max_drawdown: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    ir_vs_baseline: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    calmar: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    monthly_returns: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    # Gate outcome: FR-6.4
    gate_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")

    # Flag for ex-2020 stress slice (FR-6.5)
    is_partial_year: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Config snapshot for reproducibility and Phase 8 Explorer display
    config_snapshot: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
