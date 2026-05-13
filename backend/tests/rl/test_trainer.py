"""Tests for worker/flows/rl_trainer.py (FR-5.7).

TDD RED phase: these tests must fail before rl_trainer.py is created.
"""

from __future__ import annotations

import importlib.util
import sys
import os

import pytest

# Ensure root is in path so worker/ is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_trainer_module_exists():
    """worker.flows.rl_trainer must be importable as a module."""
    spec = importlib.util.find_spec("worker.flows.rl_trainer")
    assert spec is not None, (
        "worker.flows.rl_trainer module not found. "
        "Expected at worker/flows/rl_trainer.py"
    )


def test_checkpoint_interval_constant():
    """CHECKPOINT_INTERVAL must equal 1000 per FR-5.7."""
    import worker.flows.rl_trainer as t
    assert t.CHECKPOINT_INTERVAL == 1000


def test_main_function_exists():
    """main() entrypoint must exist and be callable."""
    import worker.flows.rl_trainer as t
    assert callable(t.main)


def test_save_checkpoints_to_db_exists():
    """save_checkpoints_to_db helper must exist."""
    import worker.flows.rl_trainer as t
    assert callable(t.save_checkpoints_to_db)


def test_state_dict_bundle_on_ensemble():
    """SACEnsemble must have state_dict_bundle helper (FR-5.7)."""
    import sys
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    from config import SACConfig
    from rl.sac_agent import SACEnsemble

    cfg = SACConfig()
    ensemble = SACEnsemble(obs_dim=4, cfg=cfg, encoder=None, device="cpu")
    assert hasattr(ensemble, "state_dict_bundle")
    bundle = ensemble.state_dict_bundle(0)
    assert isinstance(bundle, dict)
    assert "cont_actor" in bundle
    assert "disc_actor" in bundle
    assert "critic" in bundle
    assert "critic_target" in bundle
    assert "log_alpha" in bundle
