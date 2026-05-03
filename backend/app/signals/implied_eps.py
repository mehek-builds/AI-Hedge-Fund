"""Market-implied EPS computation (FR-3.1).

implied_eps = last_close_price / sector_median_forward_PE

This is NOT analyst consensus — it is what EPS *would need to be* to justify
the current market price at the sector's typical multiple. The eps_gap
between actual reported EPS and this implied EPS is the valuation signal.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.signals.sectors import SECTOR_FWD_PE


_FOUR_DP = Decimal("0.0001")


def compute_implied_eps(last_close: Decimal, sector: str) -> Decimal:
    """Return market-implied EPS = last_close / sector_median_fwd_pe.

    Raises ValueError if last_close < 0 or None. Unknown sector falls back to "Other".
    """
    if last_close is None:
        raise ValueError("last_close must not be None")
    if last_close < 0:
        raise ValueError(f"last_close must be >= 0, got {last_close}")
    if last_close == 0:
        return Decimal("0")
    fwd_pe = SECTOR_FWD_PE.get(sector, SECTOR_FWD_PE["Other"])
    return (Decimal(last_close) / fwd_pe).quantize(_FOUR_DP, rounding=ROUND_HALF_UP)


def eps_gap(eps_actual: Optional[Decimal], eps_implied: Decimal) -> Optional[Decimal]:
    """Return (eps_actual - eps_implied) / eps_implied, rounded to 4dp.

    Returns None if eps_actual is None. Returns Decimal('0') if eps_implied is 0.
    """
    if eps_actual is None:
        return None
    if eps_implied == 0:
        return Decimal("0")
    gap = (Decimal(eps_actual) - Decimal(eps_implied)) / Decimal(eps_implied)
    return gap.quantize(_FOUR_DP, rounding=ROUND_HALF_UP)
