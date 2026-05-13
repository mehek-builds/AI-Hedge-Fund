from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


@router.get("/positions")
async def get_positions(db: AsyncSession = Depends(get_db)):
    """Return the latest portfolio position snapshot per symbol."""
    result = await db.execute(
        text(
            """
            SELECT DISTINCT ON (symbol)
                snapshot_at,
                symbol,
                qty,
                avg_entry_price,
                current_price,
                unrealized_pnl,
                stop_loss_price,
                take_profit_price,
                status
            FROM portfolio_positions
            ORDER BY symbol, snapshot_at DESC
            """
        )
    )
    rows = result.fetchall()
    return [
        {
            "snapshot_at": r.snapshot_at.isoformat() if r.snapshot_at else None,
            "symbol": r.symbol,
            "qty": float(r.qty) if r.qty is not None else None,
            "avg_entry_price": float(r.avg_entry_price) if r.avg_entry_price is not None else None,
            "current_price": float(r.current_price) if r.current_price is not None else None,
            "unrealized_pnl": float(r.unrealized_pnl) if r.unrealized_pnl is not None else None,
            "stop_loss_price": float(r.stop_loss_price) if r.stop_loss_price is not None else None,
            "take_profit_price": float(r.take_profit_price) if r.take_profit_price is not None else None,
            "status": r.status,
        }
        for r in rows
    ]
