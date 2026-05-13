"""Tests for rl/diversity_monitor.py (FR-5.6).

TDD RED phase: these tests must fail before diversity_monitor.py is created.
"""

from __future__ import annotations

import sys
import os
import types
from unittest.mock import MagicMock, patch, call

import pytest
import torch
import torch.nn as nn

# Ensure root is in path so rl/ is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Minimal stub agent that has cont_actor returning two tensors (alpha, beta)
# ---------------------------------------------------------------------------

class _FakeContActor(nn.Module):
    def __init__(self, alpha_val: float, beta_val: float) -> None:
        super().__init__()
        self._alpha = torch.tensor([[alpha_val]])
        self._beta = torch.tensor([[beta_val]])

    def forward(self, obs: torch.Tensor):
        batch = obs.shape[0]
        return self._alpha.expand(batch, 1), self._beta.expand(batch, 1)


class _FakeAgent:
    def __init__(self, alpha_val: float, beta_val: float) -> None:
        self.cont_actor = _FakeContActor(alpha_val, beta_val)


# ---------------------------------------------------------------------------
# Tests for should_fire_alert
# ---------------------------------------------------------------------------

def test_alert_fires_above_threshold():
    """should_fire_alert returns True for max_sim strictly above 0.9."""
    from rl.diversity_monitor import should_fire_alert
    assert should_fire_alert(0.95) is True
    assert should_fire_alert(0.91) is True


def test_no_alert_below_threshold():
    """should_fire_alert returns False at or below 0.9."""
    from rl.diversity_monitor import should_fire_alert
    assert should_fire_alert(0.9) is False
    assert should_fire_alert(0.85) is False
    assert should_fire_alert(0.0) is False


# ---------------------------------------------------------------------------
# Tests for compute_pairwise_diversity
# ---------------------------------------------------------------------------

def test_compute_pairwise_diversity_signature():
    """compute_pairwise_diversity accepts 'agents' param and returns (float, tuple)."""
    from rl.diversity_monitor import compute_pairwise_diversity

    agents = [_FakeAgent(1.0, 2.0), _FakeAgent(1.0, 2.0)]
    sample_obs = torch.ones(4, 5)  # batch=4, obs_dim=5

    result = compute_pairwise_diversity(agents=agents, sample_obs=sample_obs)
    assert isinstance(result, tuple), "Should return a tuple"
    assert len(result) == 2
    max_sim, pair = result
    assert isinstance(max_sim, float)
    assert isinstance(pair, tuple)
    assert len(pair) == 2


def test_compute_pairwise_diversity_identical_agents():
    """Identical agents should return max_sim of ~1.0."""
    from rl.diversity_monitor import compute_pairwise_diversity

    agents = [_FakeAgent(1.0, 2.0)] * 3
    sample_obs = torch.ones(4, 5)

    max_sim, pair = compute_pairwise_diversity(agents=agents, sample_obs=sample_obs)
    assert max_sim == pytest.approx(1.0, abs=1e-5)


def test_compute_pairwise_diversity_single_agent():
    """Single agent returns max_sim=0.0 (no pairs)."""
    from rl.diversity_monitor import compute_pairwise_diversity

    agents = [_FakeAgent(1.0, 2.0)]
    sample_obs = torch.ones(4, 5)

    max_sim, _ = compute_pairwise_diversity(agents=agents, sample_obs=sample_obs)
    assert max_sim == 0.0


# ---------------------------------------------------------------------------
# Test for fire_diversity_alert (DB persistence + Celery dispatch)
# ---------------------------------------------------------------------------

def test_alert_dispatch():
    """fire_diversity_alert inserts into DB and calls dispatch_alert.delay."""
    from rl.diversity_monitor import fire_diversity_alert

    # Mock engine
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_engine = MagicMock()
    mock_engine.begin.return_value = mock_conn

    # Mock dispatch_alert Celery task
    mock_dispatch = MagicMock()
    mock_dispatch_task = MagicMock()
    mock_dispatch_task.delay = MagicMock()

    fake_alerts_module = types.ModuleType("app.tasks.alerts")
    fake_alerts_module.dispatch_alert = mock_dispatch_task

    with patch.dict("sys.modules", {"app.tasks.alerts": fake_alerts_module}):
        fire_diversity_alert(
            mock_engine,
            max_sim=0.95,
            agent_pair=(0, 2),
            epoch=3,
        )

    # DB insert was called
    assert mock_conn.execute.called, "Should have called conn.execute for DB insert"

    # Celery dispatch was called
    mock_dispatch_task.delay.assert_called_once()
    call_kwargs = mock_dispatch_task.delay.call_args
    # event_type must be 'rl_diversity_alert'
    assert "rl_diversity_alert" in str(call_kwargs)
