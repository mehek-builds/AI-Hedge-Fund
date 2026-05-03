from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_bars import PriceBar


async def get_prices_as_of(
    db: AsyncSession,
    symbol: str,
    as_of: datetime,
    lookback_days: int = 90,
) -> list[PriceBar]:
    """Return price bars for *symbol* visible as of *as_of*.

    FR-1.5: only rows whose ingestion_timestamp <= as_of are returned,
    preventing any look-ahead bias from late-arriving data corrections.
    """
    stmt = (
        select(PriceBar)
        .where(PriceBar.symbol == symbol)
        .where(PriceBar.time >= as_of - timedelta(days=lookback_days))
        .where(PriceBar.time <= as_of)
        .where(PriceBar.ingestion_timestamp <= as_of)
        .order_by(PriceBar.time.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
