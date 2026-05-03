"""Macro composite scorer and position-sizing multiplier (FR-4.1, FR-4.2).

Computes a 6-component macro composite score in [-6, 0] and maps it to
a sizing multiplier. All computations are Decimal-based, DB-free, and
deterministic — suitable for unit testing without any external dependencies.
"""
from decimal import Decimal
from typing import Optional

MACRO_BANDS: dict[tuple[int, int], Decimal] = {
    (0, -1): Decimal("1.0"),
    (-2, -3): Decimal("0.65"),
    (-4, -6): Decimal("0.25"),
}

COMPONENT_NAMES = ("yield_curve", "sahm", "lei", "ism_pmi", "hyg_lqd_spread", "jpy_aud_carry")

# Component thresholds — breach means deteriorating (-1); otherwise 0.
# yield_curve   : T10Y2Y; -1 if < 0 (inverted yield curve)
# sahm          : Sahm Rule Real-time indicator; -1 if >= 0.50
# lei           : Leading Economic Index 6m change; -1 if < 0
# ism_pmi       : Manufacturing employment (MANEMP) YoY; -1 if < 0
# hyg_lqd_spread: High-yield vs IG spread; -1 if > 4.5
# jpy_aud_carry : JPY/AUD carry; -1 if < 0


def score_component(name: str, value: Optional[Decimal]) -> int:
    """Return 0 or -1 for one macro component.

    Returns 0 if value is None (missing data is treated as neutral — no
    risk-on bias from missing data, per threat model T-04-01).

    Raises ValueError for unknown component names.
    """
    if name not in COMPONENT_NAMES:
        raise ValueError(f"Unknown macro component: {name!r}. Must be one of {COMPONENT_NAMES}")
    if value is None:
        return 0
    v = Decimal(value)
    if name == "yield_curve":
        return -1 if v < Decimal("0") else 0
    if name == "sahm":
        return -1 if v >= Decimal("0.50") else 0
    if name == "lei":
        return -1 if v < Decimal("0") else 0
    if name == "ism_pmi":
        return -1 if v < Decimal("0") else 0
    if name == "hyg_lqd_spread":
        return -1 if v > Decimal("4.5") else 0
    if name == "jpy_aud_carry":
        return -1 if v < Decimal("0") else 0
    return 0  # unreachable, but satisfy type checkers


def compute_macro_score(components: dict[str, Optional[Decimal]]) -> int:
    """Sum component scores across all 6 components; clamp to [-6, 0].

    Missing keys in *components* contribute 0 (not -1).
    """
    total = sum(
        score_component(name, components.get(name))
        for name in COMPONENT_NAMES
    )
    return max(-6, min(0, total))


def apply_sizing_multiplier(score: int) -> Decimal:
    """Map macro composite score to a position-sizing multiplier.

    Band lookup:
      score in {0, -1}       -> 1.0  (full size, macro neutral/mild)
      score in {-2, -3}      -> 0.65 (reduced size, macro deteriorating)
      score in {-4, -5, -6}  -> 0.25 (defensive, macro severely deteriorating)

    Raises ValueError for score outside [-6, 0].
    """
    if score > 0 or score < -6:
        raise ValueError(f"score {score} out of [-6, 0]")
    for (hi, lo), multiplier in MACRO_BANDS.items():
        if lo <= score <= hi:
            return multiplier
    # unreachable given validated score range
    raise ValueError(f"score {score} out of [-6, 0]")
