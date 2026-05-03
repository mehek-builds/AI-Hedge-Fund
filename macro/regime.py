"""L3 Macro Regime Module.

Produces a composite score ∈ {0, -1, -2, -3, ≤-4} that gates position sizing.

Each of 6 signals contributes -1 when its adverse threshold is breached.
A carry crash overlay adds an additional -1 regardless of equity signals.

Score → Sizing multiplier:
  0    → 1.00x (full)
  -1   → 0.85x
  -2   → 0.65x
  -3   → 0.35x
  ≤-4  → 0.00x (halt new entries)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from data.fred_client import FREDClient
from data.price_data import PriceDataClient
from config import CONFIG


@dataclass
class RegimeSnapshot:
    date: pd.Timestamp
    composite_score: int           # 0 to ≤-4
    sizing_multiplier: float
    is_halted: bool
    component_scores: dict[str, int]  # signal → -1 or 0


class MacroRegimeModule:
    """Computes daily macro regime snapshots over a date range.

    Signals evaluated:
      1. 10Y-2Y yield spread (T10Y2Y)
      2. Core PCE YoY (PCEPILFE)
      3. Real GDP QoQ annualised (GDPC1)
      4. HY credit spread OAS (BAMLH0A0HYM2)
      5. VIX (^VIX via yfinance)
      6. Sahm Rule (SAHMREALTIME)
      7. Carry crash overlay (JPY/AUD rate of change)
    """

    def __init__(
        self,
        fred_client: FREDClient | None = None,
        price_client: PriceDataClient | None = None,
    ):
        self._fred = fred_client or FREDClient(api_key=CONFIG.data.fred_api_key)
        self._prices = price_client or PriceDataClient()
        self._cfg = CONFIG.macro

    def build_regime_series(
        self, start: str = "2010-01-01", end: str = "2024-01-01"
    ) -> pd.DataFrame:
        """Return a daily DataFrame of regime snapshots over the date range."""
        logger.info(f"Building macro regime series [{start} → {end}]")

        # Fetch all raw series
        yield_spread = self._fred.get_yield_spread(start)
        core_pce = self._fred.get_core_pce(start)
        gdp_growth = self._fred.get_real_gdp_growth(start)
        hy_spread = self._fred.get_hy_spread(start)
        vix = self._prices.get_vix(start=start, end=end)
        sahm = self._fred.get_sahm_rule(start)
        jpy = self._fred.get_jpy_usd(start)
        aud = self._fred.get_aud_usd(start)

        # Carry crash proxy: JPY/AUD in USD terms → AUD/JPY
        aud_jpy = aud / (1.0 / jpy.reindex(aud.index, method="ffill"))
        carry_crash = self._carry_crash_signal(aud_jpy)

        # Build on business-day index
        bdays = pd.date_range(start, end, freq="B")
        df = pd.DataFrame(index=bdays)

        # Forward-fill lower-frequency series to daily
        df["yield_spread"] = yield_spread.reindex(bdays, method="ffill")
        df["core_pce"]     = core_pce.reindex(bdays, method="ffill")
        df["gdp_growth"]   = gdp_growth.reindex(bdays, method="ffill")
        df["hy_spread"]    = hy_spread.reindex(bdays, method="ffill")
        df["vix"]          = vix.reindex(bdays, method="ffill")
        df["sahm"]         = sahm.reindex(bdays, method="ffill")
        df["carry_crash"]  = carry_crash.reindex(bdays, method="ffill").fillna(0)

        df = df.dropna(subset=["yield_spread", "hy_spread", "vix"])

        # Compute component scores
        df["s_yield"]  = (df["yield_spread"] < self._cfg.yield_spread_threshold).astype(int) * -1
        df["s_pce"]    = (df["core_pce"]    > self._cfg.core_pce_threshold).astype(int) * -1
        df["s_gdp"]    = (df["gdp_growth"]  < self._cfg.real_gdp_threshold).astype(int) * -1
        df["s_hy"]     = (df["hy_spread"]   > self._cfg.hy_spread_threshold).astype(int) * -1
        df["s_vix"]    = (df["vix"]         > self._cfg.vix_threshold).astype(int) * -1
        df["s_sahm"]   = (df["sahm"]        >= self._cfg.sahm_threshold).astype(int) * -1
        df["s_carry"]  = df["carry_crash"].astype(int) * -1

        component_cols = ["s_yield", "s_pce", "s_gdp", "s_hy", "s_vix", "s_sahm", "s_carry"]
        df["composite_score"] = df[component_cols].sum(axis=1).astype(int)

        df["sizing_multiplier"] = df["composite_score"].map(self._score_to_multiplier)
        df["is_halted"] = df["composite_score"] <= self._cfg.halt_threshold

        logger.info(
            f"Regime series built: {len(df)} days | "
            f"halted days: {df['is_halted'].sum()} "
            f"({100*df['is_halted'].mean():.1f}%)"
        )
        return df

    def get_snapshot(
        self, regime_df: pd.DataFrame, date: pd.Timestamp
    ) -> RegimeSnapshot:
        """Look up regime state on a specific date."""
        idx = regime_df.index.get_indexer([date], method="ffill")[0]
        if idx < 0:
            return RegimeSnapshot(
                date=date,
                composite_score=0,
                sizing_multiplier=1.0,
                is_halted=False,
                component_scores={},
            )
        row = regime_df.iloc[idx]
        comp_scores = {
            col: int(row[col])
            for col in regime_df.columns
            if col.startswith("s_")
        }
        return RegimeSnapshot(
            date=date,
            composite_score=int(row["composite_score"]),
            sizing_multiplier=float(row["sizing_multiplier"]),
            is_halted=bool(row["is_halted"]),
            component_scores=comp_scores,
        )

    # ------------------------------------------------------------------
    # Carry crash detection
    # ------------------------------------------------------------------

    @staticmethod
    def _carry_crash_signal(aud_jpy: pd.Series, window: int = 20, threshold: float = -0.05) -> pd.Series:
        """Flag carry crash: AUD/JPY down > 5% over 20-day rolling window."""
        rolling_return = aud_jpy.pct_change(window)
        return (rolling_return < threshold).astype(float)

    # ------------------------------------------------------------------
    # Score → multiplier mapping
    # ------------------------------------------------------------------

    def _score_to_multiplier(self, score: int) -> float:
        if score <= self._cfg.halt_threshold:
            return 0.0
        return self._cfg.sizing_multipliers.get(score, 0.0)
