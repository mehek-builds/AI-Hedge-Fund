"""Three-axis composite scorer (FR-3.5)."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

_FOUR_DP = Decimal("0.0001")
_TWO_DP = Decimal("0.01")


def valuation_score(
    eps_gap_value: Optional[Decimal],
    max_eps_gap_in_cohort: Optional[Decimal],
) -> Decimal:
    """0-100 valuation score. Larger |eps_gap| → lower score (more mispriced).

    Returns Decimal('50.0') when eps_gap_value or max_eps_gap_in_cohort is None or zero.
    """
    if eps_gap_value is None or max_eps_gap_in_cohort is None or max_eps_gap_in_cohort == 0:
        return Decimal("50.0")
    ratio = abs(Decimal(eps_gap_value)) / abs(Decimal(max_eps_gap_in_cohort))
    if ratio > 1:
        ratio = Decimal("1")
    return ((Decimal("1") - ratio) * Decimal("100")).quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def compute_composite(
    valuation: Decimal,
    quality: Decimal,
    momentum: Decimal,
) -> Decimal:
    """Arithmetic mean of three axes, each in [0, 100]. Result rounded to 4dp."""
    total = (Decimal(valuation) + Decimal(quality) + Decimal(momentum)) / Decimal("3")
    return total.quantize(_FOUR_DP, rounding=ROUND_HALF_UP)


def direction_for_composite(composite: Decimal) -> str:
    """Map composite to {'long','short','hold'}."""
    if composite > Decimal("50"):
        return "long"
    if composite < Decimal("50"):
        return "short"
    return "hold"
