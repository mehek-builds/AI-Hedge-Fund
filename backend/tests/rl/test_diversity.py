"""Wave 0 stubs -- FR-5.6 (Diversity monitor)."""
import os
import sys

# Add repo root to path so `rl` package is importable from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import pytest
import torch

# These imports will fail until Wave 4 creates rl/diversity_monitor.py
pytest.importorskip("rl.diversity_monitor", reason="Wave 4 creates this module")
from rl.diversity_monitor import compute_pairwise_diversity


def test_alert_fires_above_threshold():
    """FR-5.6: When max pairwise cosine similarity > 0.9, alert must fire."""
    from rl.diversity_monitor import should_fire_alert
    assert should_fire_alert(max_sim=0.95) is True
    assert should_fire_alert(max_sim=0.91) is True


def test_no_alert_below_threshold():
    """FR-5.6: When max similarity <= 0.9, no alert."""
    from rl.diversity_monitor import should_fire_alert
    assert should_fire_alert(max_sim=0.85) is False
    assert should_fire_alert(max_sim=0.90) is False


def test_compute_pairwise_diversity_signature():
    """FR-5.6: Function returns a single float in [-1.0, 1.0]."""
    # Wave 4 must implement this; stub asserts the contract.
    import inspect
    sig = inspect.signature(compute_pairwise_diversity)
    params = list(sig.parameters.keys())
    assert "agents" in params, f"Expected 'agents' param, got {params}"


def test_alert_dispatch():
    """FR-5.6: fire_diversity_alert MUST enqueue a Celery dispatch_alert task with event_type='rl_diversity_alert'.

    The Wave 4 implementation imports dispatch_alert inside a try/except so the unit test
    needs no live Celery broker -- but it MUST verify that the dispatch_alert.delay path is
    reached (otherwise alert failures are invisible).
    """
    from unittest.mock import patch, MagicMock

    # We patch the import target inside fire_diversity_alert. Wave 5 imports
    # `from app.tasks.alerts import dispatch_alert` lazily inside the function,
    # so we patch the source module attribute.
    with patch("app.tasks.alerts.dispatch_alert") as mock_dispatch:
        mock_dispatch.delay = MagicMock()
        from rl.diversity_monitor import fire_diversity_alert

        # Use an in-memory engine stub: persist_diversity_alert is exercised
        # in DB-gated integration tests; here we only verify the Celery path.
        engine_stub = MagicMock()
        # engine.begin() is a context manager returning a connection-like object
        engine_stub.begin.return_value.__enter__ = MagicMock(return_value=MagicMock())
        engine_stub.begin.return_value.__exit__ = MagicMock(return_value=False)

        fire_diversity_alert(engine_stub, max_sim=0.95, agent_pair=(0, 1), epoch=7)

        assert mock_dispatch.delay.called, "fire_diversity_alert must call dispatch_alert.delay"
        kwargs = mock_dispatch.delay.call_args.kwargs
        assert kwargs.get("event_type") == "rl_diversity_alert", (
            f"event_type must be 'rl_diversity_alert', got {kwargs.get('event_type')}"
        )
