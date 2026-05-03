from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.queries.point_in_time import get_prices_as_of


@pytest.mark.asyncio
async def test_future_ingested_row_excluded(db):
    """FR-1.5: a row ingested in the future must not appear in an as_of query."""
    future_ingestion = datetime.now(tz=timezone.utc) + timedelta(days=365)
    past_time = datetime.now(tz=timezone.utc) - timedelta(days=1)
    await db.execute(
        text(
            "INSERT INTO price_bars (time, symbol, close, ingestion_timestamp) "
            "VALUES (:t, 'FUTURE_TEST', 100.00, :ing)"
        ),
        {"t": past_time, "ing": future_ingestion},
    )
    as_of = datetime.now(tz=timezone.utc)
    rows = await get_prices_as_of(db, symbol="FUTURE_TEST", as_of=as_of)
    assert rows == [], (
        f"Expected empty list but got {rows}; "
        "future-ingested row leaked through as_of filter (look-ahead bias)"
    )


@pytest.mark.asyncio
async def test_past_ingested_row_included(db):
    """FR-1.5: a row ingested in the past must appear in an as_of query."""
    past_ingestion = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    past_time = datetime.now(tz=timezone.utc) - timedelta(days=1)
    await db.execute(
        text(
            "INSERT INTO price_bars (time, symbol, close, ingestion_timestamp) "
            "VALUES (:t, 'PAST_TEST', 99.00, :ing)"
        ),
        {"t": past_time, "ing": past_ingestion},
    )
    as_of = datetime.now(tz=timezone.utc)
    rows = await get_prices_as_of(db, symbol="PAST_TEST", as_of=as_of)
    assert len(rows) >= 1, (
        "Expected at least one row but got none; "
        "past-ingested row was incorrectly excluded by as_of filter"
    )
