"""Tests for app.execution.orphan_detector — orphan order cancellation logic.

TDD tests for FR-7.3 (orphan detection, 60-second grace period).
"""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("SKIP_GATE_CHECK", "1")


def _make_sell_order(order_id="order-sell-001", symbol="AAPL", age_seconds=120):
    """Create a mock open SELL order."""
    from alpaca.trading.enums import OrderSide
    order = MagicMock()
    order.id = order_id
    order.symbol = symbol
    order.side = OrderSide.SELL
    submitted_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    # Return tz-aware datetime
    order.submitted_at = submitted_at.replace(tzinfo=None)  # simulate naive UTC from SDK
    return order


@patch("app.execution.orphan_detector.get_trading_client")
def test_orphan_cancel_called_for_unmatched_exit_order(mock_get_client):
    """FR-7.3: sell order older than 60s with no DB position triggers cancel_order_by_id."""
    from app.execution.orphan_detector import detect_and_cancel_orphans

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Sell order for AAPL, submitted 120s ago (older than grace period)
    old_sell_order = _make_sell_order(order_id="orphan-001", symbol="AAPL", age_seconds=120)
    mock_client.get_orders.return_value = [old_sell_order]

    # DB has no position for AAPL
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = []

    cancelled = detect_and_cancel_orphans(mock_session)

    mock_client.cancel_order_by_id.assert_called_once_with("orphan-001")
    assert "orphan-001" in cancelled


@patch("app.execution.orphan_detector.get_trading_client")
def test_orphan_skips_orders_younger_than_60s(mock_get_client):
    """FR-7.3: sell order submitted 30s ago is NOT cancelled (within grace period)."""
    from app.execution.orphan_detector import detect_and_cancel_orphans

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Sell order for AAPL, submitted only 30s ago
    recent_sell_order = _make_sell_order(order_id="recent-001", symbol="AAPL", age_seconds=30)
    mock_client.get_orders.return_value = [recent_sell_order]

    # DB has no position for AAPL
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = []

    cancelled = detect_and_cancel_orphans(mock_session)

    mock_client.cancel_order_by_id.assert_not_called()
    assert cancelled == []
