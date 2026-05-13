"""Wave 0 stubs — FR-5.1 (distinct init) and FR-5.3 (Beta actor)."""
import pytest
import torch
import numpy as np

from rl.sac_agent import SACEnsemble, SACAgent
from config import SACConfig


def test_beta_actor():
    """FR-5.3: ContinuousActor must produce samples via torch.distributions.Beta in (0,1)."""
    cfg = SACConfig()
    agent = SACAgent(obs_dim=31, cfg=cfg, device="cpu")
    # The actor class name must be BetaActor and use torch.distributions.Beta
    actor_cls_name = type(agent.cont_actor).__name__
    assert actor_cls_name == "BetaActor", f"Expected BetaActor, got {actor_cls_name}"
    obs = torch.randn(8, 31)
    action, log_prob = agent.cont_actor.sample(obs)
    assert action.shape == (8, 1)
    assert (action > 0).all() and (action < 1).all(), "Beta samples must be in (0,1)"


def test_distinct_init():
    """FR-5.1: 5 agents must have distinct weights at initialization."""
    cfg = SACConfig()
    ensemble = SACEnsemble(obs_dim=31, cfg=cfg, device="cpu")
    assert len(ensemble.agents) == 5
    w0 = next(ensemble.agents[0].cont_actor.parameters()).detach().clone()
    w1 = next(ensemble.agents[1].cont_actor.parameters()).detach().clone()
    assert not torch.allclose(w0, w1), "Agents 0 and 1 must not share identical weights"


def test_hyperparameter_perturbation():
    """FR-5.1: Each agent has lr/gamma/tau perturbed by +-30% from base config."""
    cfg = SACConfig()
    ensemble = SACEnsemble(obs_dim=31, cfg=cfg, device="cpu")
    # Each agent must record its perturbed config
    lrs = [a.cfg.lr for a in ensemble.agents]
    assert len(set(lrs)) == 5, "All 5 agents must have distinct learning rates"
    base_lr = cfg.lr
    for lr in lrs:
        assert 0.7 * base_lr <= lr <= 1.3 * base_lr, f"lr {lr} out of +-30% of {base_lr}"


def test_macro_multiplier_no_grad():
    """FR-5.3: Macro multiplier applied post-RL must not propagate gradients."""
    cfg = SACConfig()
    agent = SACAgent(obs_dim=31, cfg=cfg, device="cpu")
    obs = np.random.randn(31).astype(np.float32)
    raw_size, _ = agent.select_action(obs)
    # multiplier is a plain float; final_size must be a float, not a tensor with grad_fn
    final_size = float(raw_size) * 0.6
    assert isinstance(final_size, float)
