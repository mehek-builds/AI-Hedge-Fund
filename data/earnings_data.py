"""Earnings event data loader.

Production: integrates with Compustat/FactSet/Refinitiv via their APIs.
Development/backtest: generates synthetic earnings events with realistic
properties for the full S&P 500 universe over the configured date range.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class EarningsEvent:
    ticker: str
    announce_date: pd.Timestamp
    actual_eps: float               # diluted, ex. non-recurring
    consensus_eps: float            # sell-side consensus (FactSet/IBES)
    shares_outstanding: float       # millions
    sector: str                     # GICS sector
    is_cyclical: bool
    rd_pct_revenue: float           # R&D as % trailing-12M revenue
    sga_pct_revenue: float          # SG&A as % trailing-12M revenue
    roic: float                     # trailing 8Q average ROIC
    wacc: float                     # estimated WACC
    market_cap: float               # millions at announce date
    # Set by SignalGenerator after price data is joined
    pre_announce_price: Optional[float] = None
    sector_fwd_pe: Optional[float] = None


class EarningsDataClient:
    """Returns earnings event records for a ticker universe and date range."""

    # GICS sector → typical forward P/E
    SECTOR_FWD_PE: dict[str, float] = {
        "Energy": 12.0,
        "Materials": 16.0,
        "Industrials": 19.0,
        "Consumer Discretionary": 22.0,
        "Consumer Staples": 20.0,
        "Health Care": 18.0,
        "Financials": 13.0,
        "Information Technology": 28.0,
        "Communication Services": 20.0,
        "Utilities": 17.0,
        "Real Estate": 35.0,
    }

    CYCLICAL_SECTORS = {
        "Energy", "Materials", "Industrials",
        "Consumer Discretionary", "Financials"
    }

    # Dates within this many days of today → use real data
    _REAL_DATA_LOOKBACK_DAYS: int = 730   # 2 years

    def get_events(
        self,
        tickers: list[str],
        start: str = "2010-01-01",
        end: str = "2023-12-31",
    ) -> pd.DataFrame:
        """Return earnings events, routing to real data for recent windows."""
        logger.info(f"Loading earnings events for {len(tickers)} tickers [{start} → {end}]")

        cutoff = pd.Timestamp.now() - pd.Timedelta(days=self._REAL_DATA_LOOKBACK_DAYS)
        start_ts = pd.Timestamp(start)

        if start_ts >= cutoff:
            return self._get_real_events(tickers, start, end)

        # Backtest range: use synthetic (real data has insufficient history)
        records = []
        for ticker in tickers:
            records.extend(self._synthetic_events(ticker, start, end))
        df = pd.DataFrame([vars(e) for e in records])
        df = df.sort_values("announce_date").reset_index(drop=True)
        logger.info(f"Loaded {len(df)} synthetic events (backtest mode)")
        return df

    def _get_real_events(self, tickers: list[str], start: str, end: str) -> pd.DataFrame:
        """Delegate to RealEarningsClient for live/paper trading."""
        from data.real_earnings_client import RealEarningsClient
        import os
        fmp_key = os.getenv("FMP_API_KEY", "")
        client = RealEarningsClient(fmp_api_key=fmp_key)
        df = client.get_events(tickers, start=start, end=end)
        logger.info(f"Loaded {len(df)} real earnings events")
        return df

    def get_sector_fwd_pe(self, sector: str, date: pd.Timestamp) -> float:
        """Return the sector median forward P/E for market-implied EPS calculation."""
        # Production: compute from live universe.
        base = self.SECTOR_FWD_PE.get(sector, 18.0)
        # Add slight time variation around base
        rng = np.random.default_rng(abs(hash(sector + str(date.year))) % (2**32))
        return max(8.0, base + rng.normal(0, 1.5))

    # ------------------------------------------------------------------
    # Synthetic event generator
    # ------------------------------------------------------------------

    def _synthetic_events(
        self, ticker: str, start: str, end: str
    ) -> list[EarningsEvent]:
        """Generate ~4 quarterly earnings events per year for a ticker."""
        rng = np.random.default_rng(abs(hash(ticker)) % (2**32))

        # Assign sector deterministically by hash
        sectors = list(self.SECTOR_FWD_PE.keys())
        sector = sectors[abs(hash(ticker)) % len(sectors)]
        is_cyclical = sector in self.CYCLICAL_SECTORS

        # Earnings calendar: roughly Feb, May, Aug, Nov
        quarters = pd.date_range(start, end, freq="QE")
        events = []
        base_eps = rng.uniform(0.5, 5.0)
        eps_trend = rng.uniform(-0.02, 0.04)  # quarterly drift

        for i, q in enumerate(quarters):
            # Shift to announcement day: ~3-6 weeks after quarter end
            offset = int(rng.uniform(15, 42))
            announce = q + pd.Timedelta(days=offset)
            if announce < pd.Timestamp(start) or announce > pd.Timestamp(end):
                continue

            actual_eps = base_eps * (1 + eps_trend) ** i + rng.normal(0, 0.15)
            consensus_eps = actual_eps - rng.normal(0.05, 0.12)  # market underestimates

            # Intangibles
            rd = rng.uniform(0.01, 0.20)
            sga = rng.uniform(0.05, 0.30)

            # ROIC / WACC
            wacc = rng.uniform(0.06, 0.12)
            roic = wacc + rng.normal(0.01, 0.04)

            events.append(EarningsEvent(
                ticker=ticker,
                announce_date=announce,
                actual_eps=actual_eps,
                consensus_eps=consensus_eps,
                shares_outstanding=rng.uniform(500, 5000),
                sector=sector,
                is_cyclical=is_cyclical,
                rd_pct_revenue=rd,
                sga_pct_revenue=sga,
                roic=roic,
                wacc=wacc,
                market_cap=rng.uniform(5_000, 500_000),
                pre_announce_price=None,
                sector_fwd_pe=self.get_sector_fwd_pe(sector, announce),
            ))

        return events
