"""8% stop-loss enforcement (FR-4.6).

Stop-loss is enforced independently of RL sizing recommendations (FR-4.6).
This module has no dependency on position sizing — it only takes
entry/current prices and direction.

All computations use Decimal arithmetic for exact boundary semantics.
"""
from decimal import Decimal

STOP_LOSS_THRESHOLD: Decimal = Decimal("0.08")

_VALID_DIRECTIONS = frozenset({"long", "short"})


def _validate_entry_price(entry_price: Decimal) -> None:
    if entry_price <= Decimal("0"):
        raise ValueError(f"entry_price must be positive, got {entry_price}")


def _validate_direction(direction: str) -> None:
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(
            f"direction must be 'long' or 'short', got {direction!r}"
        )


def stop_loss_price(entry_price: Decimal, direction: str) -> Decimal:
    """Compute the absolute price level at which the stop-loss triggers.

    long:  entry * (1 - 0.08)
    short: entry * (1 + 0.08)
    """
    _validate_entry_price(entry_price)
    _validate_direction(direction)
    if direction == "long":
        return entry_price * (Decimal("1") - STOP_LOSS_THRESHOLD)
    # direction == "short"
    return entry_price * (Decimal("1") + STOP_LOSS_THRESHOLD)


def stop_loss_triggered(
    entry_price: Decimal,
    current_price: Decimal,
    direction: str,
) -> bool:
    """Return True when the drawdown from entry meets or exceeds 8%.

    long:  drawdown = (entry - current) / entry; trigger iff >= 0.08
    short: drawdown = (current - entry) / entry; trigger iff >= 0.08

    Uses `>=` so that exactly 8% drawdown triggers (FR-4.6 spec: "triggers
    at exactly 8%"). Computed entirely in Decimal — no floating-point rounding.
    """
    _validate_entry_price(entry_price)
    _validate_direction(direction)
    if direction == "long":
        drawdown = (entry_price - current_price) / entry_price
    else:
        drawdown = (current_price - entry_price) / entry_price
    return drawdown >= STOP_LOSS_THRESHOLD
