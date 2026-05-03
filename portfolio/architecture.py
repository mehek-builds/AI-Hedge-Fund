"""Portfolio architecture controls — ERP, growth/value spread, Mag7, completion portfolio."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


MAG7: frozenset[str] = frozenset({"AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA"})

GROWTH_SECTORS: frozenset[str] = frozenset({
    "Information Technology", "Consumer Discretionary", "Communication Services"
})


@dataclass
class ERPState:
    earnings_yield: float       # S&P 500 E/P
    real_10y_yield: float       # TIPS 10Y (FRED DFII10)
    erp_spread: float           # earnings_yield - real_10y_yield
    erp_compressed: bool        # spread < 0
    global_size_cap: float      # 0.8 if compressed else 1.0


@dataclass
class GrowthValueState:
    vug_pe: float
    vtv_pe: float
    ratio: float
    stretched: bool             # ratio > 2.0


@dataclass
class CompletionResult:
    active_betas: dict[str, float]
    target_betas: dict[str, float]
    deviations: dict[str, float]
    recommended_etf: str
    sleeve_pct_nav: float
    max_deviation: float


@dataclass
class ArchCheckResult:
    allowed: bool
    reason: str
    effective_size_cap: float   # product of all caps


class ERPMonitor:
    def compute(self, earnings_yield: float, real_10y_yield: float) -> ERPState:
        spread = earnings_yield - real_10y_yield
        compressed = spread < 0
        return ERPState(
            earnings_yield=earnings_yield,
            real_10y_yield=real_10y_yield,
            erp_spread=spread,
            erp_compressed=compressed,
            global_size_cap=0.8 if compressed else 1.0,
        )


class GrowthValueMonitor:
    def __init__(self, stretched_threshold: float = 2.0):
        self._threshold = stretched_threshold

    def compute(self, vug_pe: float, vtv_pe: float) -> GrowthValueState:
        ratio = vug_pe / vtv_pe if vtv_pe > 0 else 0.0
        return GrowthValueState(vug_pe=vug_pe, vtv_pe=vtv_pe, ratio=ratio, stretched=ratio > self._threshold)

    def adjusted_threshold(self, sector: str, base_threshold: float, state: GrowthValueState) -> float:
        if state.stretched and sector in GROWTH_SECTORS:
            return base_threshold + 0.25
        return base_threshold


class CompletionPortfolio:
    """Weekly FF5 factor neutralization via passive ETF sleeve."""

    _TARGET = {"mkt_rf": 1.0, "smb": 0.0, "hml": 0.0, "rmw": 0.0, "cma": 0.0}
    _ETF_FACTOR_PROXY = {
        "SPY": {"mkt_rf": 1.0, "smb": 0.0, "hml": 0.05, "rmw": 0.0, "cma": 0.0},
        "IVV": {"mkt_rf": 1.0, "smb": 0.0, "hml": 0.04, "rmw": 0.0, "cma": 0.0},
        "VTI": {"mkt_rf": 1.0, "smb": 0.10, "hml": 0.02, "rmw": 0.0, "cma": 0.0},
    }

    def compute(self, active_betas: dict[str, float]) -> CompletionResult:
        deviations = {f: self._TARGET[f] - active_betas.get(f, 0.0) for f in self._TARGET}
        max_dev = max(abs(v) for v in deviations.values())

        # Pick ETF that best reduces largest deviation (simplified: always SPY for mkt_rf dominance)
        recommended = "VTI" if deviations.get("smb", 0) > 0.1 else "SPY"

        # Sleeve size proportional to total deviation magnitude
        total_dev = sum(abs(v) for v in deviations.values())
        sleeve_pct = min(float(np.clip(total_dev * 0.1, 0.0, 0.20)), 0.20)

        return CompletionResult(
            active_betas=active_betas,
            target_betas=self._TARGET.copy(),
            deviations=deviations,
            recommended_etf=recommended,
            sleeve_pct_nav=sleeve_pct,
            max_deviation=max_dev,
        )


class PortfolioArchitectureController:
    """Combines all architecture checks into a single entry gate."""

    def __init__(
        self,
        mag7_per_name_cap: float = 0.03,
        mag7_signal_floor: float = 1.5,
        mag7_quality_floor: float = 0.65,
        mag7_aggregate_cap: float = 0.12,
        erp_compression_cap: float = 0.8,
        gv_stretched_threshold: float = 2.0,
        gv_signal_adjustment: float = 0.25,
        max_position_pct: float = 0.05,
        max_sector_pct: float = 0.30,
    ):
        self._mag7_per_name_cap = mag7_per_name_cap
        self._mag7_signal_floor = mag7_signal_floor
        self._mag7_quality_floor = mag7_quality_floor
        self._mag7_aggregate_cap = mag7_aggregate_cap
        self._erp_compression_cap = erp_compression_cap
        self._gv_threshold = gv_stretched_threshold
        self._gv_adjustment = gv_signal_adjustment
        self._max_position_pct = max_position_pct
        self._max_sector_pct = max_sector_pct
        self.erp_monitor = ERPMonitor()
        self.gv_monitor = GrowthValueMonitor(gv_stretched_threshold)
        self.completion = CompletionPortfolio()

    def check_entry(
        self,
        ticker: str,
        sector: str,
        signal_composite: float,
        quality_score: float,
        direction: str,             # 'long' | 'short'
        nav: float,
        sector_nav: float,
        mag7_total_nav: float,
        erp_compressed: bool,
        gv_stretched: bool,
        macro_score: int,
        macro_halted: bool,
    ) -> ArchCheckResult:
        size_cap = 1.0

        if macro_halted:
            return ArchCheckResult(allowed=False, reason="macro_halted", effective_size_cap=0.0)

        is_mag7 = ticker in MAG7

        # Mag7 short block
        if is_mag7 and direction == "short":
            return ArchCheckResult(allowed=False, reason="mag7_no_short", effective_size_cap=0.0)

        # Mag7 signal/quality floor
        if is_mag7:
            if abs(signal_composite) < self._mag7_signal_floor:
                return ArchCheckResult(allowed=False, reason="mag7_signal_below_floor", effective_size_cap=0.0)
            if quality_score < self._mag7_quality_floor:
                return ArchCheckResult(allowed=False, reason="mag7_quality_below_floor", effective_size_cap=0.0)

        # Mag7 aggregate cap
        if is_mag7 and nav > 0 and (mag7_total_nav / nav) >= self._mag7_aggregate_cap:
            return ArchCheckResult(allowed=False, reason="mag7_aggregate_cap", effective_size_cap=0.0)

        # Sector concentration
        if nav > 0 and (sector_nav / nav) >= self._max_sector_pct:
            return ArchCheckResult(allowed=False, reason="sector_concentration", effective_size_cap=0.0)

        # ERP compression cap
        if erp_compressed:
            size_cap *= self._erp_compression_cap

        # GV stretch: tighten threshold in growth sectors (not a block, handled upstream)

        return ArchCheckResult(allowed=True, reason="ok", effective_size_cap=size_cap)

    def get_position_cap(
        self, ticker: str, is_mag7: bool, erp_compressed: bool, macro_mult: float
    ) -> float:
        base = self._mag7_per_name_cap if is_mag7 else self._max_position_pct
        erp_factor = self._erp_compression_cap if erp_compressed else 1.0
        return base * erp_factor * macro_mult
