"""L2 Core Signal: Market-Implied EPS Gap.

Signal = (Actual EPS − Market-Implied EPS) / rolling 4Q std dev of surprises

Market-implied EPS = pre-announcement 5-day avg price / sector median forward P/E
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from config import CONFIG


@dataclass
class EarningsSurprise:
    ticker: str
    announce_date: pd.Timestamp
    actual_eps: float
    implied_eps: float
    raw_surprise: float       # actual - implied
    std_surprise: float       # standardized by rolling 4Q std
    direction: int            # +1 long, -1 short, 0 no signal


class EPSGapSignal:
    """Computes the standardised EPS gap signal for each earnings event.

    The market-implied EPS is reverse-engineered from the pre-announcement
    stock price using sector median forward P/E:
        implied_EPS = avg_price_5d / sector_fwd_PE

    The surprise is then standardised by the ticker's rolling 4-quarter
    standard deviation of surprises to produce a z-score comparable across
    companies.
    """

    def __init__(self, min_std_threshold: float = 0.1):
        # Minimum std dev to avoid division blow-up on tickers with few events
        self._min_std = min_std_threshold
        # Per-ticker rolling surprise history {ticker: [surprise, ...]}
        self._surprise_history: dict[str, list[float]] = {}

    def compute(
        self,
        ticker: str,
        announce_date: pd.Timestamp,
        actual_eps: float,
        pre_announce_price: float,
        sector_fwd_pe: float,
    ) -> EarningsSurprise:
        """Compute signal for a single earnings event."""
        if sector_fwd_pe <= 0 or pre_announce_price <= 0:
            return self._zero_signal(ticker, announce_date, actual_eps)

        implied_eps = pre_announce_price / sector_fwd_pe
        raw_surprise = actual_eps - implied_eps

        # Update history and compute rolling std
        history = self._surprise_history.setdefault(ticker, [])
        history.append(raw_surprise)

        # Use last 4Q for std (rolling window)
        window = CONFIG.signal.surprise_std_quarters
        recent = history[-window:]
        std = max(float(np.std(recent)), self._min_std) if len(recent) > 1 else self._min_std

        std_surprise = raw_surprise / std
        direction = int(np.sign(std_surprise)) if abs(std_surprise) > 0.5 else 0

        return EarningsSurprise(
            ticker=ticker,
            announce_date=announce_date,
            actual_eps=actual_eps,
            implied_eps=implied_eps,
            raw_surprise=raw_surprise,
            std_surprise=std_surprise,
            direction=direction,
        )

    def compute_batch(self, events_df: pd.DataFrame) -> pd.DataFrame:
        """Process a sorted DataFrame of earnings events.

        Required columns: ticker, announce_date, actual_eps,
                          pre_announce_price, sector_fwd_pe
        Returns input DataFrame with added signal columns.
        """
        required = {"ticker", "announce_date", "actual_eps",
                    "pre_announce_price", "sector_fwd_pe"}
        missing = required - set(events_df.columns)
        if missing:
            raise ValueError(f"events_df missing columns: {missing}")

        results = []
        for _, row in events_df.iterrows():
            s = self.compute(
                ticker=row["ticker"],
                announce_date=row["announce_date"],
                actual_eps=row["actual_eps"],
                pre_announce_price=row["pre_announce_price"],
                sector_fwd_pe=row["sector_fwd_pe"],
            )
            results.append({
                "implied_eps":  s.implied_eps,
                "raw_surprise": s.raw_surprise,
                "std_surprise": s.std_surprise,
                "direction":    s.direction,
            })

        signal_df = pd.DataFrame(results, index=events_df.index)
        return pd.concat([events_df, signal_df], axis=1)

    # ------------------------------------------------------------------

    @staticmethod
    def _zero_signal(
        ticker: str, announce_date: pd.Timestamp, actual_eps: float
    ) -> EarningsSurprise:
        return EarningsSurprise(
            ticker=ticker,
            announce_date=announce_date,
            actual_eps=actual_eps,
            implied_eps=float("nan"),
            raw_surprise=0.0,
            std_surprise=0.0,
            direction=0,
        )
