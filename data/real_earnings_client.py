"""Real earnings data via yfinance (live/paper) with optional FMP upgrade.

Provides the same EarningsEvent schema as the synthetic generator so the
signal pipeline, backtest engine, and RL environment need no changes.

Data sources (in priority order):
  1. FMP API  — if FMP_API_KEY is set; richer history, consensus from IBES
  2. yfinance — always available; ~4-8 quarters of actual vs. estimate
  3. Synthetic — explicit fallback (never auto-triggered here)

Route:
  - start/end within last 2 years  → real data
  - older dates                    → caller should use synthetic generator
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from loguru import logger

from data.earnings_data import EarningsEvent

# ---------------------------------------------------------------------------
# Sector name normalisation (yfinance → GICS)
# ---------------------------------------------------------------------------

_YF_TO_GICS: dict[str, str] = {
    "Technology":             "Information Technology",
    "Healthcare":             "Health Care",
    "Financial Services":     "Financials",
    "Consumer Cyclical":      "Consumer Discretionary",
    "Consumer Defensive":     "Consumer Staples",
    "Basic Materials":        "Materials",
    "Communication Services": "Communication Services",
    "Energy":                 "Energy",
    "Real Estate":            "Real Estate",
    "Utilities":              "Utilities",
    "Industrials":            "Industrials",
    # already GICS-named (some yfinance versions)
    "Information Technology": "Information Technology",
    "Health Care":            "Health Care",
    "Financials":             "Financials",
    "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples":       "Consumer Staples",
    "Materials":              "Materials",
}

_CYCLICAL = {
    "Energy", "Materials", "Industrials",
    "Consumer Discretionary", "Financials",
}

# Default WACC by GICS sector (rough estimate; production would use CAPM)
_SECTOR_WACC: dict[str, float] = {
    "Energy": 0.09, "Materials": 0.08, "Industrials": 0.08,
    "Consumer Discretionary": 0.09, "Consumer Staples": 0.07,
    "Health Care": 0.08, "Financials": 0.10,
    "Information Technology": 0.10, "Communication Services": 0.09,
    "Utilities": 0.06, "Real Estate": 0.07,
}


# ---------------------------------------------------------------------------
# FMP client (optional)
# ---------------------------------------------------------------------------

class FMPClient:
    """Thin wrapper around Financial Modeling Prep v3 API."""

    # Earnings endpoints (v3) are legacy-blocked on the free plan.
    # Only stable/profile is accessible without a paid subscription.
    STABLE = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: str):
        self._key = api_key

    def company_profile(self, ticker: str) -> dict:
        """Return sector, market cap, beta — uses stable/profile (free tier ok)."""
        url = f"{self.STABLE}/profile"
        r = requests.get(url, params={"symbol": ticker, "apikey": self._key}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data[0] if isinstance(data, list) and data else {}


# ---------------------------------------------------------------------------
# yfinance helpers
# ---------------------------------------------------------------------------

def _yf_earnings(ticker: str) -> pd.DataFrame:
    """Fetch earnings_history and normalise column names."""
    t = yf.Ticker(ticker)
    eh = t.earnings_history
    if eh is None or eh.empty:
        return pd.DataFrame()
    eh = eh.copy()
    eh.index = pd.to_datetime(eh.index)
    eh = eh.rename(columns={
        "epsActual":   "epsActual",
        "epsEstimate": "epsEstimate",
    })
    eh["announce_date"] = eh.index
    return eh[["announce_date", "epsActual", "epsEstimate"]].dropna()


def _yf_fundamentals(ticker: str) -> dict:
    """Pull sector, market cap, R&D%, SGA%, ROIC from yfinance."""
    t = yf.Ticker(ticker)
    info = t.info or {}

    raw_sector = info.get("sector", "")
    sector = _YF_TO_GICS.get(raw_sector, raw_sector or "Industrials")
    market_cap = float(info.get("marketCap") or 0) / 1e6   # → millions
    shares = float(info.get("sharesOutstanding") or 0) / 1e6

    # Income statement — annual
    rd_pct = sga_pct = roic = wacc = 0.0
    try:
        is_ = t.income_stmt
        bs  = t.balance_sheet

        def _get(df, label, col=0):
            if label in df.index:
                v = df.loc[label].iloc[col]
                return float(v) if pd.notna(v) else 0.0
            return 0.0

        revenue = _get(is_, "Total Revenue")
        rd      = _get(is_, "Research And Development")
        sga     = _get(is_, "Selling General And Administration")
        op_inc  = _get(is_, "Operating Income")
        tax_rt  = _get(is_, "Tax Rate For Calcs")
        inv_cap = _get(bs,  "Invested Capital")

        if revenue > 0:
            rd_pct  = rd  / revenue
            sga_pct = sga / revenue
        if inv_cap > 0 and op_inc != 0:
            nopat = op_inc * (1 - max(0.0, min(tax_rt, 0.50)))
            roic  = nopat / inv_cap

        wacc = _SECTOR_WACC.get(sector, 0.08)
    except Exception:
        pass

    return {
        "sector": sector,
        "market_cap": market_cap,
        "shares_outstanding": shares,
        "rd_pct_revenue": max(0.0, rd_pct),
        "sga_pct_revenue": max(0.0, sga_pct),
        "roic": roic,
        "wacc": wacc,
    }


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class RealEarningsClient:
    """
    Fetches real earnings events for a ticker list and date range.

    Produces the same EarningsEvent records as EarningsDataClient so the
    rest of the system (signal generator, backtest engine) needs no changes.
    """

    def __init__(self, fmp_api_key: str = ""):
        # FMP free tier (post-Aug 2025) only exposes stable/profile — earnings
        # endpoints require a paid plan.  We always use yfinance for earnings;
        # FMP profile enriches sector/market-cap when the key is present.
        self._fmp: Optional[FMPClient] = FMPClient(fmp_api_key) if fmp_api_key else None
        if self._fmp:
            logger.info("RealEarningsClient: yfinance (earnings) + FMP profile enrichment")
        else:
            logger.info("RealEarningsClient: yfinance only")

    def get_events(
        self,
        tickers: list[str],
        start: str = "2024-01-01",
        end: str | None = None,
    ) -> pd.DataFrame:
        end = end or datetime.now().strftime("%Y-%m-%d")
        start_ts = pd.Timestamp(start)
        end_ts   = pd.Timestamp(end)

        logger.info(
            f"RealEarningsClient: fetching {len(tickers)} tickers "
            f"[{start} → {end}]"
        )

        records = []
        for i, ticker in enumerate(tickers):
            try:
                events = self._fetch_ticker(ticker, start_ts, end_ts)
                records.extend(events)
                if i > 0 and i % 10 == 0:
                    time.sleep(0.5)   # gentle rate limit
            except Exception as e:
                logger.warning(f"  {ticker}: skipped ({e})")

        if not records:
            logger.warning("RealEarningsClient: no events found")
            return pd.DataFrame()

        df = pd.DataFrame([vars(e) for e in records])
        df = df.sort_values("announce_date").reset_index(drop=True)
        logger.info(f"RealEarningsClient: {len(df)} events loaded")
        return df

    # ------------------------------------------------------------------

    def _fetch_ticker(
        self, ticker: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp
    ) -> list[EarningsEvent]:

        # --- Earnings table (always yfinance — FMP earnings require paid plan) ---
        eh = _yf_earnings(ticker)

        if eh.empty:
            return []

        # Filter to requested window
        eh = eh[
            (eh["announce_date"] >= start_ts) &
            (eh["announce_date"] <= end_ts)
        ]
        if eh.empty:
            return []

        # Drop rows with zero/null estimate (can't compute surprise)
        eh = eh[eh["epsEstimate"].notna() & (eh["epsEstimate"] != 0)]
        if eh.empty:
            return []

        # --- Fundamentals: yfinance base + optional FMP profile enrichment ---
        fundamentals = _yf_fundamentals(ticker)
        if self._fmp:
            try:
                profile = self._fmp.company_profile(ticker)
                if profile:
                    raw_sector = profile.get("sector", "")
                    sector_fmp = _YF_TO_GICS.get(raw_sector, raw_sector)
                    if sector_fmp:
                        fundamentals["sector"] = sector_fmp
                    # stable/profile returns marketCap (not mktCap)
                    mc = profile.get("marketCap") or profile.get("mktCap")
                    if mc:
                        fundamentals["market_cap"] = float(mc) / 1e6
            except Exception:
                pass

        sector      = fundamentals["sector"]
        is_cyclical = sector in _CYCLICAL

        # --- Standardise surprise across all available yfinance history ---
        all_eh = _yf_earnings(ticker)
        surprise_history = (
            (all_eh["epsActual"] - all_eh["epsEstimate"]) / all_eh["epsEstimate"].abs()
        ).dropna()
        std_denom = float(surprise_history.std()) if len(surprise_history) > 1 else 1.0
        std_denom = std_denom if std_denom > 1e-6 else 1.0

        events = []
        for _, row in eh.iterrows():
            actual   = float(row["epsActual"])
            estimate = float(row["epsEstimate"])
            surprise_pct = (actual - estimate) / abs(estimate)

            events.append(EarningsEvent(
                ticker=ticker,
                announce_date=pd.Timestamp(row["announce_date"]),
                actual_eps=actual,
                consensus_eps=estimate,
                shares_outstanding=fundamentals["shares_outstanding"],
                sector=sector,
                is_cyclical=is_cyclical,
                rd_pct_revenue=fundamentals["rd_pct_revenue"],
                sga_pct_revenue=fundamentals["sga_pct_revenue"],
                roic=fundamentals["roic"],
                wacc=fundamentals["wacc"],
                market_cap=fundamentals["market_cap"],
                pre_announce_price=None,
                sector_fwd_pe=None,
            ))

        return events
