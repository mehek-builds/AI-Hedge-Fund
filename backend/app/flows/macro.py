"""FRED macro indicators ingestion → macro_indicators table.

Note: HYG/LQD credit-spread inputs come from price_bars (handled by plan 02-02);
they are *derived* from prices, not pulled from FRED, so they are NOT in this flow.
"""
from __future__ import annotations
from datetime import datetime, timedelta

from prefect import flow, task, get_run_logger
from prefect.client.schemas.schedules import CronSchedule

from app.config import settings
from app.flows._base import sync_session, upsert_rows
from app.models.macro_indicators import MacroIndicator

# Series IDs that map to the 6 macro composite components (FR-4.1).
# Used after ingestion to compute and persist composite_score (gap SC-1b).
_COMPOSITE_SERIES = {
    "T10Y2Y":       "yield_curve",
    "SAHMREALTIME": "sahm",
    "USALOLITONOSM": "lei",
    "MANEMP":       "ism_pmi",
    "HYG_LQD_SPREAD": "hyg_lqd_spread",
    "JPY_AUD_CARRY":  "jpy_aud_carry",
}

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


def _run_macro(lookback_days: int = 30, fred_client=None) -> int:
    """Core macro ingestion logic — plain function, callable without Prefect runtime.

    Same pattern as prices._run_ingestion: extracted so integration tests can
    call this directly, bypassing the Prefect ephemeral server requirement.
    """
    try:
        logger = get_run_logger()
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
    fred = fred_client if fred_client is not None else _build_fred()
    all_rows: list[dict] = []
    for sid in FRED_SERIES:
        # Call the FRED series fetch directly (bypasses @task Prefect wrapper)
        start = (datetime.utcnow() - timedelta(days=lookback_days)).date().isoformat()
        try:
            latest = fred.get_series(sid, observation_start=start)
        except Exception as e:
            logger.error(f"FRED fetch failed for {sid}: {e}")
            continue
        try:
            vintage = fred.get_series_first_release(sid)
        except Exception:
            vintage = None
        for ts, val in latest.items():
            if val is None or (hasattr(val, "isnan") and val.isnan()):
                continue
            d = ts.date() if hasattr(ts, "date") else ts
            v_date = None
            if vintage is not None and ts in vintage.index:
                v_date = d
            all_rows.append({
                "date": d,
                "series_id": sid,
                "value": float(val),
                "vintage_date": v_date if v_date is not None else d,
                "source": "FRED",
            })
    if not all_rows:
        logger.warning("No FRED rows fetched")
        return 0

    # Compute composite_score + score_components per date and attach to rows
    # (gap SC-1b): the RL state builder reads the persisted score from DB so
    # sizing decisions are replayable even if the algorithm changes later.
    _attach_composite_scores(all_rows, logger)

    with sync_session() as s:
        n = upsert_rows(
            s, MacroIndicator.__table__, all_rows,
            conflict_cols=["date", "series_id"],
            update_cols=["value", "vintage_date", "source", "composite_score", "score_components"],
        )
    logger.info(f"Upserted {n} macro rows")
    return n


def _attach_composite_scores(rows: list[dict], logger) -> None:
    """Compute composite_score + score_components per date and stamp each row.

    Groups rows by date, collects values for the 6 composite series, runs the
    scorer, then writes composite_score (int) and score_components (dict) back
    onto every row for that date. Rows for non-composite series get NULL.

    Called inline inside _run_macro so the score is co-committed with the raw
    readings in the same upsert — same ingestion_timestamp, same date.
    """
    from decimal import Decimal
    from app.portfolio.macro import score_component

    # Group values by date → {series_id: value}
    date_series: dict = {}
    for row in rows:
        d = row["date"]
        if d not in date_series:
            date_series[d] = {}
        date_series[d][row["series_id"]] = row.get("value")

    # Compute score per date
    date_scores: dict = {}
    for d, series_vals in date_series.items():
        components: dict[str, int] = {}
        for series_id, comp_name in _COMPOSITE_SERIES.items():
            raw = series_vals.get(series_id)
            val = Decimal(str(raw)) if raw is not None else None
            components[comp_name] = score_component(comp_name, val)
        # Only stamp if we have at least one of the 6 components
        if any(sid in series_vals for sid in _COMPOSITE_SERIES):
            composite = max(-6, min(0, sum(components.values())))
            date_scores[d] = (composite, components)
            logger.debug(f"macro composite {d}: {composite} {components}")

    # Stamp each row — only rows whose series_id feeds the composite carry the score
    for row in rows:
        d = row["date"]
        if d in date_scores and row["series_id"] in _COMPOSITE_SERIES:
            row["composite_score"] = date_scores[d][0]
            row["score_components"] = date_scores[d][1]
        else:
            row.setdefault("composite_score", None)
            row.setdefault("score_components", None)


@flow(name="ingest_macro_daily", retries=2, retry_delay_seconds=60)
def ingest_macro_daily(lookback_days: int = 30, fred_client=None) -> int:
    return _run_macro(lookback_days=lookback_days, fred_client=fred_client)


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
