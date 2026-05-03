"""Tests for portfolio/risk.py — 8% stop-loss enforcement (FR-4.6)."""
from decimal import Decimal

import pytest


# ── stop_loss_triggered tests (long) ──────────────────────────────────────

def test_long_exactly_8_percent_drawdown_triggers():
    from app.portfolio.risk import stop_loss_triggered
    # (100 - 92) / 100 = 0.08 -> triggered
    assert stop_loss_triggered(Decimal("100"), Decimal("92.00"), "long") is True


def test_long_just_under_8_percent_does_not_trigger():
    from app.portfolio.risk import stop_loss_triggered
    # (100 - 92.01) / 100 = 0.0799 -> not triggered
    assert stop_loss_triggered(Decimal("100"), Decimal("92.01"), "long") is False


def test_long_over_8_percent_triggers():
    from app.portfolio.risk import stop_loss_triggered
    # (100 - 91.99) / 100 = 0.0801 -> triggered
    assert stop_loss_triggered(Decimal("100"), Decimal("91.99"), "long") is True


# ── stop_loss_triggered tests (short) ─────────────────────────────────────

def test_short_exactly_8_percent_move_triggers():
    from app.portfolio.risk import stop_loss_triggered
    # (108 - 100) / 100 = 0.08 -> triggered
    assert stop_loss_triggered(Decimal("100"), Decimal("108.00"), "short") is True


def test_short_just_under_8_percent_does_not_trigger():
    from app.portfolio.risk import stop_loss_triggered
    # (107.99 - 100) / 100 = 0.0799 -> not triggered
    assert stop_loss_triggered(Decimal("100"), Decimal("107.99"), "short") is False


def test_long_no_drawdown_does_not_trigger():
    from app.portfolio.risk import stop_loss_triggered
    assert stop_loss_triggered(Decimal("100"), Decimal("100"), "long") is False


def test_long_small_entry_exactly_8_percent_triggers():
    from app.portfolio.risk import stop_loss_triggered
    # entry=50, current=46: (50-46)/50 = 0.08 -> triggered
    assert stop_loss_triggered(Decimal("50"), Decimal("46"), "long") is True


# ── stop_loss_price tests ─────────────────────────────────────────────────

def test_stop_loss_price_long_entry_100():
    from app.portfolio.risk import stop_loss_price
    # 100 * (1 - 0.08) = 92.00
    result = stop_loss_price(Decimal("100"), "long")
    assert result == Decimal("92.00")


def test_stop_loss_price_short_entry_100():
    from app.portfolio.risk import stop_loss_price
    # 100 * (1 + 0.08) = 108.00
    result = stop_loss_price(Decimal("100"), "short")
    assert result == Decimal("108.00")


# ── invalid direction tests ───────────────────────────────────────────────

def test_stop_loss_price_invalid_direction_raises():
    from app.portfolio.risk import stop_loss_price
    with pytest.raises(ValueError):
        stop_loss_price(Decimal("100"), "hold")


def test_stop_loss_triggered_invalid_direction_raises():
    from app.portfolio.risk import stop_loss_triggered
    with pytest.raises(ValueError):
        stop_loss_triggered(Decimal("100"), Decimal("90"), "hold")


# ── entry_price validation ────────────────────────────────────────────────

def test_stop_loss_price_zero_entry_raises():
    from app.portfolio.risk import stop_loss_price
    with pytest.raises(ValueError):
        stop_loss_price(Decimal("0"), "long")


def test_stop_loss_price_negative_entry_raises():
    from app.portfolio.risk import stop_loss_price
    with pytest.raises(ValueError):
        stop_loss_price(Decimal("-10"), "long")


# ── independence / boundary tests ─────────────────────────────────────────

def test_stop_loss_is_independent_of_sizing_inputs():
    """Verify that stop_loss_triggered accepts only price/direction — no sizing state needed."""
    from app.portfolio.risk import stop_loss_triggered
    # Pass arbitrary valid prices and direction; function should work without other state
    result = stop_loss_triggered(Decimal("200"), Decimal("183.00"), "long")
    # (200 - 183) / 200 = 0.085 -> triggered
    assert result is True


def test_stop_loss_threshold_constant_exported():
    from app.portfolio.risk import STOP_LOSS_THRESHOLD
    assert STOP_LOSS_THRESHOLD == Decimal("0.08")
