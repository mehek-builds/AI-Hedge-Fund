"""Point-in-time S&P 500 membership query.

FR-2.3 / Phase 2 success criterion #6: any historical date returns the correct
membership, proving the system is survivorship-bias-free.
"""
from datetime import date
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sp500_constituents import SP500Constituent


async def sp500_members_as_of(db: AsyncSession, as_of: date) -> list[str]:
    """Return list of tickers that were S&P 500 members on `as_of`.

    Membership rule: added_date <= as_of AND (removed_date IS NULL OR removed_date > as_of)
    """
    stmt = (
        select(SP500Constituent.symbol)
        .where(SP500Constituent.added_date <= as_of)
        .where(or_(
            SP500Constituent.removed_date.is_(None),
            SP500Constituent.removed_date > as_of,
        ))
        .order_by(SP500Constituent.symbol)
    )
    result = await db.execute(stmt)
    # De-dupe in case a symbol was added → removed → re-added (multiple rows)
    seen = []
    for sym in result.scalars().all():
        if sym not in seen:
            seen.append(sym)
    return seen
