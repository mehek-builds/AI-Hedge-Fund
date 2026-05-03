"""Daily market data Prefect flow — runs at 8:30 AM ET.

Chain: ingest_prices → ingest_macro → ingest_ff5_factors → compute_macro_regime (Redis cache update)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from loguru import logger
from prefect import flow, task

from worker.tasks.ingest import ingest_ff5_factors, ingest_macro, ingest_prices

# Default universe of S&P 500 representative tickers — expand as needed
DEFAULT_TICKERS = os.environ.get(
    "UNIVERSE_TICKERS",
    "AAPL,MSFT,AMZN,GOOGL,META,NVDA,TSLA,JPM,JNJ,V,PG,HD,MA,UNH,BAC,XOM,ABBV,LLY,AVGO,COST",
).split(",")


@task(name="ingest_prices_task", retries=2, retry_delay_seconds=60)
def run_ingest_prices(tickers: list[str]) -> dict:
    result = ingest_prices.apply_async(args=[tickers]).get(timeout=300)
    logger.info(f"ingest_prices result: {result}")
    return result


@task(name="ingest_macro_task", retries=2, retry_delay_seconds=120)
def run_ingest_macro() -> dict:
    result = ingest_macro.apply_async().get(timeout=300)
    logger.info(f"ingest_macro result: {result}")
    return result


@task(name="ingest_ff5_factors_task", retries=2, retry_delay_seconds=120)
def run_ingest_ff5_factors() -> dict:
    result = ingest_ff5_factors.apply_async().get(timeout=300)
    logger.info(f"ingest_ff5_factors result: {result}")
    return result


@task(name="compute_macro_regime_task")
def compute_macro_regime_cache() -> dict:
    """Read latest macro_state from DB and push to Redis cache."""
    import os
    from sqlalchemy import create_engine, text

    DATABASE_URL_SYNC = os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql+psycopg2://postgres:postgres@db:5432/pead",
    )
    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT time, composite_score, size_multiplier, is_halted,
                       t10y2y, core_pce_yoy, gdp_qoq_ann, hy_oas, vix, sahm_rule, carry_crash_flag
                FROM macro_state
                ORDER BY time DESC LIMIT 1
                """
            )
        ).fetchone()

    if row is None:
        logger.warning("No macro_state rows — skipping cache update")
        return {"status": "no_data"}

    r = dict(row._mapping)
    regime_data = {
        "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
        "composite_score": int(r.get("composite_score") or 0),
        "size_multiplier": float(r.get("size_multiplier") or 1.0),
        "is_halted": bool(r.get("is_halted", False)),
        "components": {
            "t10y2y": float(r["t10y2y"]) if r.get("t10y2y") is not None else None,
            "core_pce_yoy": float(r["core_pce_yoy"]) if r.get("core_pce_yoy") is not None else None,
            "gdp_qoq_ann": float(r["gdp_qoq_ann"]) if r.get("gdp_qoq_ann") is not None else None,
            "hy_oas": float(r["hy_oas"]) if r.get("hy_oas") is not None else None,
            "vix": float(r["vix"]) if r.get("vix") is not None else None,
            "sahm_rule": float(r["sahm_rule"]) if r.get("sahm_rule") is not None else None,
            "carry_crash_flag": bool(r.get("carry_crash_flag", False)),
        },
    }

    from api.services.redis_client import get_redis_client
    redis = get_redis_client()
    redis.set_macro_regime(regime_data, ttl=3600)

    logger.info(
        f"Macro regime cached: score={regime_data['composite_score']} "
        f"halted={regime_data['is_halted']}"
    )
    return {"status": "ok", "regime": regime_data}


