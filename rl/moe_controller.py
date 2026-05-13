"""Mixture-of-Experts meta-controller: regime-weighted blend of all 5 SAC agents."""

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


class MoEController:
    """
    Blends outputs from all 5 SAC agents using softmax regime weights derived
    from the macro composite score (FR-5.5).

    macro_score in {0, -1, -2, -3, -4, -5, -6} maps to expansion/caution/crisis logits.
    VIX optionally sharpens the caution/crisis weight.

    Agent-to-regime bucket assignment (RESEARCH.md Pattern 3 / A3):
        agents 0, 1  ->  expansion bucket
        agents 2, 3  ->  caution bucket
        agent  4     ->  crisis bucket
    """

    _SCORE_LOGITS = {
        0:  np.array([2.0,  0.0, -2.0]),   # expansion dominant
        -1: np.array([0.5,  1.5, -1.0]),   # caution mild
        -2: np.array([-1.0, 1.0,  1.0]),   # caution/crisis split
        -3: np.array([-2.0, 0.0,  2.0]),   # crisis emerging
        -4: np.array([-3.0, -0.5, 2.5]),   # crisis dominant
        -5: np.array([-3.5, -1.0, 3.0]),   # deep crisis
        -6: np.array([-4.0, -1.5, 3.5]),   # tail crisis
    }
    _DEFAULT_LOGITS = np.array([0.0, 0.0, 0.0])

    # Fixed assignment per RESEARCH.md Pattern 3 / A3:
    #   agents 0, 1 share the expansion bucket
    #   agents 2, 3 share the caution bucket
    #   agent  4    is the crisis bucket
    _AGENT_TO_REGIME_BUCKET = np.array([0, 0, 1, 1, 2], dtype=np.int64)
    _BUCKET_SIZES = np.array([2, 2, 1], dtype=np.float32)  # (expansion=2, caution=2, crisis=1)

    def __init__(self, n_bins: int = 7, temperature: float = 1.0) -> None:
        self._n_bins = n_bins
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

    def _regime_weights_to_agent_weights(self, rw: RegimeWeights) -> np.ndarray:
        """Project 3 regime weights onto 5 agent weights (uniform within bucket).

        Agent i's weight = regime_weights[bucket(i)] / bucket_size(bucket(i))
        Result sums to 1.0 (regime weights sum to 1, projection preserves total).
        """
        regime_w = rw.as_array()                        # shape (3,)
        per_bucket_share = regime_w / self._BUCKET_SIZES  # shape (3,)
        agent_w = per_bucket_share[self._AGENT_TO_REGIME_BUCKET]  # shape (5,)
        # Numerical safety: renormalize (covers float drift)
        return agent_w / agent_w.sum()

    def blend(
        self,
        agent_outputs: list[tuple[float, int]],
        macro_score: int,
        vix: float | None = None,
    ) -> MoEAction:
        """Blend 5 SAC agent outputs using regime-derived weights (FR-5.5).

        Args:
            agent_outputs: list of EXACTLY 5 (entry_size_in_0_1, hold_bin) tuples,
                           one per SACAgent in SACEnsemble.agents (order matters).
            macro_score:   composite macro score in {0, -1, ..., -6}
            vix:           optional VIX for sharpening crisis weight

        Returns:
            MoEAction with blended entry_size and hold_bin, plus regime weights for logging.
        """
        if len(agent_outputs) != 5:
            raise ValueError(
                f"FR-5.5: blend requires exactly 5 agent outputs, got {len(agent_outputs)}"
            )

        rw = self.weights(macro_score, vix)
        agent_w = self._regime_weights_to_agent_weights(rw)

        entries = np.array([float(e) for e, _ in agent_outputs], dtype=np.float32)
        holds = np.array([float(h) for _, h in agent_outputs], dtype=np.float32)

        blended_entry = float(np.dot(agent_w, entries))
        blended_entry = float(np.clip(blended_entry, 0.0, 1.0))
        blended_hold = int(round(float(np.dot(agent_w, holds))))
        blended_hold = int(np.clip(blended_hold, 0, self._n_bins - 1))

        return MoEAction(
            entry_size=blended_entry,
            hold_bin=blended_hold,
            weights=rw,
            dominant_regime=rw.dominant(),
        )
