"""Celery task: compute risk-controlled portfolio size for a signal (FR-4.1..FR-4.6).

Reads a signal from the `signals` table, loads the latest macro snapshot,
runs the position-sizing pipeline, and writes a row to `portfolio_positions`.

Routing: app.tasks.portfolio.* -> queue "portfolio"
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

from app.flows._base import sync_session, upsert_rows
from app.models.portfolio_positions import PortfolioPosition
from app.portfolio.macro_loader import load_latest_macro_components
from app.portfolio.pipeline import compute_position_size
from app.worker import celery_app

log = logging.getLogger(__name__)

# Placeholder yields until Phase 5 wires live E/P and TIPS 10Y feeds.
DEFAULT_EP_YIELD = Decimal("0.045")    # ~4.5% earnings yield proxy
DEFAULT_TIPS_YIELD = Decimal("0.020")  # ~2.0% real TIPS 10Y yield proxy


@celery_app.task(name="app.tasks.portfolio.compute_portfolio_size_task")
def compute_portfolio_size_task(signal_id: str) -> Optional[str]:
    """Read signal -> compute risk-gated position size -> write portfolio_positions row.

    Returns:
        symbol (str) on success.
        None when signal is missing, naive_size is None, or direction is "hold".

    Exceptions from compute_position_size propagate (T-04-14 — not swallowed).
    """
    with sync_session() as session:
        # Step 1: Fetch signal row
        row = session.execute(
            text(
                """
                SELECT symbol, naive_position_size, direction, created_at
                FROM signals
                WHERE signal_id = :sid
                LIMIT 1
                """
            ),
            {"sid": signal_id},
        ).fetchone()

        if row is None:
            log.warning("compute_portfolio_size_task: signal %s not found", signal_id)
            return None

        symbol, naive_size, direction, created_at = row

        if naive_size is None or direction == "hold":
            log.info(
                "compute_portfolio_size_task: signal %s skipped (naive_size=%s, direction=%s)",
                signal_id,
                naive_size,
                direction,
            )
            return None

        # Step 2: Fetch entry price from price_bars (point-in-time)
        price_row = session.execute(
            text(
                """
                SELECT close FROM price_bars
                WHERE symbol = :s
                  AND time <= :asof
                  AND ingestion_timestamp <= :asof
                ORDER BY time DESC
                LIMIT 1
                """
            ),
            {"s": symbol, "asof": created_at},
        ).fetchone()

        if price_row is None or price_row[0] is None:
            log.warning(
                "compute_portfolio_size_task: no price_bars for %s as of %s",
                symbol,
                created_at,
            )
            return None

        entry_price = Decimal(str(price_row[0]))

        # Step 3: Load macro snapshot (FR-1.5 point-in-time)
        macro = load_latest_macro_components(session, created_at)

        # Step 4: Run risk-gated position sizing pipeline
        result = compute_position_size(
            symbol=symbol,
            direction=direction,
            naive_size_nav=Decimal(str(naive_size)),
            entry_price=entry_price,
            macro_components=macro,
            ep_yield=DEFAULT_EP_YIELD,
            real_tips_yield=DEFAULT_TIPS_YIELD,
        )

        # Step 5: Write portfolio_positions row (idempotent upsert)
        now = datetime.now(timezone.utc)
        upsert_rows(
            session,
            PortfolioPosition.__table__,
            [
                {
                    "snapshot_at": now,
                    "symbol": symbol,
                    "qty": None,                   # quantity computed downstream from NAV
                    "avg_entry_price": entry_price,
                    "current_price": entry_price,
                    "unrealized_pnl": Decimal("0"),
                    "stop_loss_price": result.stop_loss_price,
                    "take_profit_price": None,
                    "status": "sized",
                }
            ],
            conflict_cols=["snapshot_at", "symbol"],
            update_cols=[
                "qty",
                "avg_entry_price",
                "current_price",
                "unrealized_pnl",
                "stop_loss_price",
                "take_profit_price",
                "status",
            ],
        )

        log.info(
            "compute_portfolio_size_task: %s sized to %.6f NAV (macro_score=%d, stop=%.4f)",
            symbol,
            result.final_size_nav,
            result.macro_score,
            result.stop_loss_price,
        )
        return symbol
