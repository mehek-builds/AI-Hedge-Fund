"""Portfolio summary router — GET /portfolio/summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import Position, get_db
from api.models.schemas import PortfolioSummary
from api.services.alpaca import get_alpaca_client
from api.services.auth import get_current_user

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> PortfolioSummary:
    """Return portfolio NAV, daily P&L, open position count, and 30-day win rate."""
    alpaca = get_alpaca_client()
    account = alpaca.get_account()

    nav = account["nav"]
    last_equity = account["last_equity"]
    daily_pnl = nav - last_equity
    daily_pnl_pct = (daily_pnl / last_equity * 100) if last_equity else 0.0

    # Open position count from DB
    open_count_result = await db.execute(
        select(func.count(Position.id)).where(Position.status == "open")
    )
    open_positions: int = open_count_result.scalar_one_or_none() or 0

    # Win rate from last 30 closed positions
    closed_result = await db.execute(
        select(Position.realized_pnl)
        .where(Position.status == "closed")
        .order_by(Position.exit_ts.desc())
        .limit(30)
    )
    closed_pnls = [row[0] for row in closed_result.fetchall() if row[0] is not None]
    if closed_pnls:
        wins = sum(1 for p in closed_pnls if float(p) > 0)
        win_rate_30 = wins / len(closed_pnls)
    else:
        win_rate_30 = 0.0

    return PortfolioSummary(
        nav=nav,
        daily_pnl=daily_pnl,
        daily_pnl_pct=daily_pnl_pct,
        open_positions=open_positions,
        win_rate_30=win_rate_30,
    )
