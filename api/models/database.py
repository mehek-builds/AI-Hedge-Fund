"""SQLAlchemy ORM models and async session factory for the PEAD API."""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Integer,
    Numeric, String, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/pead",
)

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class Base(DeclarativeBase):
    pass


class Price(Base):
    __tablename__ = "prices"

    ticker: Mapped[str] = mapped_column(Text, primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    close: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class MacroState(Base):
    __tablename__ = "macro_state"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    t10y2y: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    core_pce_yoy: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    gdp_qoq_ann: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    hy_oas: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    vix: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    sahm_rule: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    carry_crash_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    composite_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    size_multiplier: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    is_halted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    earnings_yield: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    real_10y_yield: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    erp_spread: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    erp_compressed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    vug_pe: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    vtv_pe: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    gv_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    gv_stretched: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)


class EarningsEvent(Base):
    __tablename__ = "earnings_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    announcement_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_eps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    consensus_eps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    implied_eps: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    actual_rev: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 4), nullable=True)
    implied_rev: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 4), nullable=True)
    actual_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    prior_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    surprise_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    intangible_mult: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    roic_mult: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    revenue_surprise: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    margin_surprise: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    guidance_delta: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    signal_composite: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gics_sector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_cyclical: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=True)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    signal_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    entry_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    shares: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    stop_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    holding_days_target: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hold_bin: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sac_entry_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    rl_action_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    moe_regime: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    macro_score_at_entry: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gics_sector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    realized_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    ff5_alpha: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    alpaca_order_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=True)


class RLEpisode(Base):
    __tablename__ = "rl_episodes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    position_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    state_vector: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    action: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    reward: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    done: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text("TRUE"), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=True)


class RLCheckpoint(Base):
    __tablename__ = "rl_checkpoints"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    model_path: Mapped[str] = mapped_column(Text, nullable=False)
    total_episodes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mean_reward_20: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6), nullable=True)
    factor_betas: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ir_vs_naive: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text("FALSE"), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=True)


class Alert(Base):
    __tablename__ = "alert_log"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    channels: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    delivered: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text("FALSE"), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), nullable=True)
