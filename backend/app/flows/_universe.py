"""S&P 500 universe helper — stub for plan 02-02 implementation.

Plan 02-02 will replace this with a full implementation that queries
sp500_constituents table for current active members.

For now, returns an empty list so that plan 02-04 flows can import
without errors. Tests monkeypatch this function directly.
"""
from __future__ import annotations


def current_sp500_universe() -> list[str]:
    """Return list of currently active S&P 500 tickers.

    Implemented in plan 02-02. This stub is a placeholder so plan 02-04
    flows can import without errors until 02-02 is merged.
    """
    return []
