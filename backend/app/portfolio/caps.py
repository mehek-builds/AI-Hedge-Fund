"""Mag-7 concentration cap and ERP compression cap (FR-4.3, FR-4.4).

Both functions return a CapDecision dataclass. Caller logs `CapDecision`
as a constraint event when was_capped is True. This module does NOT log
directly — logging responsibility belongs to the Plan 02 pipeline.
"""
from dataclasses import dataclass
from decimal import Decimal

MAG7: frozenset[str] = frozenset({"AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN"})
MAG7_CAP: Decimal = Decimal("0.03")
ERP_CAP_MULTIPLIER: Decimal = Decimal("0.80")


@dataclass(frozen=True)
class CapDecision:
    """Result of a cap check.

    Attributes:
        size_nav: Final position size as a fraction of NAV.
        was_capped: True when a constraint was applied.
        reason: Human-readable reason; empty string when was_capped is False.
    """
    size_nav: Decimal
    was_capped: bool
    reason: str  # empty string when was_capped=False


def apply_mag7_cap(symbol: str, size_nav: Decimal) -> CapDecision:
    """Enforce the 3% NAV concentration cap on Mag-7 positions.

    Uses strict `>` comparison: size_nav exactly equal to MAG7_CAP is not capped.
    Symbol lookup is case-insensitive.

    Returns a CapDecision. Caller logs when was_capped is True.
    """
    upper_symbol = symbol.upper()
    if upper_symbol in MAG7 and size_nav > MAG7_CAP:
        return CapDecision(
            size_nav=MAG7_CAP,
            was_capped=True,
            reason=f"MAG7 concentration cap: {upper_symbol} capped from {size_nav} to {MAG7_CAP} NAV",
        )
    return CapDecision(size_nav=size_nav, was_capped=False, reason="")


def apply_erp_cap(
    size_nav: Decimal,
    ep_yield: Decimal,
    real_tips_yield: Decimal,
) -> CapDecision:
    """Apply ERP compression cap when E/P yield falls below real TIPS 10Y yield.

    Uses strict `<` comparison: ep_yield equal to real_tips_yield does NOT trigger cap.

    Returns a CapDecision. Caller logs when was_capped is True.
    """
    if ep_yield < real_tips_yield:
        capped_size = size_nav * ERP_CAP_MULTIPLIER
        return CapDecision(
            size_nav=capped_size,
            was_capped=True,
            reason=(
                f"ERP compression cap: E/P {ep_yield} < real TIPS {real_tips_yield}; "
                f"size reduced by {ERP_CAP_MULTIPLIER} multiplier"
            ),
        )
    return CapDecision(size_nav=size_nav, was_capped=False, reason="")
