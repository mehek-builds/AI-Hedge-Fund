"""L2 Augmenting Filter: Intangible Intensity.

High-intangible companies (software, biotech, IP-heavy industrials) are
systematically mispriced by traditional valuation screens → larger expected PEAD.

Multiplier by tercile (R&D + SG&A as % trailing-12M revenue):
  Bottom tercile: 1.0x
  Middle tercile: 1.15x
  Top tercile:    1.30x
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger

from config import CONFIG


class IntangibleFilter:
    """Computes intangible-intensity multiplier for position sizing."""

    def __init__(self):
        self._multipliers = CONFIG.signal.intangible_multipliers
        # Universe-level tercile thresholds (updated as events roll in)
        self._thresholds: tuple[float, float] | None = None
        self._history: list[float] = []

    def fit(self, intangible_ratios: pd.Series) -> None:
        """Fit tercile thresholds from universe-level data."""
        clean = intangible_ratios.dropna()
        if len(clean) < 3:
            return
        self._history.extend(clean.tolist())
        arr = np.array(self._history)
        self._thresholds = (float(np.percentile(arr, 33)), float(np.percentile(arr, 67)))
        logger.debug(f"Intangible thresholds: {self._thresholds}")

    def multiplier(self, rd_pct: float, sga_pct: float) -> float:
        """Return position sizing multiplier for a single event."""
        intangible_ratio = rd_pct + sga_pct

        if self._thresholds is None:
            # Before fit: use absolute heuristic (>30% = top, <15% = bottom)
            if intangible_ratio > 0.30:
                tercile = "top"
            elif intangible_ratio < 0.15:
                tercile = "bottom"
            else:
                tercile = "middle"
        else:
            t33, t67 = self._thresholds
            if intangible_ratio >= t67:
                tercile = "top"
            elif intangible_ratio <= t33:
                tercile = "bottom"
            else:
                tercile = "middle"

        return self._multipliers[tercile]

    def apply_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add 'intangible_multiplier' column to a DataFrame of events.

        Required columns: rd_pct_revenue, sga_pct_revenue
        """
        # Fit on this batch before applying
        if "rd_pct_revenue" in df.columns and "sga_pct_revenue" in df.columns:
            combined = df["rd_pct_revenue"] + df["sga_pct_revenue"]
            self.fit(combined)
            df = df.copy()
            df["intangible_multiplier"] = combined.map(
                lambda v: self.multiplier(v, 0.0)  # already summed
            )
        else:
            df = df.copy()
            df["intangible_multiplier"] = 1.0
        return df
