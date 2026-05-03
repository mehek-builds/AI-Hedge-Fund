"""FRED macro indicators ingestion → macro_indicators table.

Note: HYG/LQD credit-spread inputs come from price_bars (handled by plan 02-02);
they are *derived* from prices, not pulled from FRED, so they are NOT in this flow.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Optional

from prefect import flow, task, get_run_logger
from prefect.client.schemas.schedules import CronSchedule

from app.config import settings
from app.flows._base import sync_session, upsert_rows
from app.models.macro_indicators import MacroIndicator

# Six FRED series the Phase 4 macro composite scorer needs:
# 1. Yield curve = DGS10 - DGS2 (we store both, derive at query time)
# 2. Sahm Rule current value
# 3. Leading Economic Index proxy (USSLIND — Philly Fed leading index)
# 4. ISM PMI proxy (MANEMP — manufacturing employment is a near-real-time proxy
#    since ISM is licensed; sourced via FRED MANEMP)
# 5. JPY carry: DEXJPUS (yen per USD)
# 6. AUD carry: DEXUSAL (USD per AUD)
FRED_SERIES = {
    "DGS10":        "10-Year Treasury Constant Maturity Rate",
    "DGS2":         "2-Year Treasury Constant Maturity Rate",
    "SAHMCURRENT":  "Sahm Rule Recession Indicator",
    "USSLIND":      "Leading Economic Index proxy (Philly Fed)",
    "MANEMP":       "Manufacturing Employment (ISM PMI proxy)",
    "DEXJPUS":      "Japanese Yen / U.S. Dollar Exchange Rate",
    "DEXUSAL":      "U.S. Dollar / Australian Dollar Exchange Rate",
}


def _build_fred():
    from fredapi import Fred
    return Fred(api_key=settings.FRED_API_KEY)


@task(retries=2, retry_delay_seconds=30)
def fetch_one_series(series_id: str, fred, lookback_days: int) -> list[dict]:
    logger = get_run_logger()
    start = (datetime.utcnow() - timedelta(days=lookback_days)).date().isoformat()
    try:
        latest = fred.get_series(series_id, observation_start=start)
    except Exception as e:
        logger.error(f"FRED fetch failed for {series_id}: {e}")
        return []
    try:
        vintage = fred.get_series_first_release(series_id)
    except Exception:
        vintage = None
    rows: list[dict] = []
    for ts, val in latest.items():
        if val is None or (hasattr(val, "isnan") and val.isnan()):
            continue
        d = ts.date() if hasattr(ts, "date") else ts
        v_date = None
        if vintage is not None and ts in vintage.index:
            v_date = d  # first-release date == observation date for these series
        rows.append({
            "date": d,
            "series_id": series_id,
            "value": float(val),
            "vintage_date": v_date if v_date is not None else d,
            "source": "FRED",
        })
    logger.info(f"{series_id}: {len(rows)} observations to upsert")
    return rows


@flow(name="ingest_macro_daily", retries=2, retry_delay_seconds=60)
def ingest_macro_daily(lookback_days: int = 30, fred_client=None) -> int:
    logger = get_run_logger()
    fred = fred_client if fred_client is not None else _build_fred()
    all_rows: list[dict] = []
    for sid in FRED_SERIES:
        all_rows.extend(fetch_one_series(sid, fred, lookback_days))
    if not all_rows:
        logger.warning("No FRED rows fetched")
        return 0
    with sync_session() as s:
        n = upsert_rows(
            s, MacroIndicator.__table__, all_rows,
            conflict_cols=["date", "series_id"],
            update_cols=["value", "vintage_date", "source"],
        )
    logger.info(f"Upserted {n} macro rows")
    return n


def deploy() -> None:
    """Daily at 13:00 UTC (~9am ET, after FRED morning data drops)."""
    ingest_macro_daily.serve(
        name="ingest-macro-daily",
        schedule=CronSchedule(cron="0 13 * * 1-5", timezone="UTC"),
        tags=["phase-2", "macro"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy()
    else:
        ingest_macro_daily()
