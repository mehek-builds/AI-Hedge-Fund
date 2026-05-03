"""FMP earnings ingestion → earnings_events table.

For each S&P 500 symbol:
  1. GET /income-statement?period=quarter&limit=8  (last 2 years = 8 quarters)
  2. GET /earnings-surprises  (for actual+estimate EPS pairing)
  3. Merge by quarter end date → upsert one earnings_events row per (symbol, quarter)
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

import httpx
from prefect import flow, task, get_run_logger
from prefect.client.schemas.schedules import CronSchedule

from app.config import settings
from app.flows._base import sync_session, upsert_rows
from app.flows._universe import current_sp500_universe
from app.models.earnings_events import EarningsEvent

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _http_get(path: str, params: Optional[dict] = None) -> list:
    params = dict(params or {})
    params["apikey"] = settings.FMP_API_KEY
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{FMP_BASE}{path}", params=params)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []


def _to_quarter_label(period: str | None, calendar_year: int | str | None) -> str | None:
    """Build 'YYYYQn' label, e.g. '2026Q1'. Returns None if missing fields."""
    if not period or calendar_year is None:
        return None
    p = str(period).upper()
    if p not in {"Q1", "Q2", "Q3", "Q4"}:
        return None
    return f"{calendar_year}{p}"


def _parse_fmp_response(income: list[dict], surprises: list[dict], symbol: str) -> list[dict]:
    # Index surprises by date string for actual+estimate EPS lookup
    sur_by_date: dict[str, dict] = {s.get("date"): s for s in surprises if s.get("date")}
    rows: list[dict] = []
    for stmt in income:
        q_date = stmt.get("date")
        if not q_date:
            continue
        announced_at = datetime.fromisoformat(q_date).replace(tzinfo=timezone.utc)
        fq = _to_quarter_label(stmt.get("period"), stmt.get("calendarYear"))
        if fq is None:
            continue
        sur = sur_by_date.get(q_date, {})
        rows.append({
            "symbol": symbol,
            "announced_at": announced_at,
            "fiscal_quarter": fq,
            "eps_actual": sur.get("actualEarningResult") or stmt.get("eps"),
            "eps_estimate": sur.get("estimatedEarning"),
            "revenue_actual": stmt.get("revenue"),
            "revenue_estimate": None,  # FMP income-statement doesn't carry revenue estimate
            "operating_income": stmt.get("operatingIncome"),
            "share_count": stmt.get("weightedAverageShsOut"),
            # Phase 2 stores 'none'; future plan enriches from transcripts
            "guidance_direction": "none",
            "source": "FMP",
        })
    return rows


@task(retries=2, retry_delay_seconds=15)
def ingest_one_symbol(symbol: str, http_get: Callable, limit: int) -> int:
    logger = get_run_logger()
    try:
        income = http_get(f"/income-statement/{symbol}", {"period": "quarter", "limit": limit})
        surprises = http_get(f"/earnings-surprises/{symbol}", None)
    except Exception as e:
        logger.error(f"FMP fetch failed for {symbol}: {e}")
        return 0
    rows = _parse_fmp_response(income or [], surprises or [], symbol)
    if not rows:
        return 0
    with sync_session() as s:
        n = upsert_rows(
            s, EarningsEvent.__table__, rows,
            conflict_cols=["symbol", "fiscal_quarter"],
            update_cols=[
                "announced_at", "eps_actual", "eps_estimate",
                "revenue_actual", "revenue_estimate",
                "operating_income", "share_count",
                "guidance_direction", "source",
            ],
        )
    return n


def _run_earnings(quarters: int = 8, http_override: Optional[Callable] = None) -> int:
    """Core earnings ingestion logic — plain function, callable without Prefect runtime.

    Same pattern as prices._run_ingestion: extracted so integration tests can
    call this directly, bypassing the Prefect ephemeral server requirement.
    """
    try:
        logger = get_run_logger()
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
    getter = http_override if http_override is not None else _http_get
    universe = current_sp500_universe()
    total = 0
    for sym in universe:
        try:
            income = getter(f"/income-statement/{sym}", {"period": "quarter", "limit": quarters})
            surprises = getter(f"/earnings-surprises/{sym}", None)
        except Exception as e:
            logger.error(f"FMP fetch failed for {sym}: {e}")
            continue
        rows = _parse_fmp_response(income or [], surprises or [], sym)
        if not rows:
            continue
        with sync_session() as s:
            n = upsert_rows(
                s, EarningsEvent.__table__, rows,
                conflict_cols=["symbol", "fiscal_quarter"],
                update_cols=[
                    "announced_at", "eps_actual", "eps_estimate",
                    "revenue_actual", "revenue_estimate",
                    "operating_income", "share_count",
                    "guidance_direction", "source",
                ],
            )
            total += n
    logger.info(f"Earnings: {total} rows across {len(universe)} symbols")
    return total


@flow(name="ingest_earnings_daily", retries=2, retry_delay_seconds=60)
def ingest_earnings_daily(quarters: int = 8, http_override: Optional[Callable] = None) -> int:
    """Fetch last `quarters` quarters of earnings for each S&P 500 symbol."""
    return _run_earnings(quarters=quarters, http_override=http_override)


def deploy() -> None:
    """Daily at 23:30 UTC — after most US after-hours earnings releases."""
    ingest_earnings_daily.serve(
        name="ingest-earnings-daily",
        schedule=CronSchedule(cron="30 23 * * 1-5", timezone="UTC"),
        tags=["phase-2", "earnings"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy()
    else:
        ingest_earnings_daily()
