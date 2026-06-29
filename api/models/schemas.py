"""Pydantic schemas for the PEAD API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    direction: str
    status: str
    entry_ts: datetime
    entry_price: Optional[float] = None
    shares: Optional[int] = None
    gics_sector: Optional[str] = None
    moe_regime: Optional[str] = None
    exit_ts: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    realized_pnl: Optional[float] = None
    ff5_alpha: Optional[float] = None
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    days_held: Optional[int] = None
    created_at: Optional[datetime] = None


class ClosedPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    direction: str
    status: str
    entry_ts: datetime
    entry_price: Optional[float] = None
    shares: Optional[int] = None
    exit_ts: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    realized_pnl: Optional[float] = None
    ff5_alpha: Optional[float] = None
    gics_sector: Optional[str] = None
    created_at: Optional[datetime] = None


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    announcement_ts: datetime
    actual_eps: Optional[float] = None
    consensus_eps: Optional[float] = None
    surprise_score: Optional[float] = None
    quality_score: Optional[float] = None
    signal_composite: Optional[float] = None
    direction: Optional[str] = None
    gics_sector: Optional[str] = None
    guidance: Optional[str] = None
    created_at: Optional[datetime] = None


class MacroRegimeOut(BaseModel):
    time: datetime
    composite_score: int
    size_multiplier: float
    is_halted: bool
    components: dict[str, Any]


class MacroHistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: datetime
    composite_score: Optional[int] = None
    size_multiplier: Optional[float] = None
    is_halted: Optional[bool] = None
    t10y2y: Optional[float] = None
    core_pce_yoy: Optional[float] = None
    gdp_qoq_ann: Optional[float] = None
    hy_oas: Optional[float] = None
    vix: Optional[float] = None
    sahm_rule: Optional[float] = None
    carry_crash_flag: Optional[bool] = None


class InflationData(BaseModel):
    date: datetime
    value: float
    series: str


class YieldCurvePoint(BaseModel):
    maturity: str
    yield_pct: float


class PortfolioSummary(BaseModel):
    nav: float
    daily_pnl: float
    daily_pnl_pct: float
    open_positions: int
    win_rate_30: float


class OrderOut(BaseModel):
    id: str
    client_order_id: Optional[str] = None
    symbol: str
    side: str
    qty: Optional[float] = None
    filled_qty: Optional[float] = None
    type: str
    status: str
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    filled_avg_price: Optional[float] = None


class RLEpisodeOut(BaseModel):
    id: UUID
    position_id: Optional[UUID] = None
    action: float
    reward: float
    done: bool
    created_at: Optional[datetime] = None


class RLMetrics(BaseModel):
    episode_count: int
    mean_reward_20: Optional[float] = None
    last_trained_at: Optional[datetime] = None
    factor_betas: Optional[dict[str, float]] = None


class TaskSubmitted(BaseModel):
    task_id: str
    status: str


class SettingOut(BaseModel):
    key: str
    value: Any
    updated_at: Optional[datetime] = None


class SettingsUpdate(BaseModel):
    key: str
    value: Any
