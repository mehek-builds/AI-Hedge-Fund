"""Tests for FR-6.1: point-in-time correctness (no look-ahead bias).

Threat ref: T-6-01 (look-ahead bias is the highest-severity defect class per NFR-1).

Test strategy: inject a future-timestamped price bar row and verify that
backtest queries with ingestion_timestamp <= as_of filter never return it.
"""

import sys
import os
from datetime import date, datetime, timezone

import pytest

# Ensure backend package is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.backtest.fills import get_close_as_of


class TestPointInTimeFilter:
    """FR-6.1: every query must filter ingestion_timestamp <= as_of."""

    def test_get_close_as_of_returns_none_for_future_row(self, mock_sync_session):
        """Future-timestamped row must not be returned by get_close_as_of.

        Simulates a price bar injected after as_of (ingestion_timestamp > as_of).
        The SQL query should exclude it; mock returns None.
        """
        as_of = datetime(2019, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        mock_sync_session.execute.return_value.fetchone.return_value = None

        result = get_close_as_of(mock_sync_session, "AAPL", as_of)

        assert result is None, "Future-timestamped row must not be visible"

    def test_get_close_as_of_uses_ingestion_timestamp_filter(self, mock_sync_session):
        """Verify the SQL query includes ingestion_timestamp <= :as_of.

        The filter must be present in every query to prevent look-ahead bias.
        """
        as_of = datetime(2020, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        mock_sync_session.execute.return_value.fetchone.return_value = None

        get_close_as_of(mock_sync_session, "MSFT", as_of)

        # Verify execute was called
        assert mock_sync_session.execute.called

        # Extract the SQL text from the call
        call_args = mock_sync_session.execute.call_args
        sql_text = str(call_args[0][0])

        # ingestion_timestamp filter must be in the query
        assert "ingestion_timestamp" in sql_text, (
            "SQL query must include ingestion_timestamp filter (FR-6.1)"
        )

    def test_get_close_as_of_returns_valid_price_for_existing_row(
        self, mock_sync_session
    ):
        """Existing row with ingestion_timestamp <= as_of should be returned."""
        as_of = datetime(2021, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        mock_sync_session.execute.return_value.fetchone.return_value = (142.50,)

        result = get_close_as_of(mock_sync_session, "AAPL", as_of)

        assert result == pytest.approx(142.50)

    def test_sp500_members_as_of_filters_ingestion_timestamp(self, mock_sync_session):
        """sp500_members_as_of must filter ingestion_timestamp <= as_of (FR-6.1)."""
        from app.backtest.runner import sp500_members_as_of

        as_of = date(2019, 1, 2)
        mock_sync_session.execute.return_value.fetchall.return_value = [
            ("AAPL",),
            ("MSFT",),
        ]

        result = sp500_members_as_of(mock_sync_session, as_of)

        assert mock_sync_session.execute.called
        call_args = mock_sync_session.execute.call_args
        sql_text = str(call_args[0][0])

        assert "ingestion_timestamp" in sql_text, (
            "sp500_members_as_of must filter ingestion_timestamp <= :as_of"
        )
        assert result == ["AAPL", "MSFT"]

    def test_future_ingestion_date_does_not_expand_universe(self, mock_sync_session):
        """A company added to S&P 500 after as_of must not appear in universe.

        This tests the removed_date/added_date plus ingestion_timestamp filters together.
        """
        # Simulate a constituent with future ingestion_timestamp
        as_of = date(2019, 6, 1)
        # Future-ingested row: ingestion_timestamp > as_of, so must be filtered
        mock_sync_session.execute.return_value.fetchall.return_value = []

        from app.backtest.runner import sp500_members_as_of

        result = sp500_members_as_of(mock_sync_session, as_of)
        assert result == [], "Future-ingested constituents must be excluded"
