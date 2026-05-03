"""Tests for portfolio/caps.py — Mag-7 concentration cap and ERP compression cap (FR-4.3, FR-4.4)."""
from decimal import Decimal

import pytest


# ── apply_mag7_cap tests ───────────────────────────────────────────────────

def test_mag7_aapl_over_cap_is_capped():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("AAPL", Decimal("0.05"))
    assert decision.size_nav == Decimal("0.03")
    assert decision.was_capped is True
    assert "MAG7" in decision.reason


def test_mag7_aapl_under_cap_passes_through():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("AAPL", Decimal("0.025"))
    assert decision.size_nav == Decimal("0.025")
    assert decision.was_capped is False


def test_mag7_exactly_at_boundary_not_capped():
    from app.portfolio.caps import apply_mag7_cap
    # exactly 0.03 -> NOT capped (strict >)
    decision = apply_mag7_cap("NVDA", Decimal("0.03"))
    assert decision.size_nav == Decimal("0.03")
    assert decision.was_capped is False


def test_mag7_just_over_boundary_is_capped():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("AAPL", Decimal("0.0301"))
    assert decision.size_nav == Decimal("0.03")
    assert decision.was_capped is True


def test_non_mag7_symbol_passes_through():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("JPM", Decimal("0.10"))
    assert decision.size_nav == Decimal("0.10")
    assert decision.was_capped is False


def test_googl_is_mag7():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("GOOGL", Decimal("0.05"))
    assert decision.was_capped is True


def test_goog_is_mag7():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("GOOG", Decimal("0.05"))
    assert decision.was_capped is True


# ── apply_erp_cap tests ────────────────────────────────────────────────────

def test_erp_cap_applied_when_ep_below_tips():
    from app.portfolio.caps import apply_erp_cap
    # ep_yield=0.04 < tips_yield=0.05 -> apply 0.80 multiplier
    decision = apply_erp_cap(Decimal("0.10"), Decimal("0.04"), Decimal("0.05"))
    assert decision.size_nav == Decimal("0.10") * Decimal("0.80")
    assert decision.was_capped is True


def test_erp_cap_not_applied_when_ep_above_tips():
    from app.portfolio.caps import apply_erp_cap
    # ep_yield=0.06 > tips_yield=0.05 -> passthrough
    decision = apply_erp_cap(Decimal("0.10"), Decimal("0.06"), Decimal("0.05"))
    assert decision.size_nav == Decimal("0.10")
    assert decision.was_capped is False


def test_erp_cap_boundary_equal_not_capped():
    from app.portfolio.caps import apply_erp_cap
    # ep_yield == tips_yield -> NOT capped (strict <)
    decision = apply_erp_cap(Decimal("0.10"), Decimal("0.05"), Decimal("0.05"))
    assert decision.was_capped is False


# ── case-insensitivity test ────────────────────────────────────────────────

def test_mag7_lowercase_symbol_treated_as_mag7():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("aapl", Decimal("0.05"))
    assert decision.was_capped is True


# ── CapDecision structure tests ────────────────────────────────────────────

def test_cap_decision_is_frozen():
    from app.portfolio.caps import apply_mag7_cap, CapDecision
    decision = apply_mag7_cap("AAPL", Decimal("0.05"))
    assert isinstance(decision, CapDecision)
    with pytest.raises((AttributeError, TypeError)):
        decision.size_nav = Decimal("0.99")  # type: ignore[misc]


def test_uncapped_decision_has_empty_reason():
    from app.portfolio.caps import apply_mag7_cap
    decision = apply_mag7_cap("JPM", Decimal("0.10"))
    assert decision.reason == ""
