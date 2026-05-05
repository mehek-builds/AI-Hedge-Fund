"""Tests for portfolio position-sizing pipeline orchestrator.

Tests 1-10 cover the compute_position_size() function which chains:
  macro multiplier -> ERP cap -> Mag-7 cap -> stop-loss price
"""
import logging
from decimal import Decimal

import pytest

from app.portfolio.pipeline import PositionSizingResult, compute_position_size

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# All-neutral macro components (score = 0, multiplier = 1.0)
NEUTRAL_MACRO = {
    "yield_curve": Decimal("0.5"),   # positive -> 0
    "sahm": Decimal("0.10"),         # < 0.50 -> 0
    "lei": Decimal("1.0"),           # positive -> 0
    "ism_pmi": Decimal("1.0"),       # positive -> 0
    "hyg_lqd_spread": Decimal("3.0"), # <= 4.5 -> 0
    "jpy_aud_carry": Decimal("0.1"), # positive -> 0
}

# Macro components producing score = -3 (multiplier = 0.65)
# yield_curve=-0.1(-1), sahm=0.6(-1), lei=-0.1(-1) -> score=-3
MACRO_SCORE_MINUS3 = {
    "yield_curve": Decimal("-0.1"),  # < 0 -> -1
    "sahm": Decimal("0.60"),         # >= 0.5 -> -1
    "lei": Decimal("-0.5"),          # < 0 -> -1
    "ism_pmi": Decimal("1.0"),       # neutral
    "hyg_lqd_spread": Decimal("3.0"),
    "jpy_aud_carry": Decimal("0.1"),
}

# Macro components producing score = -5 (multiplier = 0.25)
# yield_curve=-1(-1), sahm=0.6(-1), lei=-1(-1), ism_pmi=-1(-1), hyg_lqd_spread=5(-1) -> -5
MACRO_SCORE_MINUS5 = {
    "yield_curve": Decimal("-0.5"),  # -1
    "sahm": Decimal("0.60"),         # -1
    "lei": Decimal("-1.0"),          # -1
    "ism_pmi": Decimal("-1.0"),      # -1
    "hyg_lqd_spread": Decimal("5.0"), # > 4.5 -> -1
    "jpy_aud_carry": Decimal("0.1"), # neutral
}

# Non-Mag-7 symbol
TSLA = "TSLA"
AAPL = "AAPL"

# ERP values where cap does NOT trigger (ep_yield >= real_tips_yield)
EP_NO_CAP = Decimal("0.06")
TIPS_NO_CAP = Decimal("0.03")

# ERP values where cap DOES trigger (ep_yield < real_tips_yield)
EP_CAP = Decimal("0.04")
TIPS_CAP = Decimal("0.05")

ENTRY_100 = Decimal("100")


# ---------------------------------------------------------------------------
# Test 1: Macro score 0, no caps, AAPL 0.02 NAV -> final_size=0.02
# ---------------------------------------------------------------------------

def test_no_caps_macro_neutral_aapl():
    """Score=0 gives multiplier=1.0; no ERP cap (ep>tips); AAPL at 0.02 -> not capped (<=MAG7_CAP)."""
    result = compute_position_size(
        symbol=AAPL,
        direction="long",
        naive_size_nav=Decimal("0.02"),
        entry_price=ENTRY_100,
        macro_components=NEUTRAL_MACRO,
        ep_yield=EP_NO_CAP,
        real_tips_yield=TIPS_NO_CAP,
    )
    assert result.final_size_nav == Decimal("0.02"), f"Got {result.final_size_nav}"
    assert result.mag7_capped is False
    assert result.erp_capped is False


# ---------------------------------------------------------------------------
# Test 2: Macro score -3, AAPL 0.02 -> final_size = 0.02 * 0.65 = 0.013
# ---------------------------------------------------------------------------

def test_macro_score_minus3_reduces_size():
    """Score=-3 gives multiplier=0.65; 0.02 * 0.65 = 0.013."""
    result = compute_position_size(
        symbol=TSLA,
        direction="long",
        naive_size_nav=Decimal("0.02"),
        entry_price=ENTRY_100,
        macro_components=MACRO_SCORE_MINUS3,
        ep_yield=EP_NO_CAP,
        real_tips_yield=TIPS_NO_CAP,
    )
    assert result.final_size_nav == Decimal("0.013"), f"Got {result.final_size_nav}"
    assert result.macro_score == -3
    assert result.macro_multiplier == Decimal("0.65")


# ---------------------------------------------------------------------------
# Test 3: Macro score -5, AAPL 0.02 -> final_size = 0.02 * 0.25 = 0.005
# ---------------------------------------------------------------------------

def test_macro_score_minus5_reduces_size():
    """Score=-5 gives multiplier=0.25; 0.02 * 0.25 = 0.005."""
    result = compute_position_size(
        symbol=TSLA,
        direction="long",
        naive_size_nav=Decimal("0.02"),
        entry_price=ENTRY_100,
        macro_components=MACRO_SCORE_MINUS5,
        ep_yield=EP_NO_CAP,
        real_tips_yield=TIPS_NO_CAP,
    )
    assert result.final_size_nav == Decimal("0.005"), f"Got {result.final_size_nav}"
    assert result.macro_score == -5
    assert result.macro_multiplier == Decimal("0.25")


# ---------------------------------------------------------------------------
# Test 4: AAPL 0.05, score=0, no ERP cap -> Mag-7 cap to 0.03
# ---------------------------------------------------------------------------

