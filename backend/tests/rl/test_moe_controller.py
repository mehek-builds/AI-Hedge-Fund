"""Wave 0 stubs -- FR-5.5 (MoE blend of all 5 agents)."""
import os
import sys

# Add repo root to path so `rl` package is importable from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import inspect
import pytest
import numpy as np

from rl.moe_controller import MoEController, RegimeWeights


def test_blend_all_five():
    """FR-5.5: MoEController.blend must accept outputs from all 5 SAC agents (not 3 specialists)."""
    moe = MoEController()
    sig = inspect.signature(moe.blend)
    params = list(sig.parameters.keys())
    # After Wave 3 redesign, blend must accept agent_outputs (list/array of 5)
    # NOT the legacy raw_entries: dict[Regime, float] (3-specialist API)
    assert "agent_outputs" in params, \
        f"blend() must accept 'agent_outputs' parameter (got {params})"


def test_five_agent_blend_shape():
    """FR-5.5: Passing 5 (entry, hold) tuples must produce a single MoEAction."""
    moe = MoEController()
    # 5 distinct (entry_size, hold_bin) tuples -- one per agent
    agent_outputs = [(0.1, 0), (0.2, 1), (0.3, 2), (0.4, 3), (0.5, 4)]
    result = moe.blend(agent_outputs=agent_outputs, macro_score=0)
    assert hasattr(result, "entry_size") and hasattr(result, "hold_bin")
    assert 0.0 <= result.entry_size <= 1.0


def test_regime_weights_sum():
    """FR-5.5: Regime weights for any macro_score must sum to ~1.0."""
    moe = MoEController()
    for score in [0, -1, -2, -3, -4, -6]:
        rw = moe.weights(score)
        total = rw.expansion + rw.caution + rw.crisis
        assert abs(total - 1.0) < 1e-5, f"score={score} weights sum={total}, expected 1.0"
