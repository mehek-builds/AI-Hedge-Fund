"""Tests for L3 macro regime module."""

import pytest
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from macro.regime import MacroRegimeModule
from data.fred_client import FREDClient


class TestFREDClient:
    def test_synthetic_fallback_returns_series(self):
        client = FREDClient(api_key="")  # no key → synthetic
        s = client.get_yield_spread(start="2020-01-01")
        assert isinstance(s, pd.Series)
        assert len(s) > 0

    def test_synthetic_carry_series(self):
        client = FREDClient(api_key="")
        jpy = client.get_jpy_usd(start="2020-01-01")
        aud = client.get_aud_usd(start="2020-01-01")
        assert len(jpy) > 0
        assert len(aud) > 0


class TestMacroRegime:
    def setup_method(self):
        self.module = MacroRegimeModule()

    def test_regime_series_has_expected_columns(self):
        df = self.module.build_regime_series("2020-01-01", "2022-12-31")
        for col in ["composite_score", "sizing_multiplier", "is_halted"]:
            assert col in df.columns

    def test_composite_score_range(self):
        df = self.module.build_regime_series("2020-01-01", "2022-12-31")
        assert df["composite_score"].max() <= 0
        assert df["composite_score"].min() >= -7

    def test_halted_when_score_le_minus_4(self):
        df = self.module.build_regime_series("2020-01-01", "2022-12-31")
        halted_rows = df[df["is_halted"]]
        if len(halted_rows) > 0:
            assert (halted_rows["composite_score"] <= -4).all()

    def test_sizing_multiplier_values(self):
        df = self.module.build_regime_series("2020-01-01", "2021-12-31")
        valid_mults = {0.0, 0.35, 0.65, 0.85, 1.0}
        unique = set(df["sizing_multiplier"].round(2).unique())
        assert unique.issubset(valid_mults)

    def test_snapshot_lookup(self):
        df = self.module.build_regime_series("2020-01-01", "2021-12-31")
        snap = self.module.get_snapshot(df, pd.Timestamp("2021-06-15"))
        assert isinstance(snap.composite_score, int)
        assert 0.0 <= snap.sizing_multiplier <= 1.0

    def test_full_size_in_benign_regime(self):
        """If no signals are adverse, composite=0 → 1.0x."""
        df = self.module.build_regime_series("2015-01-01", "2016-01-01")
        benign = df[df["composite_score"] == 0]
        if len(benign) > 0:
            assert (benign["sizing_multiplier"] == 1.0).all()
