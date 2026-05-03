"""Unit tests for the 4-component earnings quality scorer (FR-3.2)."""
from decimal import Decimal
from types import SimpleNamespace

import pytest


def make_event(
    revenue_actual=None,
    revenue_estimate=None,
    operating_income=None,
    share_count=None,
    guidance_direction=None,
):
    """Build a minimal EarningsEvent-like namespace for testing."""
    return SimpleNamespace(
        revenue_actual=revenue_actual,
        revenue_estimate=revenue_estimate,
        operating_income=operating_income,
        share_count=share_count,
        guidance_direction=guidance_direction,
    )


# ---------------------------------------------------------------------------
# QualityBreakdown dataclass structure
# ---------------------------------------------------------------------------

def test_quality_breakdown_has_required_fields():
    from app.signals.quality import QualityBreakdown
    bd = QualityBreakdown(
        revenue_surprise=25.0,
        margin_expansion=25.0,
        share_count_discipline=25.0,
        guidance_direction=25.0,
        total=100,
    )
    assert bd.revenue_surprise == 25.0
    assert bd.margin_expansion == 25.0
    assert bd.share_count_discipline == 25.0
    assert bd.guidance_direction == 25.0
    assert bd.total == 100


# ---------------------------------------------------------------------------
# All-good event → total >= 95
# ---------------------------------------------------------------------------

def test_all_good_event_total_gte_95():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("110"),
        revenue_estimate=Decimal("100"),
        operating_income=Decimal("20"),
        share_count=900,
        guidance_direction="up",
    )
    prior = make_event(
        revenue_actual=Decimal("100"),
        revenue_estimate=Decimal("95"),
        operating_income=Decimal("10"),
        share_count=1000,
        guidance_direction="flat",
    )
    bd = compute_quality_score(current, prior)
    assert bd.total >= 95


# ---------------------------------------------------------------------------
# All-bad event → total == 0
# ---------------------------------------------------------------------------

def test_all_bad_event_total_is_zero():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("90"),
        revenue_estimate=Decimal("100"),
        operating_income=Decimal("5"),
        share_count=1100,
        guidance_direction="down",
    )
    prior = make_event(
        revenue_actual=Decimal("100"),
        revenue_estimate=Decimal("100"),
        operating_income=Decimal("20"),
        share_count=1000,
        guidance_direction=None,
    )
    bd = compute_quality_score(current, prior)
    assert bd.total == 0


# ---------------------------------------------------------------------------
# Revenue surprise component
# ---------------------------------------------------------------------------

def test_revenue_surprise_10pct_cap():
    """10% surprise → full 25 pts."""
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("110"), revenue_estimate=Decimal("100"), guidance_direction=None)
    bd = compute_quality_score(current, None)
    assert bd.revenue_surprise == 25.0


def test_revenue_surprise_zero():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), guidance_direction=None)
    bd = compute_quality_score(current, None)
    assert bd.revenue_surprise == 0.0


def test_revenue_surprise_half_5pct():
    """5% surprise → 12.5 pts."""
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("105"), revenue_estimate=Decimal("100"), guidance_direction=None)
    bd = compute_quality_score(current, None)
    assert bd.revenue_surprise == pytest.approx(12.5, abs=0.01)


def test_revenue_surprise_estimate_zero():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("0"), guidance_direction=None)
    bd = compute_quality_score(current, None)
    assert bd.revenue_surprise == 0.0


def test_revenue_surprise_none_actual():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=None, revenue_estimate=Decimal("100"), guidance_direction=None)
    bd = compute_quality_score(current, None)
    assert bd.revenue_surprise == 0.0


def test_revenue_surprise_none_estimate():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=None, guidance_direction=None)
    bd = compute_quality_score(current, None)
    assert bd.revenue_surprise == 0.0


# ---------------------------------------------------------------------------
# Margin expansion component
# ---------------------------------------------------------------------------

def test_margin_expansion_5pp_up_full_score():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("100"),
        revenue_estimate=Decimal("100"),
        operating_income=Decimal("20"),
        guidance_direction=None,
    )
    prior = make_event(
        revenue_actual=Decimal("100"),
        operating_income=Decimal("15"),
    )
    bd = compute_quality_score(current, prior)
    assert bd.margin_expansion == 25.0


def test_margin_expansion_equal_margins_is_midpoint():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("100"),
        revenue_estimate=Decimal("100"),
        operating_income=Decimal("15"),
        guidance_direction=None,
    )
    prior = make_event(
        revenue_actual=Decimal("100"),
        operating_income=Decimal("15"),
    )
    bd = compute_quality_score(current, prior)
    assert bd.margin_expansion == pytest.approx(12.5, abs=0.01)