@task(name="compute_erp_gv_task")
def compute_erp_gv() -> dict:
    """
    Compute ERP (earnings yield − TIPS 10Y) and Growth/Value spread (VUG/VTV P/E).
    Writes results into the latest macro_state row.
    """
    import os
    from sqlalchemy import create_engine, text

    DATABASE_URL_SYNC = os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql+psycopg2://postgres:postgres@db:5432/pead",
    )
    engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)

    # Fetch ERP inputs from macro_state (earnings_yield / real_10y_yield may already be stored)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT time, earnings_yield, real_10y_yield, vug_pe, vtv_pe FROM macro_state ORDER BY time DESC LIMIT 1")
        ).fetchone()

    if row is None:
        return {"status": "no_macro_state"}

    r = dict(row._mapping)
    ts = r["time"]

    # Attempt to pull fresh FRED data for TIPS 10Y (DFII10) and SP500 E/P
    earnings_yield = r.get("earnings_yield")
    real_10y_yield = r.get("real_10y_yield")
    vug_pe = r.get("vug_pe")
    vtv_pe = r.get("vtv_pe")

    try:
        import fredapi
        import os as _os
        fred = fredapi.Fred(api_key=_os.environ.get("FRED_API_KEY", ""))
        tips = fred.get_series_latest_release("DFII10")
        if not tips.empty:
            real_10y_yield = float(tips.iloc[-1]) / 100.0
    except Exception as exc:
        logger.warning(f"FRED TIPS fetch failed: {exc}")

    # Derive ERP
    erp_spread = None
    erp_compressed = False
    if earnings_yield is not None and real_10y_yield is not None:
        erp_spread = float(earnings_yield) - float(real_10y_yield)
        erp_compressed = erp_spread < 0

    # GV ratio
    gv_ratio = None
    gv_stretched = False
    if vug_pe and vtv_pe and float(vtv_pe) > 0:
        gv_ratio = float(vug_pe) / float(vtv_pe)
        gv_stretched = gv_ratio > 2.0

    from portfolio.architecture import ERPMonitor, GrowthValueMonitor
    if earnings_yield is not None and real_10y_yield is not None:
        erp_state = ERPMonitor().compute(float(earnings_yield), float(real_10y_yield))
        erp_spread = erp_state.erp_spread
        erp_compressed = erp_state.erp_compressed

    if vug_pe and vtv_pe:
        gv_state = GrowthValueMonitor().compute(float(vug_pe), float(vtv_pe))
        gv_ratio = gv_state.ratio
        gv_stretched = gv_state.stretched

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE macro_state SET
                    real_10y_yield = COALESCE(:real_10y_yield, real_10y_yield),
                    erp_spread     = :erp_spread,
                    erp_compressed = :erp_compressed,
                    gv_ratio       = :gv_ratio,
                    gv_stretched   = :gv_stretched
                WHERE time = :ts
                """
            ),
            {
                "real_10y_yield": real_10y_yield,
                "erp_spread": erp_spread,
                "erp_compressed": erp_compressed,
                "gv_ratio": gv_ratio,
                "gv_stretched": gv_stretched,
                "ts": ts,
            },
        )

    logger.info(
        f"ERP/GV updated: erp_spread={erp_spread} compressed={erp_compressed} "
        f"gv_ratio={gv_ratio} stretched={gv_stretched}"
    )
    return {
        "status": "ok",
        "erp_spread": erp_spread,
        "erp_compressed": erp_compressed,
        "gv_ratio": gv_ratio,
        "gv_stretched": gv_stretched,
    }


@flow(
    name="daily_market_flow",
    description="Daily data ingestion pipeline — runs at 8:30 AM ET",
)
def daily_market_flow(tickers: list[str] | None = None) -> None:
    """Orchestrate daily market data ingestion in sequence."""
    universe = tickers or DEFAULT_TICKERS
    logger.info(f"Starting daily_market_flow for {len(universe)} tickers at {datetime.now(timezone.utc)}")

    prices_result = run_ingest_prices(universe)
    macro_result = run_ingest_macro()
    ff5_result = run_ingest_ff5_factors()
    regime_result = compute_macro_regime_cache()
    erp_gv_result = compute_erp_gv()

    logger.info(
        f"daily_market_flow complete: "
        f"prices={prices_result.get('rows', 0)} rows, "
        f"macro={macro_result.get('rows', 0)} rows, "
        f"ff5={ff5_result.get('rows', 0)} rows, "
        f"regime={regime_result.get('status')}, "
        f"erp_gv={erp_gv_result.get('status')}"
    )


if __name__ == "__main__":
    daily_market_flow()
