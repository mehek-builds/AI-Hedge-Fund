"""Tests for completion-portfolio SLSQP optimizer (FR-4.5)."""
from decimal import Decimal

import pytest

from app.portfolio.completion import (
    COMPLETION_INSTRUMENTS,
    COMPLETION_WEIGHT,
    FF3_TARGETS,
    FF3_TOLERANCE,
    CompletionAllocation,
    optimize_completion_weights,
)


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

# Realistic IVE/IYR betas — targets lie within the convex hull so the optimizer
# can actually achieve them. Derived from typical ETF factor loadings where
# IVE (value tilt) and IYR (real-estate tilt) bracket the FF3 targets.
# Mkt-Rf targets: 0.985 in [0.97, 1.05] → achievable with ~85% IVE
# SMB targets: -0.155 in [-0.18, 0.08] → achievable with ~88% IVE
# HML targets: 0.025 in [-0.05, 0.10] → achievable with ~40% IVE
REALISTIC_BETAS = {
    "IVE": {"Mkt-Rf": 0.97, "SMB": -0.18, "HML": -0.05},
    "IYR": {"Mkt-Rf": 1.05, "SMB": 0.08, "HML": 0.10},
}

# "Perfect" fixture where IVE alone matches Mkt-Rf target exactly
# and IYR is tuned to match SMB/HML; any convex combination will be near target
PERFECT_BETAS = {
    "IVE": {"Mkt-Rf": 0.985, "SMB": -0.155, "HML": 0.025},
    "IYR": {"Mkt-Rf": 0.985, "SMB": -0.155, "HML": 0.025},
}


# ---------------------------------------------------------------------------
# Test 1: Near-zero objective when instruments match targets
# ---------------------------------------------------------------------------

def test_achieved_mkt_rf_within_tolerance_on_perfect_inputs():
    """When both instruments exactly match the FF3 targets, achieved Mkt-Rf
    should be within ±FF3_TOLERANCE of 0.985."""
    alloc = optimize_completion_weights(PERFECT_BETAS)
    assert abs(alloc.achieved_betas["Mkt-Rf"] - FF3_TARGETS["Mkt-Rf"]) <= FF3_TOLERANCE


# ---------------------------------------------------------------------------
# Test 2: Weights sum to exactly COMPLETION_WEIGHT (23%)
# ---------------------------------------------------------------------------

def test_weights_sum_to_completion_weight():
    """Weights dict values must sum to exactly 0.23 within 1e-6 tolerance."""
    alloc = optimize_completion_weights(REALISTIC_BETAS)
    total = alloc.weights["IVE"] + alloc.weights["IYR"]
    assert abs(float(total) - float(COMPLETION_WEIGHT)) < 1e-6


# ---------------------------------------------------------------------------
# Test 3: Individual weights are non-negative and bounded by COMPLETION_WEIGHT
# ---------------------------------------------------------------------------

def test_individual_weights_within_bounds():
    """Each weight must be >= 0 and <= COMPLETION_WEIGHT (0.23)."""
    alloc = optimize_completion_weights(REALISTIC_BETAS)
    for symbol in ("IVE", "IYR"):
        w = alloc.weights[symbol]
        assert w >= Decimal("0"), f"{symbol} weight {w} is negative"
        assert w <= COMPLETION_WEIGHT, f"{symbol} weight {w} exceeds COMPLETION_WEIGHT"


# ---------------------------------------------------------------------------
# Test 4: success flag True on feasible problem
# ---------------------------------------------------------------------------

def test_success_flag_true_on_feasible_problem():
    """SLSQP should converge on a feasible (realistic) problem."""
    alloc = optimize_completion_weights(REALISTIC_BETAS)
    assert alloc.success is True


# ---------------------------------------------------------------------------
# Test 5: Achieved betas within FF3_TOLERANCE on realistic inputs
# ---------------------------------------------------------------------------

def test_achieved_betas_within_tolerance_realistic():
    """On the plan's realistic IVE/IYR fixture, all three achieved betas
    must be within ±FF3_TOLERANCE of the corresponding target."""
    alloc = optimize_completion_weights(REALISTIC_BETAS)
    for factor, target in FF3_TARGETS.items():
        achieved = alloc.achieved_betas[factor]
        assert abs(achieved - target) <= FF3_TOLERANCE, (
            f"Factor {factor}: achieved={achieved:.4f}, target={target:.4f}, "
            f"tolerance={FF3_TOLERANCE}"
        )


# ---------------------------------------------------------------------------
# Test 6: Module constants
# ---------------------------------------------------------------------------

def test_completion_weight_constant():
    """COMPLETION_WEIGHT must equal Decimal('0.23')."""
    assert COMPLETION_WEIGHT == Decimal("0.23")


def test_completion_instruments_constant():
    """COMPLETION_INSTRUMENTS must be ('IVE', 'IYR')."""
    assert COMPLETION_INSTRUMENTS == ("IVE", "IYR")


# ---------------------------------------------------------------------------
# Test 7: FF3_TARGETS values
# ---------------------------------------------------------------------------

def test_ff3_targets_values():
    """FF3_TARGETS must contain exactly 0.985, -0.155, 0.025."""
    assert FF3_TARGETS["Mkt-Rf"] == 0.985
    assert FF3_TARGETS["SMB"] == -0.155
    assert FF3_TARGETS["HML"] == 0.025
    assert len(FF3_TARGETS) == 3


# ---------------------------------------------------------------------------
# Additional sanity checks
# ---------------------------------------------------------------------------

def test_completion_allocation_is_frozen_dataclass():
    """CompletionAllocation must be immutable (frozen dataclass)."""
    alloc = optimize_completion_weights(PERFECT_BETAS)
    with pytest.raises((AttributeError, TypeError)):
        alloc.success = False  # type: ignore[misc]


def test_weights_keys_are_ive_and_iyr():
    """The weights dict must have exactly the keys 'IVE' and 'IYR'."""
    alloc = optimize_completion_weights(REALISTIC_BETAS)
    assert set(alloc.weights.keys()) == {"IVE", "IYR"}
