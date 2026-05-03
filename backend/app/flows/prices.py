"""Daily OHLCV ingestion from Alpaca → price_bars."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from prefect import flow, task, get_run_logger

from app.config import settings
from app.flows._base import sync_session, upsert_rows
from app.flows._universe import current_sp500_universe
from app.models.price_bars import PriceBar

BATCH_SIZE = 200  # alpaca-py accepts ~200 symbols per request

logger = logging.getLogger(__name__)


def _build_client():
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY)


def _fetch_batch(client, symbols: list[str], start: datetime, end: datetime):
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )
    return client.get_stock_bars(req)


def _process_batch(symbols: list[str], start: datetime, end: datetime, client) -> int:
    """Core batch-fetch-and-upsert logic. Pure function, testable without Prefect runtime."""
    try:
        log = get_run_logger()
    except Exception:
        log = logger

    resp = _fetch_batch(client, symbols, start, end)
    data = getattr(resp, "data", {}) or {}
    rows: list[dict] = []
    for sym, bars in data.items():
        if not bars:
            log.warning(f"No bars returned for {sym}")
            continue
        for b in bars:
            rows.append({
                "time": b.timestamp,
                "symbol": sym,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "vwap": getattr(b, "vwap", None),
                "volume": b.volume,
            })
    if not rows:
        return 0
    with sync_session() as s:
        n = upsert_rows(
            s, PriceBar.__table__, rows,
            conflict_cols=["time", "symbol"],
            update_cols=["open", "high", "low", "close", "vwap", "volume"],
        )
    log.info(f"Upserted {n} price bars for batch starting {symbols[0]}")
    return n


@task(retries=2, retry_delay_seconds=30)
def fetch_and_upsert_batch(symbols: list[str], start: datetime, end: datetime, client) -> int:
    """Prefect task wrapper around _process_batch for use in scheduled flows."""
    return _process_batch(symbols, start, end, client)


def _run_ingestion(lookback_days: int = 5, test_client=None) -> int:
    """Core ingestion logic — called by the Prefect flow and directly in tests."""
    try:
        log = get_run_logger()
    except Exception:
        log = logger

    client = test_client if test_client is not None else _build_client()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    universe = current_sp500_universe()
    log.info(
        f"Ingesting prices for {len(universe)} symbols, "
        f"window {start.date()}..{end.date()}"
    )
    total = 0
    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i : i + BATCH_SIZE]
        total += _process_batch(batch, start, end, client)
    log.info(f"Total bars upserted: {total}")
    return total


@flow(name="ingest_prices_daily", retries=2, retry_delay_seconds=60)
def ingest_prices_daily(lookback_days: int = 5, test_client=None) -> int:
    """Fetch last `lookback_days` of daily OHLCV for current S&P 500 and upsert.

    `test_client` is for dependency injection in tests; production passes None
    and a real Alpaca client is built from settings.
    """
    return _run_ingestion(lookback_days=lookback_days, test_client=test_client)


def deploy() -> None:
    """Register/update the daily-prices deployment on the Prefect server.

    Cron: '0 22 * * 1-5' (UTC) — every weekday at 22:00 UTC,
    ~30 min after the US equity close (16:00 ET = 21:00 UTC in DST).
    """
    from prefect.client.schemas.schedules import CronSchedule
    ingest_prices_daily.serve(
        name="ingest-prices-daily",
        schedule=CronSchedule(cron="0 22 * * 1-5", timezone="UTC"),
        tags=["phase-2", "prices"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy()
    else:
        ingest_prices_daily()
