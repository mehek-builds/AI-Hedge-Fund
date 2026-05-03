"""Mixture-of-Experts meta-controller: 3 regime specialists + softmax blending."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import numpy as np


class Regime(str, Enum):
    EXPANSION = "expansion"
    CAUTION = "caution"
    CRISIS = "crisis"


@dataclass
class RegimeWeights:
    expansion: float
    caution: float
    crisis: float

    def as_array(self) -> np.ndarray:
        return np.array([self.expansion, self.caution, self.crisis], dtype=np.float32)

    def dominant(self) -> Regime:
        idx = int(np.argmax(self.as_array()))
        return [Regime.EXPANSION, Regime.CAUTION, Regime.CRISIS][idx]


@dataclass
class MoEAction:
    entry_size: float    # blended entry size in [0, 1]
    hold_bin: int        # blended hold duration bin index
    weights: RegimeWeights
    dominant_regime: Regime


class RegimeSpecialist:
    """Wraps a SACAgent with regime-specific action scaling."""

    def __init__(self, regime: Regime, entry_scale: float, hold_shift: int = 0) -> None:
        self.regime = regime
        self.entry_scale = entry_scale   # multiplicative cap on entry_size
        self.hold_shift = hold_shift     # bin offset for hold duration

    def adjust(self, entry: float, hold_bin: int, n_bins: int) -> tuple[float, int]:
        adj_entry = min(entry * self.entry_scale, 1.0)
        adj_hold = int(np.clip(hold_bin + self.hold_shift, 0, n_bins - 1))
        return adj_entry, adj_hold


# Default specialist parameterisation (overridable)
_SPECIALISTS = {
    Regime.EXPANSION: RegimeSpecialist(Regime.EXPANSION, entry_scale=1.0, hold_shift=0),
    Regime.CAUTION:   RegimeSpecialist(Regime.CAUTION,   entry_scale=0.65, hold_shift=-1),
    Regime.CRISIS:    RegimeSpecialist(Regime.CRISIS,    entry_scale=0.35, hold_shift=-2),
}


class MoEController:
    """
    Blends three regime-specialist SAC actions using softmax weights derived
    from the macro composite score.

    macro_score ∈ {0, -1, -2, -3} maps to expansion/caution/crisis logits.
    VIX optionally sharpens the caution/crisis weight.
    """

    _SCORE_LOGITS = {
        0:  np.array([2.0,  0.0, -2.0]),   # expansion dominant
        -1: np.array([0.5,  1.5, -1.0]),   # caution mild
        -2: np.array([-1.0, 1.0,  1.0]),   # caution/crisis split
        -3: np.array([-2.0, 0.0,  2.0]),   # crisis dominant
    }
    _DEFAULT_LOGITS = np.array([0.0, 0.0, 0.0])

    def __init__(
        self,
        n_bins: int = 7,
        specialists: dict[Regime, RegimeSpecialist] | None = None,
        temperature: float = 1.0,
    ) -> None:
        self._n_bins = n_bins
        self._specialists = specialists or _SPECIALISTS
        self._temperature = temperature

    def _logits(self, macro_score: int, vix: float | None) -> np.ndarray:
        logits = self._SCORE_LOGITS.get(macro_score, self._DEFAULT_LOGITS).copy()
        if vix is not None and vix > 30.0:
            # Increase crisis/caution weight proportionally above VIX=30
            bonus = min((vix - 30.0) / 20.0, 1.0)
            logits[1] += bonus * 0.5
            logits[2] += bonus * 1.0
        return logits / self._temperature

    def weights(self, macro_score: int, vix: float | None = None) -> RegimeWeights:
        logits = self._logits(macro_score, vix)
        e = np.exp(logits - logits.max())
        w = e / e.sum()
        return RegimeWeights(expansion=float(w[0]), caution=float(w[1]), crisis=float(w[2]))

    def blend(
        self,
        raw_entries: dict[Regime, float],
        raw_holds: dict[Regime, int],
        macro_score: int,
        vix: float | None = None,
    ) -> MoEAction:
        """
        Args:
            raw_entries: per-regime entry_size from each specialist's SAC agent
            raw_holds:   per-regime hold_bin from each specialist's SAC agent
            macro_score: 0 / -1 / -2 / -3
            vix:         optional VIX override for weight sharpening
        """
        rw = self.weights(macro_score, vix)
        w = rw.as_array()

        regimes = [Regime.EXPANSION, Regime.CAUTION, Regime.CRISIS]
        adj_entries = []
        adj_holds = []
        for i, r in enumerate(regimes):
            spec = self._specialists[r]
            ae, ah = spec.adjust(raw_entries[r], raw_holds[r], self._n_bins)
            adj_entries.append(ae)
            adj_holds.append(ah)

        blended_entry = float(np.dot(w, adj_entries))
        blended_hold = int(round(float(np.dot(w, adj_holds))))
        blended_hold = int(np.clip(blended_hold, 0, self._n_bins - 1))

        return MoEAction(
            entry_size=blended_entry,
            hold_bin=blended_hold,
            weights=rw,
            dominant_regime=rw.dominant(),
        )
