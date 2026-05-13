from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/macro")
async def get_macro(db: AsyncSession = Depends(get_db)):
    """Return latest macro indicator values per series and composite gate status."""

    # Latest value per series
    indicators_result = await db.execute(
        text(
            """
            SELECT DISTINCT ON (series_id)
                date,
                series_id,
                value,
                vintage_date,
                source
            FROM macro_indicators
            ORDER BY series_id, date DESC
            """
        )
    )
    indicators_rows = indicators_result.fetchall()
    indicators = [
        {
            "date": r.date.isoformat() if r.date else None,
            "series_id": r.series_id,
            "value": float(r.value) if r.value is not None else None,
            "vintage_date": r.vintage_date.isoformat() if r.vintage_date else None,
            "source": r.source,
        }
        for r in indicators_rows
    ]

    # Composite gate from most recent backtest run with gate info
    gate_result = await db.execute(
        text(
            """
            SELECT macro_gate_open, created_at
            FROM backtest_runs
            WHERE macro_gate_open IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
    )
    gate_row = gate_result.fetchone()
    gate_status = {
        "macro_gate_open": gate_row.macro_gate_open if gate_row else None,
        "last_evaluated_at": gate_row.created_at.isoformat() if gate_row and gate_row.created_at else None,
    }

    return {
        "indicators": indicators,
        "gate_status": gate_status,
    }
