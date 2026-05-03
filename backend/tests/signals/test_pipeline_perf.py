"""Performance benchmark for the signal pipeline (FR-3.7).

Asserts: compute_signal_for_event for one earnings event completes in < 5 seconds
end-to-end (DB read + computation + signals row write).

Requires: docker compose up + alembic upgrade head. CI-gated.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.flows._base import sync_session
from app.models.earnings_events import EarningsEvent
from app.signals.pipeline import compute_signal_for_event


pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_SYNC"),
    reason="DB-gated: set DATABASE_URL_SYNC and run `alembic upgrade head` first",
)


PERF_BUDGET_SECONDS = 5.0


def _setup_fixture(symbol: str) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    with sync_session() as s:
        s.execute(text("DELETE FROM signals WHERE symbol = :s"), {"s": symbol})
        s.execute(text("DELETE FROM earnings_events WHERE symbol = :s"), {"s": symbol})
        s.execute(text("DELETE FROM price_bars WHERE symbol = :s"), {"s": symbol})

        prior = EarningsEvent(
            symbol=symbol, announced_at=now - timedelta(days=91),
            fiscal_quarter="2025Q4", eps_actual=Decimal("8.0"), eps_estimate=Decimal("7.5"),
            revenue_actual=Decimal("9000"), revenue_estimate=Decimal("8800"),
            operating_income=Decimal("1350"),
            share_count=950_000_000, guidance_direction="flat", source="perf",
        )
        s.add(prior)
        cur = EarningsEvent(
            symbol=symbol, announced_at=now,
            fiscal_quarter="2026Q1", eps_actual=Decimal("10.0"), eps_estimate=Decimal("8.0"),
            revenue_actual=Decimal("10000"), revenue_estimate=Decimal("9000"),
            operating_income=Decimal("2000"),
            share_count=900_000_000, guidance_direction="up", source="perf",
        )
        s.add(cur)
        s.flush()
        prior_id, eid = prior.id, cur.id

        # 21 daily bars, $250 -> $280
        step = (280.0 - 250.0) / 20.0
        for i in range(21):
            t = now - timedelta(days=20 - i)
            price = Decimal(str(round(250.0 + step * i, 2)))
            s.execute(
                text(
                    """
                    INSERT INTO price_bars(time, symbol, open, high, low, close, vwap, volume, ingestion_timestamp)
                    VALUES (:t, :sym, :p, :p, :p, :p, :p, 1000000, NOW())
                    ON CONFLICT (time, symbol) DO UPDATE SET close = EXCLUDED.close
                    """
                ),
                {"t": t, "sym": symbol, "p": price},
            )
        s.commit()
        return prior_id, eid


def _cleanup(symbol: str):
    with sync_session() as s:
        s.execute(text("DELETE FROM signals WHERE symbol = :s"), {"s": symbol})
        s.execute(text("DELETE FROM earnings_events WHERE symbol = :s"), {"s": symbol})
        s.execute(text("DELETE FROM price_bars WHERE symbol = :s"), {"s": symbol})


def test_signal_computation_under_5_seconds():
    sym = "AAPL"
    _, eid = _setup_fixture(sym)
    try:
        # Warmup pass — load imports, prime connection pool, populate query plan cache.
        with sync_session() as s:
            compute_signal_for_event(s, eid)

        # Timed pass.
        with sync_session() as s:
            t0 = time.perf_counter()
            signal_id = compute_signal_for_event(s, eid)
            elapsed = time.perf_counter() - t0

        assert signal_id is not None, "fixture must produce a signal"
        assert elapsed < PERF_BUDGET_SECONDS, (
            f"FR-3.7 perf budget violated: compute_signal_for_event took "
            f"{elapsed:.3f}s (budget {PERF_BUDGET_SECONDS}s)"
        )
    finally:
        _cleanup(sym)
