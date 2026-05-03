"""Derived macro indicators computed from price_bars.

HYG_LQD_SPREAD = LQD_close / HYG_close   (a credit-spread proxy used by the
Phase 4 macro composite). We compute it daily right after price ingestion.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from prefect import flow, get_run_logger
from prefect.client.schemas.schedules import CronSchedule
from sqlalchemy import select

from app.flows._base import sync_session, upsert_rows
from app.models.price_bars import PriceBar
from app.models.macro_indicators import MacroIndicator


def _run_derived_macro(lookback_days: int = 7) -> int:
    """Core HYG/LQD spread computation — plain function, callable without Prefect runtime.

    Same pattern as prices._run_ingestion: extracted so integration tests can
    call this directly, bypassing the Prefect ephemeral server requirement.
    """
    try:
        logger = get_run_logger()
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    rows: list[dict] = []
    with sync_session() as s:
        hyg = {b.time.date(): b.close for b in s.execute(
            select(PriceBar).where(PriceBar.symbol == "HYG").where(PriceBar.time >= cutoff)
        ).scalars().all()}
        lqd = {b.time.date(): b.close for b in s.execute(
            select(PriceBar).where(PriceBar.symbol == "LQD").where(PriceBar.time >= cutoff)
        ).scalars().all()}
        common_dates = sorted(set(hyg) & set(lqd))
        if not common_dates:
            logger.warning("No overlapping HYG/LQD bars to compute spread")
            return 0
        for d in common_dates:
            h = hyg[d]
            l = lqd[d]
            if not h or not l or Decimal(str(h)) == 0:
                continue
            rows.append({
                "date": d,
                "series_id": "HYG_LQD_SPREAD",
                "value": float(Decimal(str(l)) / Decimal(str(h))),
                "vintage_date": d,
                "source": "DERIVED:price_bars",
            })
        if not rows:
            return 0
        n = upsert_rows(
            s, MacroIndicator.__table__, rows,
            conflict_cols=["date", "series_id"],
            update_cols=["value", "vintage_date", "source"],
        )
    logger.info(f"Wrote {n} HYG_LQD_SPREAD rows")
    return n


@flow(name="compute_hyg_lqd_daily", retries=2, retry_delay_seconds=30)
def compute_hyg_lqd_daily(lookback_days: int = 7) -> int:
    return _run_derived_macro(lookback_days=lookback_days)


def deploy() -> None:
    """Daily at 22:30 UTC — 30 min after ingest-prices-daily."""
    compute_hyg_lqd_daily.serve(
        name="compute-hyg-lqd-daily",
        schedule=CronSchedule(cron="30 22 * * 1-5", timezone="UTC"),
        tags=["phase-2", "derived"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy()
    else:
        compute_hyg_lqd_daily()
