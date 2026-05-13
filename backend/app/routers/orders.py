"""POST /api/v1/orders - submit a bracket order via Alpaca paper trading.

Alert wiring (Plan 07-04): fires order_submitted event via dispatch_alert
after successful bracket order submission. Uses asyncio.create_task() for
fire-and-forget (alert dispatch never blocks the order response).
"""
import asyncio
import logging

import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerting.dispatcher import dispatch_alert
from app.config import settings
from app.database import get_db
from app.execution.broker import submit_bracket_order

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_redis() -> redis.Redis:
    """Return a synchronous Redis client for rate limiting and pub/sub."""
    return redis.from_url(settings.REDIS_PUB_URL, decode_responses=True)


class OrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10, description="Ticker symbol")
    qty: int = Field(..., gt=0, description="Number of shares (must be > 0)")
    side: str = Field(..., pattern="^(buy|sell)$", description="'buy' or 'sell'")
    ask_price: float = Field(..., gt=0, description="Current ask price for limit computation")


@router.post("/orders")
async def create_order(
    payload: OrderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a bracket order and fire order_submitted alert (fire-and-forget).

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
    except ValueError as exc:
        # Short side blocked by feature flag
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Order submission failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Alpaca order failed: {exc}")

    # Fire-and-forget: order_submitted alert does not block the response.
    # Opens its own AsyncSession so the alert persists after the request
    # handler's DB session is closed (request-scoped sessions close on return).
    alert_payload = {
        "symbol": payload.symbol,
        "qty": payload.qty,
        "side": payload.side,
        "order_id": result.get("order_id"),
        "filled_qty": result.get("filled_qty"),
        "limit_price": result.get("limit_price"),
    }

    async def _fire_alert() -> None:
        from app.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as session:
                await dispatch_alert("order_submitted", alert_payload, session, _get_redis())
        except Exception as _exc:
            logger.error("order_submitted alert failed (non-fatal): %s", _exc)

    asyncio.create_task(_fire_alert())

    return result
