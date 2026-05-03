"""Tests for portfolio/macro.py — macro composite scorer and sizing multiplier (FR-4.1, FR-4.2)."""
from decimal import Decimal

import pytest


# ── apply_sizing_multiplier tests ──────────────────────────────────────────

def test_score_zero_returns_1_0():
    from app.portfolio.macro import apply_sizing_multiplier
    assert apply_sizing_multiplier(0) == Decimal("1.0")


def test_score_minus_one_returns_1_0():
    from app.portfolio.macro import apply_sizing_multiplier
    assert apply_sizing_multiplier(-1) == Decimal("1.0")


def test_score_minus_two_returns_065():
    from app.portfolio.macro import apply_sizing_multiplier
    assert apply_sizing_multiplier(-2) == Decimal("0.65")


def test_score_minus_three_returns_065():
    from app.portfolio.macro import apply_sizing_multiplier
    assert apply_sizing_multiplier(-3) == Decimal("0.65")


def test_score_minus_four_returns_025():
    from app.portfolio.macro import apply_sizing_multiplier
    assert apply_sizing_multiplier(-4) == Decimal("0.25")


def test_score_minus_five_returns_025():
    from app.portfolio.macro import apply_sizing_multiplier
    assert apply_sizing_multiplier(-5) == Decimal("0.25")


def test_score_minus_six_returns_025():
    from app.portfolio.macro import apply_sizing_multiplier
    assert apply_sizing_multiplier(-6) == Decimal("0.25")


def test_score_positive_one_raises_value_error():
    from app.portfolio.macro import apply_sizing_multiplier
    with pytest.raises(ValueError):
        apply_sizing_multiplier(1)


def test_score_minus_seven_raises_value_error():
    from app.portfolio.macro import apply_sizing_multiplier
    with pytest.raises(ValueError):
        apply_sizing_multiplier(-7)


# ── compute_macro_score tests ──────────────────────────────────────────────

def test_all_six_negative_components_returns_minus_six():
    from app.portfolio.macro import compute_macro_score
    components = {
        "yield_curve": Decimal("-0.5"),
        "sahm": Decimal("0.60"),
        "lei": Decimal("-0.02"),
        "ism_pmi": Decimal("-0.01"),
        "hyg_lqd_spread": Decimal("5.0"),
        "jpy_aud_carry": Decimal("-0.01"),
    }
    assert compute_macro_score(components) == -6


def test_all_six_positive_components_returns_zero():
    from app.portfolio.macro import compute_macro_score
    components = {
        "yield_curve": Decimal("0.5"),
        "sahm": Decimal("0.10"),
        "lei": Decimal("0.05"),
        "ism_pmi": Decimal("0.02"),
        "hyg_lqd_spread": Decimal("2.0"),
        "jpy_aud_carry": Decimal("0.01"),
    }
    assert compute_macro_score(components) == 0


def test_three_negative_three_positive_returns_minus_three():
    from app.portfolio.macro import compute_macro_score
    components = {
        "yield_curve": Decimal("-0.5"),   # -1
        "sahm": Decimal("0.60"),           # -1
        "lei": Decimal("-0.02"),           # -1
        "ism_pmi": Decimal("0.02"),        # 0
        "hyg_lqd_spread": Decimal("2.0"),  # 0
        "jpy_aud_carry": Decimal("0.01"),  # 0
    }
    assert compute_macro_score(components) == -3


def test_missing_components_contribute_zero():
    from app.portfolio.macro import compute_macro_score
    # empty dict -> all missing -> all 0 -> score = 0
    assert compute_macro_score({}) == 0


# ── score_component threshold tests ───────────────────────────────────────

def test_yield_curve_negative_triggers_minus_one():
    from app.portfolio.macro import score_component
    assert score_component("yield_curve", Decimal("-0.01")) == -1


def test_yield_curve_zero_is_neutral():
    from app.portfolio.macro import score_component
    assert score_component("yield_curve", Decimal("0.0")) == 0


def test_sahm_at_threshold_triggers_minus_one():
    from app.portfolio.macro import score_component
    # 0.50 >= 0.50 -> -1
    assert score_component("sahm", Decimal("0.50")) == -1


def test_sahm_just_below_threshold_is_neutral():
    from app.portfolio.macro import score_component
    assert score_component("sahm", Decimal("0.49")) == 0


def test_score_component_unknown_name_raises():
    from app.portfolio.macro import score_component
    with pytest.raises(ValueError):
        score_component("unknown_series", Decimal("1.0"))


def test_score_component_none_value_returns_zero():
    from app.portfolio.macro import score_component
    assert score_component("yield_curve", None) == 0


def test_macro_bands_exported_with_correct_keys():
    from app.portfolio.macro import MACRO_BANDS
    assert (0, -1) in MACRO_BANDS
    assert (-2, -3) in MACRO_BANDS
    assert (-4, -6) in MACRO_BANDS
    assert MACRO_BANDS[(0, -1)] == Decimal("1.0")
    assert MACRO_BANDS[(-2, -3)] == Decimal("0.65")
    assert MACRO_BANDS[(-4, -6)] == Decimal("0.25")


def test_multiplier_returns_decimal_type():
    from app.portfolio.macro import apply_sizing_multiplier
    result = apply_sizing_multiplier(0)
    assert isinstance(result, Decimal)
