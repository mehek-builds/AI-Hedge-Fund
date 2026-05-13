from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Aggregated dashboard data: position count, P&L placeholder, macro gate, last 5 alerts."""

    # Position count
    pos_result = await db.execute(
        text("SELECT COUNT(DISTINCT symbol) AS symbol_count FROM portfolio_positions WHERE status = 'open'")
    )
    pos_row = pos_result.fetchone()
    position_count = pos_row.symbol_count if pos_row else 0

    # Total unrealized P&L
    pnl_result = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(latest.unrealized_pnl), 0) AS total_pnl
            FROM (
                SELECT DISTINCT ON (symbol) unrealized_pnl
                FROM portfolio_positions
                ORDER BY symbol, snapshot_at DESC
            ) latest
            """
        )
    )
    pnl_row = pnl_result.fetchone()
    total_pnl = float(pnl_row.total_pnl) if pnl_row else 0.0

    # Latest macro gate status
    macro_result = await db.execute(
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
    macro_row = macro_result.fetchone()
    macro_gate_open = macro_row.macro_gate_open if macro_row else None

    # Last 5 alerts
    alerts_result = await db.execute(
        text(
            """
            SELECT alert_id, created_at, level, category, symbol, message
            FROM alerts
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
    )
    alerts_rows = alerts_result.fetchall()
    alerts = [
        {
            "alert_id": r.alert_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "level": r.level,
            "category": r.category,
            "symbol": r.symbol,
            "message": r.message,
        }
        for r in alerts_rows
    ]

    return {
        "position_count": int(position_count),
        "total_unrealized_pnl": total_pnl,
        "macro_gate_open": macro_gate_open,
        "recent_alerts": alerts,
    }
