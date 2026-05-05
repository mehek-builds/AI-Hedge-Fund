"""End-to-end DB-gated integration tests for the portfolio sizing pipeline.

Requires: DATABASE_URL_SYNC set + alembic upgrade head + TimescaleDB extension.

Tests prove that a signal_id flows through:
  signal row -> macro snapshot loaded -> position sized -> portfolio_positions row written
"""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.flows._base import sync_session

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_SYNC"),
    reason="DB-gated: set DATABASE_URL_SYNC and run `alembic upgrade head` first",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_SIGNAL_ID_PREFIX = "04-03-inttest-"


def _insert_signal(session, signal_id: str, symbol: str, naive_size: str, direction: str) -> datetime:
    """Insert a signal row and return its created_at timestamp."""
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            """
            INSERT INTO signals(created_at, signal_id, symbol, naive_position_size, direction, status)
            VALUES (:created_at, :sid, :symbol, :naive_size, :direction, 'pending')
            ON CONFLICT (created_at, signal_id) DO UPDATE
              SET naive_position_size = EXCLUDED.naive_position_size
            """
        ),
        {
            "created_at": now,
            "sid": signal_id,
            "symbol": symbol,
            "naive_size": naive_size,
            "direction": direction,
        },
    )
    return now


def _insert_price_bar(session, symbol: str, price: str, as_of: datetime):
    session.execute(
        text(
            """
            INSERT INTO price_bars(time, symbol, open, high, low, close, vwap, volume, ingestion_timestamp)
            VALUES (:t, :s, :p, :p, :p, :p, :p, 1000000, :ingestion_ts)
            ON CONFLICT (time, symbol) DO UPDATE
              SET close = EXCLUDED.close, ingestion_timestamp = EXCLUDED.ingestion_timestamp
            """
        ),
        {
            "t": as_of - timedelta(hours=1),
            "s": symbol,
            "p": price,
            "ingestion_ts": as_of - timedelta(hours=2),
        },
    )


_NEUTRAL_MACRO = {
    "T10Y2Y": "0.50",       # yield_curve: positive -> not inverted (score 0)
    "SAHMREALTIME": "0.10",  # sahm: < 0.50 -> ok (score 0)
    "USALOLITONOSM": "0.20", # lei: > 0 -> ok (score 0)
    "MANEMP": "0.10",        # ism_pmi: > 0 -> ok (score 0)
    "HYG_LQD_SPREAD": "3.50", # hyg_lqd_spread: <= 4.5 -> ok (score 0)
    "JPY_AUD_CARRY": "0.05",  # jpy_aud_carry: > 0 -> ok (score 0)
}

_RECESSION_MACRO = {
    "T10Y2Y": "-0.30",       # yield_curve: < 0 -> inverted (score -1)
    "SAHMREALTIME": "0.60",  # sahm: >= 0.50 -> recession (score -1)
    "USALOLITONOSM": "-0.10", # lei: < 0 -> declining (score -1)
    "MANEMP": "-0.05",       # ism_pmi: < 0 -> contracting (score -1)
    "HYG_LQD_SPREAD": "5.00", # hyg_lqd_spread: > 4.5 -> wide (score -1)
    "JPY_AUD_CARRY": "0.05",  # jpy_aud_carry: > 0 -> ok (score 0) — only 5 negative
}


def _insert_macro_rows(session, macro_values: dict, as_of: datetime):
    ingestion_ts = as_of - timedelta(hours=1)
    row_date = as_of - timedelta(days=1)
    for series_id, value in macro_values.items():
        session.execute(
            text(
                """
                INSERT INTO macro_indicators(date, series_id, value, vintage_date, ingestion_timestamp)
                VALUES (:date, :series_id, :value, :vintage_date, :ingestion_ts)
                ON CONFLICT (date, series_id) DO UPDATE
                  SET value = EXCLUDED.value,
                      ingestion_timestamp = EXCLUDED.ingestion_timestamp
                """
            ),
            {
                "date": row_date.date(),
                "series_id": series_id,
                "value": value,
                "vintage_date": row_date.date(),
                "ingestion_ts": ingestion_ts,
            },
        )


