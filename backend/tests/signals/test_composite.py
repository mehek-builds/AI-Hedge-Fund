"""Tests for composite.py — valuation_score, compute_composite, direction_for_composite."""
from decimal import Decimal

import pytest


class TestValuationScore:
    def test_none_eps_gap_gives_50(self):
        from app.signals.composite import valuation_score
        result = valuation_score(None, Decimal("1.0"))
        assert result == Decimal("50.0")

    def test_zero_max_eps_gap_gives_50(self):
        from app.signals.composite import valuation_score
        result = valuation_score(Decimal("0.5"), Decimal("0"))
        assert result == Decimal("50.0")

    def test_none_max_eps_gap_gives_50(self):
        from app.signals.composite import valuation_score
        result = valuation_score(Decimal("0.5"), None)
        assert result == Decimal("50.0")

    def test_eps_gap_equals_max_gives_0(self):
        from app.signals.composite import valuation_score
        # |eps_gap| == max_eps_gap → ratio = 1 → (1 - 1) * 100 = 0
        result = valuation_score(Decimal("1.0"), Decimal("1.0"))
        assert result == Decimal("0.00")

    def test_eps_gap_of_zero_gives_100(self):
        from app.signals.composite import valuation_score
        # |eps_gap| = 0 → ratio = 0 → (1 - 0) * 100 = 100
        result = valuation_score(Decimal("0"), Decimal("1.0"))
        assert result == Decimal("100.00")

    def test_half_gap_gives_50(self):
        from app.signals.composite import valuation_score
        # |eps_gap| = 0.5, max = 1.0 → ratio = 0.5 → score = 50
        result = valuation_score(Decimal("0.5"), Decimal("1.0"))
        assert result == Decimal("50.00")

    def test_negative_eps_gap_uses_abs(self):
        from app.signals.composite import valuation_score
        # negative gap should use abs
        result_pos = valuation_score(Decimal("0.3"), Decimal("1.0"))
        result_neg = valuation_score(Decimal("-0.3"), Decimal("1.0"))
        assert result_pos == result_neg

    def test_eps_gap_exceeds_max_clamps_to_0(self):
        from app.signals.composite import valuation_score
        # ratio > 1 → clamped to 1 → score = 0
        result = valuation_score(Decimal("2.0"), Decimal("1.0"))
        assert result == Decimal("0.00")

    def test_result_is_decimal(self):
        from app.signals.composite import valuation_score
        result = valuation_score(Decimal("0.2"), Decimal("1.0"))
        assert isinstance(result, Decimal)


class TestComputeComposite:
    def test_equal_components_returns_same(self):
        from app.signals.composite import compute_composite
        result = compute_composite(Decimal("60"), Decimal("60"), Decimal("60"))
        assert result == Decimal("60.0000")

    def test_arithmetic_mean(self):
        from app.signals.composite import compute_composite
        # (30 + 60 + 90) / 3 = 60.0000
        result = compute_composite(Decimal("30"), Decimal("60"), Decimal("90"))
        assert result == Decimal("60.0000")

    def test_result_rounded_to_4dp(self):
        from app.signals.composite import compute_composite
        # (10 + 20 + 30) / 3 = 20.0
        result = compute_composite(Decimal("10"), Decimal("20"), Decimal("30"))
        # Should have 4 decimal places
        assert str(result).endswith("0000") or "." in str(result)
        # More importantly: value is correct
        assert result == Decimal("20.0000")

    def test_non_round_mean_rounded_to_4dp(self):
        from app.signals.composite import compute_composite
        # (0 + 0 + 1) / 3 = 0.3333...
        result = compute_composite(Decimal("0"), Decimal("0"), Decimal("1"))
        assert result == Decimal("0.3333")

    def test_result_is_decimal(self):
        from app.signals.composite import compute_composite
        result = compute_composite(Decimal("50"), Decimal("50"), Decimal("50"))
        assert isinstance(result, Decimal)


class TestDirectionForComposite:
    def test_above_50_is_long(self):
        from app.signals.composite import direction_for_composite
        assert direction_for_composite(Decimal("60")) == "long"

    def test_below_50_is_short(self):
        from app.signals.composite import direction_for_composite
        assert direction_for_composite(Decimal("40")) == "short"

    def test_exactly_50_is_hold(self):
        from app.signals.composite import direction_for_composite
        assert direction_for_composite(Decimal("50")) == "hold"

    def test_50_0001_is_long(self):
        from app.signals.composite import direction_for_composite
        assert direction_for_composite(Decimal("50.0001")) == "long"

    def test_49_9999_is_short(self):
        from app.signals.composite import direction_for_composite
        assert direction_for_composite(Decimal("49.9999")) == "short"

    def test_100_is_long(self):
        from app.signals.composite import direction_for_composite
        assert direction_for_composite(Decimal("100")) == "long"

    def test_0_is_short(self):
        from app.signals.composite import direction_for_composite
        assert direction_for_composite(Decimal("0")) == "short"