def test_mag7_cap_fires_for_aapl_above_three_percent():
    """AAPL at 0.05 > MAG7_CAP(0.03) -> capped to 0.03; mag7_capped=True."""
    result = compute_position_size(
        symbol=AAPL,
        direction="long",
        naive_size_nav=Decimal("0.05"),
        entry_price=ENTRY_100,
        macro_components=NEUTRAL_MACRO,
        ep_yield=EP_NO_CAP,
        real_tips_yield=TIPS_NO_CAP,
    )
    assert result.final_size_nav == Decimal("0.03"), f"Got {result.final_size_nav}"
    assert result.mag7_capped is True
    assert result.erp_capped is False


# ---------------------------------------------------------------------------
# Test 5: ERP cap fires for non-Mag7 with ep<tips
# ---------------------------------------------------------------------------

def test_erp_cap_fires_for_non_mag7():
    """ep=0.04 < tips=0.05; size=0.02 -> 0.02*0.80=0.016; erp_capped=True."""
    result = compute_position_size(
        symbol=TSLA,
        direction="long",
        naive_size_nav=Decimal("0.02"),
        entry_price=ENTRY_100,
        macro_components=NEUTRAL_MACRO,
        ep_yield=EP_CAP,
        real_tips_yield=TIPS_CAP,
    )
    assert result.final_size_nav == Decimal("0.016"), f"Got {result.final_size_nav}"
    assert result.erp_capped is True
    assert result.mag7_capped is False


# ---------------------------------------------------------------------------
# Test 6: Both caps: AAPL 0.05, ep<tips -> ERP first (0.04), then Mag-7 (0.03)
# ---------------------------------------------------------------------------

def test_both_caps_erp_then_mag7():
    """ERP applied first: 0.05*0.80=0.04; then Mag-7 cap: 0.04>0.03 -> 0.03.
    Both was_capped flags True; final=0.03."""
    result = compute_position_size(
        symbol=AAPL,
        direction="long",
        naive_size_nav=Decimal("0.05"),
        entry_price=ENTRY_100,
        macro_components=NEUTRAL_MACRO,
        ep_yield=EP_CAP,
        real_tips_yield=TIPS_CAP,
    )
    assert result.final_size_nav == Decimal("0.03"), f"Got {result.final_size_nav}"
    assert result.erp_capped is True
    assert result.mag7_capped is True


# ---------------------------------------------------------------------------
# Test 7: stop_loss_price for long entry=100 -> 92.00
# ---------------------------------------------------------------------------

def test_stop_loss_price_long():
    """Long entry=100; stop_loss_price = 100 * (1 - 0.08) = 92.00."""
    result = compute_position_size(
        symbol=TSLA,
        direction="long",
        naive_size_nav=Decimal("0.02"),
        entry_price=ENTRY_100,
        macro_components=NEUTRAL_MACRO,
        ep_yield=EP_NO_CAP,
        real_tips_yield=TIPS_NO_CAP,
    )
    assert result.stop_loss_price == Decimal("92.00"), f"Got {result.stop_loss_price}"


# ---------------------------------------------------------------------------
# Test 8: stop_loss_price for short entry=100 -> 108.00
# ---------------------------------------------------------------------------

def test_stop_loss_price_short():
    """Short entry=100; stop_loss_price = 100 * (1 + 0.08) = 108.00."""
    result = compute_position_size(
        symbol=TSLA,
        direction="short",
        naive_size_nav=Decimal("0.02"),
        entry_price=ENTRY_100,
        macro_components=NEUTRAL_MACRO,
        ep_yield=EP_NO_CAP,
        real_tips_yield=TIPS_NO_CAP,
    )
    assert result.stop_loss_price == Decimal("108.00"), f"Got {result.stop_loss_price}"


# ---------------------------------------------------------------------------
# Test 9: Constraint events logged when caps fire
# ---------------------------------------------------------------------------

def test_constraint_event_logged_when_mag7_cap_fires(caplog):
    """When Mag-7 cap fires, log.warning should include 'MAG7' in the message."""
    with caplog.at_level(logging.WARNING, logger="app.portfolio.pipeline"):
        compute_position_size(
            symbol=AAPL,
            direction="long",
            naive_size_nav=Decimal("0.05"),
            entry_price=ENTRY_100,
            macro_components=NEUTRAL_MACRO,
            ep_yield=EP_NO_CAP,
            real_tips_yield=TIPS_NO_CAP,
        )
    assert any("MAG7" in r.message for r in caplog.records), (
        f"Expected 'MAG7' in log records; got: {[r.message for r in caplog.records]}"
    )


def test_constraint_event_logged_when_erp_cap_fires(caplog):
    """When ERP cap fires, log.warning should include 'ERP' in the message."""
    with caplog.at_level(logging.WARNING, logger="app.portfolio.pipeline"):
        compute_position_size(
            symbol=TSLA,
            direction="long",
            naive_size_nav=Decimal("0.02"),
            entry_price=ENTRY_100,
            macro_components=NEUTRAL_MACRO,
            ep_yield=EP_CAP,
            real_tips_yield=TIPS_CAP,
        )
    assert any("ERP" in r.message for r in caplog.records), (
        f"Expected 'ERP' in log records; got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Test 10: Zero naive_size propagates through as final_size=0
# ---------------------------------------------------------------------------

def test_zero_naive_size_returns_zero_final():
    """When naive_size_nav=0, all multiplications produce 0; final_size_nav=0."""
    result = compute_position_size(
        symbol=TSLA,
        direction="long",
        naive_size_nav=Decimal("0"),
        entry_price=ENTRY_100,
        macro_components=NEUTRAL_MACRO,
        ep_yield=EP_NO_CAP,
        real_tips_yield=TIPS_NO_CAP,
    )
    assert result.final_size_nav == Decimal("0")
