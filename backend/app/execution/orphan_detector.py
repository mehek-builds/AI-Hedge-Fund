"""Detect and cancel orphaned exit orders.

An orphan is an open SELL order with no matching portfolio_positions row,
submitted more than ORPHAN_GRACE_SECONDS ago (avoids false positives on
just-submitted orders before the DB position write commits).
"""
import logging
from datetime import datetime, timedelta, timezone

from alpaca.trading.enums import OrderSide, QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.execution.broker import get_trading_client

logger = logging.getLogger(__name__)

# Orders younger than this threshold are never treated as orphans
ORPHAN_GRACE_SECONDS = 60


def detect_and_cancel_orphans(session: Session) -> list[str]:
    """Find open sell orders with no matching position and cancel them.

    Returns list of cancelled order IDs.
    """
    client = get_trading_client()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ORPHAN_GRACE_SECONDS)

    open_orders = client.get_orders(
        filter=GetOrdersRequest(status=QueryOrderStatus.OPEN)
    )

    # Get symbols with active DB positions (latest snapshot per symbol)
    position_rows = session.execute(
        text("""
            SELECT DISTINCT ON (symbol) symbol, qty
            FROM portfolio_positions
            ORDER BY symbol, snapshot_at DESC
        """)
    ).fetchall()
    active_symbols = {
        row[0] for row in position_rows
        if row[1] is not None and float(row[1]) > 0
    }

    cancelled_ids = []
    for order in open_orders:
        # Only check exit (sell) orders
        if order.side != OrderSide.SELL:
            continue

        # Skip orders younger than grace period
        submitted_at = order.submitted_at
        if submitted_at is not None:
            # Handle both naive and tz-aware datetimes from SDK
            if submitted_at.tzinfo is None:
                submitted_at_utc = submitted_at.replace(tzinfo=timezone.utc)
            else:
                submitted_at_utc = submitted_at
            if submitted_at_utc > cutoff:
                logger.debug(
                    "Orphan check: skipping recent order %s for %s (submitted %s)",
                    order.id, order.symbol, submitted_at,
                )
                continue

        # Cancel if symbol has no active position in DB
        if order.symbol not in active_symbols:
            try:
                client.cancel_order_by_id(order.id)
                cancelled_ids.append(str(order.id))
                logger.warning(
                    "Orphan order cancelled: order_id=%s symbol=%s",
                    order.id, order.symbol,
                )
            except Exception as exc:
                logger.error(
                    "Failed to cancel orphan order %s: %s", order.id, exc
                )

    if cancelled_ids:
        logger.warning("Orphan detector cancelled %d orders: %s", len(cancelled_ids), cancelled_ids)
    else:
        logger.info("Orphan detector: no orphaned orders found")

    return cancelled_ids