def test_margin_expansion_5pp_down_zero():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("100"),
        revenue_estimate=Decimal("100"),
        operating_income=Decimal("10"),
        guidance_direction=None,
    )
    prior = make_event(
        revenue_actual=Decimal("100"),
        operating_income=Decimal("15"),
    )
    bd = compute_quality_score(current, prior)
    assert bd.margin_expansion == pytest.approx(0.0, abs=1e-10)


def test_margin_expansion_with_none_operating_income():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("100"),
        revenue_estimate=Decimal("100"),
        operating_income=None,
        guidance_direction=None,
    )
    prior = make_event(
        revenue_actual=Decimal("100"),
        operating_income=Decimal("15"),
    )
    bd = compute_quality_score(current, prior)
    assert bd.margin_expansion == 0.0


def test_margin_expansion_with_prior_none():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("110"),
        revenue_estimate=Decimal("100"),
        guidance_direction="up",
    )
    bd = compute_quality_score(current, None)
    assert bd.margin_expansion == 0.0


# ---------------------------------------------------------------------------
# Share count discipline
# ---------------------------------------------------------------------------

def test_share_count_discipline_buyback():
    """share_count < prior.share_count → 25 pts"""
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), share_count=900, guidance_direction=None)
    prior = make_event(share_count=1000)
    bd = compute_quality_score(current, prior)
    assert bd.share_count_discipline == 25.0


def test_share_count_discipline_equal():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), share_count=1000, guidance_direction=None)
    prior = make_event(share_count=1000)
    bd = compute_quality_score(current, prior)
    assert bd.share_count_discipline == 0.0


def test_share_count_discipline_dilution():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), share_count=1100, guidance_direction=None)
    prior = make_event(share_count=1000)
    bd = compute_quality_score(current, prior)
    assert bd.share_count_discipline == 0.0


def test_share_count_discipline_none_current():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), share_count=None, guidance_direction=None)
    prior = make_event(share_count=1000)
    bd = compute_quality_score(current, prior)
    assert bd.share_count_discipline == 0.0


# ---------------------------------------------------------------------------
# Guidance direction
# ---------------------------------------------------------------------------

def test_guidance_up():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), guidance_direction="up")
    bd = compute_quality_score(current, None)
    assert bd.guidance_direction == 25.0


def test_guidance_flat():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), guidance_direction="flat")
    bd = compute_quality_score(current, None)
    assert bd.guidance_direction == 12.0


def test_guidance_down():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), guidance_direction="down")
    bd = compute_quality_score(current, None)
    assert bd.guidance_direction == 0.0


def test_guidance_withdrawn():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), guidance_direction="withdrawn")
    bd = compute_quality_score(current, None)
    assert bd.guidance_direction == 0.0


def test_guidance_none():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("100"), revenue_estimate=Decimal("100"), guidance_direction=None)
    bd = compute_quality_score(current, None)
    assert bd.guidance_direction == 0.0


# ---------------------------------------------------------------------------
# prior=None case
# ---------------------------------------------------------------------------

def test_prior_none_margin_and_share_are_zero():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("110"),
        revenue_estimate=Decimal("100"),
        guidance_direction="up",
    )
    bd = compute_quality_score(current, None)
    assert bd.margin_expansion == 0.0
    assert bd.share_count_discipline == 0.0
    # revenue_surprise (25) + guidance (25) = 50 total
    assert bd.total == 50


# ---------------------------------------------------------------------------
# Total is int and in [0, 100]
# ---------------------------------------------------------------------------

def test_total_is_int():
    from app.signals.quality import compute_quality_score
    current = make_event(revenue_actual=Decimal("105"), revenue_estimate=Decimal("100"), guidance_direction="flat")
    bd = compute_quality_score(current, None)
    assert isinstance(bd.total, int)


def test_total_in_range():
    from app.signals.quality import compute_quality_score
    current = make_event(
        revenue_actual=Decimal("200"),
        revenue_estimate=Decimal("100"),
        operating_income=Decimal("50"),
        share_count=500,
        guidance_direction="up",
    )
    prior = make_event(
        revenue_actual=Decimal("100"),
        operating_income=Decimal("10"),
        share_count=1000,
    )
    bd = compute_quality_score(current, prior)
    assert 0 <= bd.total <= 100
