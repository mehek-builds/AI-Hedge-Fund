"""Daily price and volume data via yfinance, with synthetic fallback."""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Union
from loguru import logger

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False


class PriceDataClient:
    """Fetches adjusted daily OHLCV data for S&P 500 tickers."""

    def get_prices(
        self,
        tickers: Union[str, list[str]],
        start: str = "2010-01-01",
        end: str | None = None,
        field: str = "Close",
    ) -> pd.DataFrame:
        """Return daily adjusted close (or other field) as DataFrame[ticker]."""
        if isinstance(tickers, str):
            tickers = [tickers]

        if _YF_AVAILABLE:
            try:
                raw = yf.download(
                    tickers,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                if len(tickers) == 1:
                    # yfinance returns flat DataFrame for single ticker
                    df = raw[[field]].rename(columns={field: tickers[0]})
                else:
                    df = raw[field] if field in raw.columns.get_level_values(0) else raw
                logger.debug(f"Downloaded {len(tickers)} tickers from yfinance")
                return df.dropna(how="all")
            except Exception as exc:
                logger.warning(f"yfinance download failed: {exc} — using synthetic")

        return self._synthetic_prices(tickers, start, end or "2024-01-01")

    def get_pre_announce_avg(
        self,
        ticker: str,
        announce_date: pd.Timestamp,
        window: int = 5,
        start: str = "2009-01-01",
    ) -> float:
        """Return the mean close price over `window` trading days before announcement."""
        prices = self.get_prices(ticker, start=start)
        col = ticker if ticker in prices.columns else prices.columns[0]
        series = prices[col]
        idx = series.index.get_indexer([announce_date], method="ffill")[0]
        if idx < window:
            return float(series.iloc[:idx].mean()) if idx > 0 else float("nan")
        return float(series.iloc[idx - window : idx].mean())

    def get_vix(self, start: str = "2010-01-01", end: str | None = None) -> pd.Series:
        """Fetch VIX via yfinance (^VIX)."""
        df = self.get_prices("^VIX", start=start, end=end)
        s = df.iloc[:, 0]
        s.name = "VIX"
        return s

    # ------------------------------------------------------------------
    # Synthetic fallback — geometric Brownian motion
    # ------------------------------------------------------------------

    @staticmethod
    def _synthetic_prices(
        tickers: list[str], start: str, end: str
    ) -> pd.DataFrame:
        dates = pd.date_range(start, end, freq="B")
        n = len(dates)
        result = {}
        for ticker in tickers:
            rng = np.random.default_rng(abs(hash(ticker)) % (2**32))
            log_returns = rng.normal(0.0003, 0.015, n)
            prices = 100.0 * np.exp(np.cumsum(log_returns))
            result[ticker] = prices
        return pd.DataFrame(result, index=dates)
