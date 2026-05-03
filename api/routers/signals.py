"""Signals router."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import EarningsEvent, get_db
from api.models.schemas import SignalOut
from api.services.auth import get_current_user

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalOut])
async def list_signals(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[SignalOut]:
    """Return the latest 50 earnings events ordered by announcement timestamp descending."""
    result = await db.execute(
        select(EarningsEvent)
        .order_by(EarningsEvent.announcement_ts.desc())
        .limit(50)
    )
    events = result.scalars().all()
    return [SignalOut(**{c.name: getattr(e, c.name) for c in e.__table__.columns}) for e in events]


@router.get("/history", response_model=list[SignalOut])
async def signals_history(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    sector: Optional[str] = Query(default=None),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[SignalOut]:
    """Return earnings event history, filterable by sector and date range."""
    q = select(EarningsEvent).order_by(EarningsEvent.announcement_ts.desc())
    if sector:
        q = q.where(EarningsEvent.gics_sector == sector)
    if start_date:
        q = q.where(EarningsEvent.announcement_ts >= start_date)
    if end_date:
        q = q.where(EarningsEvent.announcement_ts <= end_date)
    q = q.limit(limit)

    result = await db.execute(q)
    events = result.scalars().all()
    return [SignalOut(**{c.name: getattr(e, c.name) for c in e.__table__.columns}) for e in events]
