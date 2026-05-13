"""Alpaca TradingClient singleton and bracket order submission.

CRITICAL: TradingClient is SYNCHRONOUS. Always call submit_bracket_order()
via asyncio.to_thread() inside FastAPI async handlers to avoid blocking
the event loop.
"""
import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import (
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

from app.config import settings

logger = logging.getLogger(__name__)

# Tick size for limit price calculation (ask + 0.5 tick per locked decision)
TICK_SIZE = Decimal("0.01")
HALF_TICK = TICK_SIZE / 2


@lru_cache(maxsize=1)
def get_trading_client() -> TradingClient:
    """Return the TradingClient singleton. Created once on first call."""
    return TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.ALPACA_PAPER,
    )


def submit_bracket_order(
    symbol: str,
    qty: int,
    side: str,
    ask_price: float,
) -> dict[str, Any]:
    """Submit a bracket order (limit entry + stop-loss + take-profit) to Alpaca.

    Entry: limit at ask_price + 0.5 tick (per locked decision).
    Stop-loss: entry * (1 - STOP_LOSS_PCT) per locked decision (default 2%).
    Take-profit: entry * (1 + TAKE_PROFIT_PCT) per locked decision (default 4%).
    Partial fill: returns filled_qty from order response (not original qty).

    Args:
        symbol: Ticker symbol (e.g. "AAPL")
        qty: Number of shares to trade
        side: "buy" or "sell"
        ask_price: Current ask price used to compute limit entry

    Returns:
        dict with keys: order_id, symbol, qty, filled_qty, limit_price,
                        stop_price, take_profit_price, status

    Raises:
        ValueError: if side == "sell" and ENABLE_SHORT_SIDE is False
    """
    if side.lower() == "sell" and not settings.ENABLE_SHORT_SIDE:
        raise ValueError(
            "short orders disabled: ENABLE_SHORT_SIDE=False. "
            "Enable via settings to place short orders."
        )

    ask = Decimal(str(ask_price))
    entry_price = ask + HALF_TICK
    stop_price = (entry_price * (1 - Decimal(str(settings.STOP_LOSS_PCT)))).quantize(TICK_SIZE)
    take_profit_price = (entry_price * (1 + Decimal(str(settings.TAKE_PROFIT_PCT)))).quantize(TICK_SIZE)

    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

    request = LimitOrderRequest(
        symbol=symbol,
        qty=qty,
        side=order_side,
        limit_price=float(entry_price),
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        stop_loss=StopLossRequest(stop_price=float(stop_price)),
        take_profit=TakeProfitRequest(limit_price=float(take_profit_price)),
    )

    client = get_trading_client()
    try:
        order = client.submit_order(request)
        filled_qty = float(order.filled_qty) if order.filled_qty else 0.0
        logger.info(
            "Bracket order submitted: %s %s x%d | entry=%.4f stop=%.4f tp=%.4f | "
            "order_id=%s filled_qty=%s",
            side.upper(), symbol, qty,
            float(entry_price), float(stop_price), float(take_profit_price),
            order.id, filled_qty,
        )
        return {
            "order_id": str(order.id),
            "symbol": symbol,
            "qty": qty,
            "filled_qty": filled_qty,
            "limit_price": float(entry_price),
            "stop_price": float(stop_price),
            "take_profit_price": float(take_profit_price),
            "status": str(order.status),
        }
    except Exception as exc:
        logger.error("Bracket order failed: %s %s - %s", side, symbol, exc)
        raise
