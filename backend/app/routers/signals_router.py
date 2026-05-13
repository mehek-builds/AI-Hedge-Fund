from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/signals/recent")
async def get_recent_signals(
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent signal rows."""
    result = await db.execute(
        text(
            """
            SELECT
                created_at,
                signal_id,
                symbol,
                earnings_event_id,
                eps_gap,
                quality_score,
                three_axis_composite,
                naive_position_size,
                direction,
                status
            FROM signals
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    rows = result.fetchall()
    return [
        {
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "signal_id": r.signal_id,
            "symbol": r.symbol,
            "earnings_event_id": r.earnings_event_id,
            "eps_gap": float(r.eps_gap) if r.eps_gap is not None else None,
            "quality_score": float(r.quality_score) if r.quality_score is not None else None,
            "three_axis_composite": float(r.three_axis_composite) if r.three_axis_composite is not None else None,
            "naive_position_size": float(r.naive_position_size) if r.naive_position_size is not None else None,
            "direction": r.direction,
            "status": r.status,
        }
        for r in rows
    ]
