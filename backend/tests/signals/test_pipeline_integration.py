"""End-to-end DB-gated integration tests for the signal pipeline.

Requires: docker compose up + alembic upgrade head. CI-gated.
"""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.flows._base import sync_session
from app.models.earnings_events import EarningsEvent
from app.models.price_bars import PriceBar
from app.signals.pipeline import compute_signal_for_event


pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_SYNC"),
    reason="DB-gated: set DATABASE_URL_SYNC and run `alembic upgrade head` first",
)


def _insert_price_bars(session, symbol: str, end: datetime, n: int, start_price: float, end_price: float):
    """Insert n daily bars ending at `end` with linear price ramp."""
    step = (end_price - start_price) / max(n - 1, 1)
    for i in range(n):
        t = end - timedelta(days=(n - 1 - i))
        price = Decimal(str(round(start_price + step * i, 2)))
        session.execute(
            text(
                """
                INSERT INTO price_bars(time, symbol, open, high, low, close, vwap, volume, ingestion_timestamp)
                VALUES (:t, :s, :p, :p, :p, :p, :p, 1000000, NOW())
                ON CONFLICT (time, symbol) DO UPDATE
                  SET close = EXCLUDED.close, ingestion_timestamp = NOW()
                """
            ),
            {"t": t, "s": symbol, "p": price},
        )


def _insert_earnings_event(session, **kwargs) -> int:
    e = EarningsEvent(**kwargs)
    session.add(e)
    session.flush()
    return e.id


def _cleanup(session, symbol: str):
    session.execute(text("DELETE FROM signals WHERE symbol = :s"), {"s": symbol})
    session.execute(text("DELETE FROM earnings_events WHERE symbol = :s"), {"s": symbol})
    session.execute(text("DELETE FROM price_bars WHERE symbol = :s"), {"s": symbol})


def test_end_to_end_signal_for_earnings_event():
    sym = "AAPL"
    now = datetime.now(timezone.utc)
    with sync_session() as s:
        _cleanup(s, sym)
        # Prior quarter event: weaker margin and higher share count.
        prior_id = _insert_earnings_event(
            s, symbol=sym, announced_at=now - timedelta(days=91),
            fiscal_quarter="2025Q4", eps_actual=Decimal("8.0"), eps_estimate=Decimal("7.5"),
            revenue_actual=Decimal("9000"), revenue_estimate=Decimal("8800"),
            operating_income=Decimal("1350"),  # 15% margin
            share_count=950_000_000, guidance_direction="flat", source="test",
        )
        # Current event: strong surprise, expanding margin, share buyback, up guidance.
        eid = _insert_earnings_event(
            s, symbol=sym, announced_at=now,
            fiscal_quarter="2026Q1", eps_actual=Decimal("10.0"), eps_estimate=Decimal("8.0"),
            revenue_actual=Decimal("10000"), revenue_estimate=Decimal("9000"),
            operating_income=Decimal("2000"),  # 20% margin -> +5pp expansion
            share_count=900_000_000, guidance_direction="up", source="test",
        )
        _insert_price_bars(s, sym, now, 21, 250.0, 280.0)
        s.commit()

    with sync_session() as s:
        signal_id = compute_signal_for_event(s, eid)
    assert signal_id is not None, "Tech ticker with high quality + good price should produce a signal"

    with sync_session() as s:
        row = s.execute(
            text(
                """
                SELECT symbol, quality_score, three_axis_composite,
                       naive_position_size, direction
                FROM signals WHERE earnings_event_id = :eid
                """
            ),
            {"eid": eid},
        ).fetchone()
        assert row is not None
        assert row[0] == sym
        assert row[1] is not None and 0 <= float(row[1]) <= 100
        assert row[2] is not None and 0 <= float(row[2]) <= 100
        assert Decimal(row[3]) == Decimal("0.0200"), f"naive_position_size must be 0.0200, got {row[3]}"
        assert row[4] in ("long", "short", "hold")
        _cleanup(s, sym)


def test_signal_suppressed_below_sector_hurdle():
    sym = "MSFT"
    now = datetime.now(timezone.utc)
    with sync_session() as s:
        _cleanup(s, sym)
        # Prior event with same margin/share count -> all components yield low total.
        _insert_earnings_event(
            s, symbol=sym, announced_at=now - timedelta(days=91),
            fiscal_quarter="2025Q4", eps_actual=Decimal("8.0"), eps_estimate=Decimal("8.0"),
            revenue_actual=Decimal("9000"), revenue_estimate=Decimal("9000"),
            operating_income=Decimal("1800"),       # 20% margin
            share_count=900_000_000, guidance_direction="none", source="test",
        )
        eid = _insert_earnings_event(
            s, symbol=sym, announced_at=now,
            fiscal_quarter="2026Q1", eps_actual=Decimal("8.0"), eps_estimate=Decimal("8.0"),
            revenue_actual=Decimal("9000"), revenue_estimate=Decimal("9000"),
            operating_income=Decimal("1800"),       # 20% margin -> no expansion
            share_count=900_000_000,                # equal share count -> 0 pts
            guidance_direction="none", source="test",
        )
        _insert_price_bars(s, sym, now, 21, 250.0, 250.0)
        s.commit()

    with sync_session() as s:
        signal_id = compute_signal_for_event(s, eid)
    assert signal_id is None, "Tech with quality < 60 must be suppressed"

    with sync_session() as s:
        count = s.execute(
            text("SELECT count(*) FROM signals WHERE earnings_event_id = :eid"),
            {"eid": eid},
        ).scalar()
        assert count == 0
        _cleanup(s, sym)


def test_signal_suppressed_by_roic_wacc_filter():
    sym = "NVDA"
    now = datetime.now(timezone.utc)
    with sync_session() as s:
        _cleanup(s, sym)
        _insert_earnings_event(
            s, symbol=sym, announced_at=now - timedelta(days=91),
            fiscal_quarter="2025Q4", eps_actual=Decimal("1.0"), eps_estimate=Decimal("1.0"),
            revenue_actual=Decimal("9000"), revenue_estimate=Decimal("9000"),
            operating_income=Decimal("180"),        # 2% margin
            share_count=2_500_000_000, guidance_direction="up", source="test",
        )
        # Current event: pass quality (revenue surprise + up guidance + buyback) but ROIC = 0.05 < 0.10.
        eid = _insert_earnings_event(
            s, symbol=sym, announced_at=now,
            fiscal_quarter="2026Q1", eps_actual=Decimal("1.10"), eps_estimate=Decimal("1.00"),
            revenue_actual=Decimal("10000"), revenue_estimate=Decimal("9000"),  # 11.1% surprise -> 25 pts
            operating_income=Decimal("200"),        # ROIC = 200 / (10000*0.4) = 0.05
            share_count=2_400_000_000,              # buyback -> 25 pts
            guidance_direction="up",                # 25 pts
            source="test",
        )
        _insert_price_bars(s, sym, now, 21, 800.0, 850.0)
        s.commit()

    with sync_session() as s:
        signal_id = compute_signal_for_event(s, eid)
    assert signal_id is None, "Tech with ROIC < WACC must be suppressed"

    with sync_session() as s:
        count = s.execute(
            text("SELECT count(*) FROM signals WHERE earnings_event_id = :eid"),
            {"eid": eid},
        ).scalar()
        assert count == 0
        _cleanup(s, sym)
