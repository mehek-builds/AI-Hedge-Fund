"""Position sizing orchestrator (FR-4.1..FR-4.4, FR-4.6).

Chains macro multiplier -> ERP cap -> Mag-7 cap -> stop-loss price for one signal.

All computations are Decimal-based, DB-free, and stateless — suitable for unit
testing without any external dependencies (no SQLAlchemy, no Celery, no scipy).
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.portfolio.caps import apply_erp_cap, apply_mag7_cap
from app.portfolio.macro import apply_sizing_multiplier, compute_macro_score
from app.portfolio.risk import stop_loss_price as _stop_loss_price

log = logging.getLogger(__name__)

_QUANTIZE = Decimal("0.000001")


@dataclass(frozen=True)
class PositionSizingResult:
    """Output of compute_position_size — fully gated position for one signal.

    Attributes:
        symbol: Ticker symbol.
        direction: "long" or "short".
        final_size_nav: Final position size as fraction of NAV (after all gates).
        macro_score: Composite macro score in [-6, 0].
        macro_multiplier: Sizing multiplier applied (1.0, 0.65, or 0.25).
        erp_capped: True when ERP compression cap was applied.
        mag7_capped: True when Mag-7 concentration cap was applied.
        stop_loss_price: Absolute price level triggering stop-loss.
        constraint_events: Human-readable reasons for any caps applied.
    """
    symbol: str
    direction: str
    final_size_nav: Decimal
    macro_score: int
    macro_multiplier: Decimal
    erp_capped: bool
    mag7_capped: bool
    stop_loss_price: Decimal
    constraint_events: tuple[str, ...]


def compute_position_size(
    symbol: str,
    direction: str,                         # "long" or "short"
    naive_size_nav: Decimal,                # from Phase 3 SignalPayload (e.g. 0.02)
    entry_price: Decimal,
    macro_components: dict[str, Optional[Decimal]],
    ep_yield: Decimal,
    real_tips_yield: Decimal,
) -> PositionSizingResult:
    """Apply all risk gates to a naive signal size, returning a fully gated result.

    Order of operations (deterministic, stateless):
      1. compute_macro_score(macro_components)           -> int score in [-6, 0]
      2. apply_sizing_multiplier(score)                  -> Decimal multiplier
      3. size_after_macro = naive_size_nav * multiplier
      4. apply_erp_cap(size_after_macro, ep_yield, tips) -> CapDecision; log if capped
      5. apply_mag7_cap(symbol, erp_result.size_nav)     -> CapDecision; log if capped
      6. stop_loss_price(entry_price, direction)         -> trigger price
      7. Return PositionSizingResult
    """
    constraint_events: list[str] = []

    # Step 1-2: Macro score + multiplier
    macro_score = compute_macro_score(macro_components)
    macro_mult = apply_sizing_multiplier(macro_score)

    # Step 3: Apply macro multiplier
    size_after_macro = naive_size_nav * macro_mult

    # Step 4: ERP compression cap
    erp_decision = apply_erp_cap(size_after_macro, ep_yield, real_tips_yield)
    if erp_decision.was_capped:
        log.warning(
            "ERP cap applied: %s size %s -> %s reason=%s",
            symbol,
            size_after_macro,
            erp_decision.size_nav,
            erp_decision.reason,
        )
        constraint_events.append(erp_decision.reason)

    # Step 5: Mag-7 concentration cap
    mag7_decision = apply_mag7_cap(symbol, erp_decision.size_nav)
    if mag7_decision.was_capped:
        log.warning(
            "MAG7 cap applied: %s size %s -> %s reason=%s",
            symbol,
            erp_decision.size_nav,
            mag7_decision.size_nav,
            mag7_decision.reason,
        )
        constraint_events.append(mag7_decision.reason)

    # Step 6: Stop-loss price
    stop_price = _stop_loss_price(entry_price, direction)

    # Step 7: Final result (quantize to 6 dp)
    final_size = mag7_decision.size_nav.quantize(_QUANTIZE)

    return PositionSizingResult(
        symbol=symbol,
        direction=direction,
        final_size_nav=final_size,
        macro_score=macro_score,
        macro_multiplier=macro_mult,
        erp_capped=erp_decision.was_capped,
        mag7_capped=mag7_decision.was_capped,
        stop_loss_price=stop_price,
        constraint_events=tuple(constraint_events),
    )
