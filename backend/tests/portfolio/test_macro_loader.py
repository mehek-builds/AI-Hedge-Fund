"""DB-gated tests for macro_loader — FR-4.1, FR-1.5 point-in-time filter.

Requires: DATABASE_URL_SYNC set + alembic upgrade head.
"""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.portfolio.macro import COMPONENT_NAMES
from app.flows._base import sync_session

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL_SYNC"),
    reason="DB-gated: set DATABASE_URL_SYNC and run `alembic upgrade head` first",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SERIES_IDS = [
    "T10Y2Y",
    "SAHMREALTIME",
    "USALOLITONOSM",
    "MANEMP",
    "HYG_LQD_SPREAD",
    "JPY_AUD_CARRY",
]

_NEUTRAL_VALUES = {
    "T10Y2Y": "0.50",       # positive -> yield_curve not inverted (score 0)
    "SAHMREALTIME": "0.10",  # < 0.50 -> sahm ok (score 0)
    "USALOLITONOSM": "0.20",  # > 0 -> lei ok (score 0)
    "MANEMP": "0.10",        # > 0 -> ism_pmi ok (score 0)
    "HYG_LQD_SPREAD": "3.50",  # <= 4.5 -> hyg_lqd_spread ok (score 0)
    "JPY_AUD_CARRY": "0.05",   # > 0 -> jpy_aud_carry ok (score 0)
}


def _insert_macro_row(
    session,
    series_id: str,
    value: str,
    row_date: datetime,
    ingestion_timestamp: datetime,
    vintage_date: datetime | None = None,
):
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
            "vintage_date": vintage_date.date() if vintage_date else None,
            "ingestion_ts": ingestion_timestamp,
        },
    )


def _cleanup(session, series_ids: list[str]):
    for sid in series_ids:
        session.execute(
            text("DELETE FROM macro_indicators WHERE series_id = :sid"),
            {"sid": sid},
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_6_series_present_returns_6_decimal_values():
    """Test 1: All 6 series in fixture -> 6 keys with Decimal values."""
    from app.portfolio.macro_loader import load_latest_macro_components, SERIES_TO_COMPONENT

    now = datetime.now(timezone.utc)
    as_of = now

    with sync_session() as session:
        try:
            for series_id, value in _NEUTRAL_VALUES.items():
                _insert_macro_row(session, series_id, value, now, now - timedelta(hours=1))
            session.flush()

            result = load_latest_macro_components(session, as_of)

            assert len(result) == 6
            for component in SERIES_TO_COMPONENT.values():
                assert component in result, f"Missing component: {component}"
                assert isinstance(result[component], Decimal), (
                    f"Expected Decimal for {component}, got {type(result[component])}"
                )
        finally:
            _cleanup(session, _SERIES_IDS)


def test_empty_table_returns_6_none_values():
    """Test 2: Empty macro_indicators table -> all 6 keys present with value=None."""
    from app.portfolio.macro_loader import load_latest_macro_components, SERIES_TO_COMPONENT

    now = datetime.now(timezone.utc)

    with sync_session() as session:
        try:
            _cleanup(session, _SERIES_IDS)
            session.flush()

            result = load_latest_macro_components(session, now)

            assert len(result) == 6
            for component in SERIES_TO_COMPONENT.values():
                assert component in result
                assert result[component] is None, f"Expected None for {component}"
        finally:
            _cleanup(session, _SERIES_IDS)


def test_mixed_3_present_3_missing_returns_6_keys():
    """Test 3: 3 series present, 3 missing -> 6 keys; missing ones are None."""
    from app.portfolio.macro_loader import load_latest_macro_components

    now = datetime.now(timezone.utc)
    present_series = ["T10Y2Y", "SAHMREALTIME", "USALOLITONOSM"]
    missing_series = ["MANEMP", "HYG_LQD_SPREAD", "JPY_AUD_CARRY"]

    with sync_session() as session:
        try:
            _cleanup(session, _SERIES_IDS)
            session.flush()

            for series_id in present_series:
                _insert_macro_row(
                    session, series_id, _NEUTRAL_VALUES[series_id],
                    now, now - timedelta(hours=1),
                )
            session.flush()

            result = load_latest_macro_components(session, now)

            assert len(result) == 6
            # Present ones have Decimal values
            assert isinstance(result["yield_curve"], Decimal)
            assert isinstance(result["sahm"], Decimal)
            assert isinstance(result["lei"], Decimal)
            # Missing ones are None
            assert result["ism_pmi"] is None
            assert result["hyg_lqd_spread"] is None
            assert result["jpy_aud_carry"] is None
        finally:
            _cleanup(session, _SERIES_IDS)


def test_point_in_time_two_rows_as_of_between_returns_older():
    """Test 4: Two rows for T10Y2Y (older + newer); as_of between them -> only older returned."""
    from app.portfolio.macro_loader import load_latest_macro_components

    now = datetime.now(timezone.utc)
    older_date = now - timedelta(days=10)
    newer_date = now + timedelta(days=1)
    as_of = now  # between older and newer

    with sync_session() as session:
        try:
            _cleanup(session, ["T10Y2Y"])
            session.flush()

            _insert_macro_row(
                session, "T10Y2Y", "0.30",
                older_date, older_date - timedelta(hours=1),
            )
            _insert_macro_row(
                session, "T10Y2Y", "1.50",
                newer_date, newer_date - timedelta(hours=1),
            )
            session.flush()

            result = load_latest_macro_components(session, as_of)

            # Should return the older value (0.30), NOT the newer (1.50)
            assert result["yield_curve"] == Decimal("0.30"), (
                f"Expected 0.30 (older), got {result['yield_curve']}"
            )
        finally:
            _cleanup(session, ["T10Y2Y"])


def test_fr15_ingestion_timestamp_after_as_of_excludes_row():
    """Test 5: ingestion_timestamp > as_of -> row excluded (FR-1.5)."""
    from app.portfolio.macro_loader import load_latest_macro_components

    now = datetime.now(timezone.utc)
    as_of = now - timedelta(hours=2)  # as_of is 2h in the past
    future_ingestion = now  # ingested AFTER as_of

    with sync_session() as session:
        try:
            _cleanup(session, ["T10Y2Y"])
            session.flush()

            # Row date is before as_of, but ingestion_timestamp is AFTER as_of
            _insert_macro_row(
                session, "T10Y2Y", "0.75",
                as_of - timedelta(days=1),  # date is fine
                future_ingestion,            # but ingestion is in the future relative to as_of
            )
            session.flush()

            result = load_latest_macro_components(session, as_of)

            # Row must be excluded because ingestion_timestamp > as_of
            assert result["yield_curve"] is None, (
                f"Row with future ingestion_timestamp must be excluded, got {result['yield_curve']}"
            )
        finally:
            _cleanup(session, ["T10Y2Y"])


def test_returned_keys_match_component_names_exactly():
    """Test 6: Returned dict keys match exactly COMPONENT_NAMES from macro.py (no extras, no typos)."""
    from app.portfolio.macro_loader import load_latest_macro_components

    now = datetime.now(timezone.utc)

    with sync_session() as session:
        try:
            _cleanup(session, _SERIES_IDS)
            session.flush()

            result = load_latest_macro_components(session, now)

            assert set(result.keys()) == set(COMPONENT_NAMES), (
                f"Keys mismatch. Got: {set(result.keys())}. Expected: {set(COMPONENT_NAMES)}"
            )
        finally:
            _cleanup(session, _SERIES_IDS)
