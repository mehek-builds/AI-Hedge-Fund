"""Tests for app.execution.broker — bracket order submission logic.

TDD tests for FR-7.1 (bracket orders) and FR-7.6 (short side flag).
"""
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("SKIP_GATE_CHECK", "1")


def _make_mock_order(filled_qty=10, qty=10, order_id="order-abc-123", status="accepted"):
    order = MagicMock()
    order.id = order_id
    order.filled_qty = str(filled_qty)
    order.qty = str(qty)
    order.status = status
    return order


@patch("app.execution.broker.get_trading_client")
def test_submit_bracket_order_buy(mock_get_client):
    """FR-7.1: BUY bracket order uses correct limit/stop/take-profit prices.

    ask_price=150.00 -> entry=150.005 (ask + 0.5 tick)
    stop = entry * 0.98 = 147.00 (rounded to tick)
    take_profit = entry * 1.04 = 156.01 (rounded to tick)
    """
    from app.execution.broker import submit_bracket_order

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.submit_order.return_value = _make_mock_order(filled_qty=10)

    result = submit_bracket_order("AAPL", qty=10, side="buy", ask_price=150.00)

    mock_client.submit_order.assert_called_once()
    request = mock_client.submit_order.call_args[0][0]

    # Entry: 150.00 + 0.005 = 150.005
    assert float(request.limit_price) == pytest.approx(150.005, abs=1e-6)
    # Stop: 150.005 * 0.98 = 147.0049 -> quantize -> 147.00
    assert float(request.stop_loss.stop_price) == pytest.approx(147.00, abs=0.02)
    # Take-profit: 150.005 * 1.04 = 156.0052 -> quantize -> 156.01
    assert float(request.take_profit.limit_price) == pytest.approx(156.01, abs=0.02)
    assert request.symbol == "AAPL"
    assert request.qty == 10


@patch("app.execution.broker.get_trading_client")
def test_submit_bracket_order_uses_filled_qty(mock_get_client):
    """FR-7.1: Partial fill - returned dict contains filled_qty from order response."""
    from app.execution.broker import submit_bracket_order

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.submit_order.return_value = _make_mock_order(filled_qty=7, qty=10)

    result = submit_bracket_order("AAPL", qty=10, side="buy", ask_price=150.00)

    assert result["filled_qty"] == 7.0


def test_short_blocked_by_flag():
    """FR-7.6: side='sell' raises ValueError when ENABLE_SHORT_SIDE=False."""
    from app.execution.broker import submit_bracket_order

    with patch("app.execution.broker.settings") as mock_settings:
        mock_settings.ENABLE_SHORT_SIDE = False
        mock_settings.STOP_LOSS_PCT = 0.02
        mock_settings.TAKE_PROFIT_PCT = 0.04
        with pytest.raises(ValueError, match="short orders disabled"):
            submit_bracket_order("AAPL", qty=10, side="sell", ask_price=150.00)


@patch("app.execution.broker.get_trading_client")
def test_short_allowed_when_flag_enabled(mock_get_client):
    """FR-7.6: No exception when ENABLE_SHORT_SIDE=True."""
    from app.execution.broker import submit_bracket_order

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.submit_order.return_value = _make_mock_order()

    with patch("app.execution.broker.settings") as mock_settings:
        mock_settings.ENABLE_SHORT_SIDE = True
        mock_settings.STOP_LOSS_PCT = 0.02
        mock_settings.TAKE_PROFIT_PCT = 0.04
        result = submit_bracket_order("AAPL", qty=10, side="sell", ask_price=150.00)

    assert "order_id" in result
