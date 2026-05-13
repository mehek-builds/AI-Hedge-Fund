"""Tests for app.execution.position_sync — position reconciliation logic.

TDD tests for FR-7.2 (position reconciliation, hypertable append semantics).
"""
import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

os.environ.setdefault("SKIP_GATE_CHECK", "1")


def _make_alpaca_position(symbol="AAPL", qty="10", avg_entry_price="148.00",
                           current_price="152.00", unrealized_pl="40.00"):
    pos = MagicMock()
    pos.symbol = symbol
    pos.qty = qty
    pos.avg_entry_price = avg_entry_price
    pos.current_price = current_price
    pos.unrealized_pl = unrealized_pl
    return pos


@patch("app.execution.position_sync.get_trading_client")
def test_reconcile_inserts_snapshot_on_discrepancy(mock_get_client):
    """FR-7.2: Discrepancy triggers INSERT of new portfolio_positions snapshot row.

    Alpaca qty=10, DB qty=8 -> INSERT new row, returns count=1.
    """
    from app.execution.position_sync import reconcile_positions_with_alpaca

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.get_all_positions.return_value = [
        _make_alpaca_position(symbol="AAPL", qty="10")
    ]

    mock_session = MagicMock()
    # First execute: SELECT latest qty -> returns qty=8
    db_row = MagicMock()
    db_row.__getitem__ = lambda self, i: Decimal("8") if i == 0 else None
    mock_session.execute.return_value.fetchone.return_value = db_row

    count = reconcile_positions_with_alpaca(mock_session)

    assert count == 1
    # Verify INSERT was called (second execute call)
    assert mock_session.execute.call_count == 2


@patch("app.execution.position_sync.get_trading_client")
def test_reconcile_no_op_when_in_sync(mock_get_client):
    """FR-7.2: No INSERT when Alpaca qty matches DB qty, returns count=0."""
    from app.execution.position_sync import reconcile_positions_with_alpaca

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.get_all_positions.return_value = [
        _make_alpaca_position(symbol="AAPL", qty="10")
    ]

    mock_session = MagicMock()
    # SELECT returns qty=10 (matches Alpaca)
    db_row = MagicMock()
    db_row.__getitem__ = lambda self, i: Decimal("10") if i == 0 else None
    mock_session.execute.return_value.fetchone.return_value = db_row

    count = reconcile_positions_with_alpaca(mock_session)

    assert count == 0
    # Only the SELECT was called, no INSERT
    assert mock_session.execute.call_count == 1
