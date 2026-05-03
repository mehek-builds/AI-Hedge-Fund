"""L2 Signal Generator — orchestrates EPS gap + filter multipliers.

Produces a final `signal_strength` per earnings event:
    signal_strength = std_surprise * intangible_multiplier * roic_multiplier

Combined with direction (+1 / -1 / 0), this drives RL position sizing.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from loguru import logger

from data.price_data import PriceDataClient
from data.earnings_data import EarningsDataClient
from signals.eps_gap import EPSGapSignal
from signals.intangible_filter import IntangibleFilter
from signals.roic_filter import ROICFilter
from config import CONFIG


class SignalGenerator:
    """End-to-end L2 signal pipeline."""

    def __init__(
        self,
        price_client: PriceDataClient | None = None,
        earnings_client: EarningsDataClient | None = None,
    ):
        self._prices = price_client or PriceDataClient()
        self._earnings = earnings_client or EarningsDataClient()
        self._eps_signal = EPSGapSignal()
        self._intangible = IntangibleFilter()
        self._roic = ROICFilter()

    def generate(
        self,
        tickers: list[str],
        start: str = "2010-01-01",
        end: str = "2023-12-31",
    ) -> pd.DataFrame:
        """Build full signal DataFrame for the given universe and date range.

        Returns a DataFrame with one row per earnings event, columns including:
          ticker, announce_date, std_surprise, direction,
          intangible_multiplier, roic_multiplier, signal_strength,
          sector, is_cyclical
        """
        # 1. Load earnings events
        events = self._earnings.get_events(tickers, start=start, end=end)

        # 2. Attach pre-announcement prices (5-day avg)
        events = self._attach_prices(events, start)

        # 3. Compute EPS gap signals
        events = self._eps_signal.compute_batch(events)

        # 4. Apply filters
        events = self._intangible.apply_batch(events)
        events = self._roic.apply_batch(events)

        # 5. Combine into signal_strength
        events["signal_strength"] = (
            events["std_surprise"]
            * events["intangible_multiplier"]
            * events["roic_multiplier"]
        )

        # Drop rows with missing core signal
        events = events.dropna(subset=["std_surprise", "pre_announce_price"])
        logger.info(f"Signal generation complete: {len(events)} events")
        return events

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _attach_prices(self, events: pd.DataFrame, data_start: str) -> pd.DataFrame:
        """Add pre_announce_price and sector_fwd_pe columns."""
        tickers = events["ticker"].unique().tolist()
        # Fetch all prices at once for efficiency
        all_prices = self._prices.get_prices(tickers, start=data_start)

        pre_prices = []
        for _, row in events.iterrows():
            ticker = row["ticker"]
            announce = row["announce_date"]
            col = ticker if ticker in all_prices.columns else None

            if col is None:
                pre_prices.append(float("nan"))
                continue

            series = all_prices[col].dropna()
            idx = series.index.get_indexer([announce], method="ffill")[0]
            window = CONFIG.signal.pre_announce_window
            if idx < 1:
                pre_prices.append(float("nan"))
            else:
                start_idx = max(0, idx - window)
                pre_prices.append(float(series.iloc[start_idx:idx].mean()))

        events = events.copy()
        events["pre_announce_price"] = pre_prices

        # Attach sector forward P/E if not already present
        if "sector_fwd_pe" not in events.columns:
            events["sector_fwd_pe"] = events.apply(
                lambda r: self._earnings.get_sector_fwd_pe(r["sector"], r["announce_date"]),
                axis=1,
            )

        return events
