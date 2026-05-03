"""Orders router — GET /orders from Alpaca."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.models.schemas import OrderOut
from api.services.alpaca import get_alpaca_client
from api.services.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
async def list_orders(
    _user: str = Depends(get_current_user),
    status: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[OrderOut]:
    """Return Alpaca order history."""
    alpaca = get_alpaca_client()
    raw_orders = alpaca.get_orders(status=status, limit=limit)

    result = []
    for o in raw_orders:
        # Parse datetime strings if needed
        import datetime

        def _parse_dt(v):
            if v is None:
                return None
            if isinstance(v, datetime.datetime):
                return v
            try:
                return datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                return None

        result.append(
            OrderOut(
                id=o["id"],
                client_order_id=o.get("client_order_id"),
                symbol=o["symbol"],
                side=o["side"],
                qty=o.get("qty"),
                filled_qty=o.get("filled_qty"),
                type=o["type"],
                status=o["status"],
                submitted_at=_parse_dt(o.get("submitted_at")),
                filled_at=_parse_dt(o.get("filled_at")),
                filled_avg_price=o.get("filled_avg_price"),
            )
        )
    return result