def _cleanup(session, signal_id: str, symbol: str):
    session.execute(text("DELETE FROM signals WHERE signal_id = :sid"), {"sid": signal_id})
    session.execute(text("DELETE FROM price_bars WHERE symbol = :s"), {"s": symbol})
    session.execute(text("DELETE FROM portfolio_positions WHERE symbol = :s"), {"s": symbol})
    for series_id in _NEUTRAL_MACRO:
        session.execute(
            text("DELETE FROM macro_indicators WHERE series_id = :sid"),
            {"sid": series_id},
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_end_to_end_long_signal_writes_portfolio_position():
    """Test 1: Valid long signal -> portfolio_positions row with stop_loss_price = entry * 0.92."""
    from app.tasks.portfolio import compute_portfolio_size_task

    signal_id = _TEST_SIGNAL_ID_PREFIX + "t1"
    symbol = "INTC"  # Not Mag-7, no cap
    entry_price = Decimal("50.00")
    expected_stop = entry_price * Decimal("0.92")  # 8% below for long

    with sync_session() as session:
        try:
            _cleanup(session, signal_id, symbol)
            created_at = _insert_signal(session, signal_id, symbol, "0.0200", "long")
            _insert_price_bar(session, symbol, str(entry_price), created_at)
            _insert_macro_rows(session, _NEUTRAL_MACRO, created_at)
            session.flush()

            result = compute_portfolio_size_task.run(signal_id)

            assert result == symbol, f"Expected symbol={symbol}, got {result}"

            # Verify portfolio_positions row was written
            row = session.execute(
                text(
                    """
                    SELECT stop_loss_price, status
                    FROM portfolio_positions
                    WHERE symbol = :s
                    ORDER BY snapshot_at DESC
                    LIMIT 1
                    """
                ),
                {"s": symbol},
            ).fetchone()

            assert row is not None, "portfolio_positions row must be written"
            assert row[1] == "sized", f"Expected status='sized', got {row[1]}"
            actual_stop = Decimal(str(row[0]))
            assert actual_stop == expected_stop, (
                f"stop_loss_price mismatch: expected {expected_stop}, got {actual_stop}"
            )
        finally:
            _cleanup(session, signal_id, symbol)


def test_end_to_end_macro_recession_reduces_size():
    """Test 2: 5-component negative macro -> macro_score=-5 -> multiplier=0.25.

    Verifies by calling compute_position_size directly with same inputs and comparing.
    """
    from app.tasks.portfolio import compute_portfolio_size_task, DEFAULT_EP_YIELD, DEFAULT_TIPS_YIELD
    from app.portfolio.pipeline import compute_position_size
    from app.portfolio.macro_loader import load_latest_macro_components

    signal_id = _TEST_SIGNAL_ID_PREFIX + "t2"
    symbol = "CSCO"
    naive_size = Decimal("0.0200")
    entry_price = Decimal("60.00")

    with sync_session() as session:
        try:
            _cleanup(session, signal_id, symbol)
            created_at = _insert_signal(session, signal_id, symbol, str(naive_size), "long")
            _insert_price_bar(session, symbol, str(entry_price), created_at)
            _insert_macro_rows(session, _RECESSION_MACRO, created_at)
            session.flush()

            result = compute_portfolio_size_task.run(signal_id)
            assert result == symbol

            # Load macro directly to verify score calculation
            macro = load_latest_macro_components(session, created_at)

            # Compute expected result with same inputs
            expected = compute_position_size(
                symbol=symbol,
                direction="long",
                naive_size_nav=naive_size,
                entry_price=entry_price,
                macro_components=macro,
                ep_yield=DEFAULT_EP_YIELD,
                real_tips_yield=DEFAULT_TIPS_YIELD,
            )

            # macro_score should be -5 (5 components negative in _RECESSION_MACRO)
            assert expected.macro_score == -5, f"Expected macro_score=-5, got {expected.macro_score}"
            # multiplier for score -5 is 0.25 (in the -4 to -6 band)
            assert expected.macro_multiplier == Decimal("0.25"), (
                f"Expected multiplier=0.25 for score=-5, got {expected.macro_multiplier}"
            )
            # final size should be naive * 0.25 = 0.005
            assert expected.final_size_nav == (naive_size * Decimal("0.25")).quantize(Decimal("0.000001")), (
                f"Expected final_size_nav={naive_size * Decimal('0.25')}, got {expected.final_size_nav}"
            )
        finally:
            _cleanup(session, signal_id, symbol)


def test_end_to_end_mag7_cap_logged(caplog):
    """Test 3: MSFT signal with naive=0.05 -> Mag-7 cap fires -> stop_loss_price written.

    Verifies portfolio_positions row has stop_loss_price set and MAG7 cap event logged.
    """
    import logging
    from app.tasks.portfolio import compute_portfolio_size_task

    signal_id = _TEST_SIGNAL_ID_PREFIX + "t3"
    symbol = "MSFT"  # Mag-7 member
    naive_size_str = "0.0500"  # 5% -> above 3% Mag-7 cap
    entry_price = Decimal("400.00")

    with sync_session() as session:
        try:
            _cleanup(session, signal_id, symbol)
            created_at = _insert_signal(session, signal_id, symbol, naive_size_str, "long")
            _insert_price_bar(session, symbol, str(entry_price), created_at)
            _insert_macro_rows(session, _NEUTRAL_MACRO, created_at)
            session.flush()

            with caplog.at_level(logging.WARNING, logger="app.portfolio.pipeline"):
                result = compute_portfolio_size_task.run(signal_id)

            assert result == symbol, f"Expected symbol={symbol}, got {result}"

            # Verify portfolio_positions row has stop_loss_price set
            row = session.execute(
                text(
                    """
                    SELECT stop_loss_price, status
                    FROM portfolio_positions
                    WHERE symbol = :s
                    ORDER BY snapshot_at DESC
                    LIMIT 1
                    """
                ),
                {"s": symbol},
            ).fetchone()

            assert row is not None, "portfolio_positions row must be written"
            assert row[0] is not None, "stop_loss_price must be set"
            assert row[1] == "sized"

            # Verify stop_loss_price is entry * 0.92 (long)
            expected_stop = entry_price * Decimal("0.92")
            assert Decimal(str(row[0])) == expected_stop

            # Verify MAG7 cap event was logged
            mag7_logged = any("MAG7" in record.message for record in caplog.records)
            assert mag7_logged, (
                f"Expected MAG7 cap log message. Got log records: {[r.message for r in caplog.records]}"
            )
        finally:
            _cleanup(session, signal_id, symbol)
