"""Risk Controls — position-level and portfolio-level enforcement.

Position-level:
  - Hard stop: -8% on any position → exit
  - Max single-position weight: 5% of NAV
  - No naked short options (equity-only enforced at RL action space level)

Portfolio-level:
  - Max gross exposure: 150%
  - Max net long: 80% of NAV
  - Sector concentration: no single GICS sector > 30% gross
  - Earnings event clustering: ≤20% NAV entering same earnings week
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List
from loguru import logger

from config import CONFIG


@dataclass
class PortfolioState:
    positions: Dict[str, float] = field(default_factory=dict)   # ticker → signed size (% NAV)
    sector_exposure: Dict[str, float] = field(default_factory=dict)  # sector → gross %
    earnings_week_entries: Dict[str, float] = field(default_factory=dict)  # week → % NAV entered


class RiskControls:
    """Enforces all position and portfolio-level risk rules from PRD §6."""

    def __init__(self):
        self._cfg = CONFIG.risk
        self._state = PortfolioState()

    # ------------------------------------------------------------------
    # Position-level checks
    # ------------------------------------------------------------------

    def clip_position_size(self, size: float) -> float:
        """Enforce max single-position weight (5% NAV)."""
        return float(np.clip(size, -self._cfg.max_position_weight, self._cfg.max_position_weight))

    def check_hard_stop(self, position_return: float) -> bool:
        """Return True if position should be exited immediately."""
        return position_return <= self._cfg.hard_stop_pct

    # ------------------------------------------------------------------
    # Portfolio-level checks
    # ------------------------------------------------------------------

    def can_enter(
        self,
        ticker: str,
        size: float,
        sector: str,
        announce_date: pd.Timestamp,
    ) -> tuple[bool, str]:
        """Return (allowed, reason) for a proposed new entry.

        Checks gross exposure, net long, sector concentration,
        and earnings week clustering limits.
        """
        current_gross = sum(abs(v) for v in self._state.positions.values())
        current_net   = sum(self._state.positions.values())
        current_sector_gross = self._state.sector_exposure.get(sector, 0.0)

        # Gross exposure
        if current_gross + abs(size) > self._cfg.max_gross_exposure:
            return False, f"Gross exposure limit: {current_gross + abs(size):.1%} > {self._cfg.max_gross_exposure:.1%}"

        # Net long
        if size > 0 and current_net + size > self._cfg.max_net_long:
            return False, f"Net long limit: {current_net + size:.1%} > {self._cfg.max_net_long:.1%}"

        # Sector concentration
        if current_sector_gross + abs(size) > self._cfg.max_sector_concentration:
            return False, (
                f"Sector {sector} concentration: "
                f"{current_sector_gross + abs(size):.1%} > {self._cfg.max_sector_concentration:.1%}"
            )

        # Earnings week clustering
        week_key = announce_date.strftime("%G-W%V")
        week_exposure = self._state.earnings_week_entries.get(week_key, 0.0)
        if week_exposure + abs(size) > self._cfg.max_earnings_week_pct:
            return False, (
                f"Earnings week clustering: "
                f"{week_exposure + abs(size):.1%} > {self._cfg.max_earnings_week_pct:.1%}"
            )

        return True, "OK"

    def register_entry(
        self,
        ticker: str,
        size: float,
        sector: str,
        announce_date: pd.Timestamp,
    ) -> None:
        """Register a new position in portfolio state."""
        self._state.positions[ticker] = size
        self._state.sector_exposure[sector] = (
            self._state.sector_exposure.get(sector, 0.0) + abs(size)
        )
        week_key = announce_date.strftime("%G-W%V")
        self._state.earnings_week_entries[week_key] = (
            self._state.earnings_week_entries.get(week_key, 0.0) + abs(size)
        )
        logger.debug(f"Position entered: {ticker} size={size:.2%} sector={sector}")

    def register_exit(self, ticker: str, sector: str) -> None:
        """Remove a closed position from portfolio state."""
        size = self._state.positions.pop(ticker, 0.0)
        current = self._state.sector_exposure.get(sector, 0.0)
        self._state.sector_exposure[sector] = max(0.0, current - abs(size))
        logger.debug(f"Position exited: {ticker} sector={sector}")

    # ------------------------------------------------------------------
    # Portfolio summary
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        positions = self._state.positions
        return {
            "n_positions":     len(positions),
            "gross_exposure":  sum(abs(v) for v in positions.values()),
            "net_long":        sum(positions.values()),
            "sector_exposure": dict(self._state.sector_exposure),
        }
