"""Reconcile portfolio_positions DB table with Alpaca live positions.

Called on service startup (via lifespan) and every 15 minutes (via Celery beat).
Append-only: inserts new snapshot rows into the portfolio_positions hypertable.
"Latest position" is always MAX(snapshot_at) per symbol.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.execution.broker import get_trading_client

logger = logging.getLogger(__name__)


def reconcile_positions_with_alpaca(session: Session) -> int:
    """Fetch live Alpaca positions and reconcile with DB.

    For each Alpaca position, reads the latest DB snapshot for that symbol.
    If qty differs, inserts a new PortfolioPosition snapshot row.
    Returns the count of discrepancies resolved.
    """
    client = get_trading_client()
    alpaca_positions = client.get_all_positions()

    discrepancy_count = 0
    now = datetime.now(timezone.utc)

    for pos in alpaca_positions:
        symbol = pos.symbol
        alpaca_qty = Decimal(str(pos.qty))

        # Read latest DB snapshot for this symbol
        row = session.execute(
            text("""
                SELECT qty
                FROM portfolio_positions
                WHERE symbol = :symbol
                ORDER BY snapshot_at DESC
                LIMIT 1
            """),
            {"symbol": symbol},
        ).fetchone()

        db_qty = Decimal(str(row[0])) if row and row[0] is not None else None

        if db_qty is None or db_qty != alpaca_qty:
            # Insert new snapshot (hypertable append semantics - never UPDATE)
            session.execute(
                text("""
                    INSERT INTO portfolio_positions
                        (snapshot_at, symbol, qty, avg_entry_price, current_price,
                         unrealized_pnl, status, ingestion_timestamp)
                    VALUES
                        (:snapshot_at, :symbol, :qty, :avg_entry_price,
                         :current_price, :unrealized_pnl, :status, :ingestion_timestamp)
                """),
                {
                    "snapshot_at": now,
                    "symbol": symbol,
                    "qty": float(alpaca_qty),
                    "avg_entry_price": float(pos.avg_entry_price) if pos.avg_entry_price else None,
                    "current_price": float(pos.current_price) if pos.current_price else None,
                    "unrealized_pnl": float(pos.unrealized_pl) if pos.unrealized_pl else None,
                    "status": "open",
                    "ingestion_timestamp": now,
                },
            )
            logger.info(
                "Position discrepancy resolved: %s db_qty=%s alpaca_qty=%s",
                symbol, db_qty, alpaca_qty,
            )
            discrepancy_count += 1

    logger.info(
        "Position reconciliation complete: %d discrepancies", discrepancy_count
    )
    return discrepancy_count
