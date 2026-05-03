"""4-component earnings quality decomposition (FR-3.2).

Score is 0–100, with four 25-point components:
  1. Revenue surprise:        (actual - estimate) / abs(estimate)  → 0–25
  2. Margin expansion:        op_margin_current vs op_margin_prior → 0–25
  3. Share count discipline:  current.share_count < prior          → 25 / 0
  4. Guidance direction:      up=25, flat=12, else 0               → 0–25
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.earnings_events import EarningsEvent


@dataclass(frozen=True)
class QualityBreakdown:
    revenue_surprise: float            # 0..25
    margin_expansion: float            # 0..25
    share_count_discipline: float      # 0..25
    guidance_direction: float          # 0..25
    total: int                         # 0..100, rounded


def _revenue_surprise_component(actual: Optional[Decimal], estimate: Optional[Decimal]) -> float:
    if actual is None or estimate is None or estimate <= 0:
        return 0.0
    ratio = float((Decimal(actual) - Decimal(estimate)) / abs(Decimal(estimate)))
    if ratio <= 0:
        return 0.0
    # Cap at 10% surprise → full 25 pts. Linear in between.
    capped = min(ratio / 0.10, 1.0)
    return 25.0 * capped


def _operating_margin(event: "EarningsEvent") -> Optional[float]:
    if event.operating_income is None or event.revenue_actual is None or event.revenue_actual == 0:
        return None
    return float(Decimal(event.operating_income) / Decimal(event.revenue_actual))


def _margin_expansion_component(current: "EarningsEvent", prior: Optional["EarningsEvent"]) -> float:
    if prior is None:
        return 0.0
    cur_m = _operating_margin(current)
    prior_m = _operating_margin(prior)
    if cur_m is None or prior_m is None:
        return 0.0
    delta_pp = (cur_m - prior_m) * 100.0  # percentage points
    # Map [-5pp, +5pp] linearly onto [0, 25]; clamp outside.
    if delta_pp >= 5.0:
        return 25.0
    if delta_pp <= -5.0:
        return 0.0
    return 12.5 + (delta_pp / 5.0) * 12.5


def _share_count_component(current: "EarningsEvent", prior: Optional["EarningsEvent"]) -> float:
    if prior is None or current.share_count is None or prior.share_count is None:
        return 0.0
    return 25.0 if current.share_count < prior.share_count else 0.0


def _guidance_component(direction: Optional[str]) -> float:
    if direction == "up":
        return 25.0
    if direction == "flat":
        return 12.0
    return 0.0  # 'down', 'withdrawn', 'none', None


def compute_quality_score(
    current: "EarningsEvent",
    prior: Optional["EarningsEvent"],
) -> QualityBreakdown:
    """Return the 4-component quality breakdown (0–100) for the given event."""
    rs = _revenue_surprise_component(current.revenue_actual, current.revenue_estimate)
    me = _margin_expansion_component(current, prior)
    sc = _share_count_component(current, prior)
    gd = _guidance_component(current.guidance_direction)
    total = round(rs + me + sc + gd)
    return QualityBreakdown(
        revenue_surprise=rs,
        margin_expansion=me,
        share_count_discipline=sc,
        guidance_direction=gd,
        total=total,
    )
