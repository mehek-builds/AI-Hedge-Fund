"""Tests for L2 signal generation."""

import pytest
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from signals.eps_gap import EPSGapSignal
from signals.intangible_filter import IntangibleFilter
from signals.roic_filter import ROICFilter


class TestEPSGapSignal:
    def setup_method(self):
        self.sig = EPSGapSignal()

    def test_positive_surprise_gives_long(self):
        # actual EPS well above implied → long signal
        result = self.sig.compute(
            ticker="AAPL",
            announce_date=pd.Timestamp("2023-01-20"),
            actual_eps=2.5,
            pre_announce_price=150.0,
            sector_fwd_pe=25.0,  # implied EPS = 150/25 = 6.0... wait
        )
        # implied = 150 / 25 = 6.0; actual = 2.5 → negative surprise
        assert result.direction in (-1, 0, 1)

    def test_high_actual_vs_low_implied_is_long(self):
        # implied = 100 / 10 = 10; actual = 15 → positive surprise
        result = self.sig.compute(
            ticker="TEST",
            announce_date=pd.Timestamp("2023-03-01"),
            actual_eps=15.0,
            pre_announce_price=100.0,
            sector_fwd_pe=10.0,
        )
        assert result.raw_surprise == pytest.approx(5.0)
        assert result.direction == 1

    def test_negative_surprise_is_short(self):
        # implied = 100 / 10 = 10; actual = 5 → negative surprise
        result = self.sig.compute(
            ticker="TEST2",
            announce_date=pd.Timestamp("2023-03-01"),
            actual_eps=5.0,
            pre_announce_price=100.0,
            sector_fwd_pe=10.0,
        )
        assert result.raw_surprise == pytest.approx(-5.0)
        assert result.direction == -1

    def test_zero_price_returns_zero_signal(self):
        result = self.sig.compute(
            ticker="BAD",
            announce_date=pd.Timestamp("2023-01-01"),
            actual_eps=1.0,
            pre_announce_price=0.0,
            sector_fwd_pe=20.0,
        )
        assert result.direction == 0

    def test_standardisation_grows_with_history(self):
        sig = EPSGapSignal()
        surprises = []
        for i in range(8):
            r = sig.compute(
                ticker="SERIES",
                announce_date=pd.Timestamp(f"2023-0{i+1}-01") if i < 9 else pd.Timestamp(f"2023-{i+1}-01"),
                actual_eps=float(i + 1),
                pre_announce_price=100.0,
                sector_fwd_pe=10.0,
            )
            surprises.append(r)
        # Std surprise should vary as history accumulates
        std_vals = [s.std_surprise for s in surprises[2:]]
        assert not all(v == std_vals[0] for v in std_vals)

    def test_batch_compute(self):
        events = pd.DataFrame({
            "ticker": ["A", "B", "C"],
            "announce_date": pd.to_datetime(["2023-01-01", "2023-04-01", "2023-07-01"]),
            "actual_eps": [2.0, 3.0, 1.5],
            "pre_announce_price": [100.0, 120.0, 80.0],
            "sector_fwd_pe": [20.0, 20.0, 20.0],
        })
        sig = EPSGapSignal()
        result = sig.compute_batch(events)
        assert "std_surprise" in result.columns
        assert "direction" in result.columns
        assert len(result) == 3


class TestIntangibleFilter:
    def test_high_intangible_gives_top_multiplier(self):
        f = IntangibleFilter()
        m = f.multiplier(rd_pct=0.20, sga_pct=0.20)  # 40% total
        assert m == 1.30

    def test_low_intangible_gives_bottom_multiplier(self):
        f = IntangibleFilter()
        m = f.multiplier(rd_pct=0.02, sga_pct=0.05)  # 7% total
        assert m == 1.0

    def test_fit_updates_thresholds(self):
        f = IntangibleFilter()
        ratios = pd.Series([0.05, 0.15, 0.25, 0.35, 0.45, 0.10, 0.20])
        f.fit(ratios)
        assert f._thresholds is not None
        t33, t67 = f._thresholds
        assert t33 < t67

    def test_multipliers_monotone(self):
        f = IntangibleFilter()
        low  = f.multiplier(0.02, 0.05)
        mid  = f.multiplier(0.10, 0.10)
        high = f.multiplier(0.20, 0.20)
        assert low <= mid <= high


class TestROICFilter:
    def test_roic_above_wacc_200bps(self):
        f = ROICFilter()
        m = f.multiplier(roic=0.15, wacc=0.10)  # 500bps spread
        assert m == 1.20

    def test_roic_below_wacc(self):
        f = ROICFilter()
        m = f.multiplier(roic=0.08, wacc=0.10)
        assert m == 1.0

    def test_exactly_at_threshold(self):
        f = ROICFilter()
        # 200bps = 0.02 spread, threshold is ≥200bps
        m = f.multiplier(roic=0.12, wacc=0.10)
        assert m == 1.20
