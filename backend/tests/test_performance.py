"""Performance regression tests - NFR-2 (signal < 5s) and NFR-3 (SSE < 500ms).

Methodology:
- Signal: plain time.time() around compute_signal_for_event() called via run_sync
- SSE: time.time() at Redis publish; stop clock when first data: line received
- No pytest-benchmark; hard assert with informative failure message

Latency is measured from Redis publish to first SSE data line received by the
httpx streaming client. This tests the Redis pub/sub -> event_generator -> SSE
delivery path end-to-end in-process.
"""
import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy import text

from app.config import settings
from app.signals.pipeline import compute_signal_for_event
from tests.conftest import requires_db

PERF_SIG_SYMBOL = "PERF_TEST_SIG"
PERF_SIG_QUARTER = "PERF_2026Q1"
SIGNAL_COMPUTE_THRESHOLD = 5.0   # seconds - NFR-2 hard limit
SSE_LATENCY_THRESHOLD = 0.5      # seconds - NFR-3 hard limit


@requires_db
@pytest.mark.asyncio
async def test_signal_computation_under_5s(db_session):
    """NFR-2: Signal computation must complete in under 5.0 seconds.

    Inserts a synthetic EarningsEvent and price_bars row so the pipeline
    has data to work with, then calls compute_signal_for_event() and asserts
    the elapsed time is under the 5-second hard limit.

    The pipeline may return None (signal suppressed by filters) - that is
    acceptable. The assertion is on duration, not the return value.
    """
    eid = None
    try:
        # Insert a synthetic EarningsEvent row
        insert_event_result = await db_session.execute(
            text(
                """
                INSERT INTO earnings_events (
                    symbol, announced_at, fiscal_quarter,
                    eps_actual, eps_estimate,
                    revenue_actual, revenue_estimate,
                    operating_income, share_count,
                    guidance_direction, ingestion_timestamp
                )
                VALUES (
                    :symbol, :announced_at, :fiscal_quarter,
                    :eps_actual, :eps_estimate,
                    :revenue_actual, :revenue_estimate,
                    :operating_income, :share_count,
                    :guidance_direction, :ingestion_timestamp
                )
                RETURNING id
                """
            ),
            {
                "symbol": PERF_SIG_SYMBOL,
                "announced_at": datetime(2026, 1, 15, 16, 0, 0, tzinfo=timezone.utc),
                "fiscal_quarter": PERF_SIG_QUARTER,
                "eps_actual": Decimal("2.50"),
                "eps_estimate": Decimal("2.00"),
                "revenue_actual": Decimal("1000000000"),
                "revenue_estimate": Decimal("950000000"),
                "operating_income": Decimal("300000000"),
                "share_count": 1000000000,
                "guidance_direction": "up",
                "ingestion_timestamp": datetime(2026, 1, 15, 16, 0, 0, tzinfo=timezone.utc),
            },
        )
        row = insert_event_result.fetchone()
        eid = row[0]

        # Insert a synthetic price_bars row so the pipeline finds a last_close
        await db_session.execute(
            text(
                """
                INSERT INTO price_bars (
                    symbol, time, open, high, low, close, volume, ingestion_timestamp
                )
                VALUES (
                    :symbol, :time, :open, :high, :low, :close, :volume, :ingestion_timestamp
                )
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "symbol": PERF_SIG_SYMBOL,
                "time": datetime(2026, 1, 14, 21, 0, 0, tzinfo=timezone.utc),
                "open": Decimal("150.00"),
                "high": Decimal("155.00"),
                "low": Decimal("149.00"),
                "close": Decimal("152.50"),
                "volume": 10000000,
                "ingestion_timestamp": datetime(2026, 1, 14, 21, 0, 0, tzinfo=timezone.utc),
            },
        )
        await db_session.flush()

        # Measure signal computation time
        start = time.time()
        signal_id = await db_session.run_sync(
            lambda s: compute_signal_for_event(s, eid)
        )
        elapsed = time.time() - start

        # NFR-2 hard assertion
        assert elapsed < 5.0, (
            f"Signal computation took {elapsed:.2f}s, expected < {SIGNAL_COMPUTE_THRESHOLD}s"
        )

        # signal_id may be None if filters suppressed the signal - that is fine
        # The test validates timing only, not signal generation outcome

    finally:
        # Cleanup synthetic rows regardless of test outcome
        if eid is not None:
            await db_session.execute(
                text("DELETE FROM signals WHERE earnings_event_id = :eid"),
                {"eid": eid},
            )
        await db_session.execute(
            text("DELETE FROM earnings_events WHERE symbol = :symbol AND fiscal_quarter = :quarter"),
            {"symbol": PERF_SIG_SYMBOL, "quarter": PERF_SIG_QUARTER},
        )
        await db_session.execute(
            text("DELETE FROM price_bars WHERE symbol = :symbol"),
            {"symbol": PERF_SIG_SYMBOL},
        )
        await db_session.commit()


@requires_db
@pytest.mark.asyncio
async def test_sse_latency_under_500ms(client):
    """NFR-3: SSE message must be delivered within 500ms of Redis publish.

    Opens an httpx streaming connection to /api/v1/events (in-process via ASGI
    transport), publishes a test message to the Redis 'signals' channel, then
    measures the time from publish to first data: line received in the SSE stream.

    Heartbeat lines (': heartbeat') are ignored - only 'data:' lines count.

    The stream.py SSE endpoint polls Redis with 1.0s timeout then sleeps 0.05s.
    With in-process ASGI transport, latency should be well under 500ms.
    """
    r = aioredis.from_url(settings.REDIS_PUB_URL, decode_responses=True)
    latency_holder = []

    async def read_stream():
        async with client.stream("GET", "/api/v1/events") as response:
            # Publish test signal after SSE connection is established
            start = time.time()
            await r.publish("signals", '{"type":"perf_test","symbol":"PERF_SSE_TEST","value":1}')
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    latency_holder.append(time.time() - start)
                    break
                # Skip heartbeat lines and event: lines, keep waiting for data:

    try:
        await asyncio.wait_for(read_stream(), timeout=2.0)
    finally:
        await r.aclose()

    assert latency_holder, "No SSE data: message received within 2.0s timeout"
    elapsed = latency_holder[0]

    # NFR-3 hard assertion
    assert elapsed < 0.5, (
        f"SSE latency {elapsed:.3f}s, expected < {SSE_LATENCY_THRESHOLD}s"
    )
