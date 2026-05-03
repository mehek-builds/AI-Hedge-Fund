"""Unit tests for market-implied EPS computation (FR-3.1)."""
from decimal import Decimal

import pytest


def test_compute_implied_eps_tech():
    """280 / 28.0 = 10.0000"""
    from app.signals.implied_eps import compute_implied_eps
    result = compute_implied_eps(Decimal("280.00"), "Tech")
    assert result == Decimal("10.0000")


def test_compute_implied_eps_healthcare():
    """180 / 18.0 = 10.0000"""
    from app.signals.implied_eps import compute_implied_eps
    result = compute_implied_eps(Decimal("180.00"), "Healthcare")
    assert result == Decimal("10.0000")


def test_compute_implied_eps_zero_price():
    from app.signals.implied_eps import compute_implied_eps
    result = compute_implied_eps(Decimal("0"), "Tech")
    assert result == Decimal("0")


def test_compute_implied_eps_unknown_sector_fallback():
    """100 / 18.0 (Other) = 5.5556 (rounded to 4dp)"""
    from app.signals.implied_eps import compute_implied_eps
    result = compute_implied_eps(Decimal("100"), "UnknownSector")
    assert result == Decimal("5.5556")


def test_compute_implied_eps_negative_price_raises():
    from app.signals.implied_eps import compute_implied_eps
    with pytest.raises(ValueError):
        compute_implied_eps(Decimal("-1"), "Tech")


def test_eps_gap_positive():
    """(10.0 - 8.0) / 8.0 = 0.25"""
    from app.signals.implied_eps import eps_gap
    result = eps_gap(Decimal("10.0"), Decimal("8.0"))
    assert result == Decimal("0.2500")


def test_eps_gap_zero_implied_returns_zero():
    from app.signals.implied_eps import eps_gap
    result = eps_gap(Decimal("10.0"), Decimal("0"))
    assert result == Decimal("0")


def test_eps_gap_none_actual_returns_none():
    from app.signals.implied_eps import eps_gap
    result = eps_gap(None, Decimal("8.0"))
    assert result is None


def test_compute_implied_eps_none_price_raises():
    from app.signals.implied_eps import compute_implied_eps
    with pytest.raises((ValueError, TypeError)):
        compute_implied_eps(None, "Tech")


def test_eps_gap_negative_gap():
    """(5.0 - 8.0) / 8.0 = -0.375 = -0.3750 (4dp)"""
    from app.signals.implied_eps import eps_gap
    result = eps_gap(Decimal("5.0"), Decimal("8.0"))
    assert result == Decimal("-0.3750")


def test_eps_gap_zero_actual():
    """(0.0 - 8.0) / 8.0 = -1.0"""
    from app.signals.implied_eps import eps_gap
    result = eps_gap(Decimal("0.0"), Decimal("8.0"))
    assert result == Decimal("-1.0000")
