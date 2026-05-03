"""Position monitor Prefect flow — runs every 5 min during market hours.

Checks stop-loss triggers, holding period expiry, and updates unrealized P&L in Redis.
"""

from __future__ import annotations

import os
from datetime import datetime, time as dt_time, timezone

from loguru import logger
from prefect import flow, task

DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://postgres:postgres@db:5432/pead",
)

_MARKET_OPEN = dt_time(9, 30)
_MARKET_CLOSE = dt_time(16, 0)


def _is_market_hours() -> bool:
    import zoneinfo

    try:
        tz = zoneinfo.ZoneInfo("America/New_York")
    except Exception:
        return True
    now_et = datetime.now(tz).time()
    return _MARKET_OPEN <= now_et <= _MARKET_CLOSE


@task(name="load_open_positions_task")
def load_open_positions() -> list[dict]:
    """Fetch all open positions from the DB."""
    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, ticker, direction, entry_ts, entry_price, shares,
                       stop_price, holding_days_target, rl_action_size, gics_sector
                FROM positions
                WHERE status = 'open'
                """
            )
        ).fetchall()
    return [dict(r._mapping) for r in rows]


@task(name="fetch_current_prices_task")
def fetch_current_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch the latest close price for each ticker from Alpaca (or DB fallback)."""
    if not tickers:
        return {}

    prices: dict[str, float] = {}

    try:
        from api.services.alpaca import get_alpaca_client

        alpaca = get_alpaca_client()
        positions = alpaca.get_positions()
        for p in positions:
            sym = p["symbol"].upper()
            if sym in [t.upper() for t in tickers]:
                prices[sym] = float(p["current_price"])
    except Exception as exc:
        logger.warning(f"Alpaca price fetch failed: {exc} — falling back to DB prices")

    # DB fallback for any missing tickers
    missing = [t for t in tickers if t.upper() not in prices]
    if missing:
        from sqlalchemy import create_engine, text

        engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
        with engine.connect() as conn:
            for ticker in missing:
                row = conn.execute(
                    text(
                        "SELECT close FROM prices WHERE ticker = :t ORDER BY time DESC LIMIT 1"
                    ),
                    {"t": ticker},
                ).fetchone()
                if row and row[0]:
                    prices[ticker.upper()] = float(row[0])

    return prices


@task(name="check_stops_and_expiry_task")
def check_stops_and_expiry(
    positions: list[dict],
    prices: dict[str, float],
) -> dict:
    """Identify positions that need to be exited (stop-loss or holding period expiry)."""
    from config import CONFIG

    to_exit: list[dict] = []
    pnl_updates: list[dict] = []

    now = datetime.now(timezone.utc)

    for pos in positions:
        ticker = pos["ticker"].upper()
        current_price = prices.get(ticker)
        if current_price is None:
            continue

        entry_price = float(pos["entry_price"] or 0)
        shares = int(pos["shares"] or 0)
        direction = pos["direction"]

        # Unrealized return
        if entry_price > 0:
            if direction == "long":
                ret = (current_price - entry_price) / entry_price
                unrealized_pnl = (current_price - entry_price) * shares
            else:
                ret = (entry_price - current_price) / entry_price
                unrealized_pnl = (entry_price - current_price) * shares
        else:
            ret = 0.0
            unrealized_pnl = 0.0

        # Days held
        entry_ts = pos["entry_ts"]
        if not isinstance(entry_ts, datetime):
            import pandas as pd
            entry_ts = pd.Timestamp(entry_ts).to_pydatetime()
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.replace(tzinfo=timezone.utc)
        days_held = (now - entry_ts).days

        pnl_updates.append(
            {
                "position_id": str(pos["id"]),
                "ticker": ticker,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "days_held": days_held,
            }
        )

        # Hard stop check
        if ret <= CONFIG.risk.hard_stop_pct:
            logger.warning(
                f"Hard stop triggered for {ticker}: ret={ret:.2%} "
                f"(threshold={CONFIG.risk.hard_stop_pct:.2%})"
            )
            to_exit.append({"position_id": str(pos["id"]), "reason": "stop"})
            continue

        # Holding period expiry
        holding_target = pos.get("holding_days_target") or CONFIG.signal.hold_max
        if days_held >= int(holding_target):
            logger.info(
                f"Holding period expired for {ticker}: {days_held} days "
                f"(target={holding_target})"
            )
            to_exit.append({"position_id": str(pos["id"]), "reason": "expiry"})

    return {"to_exit": to_exit, "pnl_updates": pnl_updates}


@task(name="update_pnl_cache_task")
def update_pnl_cache(pnl_updates: list[dict]) -> None:
    """Write unrealized P&L updates to Redis portfolio snapshot."""
    if not pnl_updates:
        return

    try:
        from api.services.redis_client import get_redis_client

        redis = get_redis_client()
        snapshot = redis.get_portfolio_snapshot() or {}
        snapshot["positions_pnl"] = pnl_updates
        snapshot["updated_at"] = datetime.now(timezone.utc).isoformat()
        redis.set_portfolio_snapshot(snapshot, ttl=300)
        logger.debug(f"Portfolio snapshot updated: {len(pnl_updates)} positions")
    except Exception as exc:
        logger.warning(f"Redis portfolio snapshot update failed: {exc}")


@task(name="trigger_exits_task")
def trigger_exits(to_exit: list[dict]) -> int:
    """Dispatch execute_exit Celery tasks for positions that need to close."""
    if not to_exit:
        return 0

    from worker.tasks.execution import execute_exit

    for item in to_exit:
        execute_exit.delay(position_id=item["position_id"], reason=item["reason"])
        logger.info(f"Exit triggered: position_id={item['position_id']} reason={item['reason']}")

    return len(to_exit)


@flow(
    name="position_monitor_flow",
    description="Checks stops and expiry every 5 min during market hours",
)
def position_monitor_flow() -> None:
    """Monitor open positions, check stops/expiry, and update Redis P&L cache."""
    if not _is_market_hours():
        logger.debug("Outside market hours — skipping position monitor")
        return

    logger.info(f"position_monitor_flow starting at {datetime.now(timezone.utc)}")

    positions = load_open_positions()
    if not positions:
        logger.debug("No open positions to monitor")
        return

    tickers = list({p["ticker"].upper() for p in positions})
    prices = fetch_current_prices(tickers)

    result = check_stops_and_expiry(positions, prices)
    to_exit: list[dict] = result["to_exit"]
    pnl_updates: list[dict] = result["pnl_updates"]

    update_pnl_cache(pnl_updates)
    exits_triggered = trigger_exits(to_exit)

    logger.info(
        f"position_monitor_flow complete: {len(positions)} monitored, "
        f"{exits_triggered} exits triggered"
    )


if __name__ == "__main__":
    position_monitor_flow()
