"""L2 Augmenting Filter: ROIC vs WACC.

Companies with ROIC consistently > WACC over trailing 8 quarters show more
persistent earnings beats — market underestimates their earnings power.

Multiplier:
  ROIC < WACC:             1.0x
  ROIC > WACC by 200bps+:  1.2x
"""

from __future__ import annotations

import pandas as pd
from config import CONFIG


class ROICFilter:
    """Computes ROIC-vs-WACC position sizing multiplier."""

    def __init__(self):
        self._spread_threshold_bps = CONFIG.signal.roic_wacc_spread_bps
        self._multiplier_above = CONFIG.signal.roic_above_wacc_multiplier
        self._multiplier_below = CONFIG.signal.roic_below_wacc_multiplier

    def multiplier(self, roic: float, wacc: float) -> float:
        """Return multiplier for a single event."""
        spread_bps = round((roic - wacc) * 10_000, 4)  # avoid IEEE 754 drift
        if spread_bps >= self._spread_threshold_bps:
            return self._multiplier_above
        return self._multiplier_below

    def apply_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add 'roic_multiplier' column.

        Required columns: roic, wacc
        """
        if "roic" in df.columns and "wacc" in df.columns:
            df = df.copy()
            df["roic_multiplier"] = df.apply(
                lambda r: self.multiplier(r["roic"], r["wacc"]), axis=1
            )
        else:
            df = df.copy()
            df["roic_multiplier"] = 1.0
        return df
