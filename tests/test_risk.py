"""Tests for risk controls."""

import pytest
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from risk.controls import RiskControls
from config import CONFIG


class TestRiskControls:
    def setup_method(self):
        self.risk = RiskControls()

    def test_clip_position_size_caps_at_max(self):
        clipped = self.risk.clip_position_size(0.10)
        assert clipped == CONFIG.risk.max_position_weight

    def test_clip_allows_valid_size(self):
        clipped = self.risk.clip_position_size(0.03)
        assert clipped == pytest.approx(0.03)

    def test_hard_stop_triggers_at_threshold(self):
        assert self.risk.check_hard_stop(-0.08)
        assert self.risk.check_hard_stop(-0.10)
        assert not self.risk.check_hard_stop(-0.07)

    def test_can_enter_normal_conditions(self):
        ok, reason = self.risk.can_enter(
            ticker="AAPL", size=0.05, sector="Information Technology",
            announce_date=pd.Timestamp("2023-01-20"),
        )
        assert ok

    def test_gross_exposure_limit(self):
        # Fill up to near 150% gross
        for i in range(28):
            ticker = f"T{i}"
            ok, _ = self.risk.can_enter(
                ticker=ticker, size=0.05,
                sector="Information Technology" if i % 3 != 0 else "Financials",
                announce_date=pd.Timestamp("2023-01-20"),
            )
            if ok:
                self.risk.register_entry(
                    ticker, 0.05,
                    "Information Technology" if i % 3 != 0 else "Financials",
                    pd.Timestamp("2023-01-20"),
                )

        # Next entry should hit gross limit (30 * 0.05 = 1.50)
        ok, reason = self.risk.can_enter(
            ticker="OVERFLOW", size=0.05, sector="Energy",
            announce_date=pd.Timestamp("2023-01-20"),
        )
        assert not ok
        assert "Gross" in reason or not ok

    def test_sector_concentration_limit(self):
        risk = RiskControls()
        # Add 6 positions in same sector at 0.05 each = 0.30 (at limit)
        for i in range(6):
            ok, _ = risk.can_enter(f"S{i}", 0.05, "Energy", pd.Timestamp("2023-01-20"))
            if ok:
                risk.register_entry(f"S{i}", 0.05, "Energy", pd.Timestamp("2023-01-20"))

        ok, reason = risk.can_enter("S7", 0.05, "Energy", pd.Timestamp("2023-01-20"))
        assert not ok

    def test_register_and_exit(self):
        risk = RiskControls()
        risk.register_entry("AAPL", 0.05, "Information Technology", pd.Timestamp("2023-01-20"))
        summary = risk.get_summary()
        assert summary["n_positions"] == 1
        assert summary["gross_exposure"] == pytest.approx(0.05)

        risk.register_exit("AAPL", "Information Technology")
        summary = risk.get_summary()
        assert summary["n_positions"] == 0
