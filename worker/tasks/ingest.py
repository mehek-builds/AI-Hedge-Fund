"""Ingestion Celery tasks — prices, macro, FF5 factors, earnings calendar."""

from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from worker.celery_app import celery_app

DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://postgres:postgres@db:5432/pead",
)
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.environ.get("ALPACA_BASE_URL", "paper")

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
    return _engine


# ---------------------------------------------------------------------------
# ingest_prices
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.ingest.ingest_prices", bind=True, max_retries=3)
def ingest_prices(self, tickers: list[str]) -> dict:
    """Fetch daily OHLCV bars from Alpaca and upsert into the prices table."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    paper = "paper" in ALPACA_BASE_URL.lower()
    client = StockHistoricalDataClient(api_key=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=5)  # fetch last 5 trading days on each run

    try:
        request = StockBarsRequest(
            symbol_or_symbols=tickers,
            start=start,
            end=end,
            timeframe=TimeFrame.Day,
        )
        bars = client.get_stock_bars(request)
        df = bars.df
    except Exception as exc:
        logger.error(f"Alpaca bars fetch failed: {exc}")
        raise self.retry(exc=exc, countdown=60)

    if df.empty:
        logger.warning("No bars returned for tickers: %s", tickers)
        return {"status": "no_data", "tickers": tickers}

    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()
        df = df.rename(columns={"symbol": "ticker", "timestamp": "time"})
    else:
        df = df.reset_index().rename(columns={"timestamp": "time"})

    records = df[["ticker", "time", "open", "high", "low", "close", "volume"]].to_dict("records")

    engine = _get_engine()
    with engine.begin() as conn:
        for rec in records:
            stmt = text(
                """
                INSERT INTO prices (ticker, time, open, high, low, close, volume)
                VALUES (:ticker, :time, :open, :high, :low, :close, :volume)
                ON CONFLICT (ticker, time) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low  = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
                """
            )
            conn.execute(stmt, rec)

    logger.info(f"Upserted {len(records)} price rows for {len(tickers)} tickers")
    return {"status": "ok", "rows": len(records)}


# ---------------------------------------------------------------------------
# ingest_macro
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.ingest.ingest_macro", bind=True, max_retries=3)
def ingest_macro(self) -> dict:
    """Fetch all FRED macro series and upsert into macro_state."""
    try:
        from fredapi import Fred
    except ImportError as exc:
        raise RuntimeError("fredapi not installed") from exc

    fred = Fred(api_key=FRED_API_KEY)

    series_map = {
        "T10Y2Y": "t10y2y",
        "PCEPILFE": "core_pce_yoy",
        "GDPC1": "gdp_qoq_ann",
        "BAMLH0A0HYM2": "hy_oas",
        "SAHMREALTIME": "sahm_rule",
    }

    try:
        data: dict[str, pd.Series] = {}
        for fred_id, col in series_map.items():
            try:
                data[col] = fred.get_series(fred_id)
            except Exception as exc:
                logger.warning(f"FRED fetch failed for {fred_id}: {exc}")
                data[col] = pd.Series(dtype=float)

        # VIX via yfinance
        try:
            import yfinance as yf
            vix_df = yf.download("^VIX", period="5d", progress=False)
            vix_series = vix_df["Close"].squeeze()
        except Exception as exc:
            logger.warning(f"VIX fetch failed: {exc}")
            vix_series = pd.Series(dtype=float)

        # Carry crash: AUD/JPY proxy
        try:
            jpy = fred.get_series("DEXJPUS")
            aud = fred.get_series("DEXUSAL")
            aud_jpy = aud / (1.0 / jpy.reindex(aud.index, method="ffill"))
            carry_return = aud_jpy.pct_change(20)
            carry_crash = (carry_return < -0.05).astype(float)
        except Exception as exc:
            logger.warning(f"Carry crash calc failed: {exc}")
            carry_crash = pd.Series(dtype=float)

    except Exception as exc:
        logger.error(f"Macro ingest failed: {exc}")
        raise self.retry(exc=exc, countdown=120)

    # Build a combined daily DataFrame
    bdays = pd.date_range(
        start=(datetime.now(timezone.utc) - timedelta(days=10)).date(),
        end=datetime.now(timezone.utc).date(),
        freq="B",
    )
    df = pd.DataFrame(index=bdays)
    for col, series in data.items():
        if not series.empty:
            df[col] = series.reindex(bdays, method="ffill")
        else:
            df[col] = None

    if not vix_series.empty:
        df["vix"] = vix_series.reindex(bdays, method="ffill")
    else:
        df["vix"] = None

    if not carry_crash.empty:
        df["carry_crash_flag"] = carry_crash.reindex(bdays, method="ffill").fillna(0).astype(bool)
    else:
        df["carry_crash_flag"] = False

    # Compute composite score
    from config import CONFIG
    cfg = CONFIG.macro
    component_cols = []
    if "t10y2y" in df.columns and df["t10y2y"].notna().any():
        df["s_yield"] = (df["t10y2y"] < cfg.yield_spread_threshold).astype(int) * -1
        component_cols.append("s_yield")
    if "core_pce_yoy" in df.columns and df["core_pce_yoy"].notna().any():
        df["s_pce"] = (df["core_pce_yoy"] > cfg.core_pce_threshold).astype(int) * -1
        component_cols.append("s_pce")
    if "gdp_qoq_ann" in df.columns and df["gdp_qoq_ann"].notna().any():
        df["s_gdp"] = (df["gdp_qoq_ann"] < cfg.real_gdp_threshold).astype(int) * -1
        component_cols.append("s_gdp")
    if "hy_oas" in df.columns and df["hy_oas"].notna().any():
        df["s_hy"] = (df["hy_oas"] > cfg.hy_spread_threshold).astype(int) * -1
        component_cols.append("s_hy")
    if "vix" in df.columns and df["vix"].notna().any():
        df["s_vix"] = (df["vix"] > cfg.vix_threshold).astype(int) * -1
        component_cols.append("s_vix")
    if "sahm_rule" in df.columns and df["sahm_rule"].notna().any():
        df["s_sahm"] = (df["sahm_rule"] >= cfg.sahm_threshold).astype(int) * -1
        component_cols.append("s_sahm")
    if "carry_crash_flag" in df.columns:
        df["s_carry"] = df["carry_crash_flag"].astype(int) * -1
        component_cols.append("s_carry")

    if component_cols:
        df["composite_score"] = df[component_cols].sum(axis=1).astype(int)
    else:
        df["composite_score"] = 0

    df["size_multiplier"] = df["composite_score"].map(
        lambda s: cfg.sizing_multipliers.get(s, 0.0) if s >= cfg.halt_threshold else 0.0
    )
    df["is_halted"] = df["composite_score"] <= cfg.halt_threshold

    df = df.reset_index().rename(columns={"index": "time"})
    df = df.dropna(subset=["composite_score"])

    engine = _get_engine()
    rows_upserted = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            rec = {
                "time": row["time"].to_pydatetime() if hasattr(row["time"], "to_pydatetime") else row["time"],
                "t10y2y": _safe_float(row.get("t10y2y")),
                "core_pce_yoy": _safe_float(row.get("core_pce_yoy")),
                "gdp_qoq_ann": _safe_float(row.get("gdp_qoq_ann")),
                "hy_oas": _safe_float(row.get("hy_oas")),
                "vix": _safe_float(row.get("vix")),
                "sahm_rule": _safe_float(row.get("sahm_rule")),
                "carry_crash_flag": bool(row.get("carry_crash_flag", False)),
                "composite_score": int(row.get("composite_score", 0)),
                "size_multiplier": _safe_float(row.get("size_multiplier", 1.0)),
                "is_halted": bool(row.get("is_halted", False)),
            }
            conn.execute(
                text(
                    """
                    INSERT INTO macro_state (time, t10y2y, core_pce_yoy, gdp_qoq_ann, hy_oas, vix,
                        sahm_rule, carry_crash_flag, composite_score, size_multiplier, is_halted)
                    VALUES (:time, :t10y2y, :core_pce_yoy, :gdp_qoq_ann, :hy_oas, :vix,
                        :sahm_rule, :carry_crash_flag, :composite_score, :size_multiplier, :is_halted)
                    ON CONFLICT (time) DO UPDATE SET
                        t10y2y = EXCLUDED.t10y2y,
                        core_pce_yoy = EXCLUDED.core_pce_yoy,
                        gdp_qoq_ann = EXCLUDED.gdp_qoq_ann,
                        hy_oas = EXCLUDED.hy_oas,
                        vix = EXCLUDED.vix,
                        sahm_rule = EXCLUDED.sahm_rule,
                        carry_crash_flag = EXCLUDED.carry_crash_flag,
                        composite_score = EXCLUDED.composite_score,
                        size_multiplier = EXCLUDED.size_multiplier,
                        is_halted = EXCLUDED.is_halted
                    """
                ),
                rec,
            )
            rows_upserted += 1

    logger.info(f"Macro ingest complete: {rows_upserted} rows upserted")
    return {"status": "ok", "rows": rows_upserted}


# ---------------------------------------------------------------------------
# ingest_ff5_factors
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.ingest.ingest_ff5_factors", bind=True, max_retries=3)
def ingest_ff5_factors(self) -> dict:
    """Download Ken French FF5 daily CSV and upsert into ff5_factors."""
    french_url = (
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
        "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
    )
    try:
        resp = requests.get(french_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:
        logger.error(f"Ken French download failed: {exc}")
        raise self.retry(exc=exc, countdown=300)

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            with zf.open(csv_name) as f:
                raw = f.read().decode("latin-1")
    except Exception as exc:
        logger.error(f"Ken French ZIP parsing failed: {exc}")
        raise

    # Skip header lines until we find the data
    lines = raw.splitlines()
    start_line = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("19") or line.strip().startswith("20"):
            start_line = i
            break

    csv_clean = "\n".join(lines[start_line:])
    df = pd.read_csv(
        io.StringIO(csv_clean),
        header=None,
        names=["date", "mkt_rf", "smb", "hml", "rmw", "cma", "rf"],
        na_values=["-99.99", "-999"],
    )
    df = df.dropna(subset=["date"])
    df["date"] = pd.to_datetime(df["date"].astype(str).str.strip(), format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["date"])

    # Convert percentage to decimal
    for col in ["mkt_rf", "smb", "hml", "rmw", "cma", "rf"]:
        df[col] = pd.to_numeric(df[col], errors="coerce") / 100.0

    # Only last 30 days to keep upsert fast
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    df = df[df["date"] >= cutoff.replace(tzinfo=None)]

    engine = _get_engine()
    rows_upserted = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            rec = {
                "time": row["date"].to_pydatetime() if hasattr(row["date"], "to_pydatetime") else row["date"],
                "mkt_rf": _safe_float(row.get("mkt_rf")),
                "smb": _safe_float(row.get("smb")),
                "hml": _safe_float(row.get("hml")),
                "rmw": _safe_float(row.get("rmw")),
                "cma": _safe_float(row.get("cma")),
                "rf": _safe_float(row.get("rf")),
            }
            conn.execute(
                text(
                    """
                    INSERT INTO ff5_factors (time, mkt_rf, smb, hml, rmw, cma, rf)
                    VALUES (:time, :mkt_rf, :smb, :hml, :rmw, :cma, :rf)
                    ON CONFLICT (time) DO UPDATE SET
                        mkt_rf = EXCLUDED.mkt_rf,
                        smb = EXCLUDED.smb,
                        hml = EXCLUDED.hml,
                        rmw = EXCLUDED.rmw,
                        cma = EXCLUDED.cma,
                        rf = EXCLUDED.rf
                    """
                ),
                rec,
            )
            rows_upserted += 1

    logger.info(f"FF5 factors ingest complete: {rows_upserted} rows")
    return {"status": "ok", "rows": rows_upserted}


# ---------------------------------------------------------------------------
# ingest_earnings_calendar
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.ingest.ingest_earnings_calendar", bind=True, max_retries=3)
def ingest_earnings_calendar(self) -> dict:
    """Fetch upcoming earnings from FMP API and store in earnings_events."""
    if not FMP_API_KEY:
        logger.warning("FMP_API_KEY not set — skipping earnings calendar ingest")
        return {"status": "skipped", "reason": "no_api_key"}

    today = datetime.now(timezone.utc).date()
    future = today + timedelta(days=14)
    url = (
        f"https://financialmodelingprep.com/api/v3/earning_calendar"
        f"?from={today}&to={future}&apikey={FMP_API_KEY}"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        events = resp.json()
    except Exception as exc:
        logger.error(f"FMP earnings calendar fetch failed: {exc}")
        raise self.retry(exc=exc, countdown=120)

    if not events:
        logger.info("No upcoming earnings events from FMP")
        return {"status": "ok", "rows": 0}

    from config import CONFIG

    engine = _get_engine()
    rows_inserted = 0

    with engine.begin() as conn:
        for event in events:
            ticker = event.get("symbol")
            date_str = event.get("date")
            eps_actual = event.get("eps")
            eps_est = event.get("epsEstimated")

            if not ticker or not date_str:
                continue

            try:
                announcement_ts = datetime.fromisoformat(date_str)
            except ValueError:
                try:
                    announcement_ts = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

            # Determine if ticker is in a cyclical sector (use config)
            # Sector not available from FMP calendar, set null — signal task will fill
            rec = {
                "ticker": ticker.upper(),
                "announcement_ts": announcement_ts,
                "actual_eps": _safe_float(eps_actual),
                "consensus_eps": _safe_float(eps_est),
                "implied_eps": None,
                "surprise_score": None,
                "intangible_mult": None,
                "roic_mult": None,
                "signal_composite": None,
                "direction": None,
                "gics_sector": None,
                "is_cyclical": None,
            }
            conn.execute(
                text(
                    """
                    INSERT INTO earnings_events
                        (ticker, announcement_ts, actual_eps, consensus_eps, implied_eps,
                         surprise_score, intangible_mult, roic_mult, signal_composite,
                         direction, gics_sector, is_cyclical)
                    VALUES
                        (:ticker, :announcement_ts, :actual_eps, :consensus_eps, :implied_eps,
                         :surprise_score, :intangible_mult, :roic_mult, :signal_composite,
                         :direction, :gics_sector, :is_cyclical)
                    ON CONFLICT DO NOTHING
                    """
                ),
                rec,
            )
            rows_inserted += 1

    logger.info(f"Earnings calendar ingest complete: {rows_inserted} events")
    return {"status": "ok", "rows": rows_inserted}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        import math
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None
