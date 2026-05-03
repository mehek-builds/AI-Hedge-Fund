"""Sector hurdle + ROIC>WACC filters (FR-3.3, FR-3.4)."""
from decimal import Decimal
from typing import Tuple, TYPE_CHECKING

from app.signals.sectors import SECTOR_HURDLE

if TYPE_CHECKING:
    from app.models.earnings_events import EarningsEvent


WACC_PROXY = Decimal("0.10")          # constant 10% per Phase 3 spec
ROIC_REVENUE_FACTOR = Decimal("0.4")  # invested-capital proxy = revenue * 0.4

# Filter applies to Tech and Healthcare (biotech sits inside Healthcare in our SECTOR_MAP).
ROIC_FILTER_SECTORS = frozenset({"Tech", "Healthcare"})


def apply_sector_hurdle(quality_score: int, sector: str) -> Tuple[bool, str]:
    """Return (passed, reason). passed=False means signal should be suppressed."""
    hurdle = SECTOR_HURDLE.get(sector, SECTOR_HURDLE["Other"])
    if quality_score >= hurdle:
        return True, ""
    return False, f"quality_score {quality_score} < sector hurdle {hurdle} ({sector})"


def apply_roic_wacc_filter(event: "EarningsEvent", sector: str) -> Tuple[bool, str]:
    """Return (passed, reason). Only applies to Tech and Healthcare; passes others."""
    if sector not in ROIC_FILTER_SECTORS:
        return True, f"filter not applicable to {sector}"
    if (
        event.operating_income is None
        or event.revenue_actual is None
        or event.revenue_actual == 0
    ):
        return False, f"ROIC inputs missing for {sector}"
    invested_capital_proxy = Decimal(event.revenue_actual) * ROIC_REVENUE_FACTOR
    roic = Decimal(event.operating_income) / invested_capital_proxy
    if roic < WACC_PROXY:
        return False, f"ROIC {roic.quantize(Decimal('0.01'))} < WACC {WACC_PROXY} ({sector})"
    return True, ""
