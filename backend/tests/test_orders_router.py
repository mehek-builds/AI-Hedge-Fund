"""Tests for POST /api/v1/orders endpoint."""
import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("SKIP_GATE_CHECK", "1")


@pytest.mark.asyncio
async def test_post_orders_returns_200(client):
    """POST /api/v1/orders with valid payload returns 200 and order details."""
    mock_result = {
        "order_id": "test-order-123",
        "symbol": "AAPL",
        "qty": 10,
        "filled_qty": 10.0,
        "limit_price": 150.005,
        "stop_price": 147.00,
        "take_profit_price": 156.01,
        "status": "accepted",
    }
    with patch("app.routers.orders.submit_bracket_order", return_value=mock_result):
        response = await client.post(
            "/api/v1/orders",
            json={"symbol": "AAPL", "qty": 10, "side": "buy", "ask_price": 150.00},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == "test-order-123"
    assert data["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_post_orders_missing_field_returns_422(client):
    """POST /api/v1/orders with missing required field returns 422."""
    response = await client.post(
        "/api/v1/orders",
        json={"symbol": "AAPL", "qty": 10, "side": "buy"},  # missing ask_price
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_orders_short_blocked_returns_400(client):
    """POST /api/v1/orders with side=sell and ENABLE_SHORT_SIDE=False returns 400."""
    with patch(
        "app.routers.orders.submit_bracket_order",
        side_effect=ValueError("short orders disabled: ENABLE_SHORT_SIDE=False"),
    ):
        response = await client.post(
            "/api/v1/orders",
            json={"symbol": "AAPL", "qty": 10, "side": "sell", "ask_price": 150.00},
        )
    assert response.status_code == 400
    assert "short orders disabled" in response.json()["detail"]
