"""Positions router."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import EarningsEvent, Position, Price, get_db
from api.models.schemas import ClosedPositionOut, PositionOut
from api.services.auth import get_current_user

router = APIRouter(prefix="/positions", tags=["positions"])


async def _enrich_position(pos: Position, db: AsyncSession) -> dict:
    """Attach current_price, unrealized_pnl, and days_held to a position dict."""
    data = {
        c.name: getattr(pos, c.name)
        for c in pos.__table__.columns
    }
    data["unrealized_pnl"] = None
    data["days_held"] = None
    data["current_price"] = None

    if pos.status == "open" and pos.ticker:
        # Latest price from prices table
        price_result = await db.execute(
            select(Price.close)
            .where(Price.ticker == pos.ticker)
            .order_by(Price.time.desc())
            .limit(1)
        )
        row = price_result.first()
        if row and row[0] is not None and pos.entry_price is not None:
            current = float(row[0])
            entry = float(pos.entry_price)
            shares = pos.shares or 0
            data["current_price"] = current
            if pos.direction == "long":
                data["unrealized_pnl"] = (current - entry) * shares
            else:
                data["unrealized_pnl"] = (entry - current) * shares

        if pos.entry_ts:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            entry_ts = pos.entry_ts
            if entry_ts.tzinfo is None:
                from datetime import timezone
                entry_ts = entry_ts.replace(tzinfo=timezone.utc)
            data["days_held"] = (now - entry_ts).days

    return data


@router.get("", response_model=list[PositionOut])
async def list_open_positions(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[PositionOut]:
    """Return all open positions with unrealized P&L and current price."""
    result = await db.execute(
        select(Position).where(Position.status == "open").order_by(Position.entry_ts.desc())
    )
    positions = result.scalars().all()
    enriched = []
    for pos in positions:
        data = await _enrich_position(pos, db)
        enriched.append(PositionOut(**data))
    return enriched


@router.get("/closed", response_model=list[ClosedPositionOut])
async def list_closed_positions(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[ClosedPositionOut]:
    """Return closed positions with ff5_alpha, paginated."""
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Position)
        .where(Position.status == "closed")
        .order_by(Position.exit_ts.desc())
        .offset(offset)
        .limit(page_size)
    )
    positions = result.scalars().all()
    return [
        ClosedPositionOut(**{c.name: getattr(p, c.name) for c in p.__table__.columns})
        for p in positions
    ]


@router.get("/{position_id}", response_model=PositionOut)
async def get_position(
    position_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> PositionOut:
    """Return a single position by ID."""
    result = await db.execute(select(Position).where(Position.id == position_id))
    pos = result.scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    data = await _enrich_position(pos, db)
    return PositionOut(**data)
