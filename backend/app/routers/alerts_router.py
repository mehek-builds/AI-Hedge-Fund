from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated alerts ordered by most recent first."""
    result = await db.execute(
        text(
            """
            SELECT
                alert_id,
                created_at,
                level,
                category,
                symbol,
                message
            FROM alerts
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    # Total count for pagination metadata
    count_result = await db.execute(text("SELECT COUNT(*) AS total FROM alerts"))
    count_row = count_result.fetchone()
    total = int(count_row.total) if count_row else 0

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "alert_id": r.alert_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "level": r.level,
                "category": r.category,
                "symbol": r.symbol,
                "message": r.message,
            }
            for r in rows
        ],
    }
