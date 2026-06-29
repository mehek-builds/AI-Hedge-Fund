"""Dashboard summary endpoint — single fetch for the main view."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Alert, MacroState, Position, get_db
from api.services.auth import get_current_user
from api.services.redis_client import get_redis_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    nav: Optional[float]
    daily_pnl: Optional[float]
    daily_pnl_pct: Optional[float]
    open_positions: int
    macro_regime: str
    macro_score: int
    size_multiplier: float
    erp_compressed: bool
    alpha_tstat: Optional[float]
    last_updated: datetime


class RecentAlert(BaseModel):
    id: str
    event_type: str
    ticker: Optional[str]
    title: str
    priority: str
    created_at: datetime


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> DashboardSummary:
    """Single-call summary for the dashboard homepage."""
    redis = get_redis_client()

    # NAV from Alpaca (cached in Redis by the daily flow)
    nav_raw = redis.client.get("alpaca:nav")
    nav = float(nav_raw) if nav_raw else None

    daily_pnl_raw = redis.client.get("alpaca:daily_pnl")
    daily_pnl = float(daily_pnl_raw) if daily_pnl_raw else None
    daily_pnl_pct = (daily_pnl / nav * 100) if (daily_pnl and nav) else None

    # Open position count
    count_result = await db.execute(
        select(func.count(Position.id)).where(Position.status == "open")
    )
    open_count: int = count_result.scalar_one() or 0

    # Macro regime
    macro_cached = redis.get_macro_regime()
    if macro_cached:
        composite = macro_cached.get("composite_score", 0)
        multiplier = macro_cached.get("size_multiplier", 1.0)
        erp_compressed = macro_cached.get("erp_compressed", False)
    else:
        macro_result = await db.execute(
            select(MacroState).order_by(MacroState.time.desc()).limit(1)
        )
        macro_row = macro_result.scalar_one_or_none()
        composite = int(macro_row.composite_score) if macro_row and macro_row.composite_score else 0
        multiplier = float(macro_row.size_multiplier) if macro_row and macro_row.size_multiplier else 1.0
        erp_compressed = bool(macro_row.erp_compressed) if macro_row else False

    if composite >= -1:
        regime = "Expansion"
    elif composite >= -3:
        regime = "Caution"
    else:
        regime = "Crisis"

    # Alpha t-stat from Redis (updated by RL trainer)
    tstat_raw = redis.client.get("rl:alpha_tstat")
    alpha_tstat = float(tstat_raw) if tstat_raw else None

    return DashboardSummary(
        nav=nav,
        daily_pnl=daily_pnl,
        daily_pnl_pct=daily_pnl_pct,
        open_positions=open_count,
        macro_regime=regime,
        macro_score=composite,
        size_multiplier=multiplier,
        erp_compressed=erp_compressed,
        alpha_tstat=alpha_tstat,
        last_updated=datetime.now(timezone.utc),
    )


@router.get("/alerts/recent", response_model=list[RecentAlert])
async def get_recent_alerts(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[RecentAlert]:
    """Return the 5 most recent alerts for the dashboard sidebar."""
    result = await db.execute(
        select(Alert).order_by(Alert.created_at.desc()).limit(5)
    )
    rows = result.scalars().all()
    return [
        RecentAlert(
            id=str(r.id),
            event_type=r.event_type,
            ticker=r.ticker,
            title=r.title,
            priority=r.priority,
            created_at=r.created_at,
        )
        for r in rows
    ]
