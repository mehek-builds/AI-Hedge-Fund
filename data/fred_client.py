"""FRED API client for macro regime data."""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import date
from typing import Optional
from loguru import logger

try:
    from fredapi import Fred
    _FRED_AVAILABLE = True
except ImportError:
    _FRED_AVAILABLE = False


class FREDClient:
    """Fetches macro time series from FRED.

    Falls back to synthetic data when no API key is configured, so
    the rest of the system can be exercised without credentials.
    """

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._fred: Optional[object] = None
        if api_key and _FRED_AVAILABLE:
            self._fred = Fred(api_key=api_key)
            logger.info("FRED client initialised with API key")
        else:
            logger.warning("FRED API key not set — using synthetic data")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_series(
        self,
        series_id: str,
        start: str = "2010-01-01",
        end: Optional[str] = None,
    ) -> pd.Series:
        """Return a named pd.Series for the given FRED series."""
        end = end or str(date.today())
        if self._fred is not None:
            try:
                data = self._fred.get_series(series_id, observation_start=start, observation_end=end)
                data.name = series_id
                return data.dropna()
            except Exception as exc:
                logger.warning(f"FRED fetch failed for {series_id}: {exc} — using synthetic")

        return self._synthetic(series_id, start, end)

    def get_yield_spread(self, start: str = "2010-01-01") -> pd.Series:
        return self.get_series("T10Y2Y", start=start)

    def get_core_pce(self, start: str = "2010-01-01") -> pd.Series:
        return self.get_series("PCEPILFE", start=start)

    def get_real_gdp_growth(self, start: str = "2010-01-01") -> pd.Series:
        """Return annualised QoQ real GDP growth (percent)."""
        gdp = self.get_series("GDPC1", start=start)
        # Quarterly, compute QoQ annualised
        growth = ((gdp / gdp.shift(1)) ** 4 - 1) * 100
        growth.name = "REAL_GDP_QOQ_ANN"
        return growth.dropna()

    def get_hy_spread(self, start: str = "2010-01-01") -> pd.Series:
        return self.get_series("BAMLH0A0HYM2", start=start)

    def get_sahm_rule(self, start: str = "2010-01-01") -> pd.Series:
        return self.get_series("SAHMREALTIME", start=start)

    def get_jpy_usd(self, start: str = "2010-01-01") -> pd.Series:
        return self.get_series("DEXJPUS", start=start)

    def get_aud_usd(self, start: str = "2010-01-01") -> pd.Series:
        return self.get_series("DEXUSAL", start=start)

    # ------------------------------------------------------------------
    # Synthetic fallback (stationary, regime-like random walks)
    # ------------------------------------------------------------------

    @staticmethod
    def _synthetic(series_id: str, start: str, end: str) -> pd.Series:
        """Generate plausible synthetic data for offline testing."""
        rng = np.random.default_rng(abs(hash(series_id)) % (2**32))
        dates = pd.date_range(start, end, freq="B")
        n = len(dates)

        defaults: dict[str, tuple[float, float, float]] = {
            # (mean, std, ar1)
            "T10Y2Y":         (0.5, 0.8, 0.98),
            "PCEPILFE":       (2.5, 0.6, 0.97),
            "GDPC1":          (20_000, 200, 0.999),  # level; growth computed later
            "BAMLH0A0HYM2":   (380.0, 80.0, 0.97),
            "SAHMREALTIME":   (0.1, 0.15, 0.95),
            "DEXJPUS":        (110.0, 5.0, 0.99),
            "DEXUSAL":        (0.75, 0.03, 0.99),
            "REAL_GDP_QOQ_ANN": (2.5, 1.5, 0.85),
        }
        mean, std, ar1 = defaults.get(series_id, (100.0, 5.0, 0.97))
        series = np.zeros(n)
        series[0] = mean
        for i in range(1, n):
            series[i] = ar1 * series[i - 1] + (1 - ar1) * mean + rng.normal(0, std * (1 - ar1))

        s = pd.Series(series, index=dates, name=series_id)
        # Monthly / quarterly series: resample
        if series_id in ("PCEPILFE", "SAHMREALTIME"):
            s = s.resample("ME").last()
        elif series_id in ("GDPC1",):
            s = s.resample("QE").last()
        return s
