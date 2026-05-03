"""Macro regime router."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import MacroState, get_db
from api.models.schemas import MacroHistoryPoint, MacroRegimeOut
from api.services.auth import get_current_user
from api.services.redis_client import get_redis_client

router = APIRouter(prefix="/macro", tags=["macro"])


def _macro_state_to_regime_out(row: MacroState) -> MacroRegimeOut:
    components = {
        "t10y2y": float(row.t10y2y) if row.t10y2y is not None else None,
        "core_pce_yoy": float(row.core_pce_yoy) if row.core_pce_yoy is not None else None,
        "gdp_qoq_ann": float(row.gdp_qoq_ann) if row.gdp_qoq_ann is not None else None,
        "hy_oas": float(row.hy_oas) if row.hy_oas is not None else None,
        "vix": float(row.vix) if row.vix is not None else None,
        "sahm_rule": float(row.sahm_rule) if row.sahm_rule is not None else None,
        "carry_crash_flag": bool(row.carry_crash_flag),
    }
    return MacroRegimeOut(
        time=row.time,
        composite_score=row.composite_score or 0,
        size_multiplier=float(row.size_multiplier or 1.0),
        is_halted=bool(row.is_halted),
        components=components,
    )


@router.get("/regime", response_model=MacroRegimeOut)
async def get_macro_regime(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> MacroRegimeOut:
    """Return current macro regime. Tries Redis cache first, falls back to DB."""
    redis = get_redis_client()
    cached = redis.get_macro_regime()
    if cached:
        return MacroRegimeOut(**cached)

    result = await db.execute(
        select(MacroState).order_by(MacroState.time.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        # Return neutral regime if no data
        return MacroRegimeOut(
            time=datetime.now(timezone.utc),
            composite_score=0,
            size_multiplier=1.0,
            is_halted=False,
            components={},
        )

    regime_out = _macro_state_to_regime_out(row)
    # Populate cache for next request
    redis.set_macro_regime(regime_out.model_dump(), ttl=3600)
    return regime_out


@router.get("/history", response_model=list[MacroHistoryPoint])
async def get_macro_history(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    days: int = Query(default=30, ge=1, le=365),
) -> list[MacroHistoryPoint]:
    """Return macro_state time series for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(MacroState)
        .where(MacroState.time >= since)
        .order_by(MacroState.time.asc())
    )
    rows = result.scalars().all()
    return [
        MacroHistoryPoint(**{c.name: getattr(r, c.name) for c in r.__table__.columns})
        for r in rows
    ]
