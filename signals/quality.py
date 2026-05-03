"""Earnings quality decomposition — v3 signal engine."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class EarningsQuality:
    revenue_surprise: float
    margin_surprise: float
    share_count_chg: float
    guidance_delta: float        # +1 raised / 0 maintained / -1 lowered
    quality_score: float         # composite [0.5, 1.5]
    signal_composite: float      # raw_signal * quality_score


class QualityDecomposer:
    """Decomposes earnings beats into four quality components and weights signal."""

    _WEIGHTS = {
        "revenue": 0.35,
        "margin": 0.30,
        "share_count": 0.15,
        "guidance": 0.20,
    }

    def compute(
        self,
        raw_signal: float,
        actual_rev: float,
        implied_rev: float,
        actual_margin: float,
        prior_margin: float,
        curr_shares: float,
        prev_shares: float,
        guidance: str,           # 'raised' | 'maintained' | 'lowered' | 'none'
    ) -> EarningsQuality:
        rev_surprise = (actual_rev - implied_rev) / implied_rev if implied_rev != 0 else 0.0
        margin_surprise = actual_margin - prior_margin
        share_improvement = (prev_shares - curr_shares) / prev_shares if prev_shares != 0 else 0.0

        guidance_map = {"raised": 1.0, "maintained": 0.0, "lowered": -1.0, "none": 0.0}
        guidance_delta = guidance_map.get(guidance.lower(), 0.0)

        rev_norm = float(np.clip(rev_surprise / 0.05, -3, 3)) / 3
        margin_norm = float(np.clip(margin_surprise / 0.02, -3, 3)) / 3
        share_norm = float(np.clip(share_improvement / 0.02, -3, 3)) / 3
        guidance_norm = guidance_delta

        quality_score = (
            self._WEIGHTS["revenue"] * rev_norm
            + self._WEIGHTS["margin"] * margin_norm
            + self._WEIGHTS["share_count"] * share_norm
            + self._WEIGHTS["guidance"] * guidance_norm
        )
        quality_score = float(np.clip(quality_score + 1.0, 0.5, 1.5))
        signal_composite = raw_signal * quality_score

        return EarningsQuality(
            revenue_surprise=rev_surprise,
            margin_surprise=margin_surprise,
            share_count_chg=share_improvement,
            guidance_delta=guidance_delta,
            quality_score=quality_score,
            signal_composite=signal_composite,
        )
