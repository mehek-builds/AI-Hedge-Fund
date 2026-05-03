"""Sector EPS hurdle rates — calibrates minimum surprise for actionability."""

from __future__ import annotations

SECTOR_HURDLES: dict[str, float] = {
    "Information Technology": 0.0025,
    "Consumer Discretionary": 0.0020,
    "Health Care": 0.0010,
    "Industrials": 0.0,
    "Financials": -0.0010,
    "Energy": -0.0015,
    "Materials": -0.0015,
    "Utilities": -0.0005,
    "Real Estate": -0.0005,
    "Communication Services": 0.0010,
    "Consumer Staples": 0.0,
}

_DEFAULT_HURDLE = 0.0


def get_hurdle(sector: str) -> float:
    return SECTOR_HURDLES.get(sector, _DEFAULT_HURDLE)


def passes_hurdle(signal_composite: float, sector: str, global_min: float = 1.0) -> bool:
    """Return True if the signal exceeds both the global minimum and sector hurdle."""
    hurdle = get_hurdle(sector)
    effective_min = global_min + hurdle
    return abs(signal_composite) >= effective_min
