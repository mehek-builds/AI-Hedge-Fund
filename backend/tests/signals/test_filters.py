"""Tests for filters.py — apply_sector_hurdle, apply_roic_wacc_filter."""
from decimal import Decimal
from types import SimpleNamespace

import pytest


def make_event(operating_income=None, revenue_actual=None):
    return SimpleNamespace(operating_income=operating_income, revenue_actual=revenue_actual)


class TestApplySectorHurdle:
    def test_tech_above_hurdle_passes(self):
        from app.signals.filters import apply_sector_hurdle
        passed, reason = apply_sector_hurdle(70, "Tech")
        assert passed is True
        assert reason == ""

    def test_tech_exactly_at_hurdle_passes(self):
        from app.signals.filters import apply_sector_hurdle
        # Tech hurdle = 60
        passed, reason = apply_sector_hurdle(60, "Tech")
        assert passed is True

    def test_tech_below_hurdle_suppressed(self):
        from app.signals.filters import apply_sector_hurdle
        passed, reason = apply_sector_hurdle(55, "Tech")
        assert passed is False
        assert "quality_score 55" in reason
        assert "sector hurdle 60" in reason
        assert "Tech" in reason

    def test_energy_above_hurdle_passes(self):
        from app.signals.filters import apply_sector_hurdle
        # Energy hurdle = 45
        passed, reason = apply_sector_hurdle(46, "Energy")
        assert passed is True
        assert reason == ""

    def test_healthcare_below_hurdle_suppressed(self):
        from app.signals.filters import apply_sector_hurdle
        # Healthcare hurdle = 55
        passed, reason = apply_sector_hurdle(54, "Healthcare")
        assert passed is False
        assert "Healthcare" in reason

    def test_financials_hurdle_is_50(self):
        from app.signals.filters import apply_sector_hurdle
        passed, _ = apply_sector_hurdle(50, "Financials")
        assert passed is True
        passed2, _ = apply_sector_hurdle(49, "Financials")
        assert passed2 is False

    def test_unknown_sector_uses_other_hurdle(self):
        from app.signals.filters import apply_sector_hurdle
        # Other hurdle = 45
        passed, _ = apply_sector_hurdle(45, "UnknownSector")
        assert passed is True
        passed2, _ = apply_sector_hurdle(44, "UnknownSector")
        assert passed2 is False


class TestApplyRoicWaccFilter:
    def test_tech_roic_below_wacc_suppressed(self):
        from app.signals.filters import apply_roic_wacc_filter
        # ROIC = 200 / (10000 * 0.4) = 200/4000 = 0.05 < 0.10
        event = make_event(operating_income=Decimal("200"), revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Tech")
        assert passed is False
        assert "ROIC" in reason
        assert "WACC" in reason
        assert "Tech" in reason

    def test_tech_roic_above_wacc_passes(self):
        from app.signals.filters import apply_roic_wacc_filter
        # ROIC = 800 / (10000 * 0.4) = 800/4000 = 0.20 > 0.10
        event = make_event(operating_income=Decimal("800"), revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Tech")
        assert passed is True
        assert reason == ""

    def test_tech_roic_exactly_at_wacc_passes(self):
        from app.signals.filters import apply_roic_wacc_filter
        # ROIC = 400 / (10000 * 0.4) = 400/4000 = 0.10 == WACC → pass (not strictly less)
        event = make_event(operating_income=Decimal("400"), revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Tech")
        assert passed is True

    def test_healthcare_roic_below_wacc_suppressed(self):
        from app.signals.filters import apply_roic_wacc_filter
        # ROIC = 200 / (10000 * 0.4) = 0.05 < 0.10
        event = make_event(operating_income=Decimal("200"), revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Healthcare")
        assert passed is False
        assert "Healthcare" in reason

    def test_energy_not_in_roic_filter_sectors_passes(self):
        from app.signals.filters import apply_roic_wacc_filter
        event = make_event(operating_income=Decimal("200"), revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Energy")
        assert passed is True
        assert "not applicable" in reason

    def test_financials_not_in_roic_filter_sectors_passes(self):
        from app.signals.filters import apply_roic_wacc_filter
        event = make_event(operating_income=Decimal("50"), revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Financials")
        assert passed is True

    def test_tech_missing_operating_income_suppressed(self):
        from app.signals.filters import apply_roic_wacc_filter
        event = make_event(operating_income=None, revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Tech")
        assert passed is False
        assert "missing" in reason.lower()

    def test_tech_missing_revenue_actual_suppressed(self):
        from app.signals.filters import apply_roic_wacc_filter
        event = make_event(operating_income=Decimal("200"), revenue_actual=None)
        passed, reason = apply_roic_wacc_filter(event, "Tech")
        assert passed is False
        assert "missing" in reason.lower()

    def test_tech_zero_revenue_suppressed(self):
        from app.signals.filters import apply_roic_wacc_filter
        event = make_event(operating_income=Decimal("200"), revenue_actual=Decimal("0"))
        passed, reason = apply_roic_wacc_filter(event, "Tech")
        assert passed is False
        assert "missing" in reason.lower()

    def test_consumer_passes_with_low_roic(self):
        from app.signals.filters import apply_roic_wacc_filter
        # Consumer not in ROIC filter sectors → always pass
        event = make_event(operating_income=Decimal("10"), revenue_actual=Decimal("10000"))
        passed, reason = apply_roic_wacc_filter(event, "Consumer")
        assert passed is True
