"""POST /api/v1/orders - submit a bracket order via Alpaca paper trading.

Called by the signal engine when a signal triggers order placement.
Uses asyncio.to_thread() to wrap the synchronous TradingClient call
(alpaca-py 0.43.4 TradingClient is synchronous).
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.execution.broker import submit_bracket_order

logger = logging.getLogger(__name__)
router = APIRouter()


class OrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10, description="Ticker symbol")
    qty: int = Field(..., gt=0, description="Number of shares (must be > 0)")
    side: str = Field(..., pattern="^(buy|sell)$", description="'buy' or 'sell'")
    ask_price: float = Field(..., gt=0, description="Current ask price for limit computation")


@router.post("/orders")
async def create_order(payload: OrderRequest):
    """Submit a bracket order. Fires and returns order details.

    Entry limit: ask_price + 0.5 tick
    Stop-loss: entry * (1 - STOP_LOSS_PCT) [default 2%]
    Take-profit: entry * (1 + TAKE_PROFIT_PCT) [default 4%]

    Returns 400 if ENABLE_SHORT_SIDE=False and side='sell'.
    Returns 502 if Alpaca API call fails.
    """
    try:
        result = await asyncio.to_thread(
            submit_bracket_order,
            payload.symbol,
            payload.qty,
            payload.side,
            payload.ask_price,
        )
        return result
    except ValueError as exc:
        # Short side blocked by feature flag
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Order submission failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Alpaca order failed: {exc}")
