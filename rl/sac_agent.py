"""SAC Ensemble — 5 independent Soft Actor-Critic agents with shared PER buffer."""

from __future__ import annotations

import copy
import dataclasses
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from dataclasses import dataclass
from typing import Optional
from torch.distributions import Beta

from rl.per_buffer import PERBuffer, Transition
from rl.transformer_encoder import TransformerStateEncoder
from config import SACConfig


BASE_SEEDS: list[int] = [42, 137, 271, 314, 999]
PERTURB_KEYS: tuple[str, ...] = ("lr", "gamma", "tau")
PERTURB_RANGE: float = 0.30  # +-30% per FR-5.1


# ── Network building blocks ──────────────────────────────────────────────────

def _mlp(in_dim: int, hidden: list[int], out_dim: int, activation: type = nn.ReLU) -> nn.Sequential:
    layers: list[nn.Module] = []
    prev = in_dim
    for h in hidden:
        layers += [nn.Linear(prev, h), activation()]
        prev = h
    layers.append(nn.Linear(prev, out_dim))
    return nn.Sequential(*layers)


class BetaActor(nn.Module):
    """Beta policy: outputs alpha, beta > 0 -- samples in (0,1) for entry_size."""

    LOG_AB_MIN = -5.0
    LOG_AB_MAX = 2.0
    PARAM_FLOOR = 1e-3

    def __init__(self, obs_dim: int, hidden: list[int] = [256, 256]) -> None:
        super().__init__()
        self.net = _mlp(obs_dim, hidden[:-1], hidden[-1])
        self.alpha_head = nn.Linear(hidden[-1], 1)
        self.beta_head = nn.Linear(hidden[-1], 1)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = F.relu(self.net(obs))
        log_alpha = self.alpha_head(h).clamp(self.LOG_AB_MIN, self.LOG_AB_MAX)
        log_beta = self.beta_head(h).clamp(self.LOG_AB_MIN, self.LOG_AB_MAX)
        alpha = log_alpha.exp() + self.PARAM_FLOOR
        beta = log_beta.exp() + self.PARAM_FLOOR
        return alpha, beta

    def sample(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        alpha, beta = self(obs)
        dist = Beta(alpha, beta)
        action = dist.rsample()
        # Numerical safety: clip to (eps, 1-eps) to avoid log(0) downstream
        action = action.clamp(1e-6, 1.0 - 1e-6)
        log_prob = dist.log_prob(action).sum(-1, keepdim=True)
        return action, log_prob

    def entropy(self, obs: torch.Tensor) -> torch.Tensor:
        alpha, beta = self(obs)
        return Beta(alpha, beta).entropy()

    def deterministic(self, obs: torch.Tensor) -> torch.Tensor:
        """Mean of Beta(alpha, beta) = alpha / (alpha + beta) -- used when deterministic=True."""
        alpha, beta = self(obs)
        return alpha / (alpha + beta)


class DiscreteActor(nn.Module):
    """Categorical policy: hold_duration ∈ {10,20,30,45,60,75,90} → 7 bins."""

    def __init__(self, obs_dim: int, n_bins: int = 7, hidden: list[int] = [256, 256]) -> None:
        super().__init__()
        self.net = _mlp(obs_dim, hidden, n_bins)
        self.n_bins = n_bins

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs)                    # logits

    def sample(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self(obs)
        dist = torch.distributions.Categorical(logits=logits)
        action = dist.sample()
        log_prob = dist.log_prob(action).unsqueeze(-1)
        return action, log_prob


class TwinCritic(nn.Module):
    """Clipped double-Q: two independent Q-networks."""

    def __init__(self, obs_dim: int, action_dim: int, hidden: list[int] = [256, 256]) -> None:
        super().__init__()
        in_dim = obs_dim + action_dim
        self.q1 = _mlp(in_dim, hidden, 1)
        self.q2 = _mlp(in_dim, hidden, 1)

    def forward(self, obs: torch.Tensor, action: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = torch.cat([obs, action], dim=-1)
        return self.q1(x), self.q2(x)

    def min_q(self, obs: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        q1, q2 = self(obs, action)
        return torch.min(q1, q2)


# ── Single SAC agent ─────────────────────────────────────────────────────────

@dataclass
class SACUpdate:
    actor_loss: float
    critic_loss: float
    alpha_loss: float
    alpha: float
    td_errors: np.ndarray


class SACAgent:
    """Single SAC agent with continuous entry_size + discrete hold_duration."""

    def __init__(
        self,
        obs_dim: int,
        cfg: SACConfig,
        device: str = "cpu",
    ) -> None:
        self.cfg = cfg
        self.device = torch.device(device)
        hidden = [256, 256]

        self.cont_actor = BetaActor(obs_dim, hidden).to(self.device)
        self.disc_actor = DiscreteActor(obs_dim, n_bins=len(cfg.hold_duration_bins), hidden=hidden).to(self.device)

        # Twin critics receive obs + [entry_size, hold_bin_onehot] concatenated
        action_dim = 1 + len(cfg.hold_duration_bins)
        self.critic = TwinCritic(obs_dim, action_dim, hidden).to(self.device)
        self.critic_target = TwinCritic(obs_dim, action_dim, hidden).to(self.device)
        self.critic_target.load_state_dict(self.critic.state_dict())
        for p in self.critic_target.parameters():
            p.requires_grad = False

        # Entropy temperature (auto-tuned)
        self.log_alpha = torch.tensor(0.0, requires_grad=True, device=self.device)
        self.target_entropy = cfg.target_entropy

        all_actor = list(self.cont_actor.parameters()) + list(self.disc_actor.parameters())
        self.actor_opt = torch.optim.Adam(all_actor, lr=cfg.lr)
        self.critic_opt = torch.optim.Adam(self.critic.parameters(), lr=cfg.lr)
        self.alpha_opt = torch.optim.Adam([self.log_alpha], lr=cfg.lr)

    @property
    def alpha(self) -> float:
        return float(self.log_alpha.exp())

    def _encode_action(self, entry: torch.Tensor, hold: torch.Tensor) -> torch.Tensor:
        n_bins = len(self.cfg.hold_duration_bins)
        hold_oh = F.one_hot(hold.long(), num_classes=n_bins).float()
        return torch.cat([entry, hold_oh], dim=-1)

    # Note: macro multiplier is NOT applied here. Per FR-5.3 it is applied
    # post-RL as a deterministic float multiplication in the calling code:
    #   raw_size, hold = ensemble.select_action(obs)
    #   final_size = raw_size * apply_sizing_multiplier(macro_score)
    # This keeps the multiplier outside the autograd graph (no backprop).
    def select_action(self, obs: np.ndarray, deterministic: bool = False) -> tuple[float, int]:
        obs_t = torch.tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            if deterministic:
                entry = self.cont_actor.deterministic(obs_t)
                hold_logits = self.disc_actor(obs_t)
                hold = hold_logits.argmax(-1)
            else:
                entry, _ = self.cont_actor.sample(obs_t)
                hold, _ = self.disc_actor.sample(obs_t)
        return float(entry.cpu()), int(hold.cpu())

    def update(self, batch_obs, batch_actions, batch_rewards, batch_next_obs, batch_dones, weights) -> SACUpdate:
        obs = torch.tensor(batch_obs, dtype=torch.float32, device=self.device)
        rewards = torch.tensor(batch_rewards, dtype=torch.float32, device=self.device).unsqueeze(-1)
        next_obs = torch.tensor(batch_next_obs, dtype=torch.float32, device=self.device)
        dones = torch.tensor(batch_dones, dtype=torch.float32, device=self.device).unsqueeze(-1)
        is_weights = torch.tensor(weights, dtype=torch.float32, device=self.device).unsqueeze(-1)

        entries = torch.tensor(batch_actions[:, 0:1], dtype=torch.float32, device=self.device)
        holds = torch.tensor(batch_actions[:, 1], dtype=torch.long, device=self.device)
        actions = self._encode_action(entries, holds)

        # ── Critic update ──
        with torch.no_grad():
            next_entry, next_entry_lp = self.cont_actor.sample(next_obs)
            next_hold, next_hold_lp = self.disc_actor.sample(next_obs)
            next_actions = self._encode_action(next_entry, next_hold)
            next_log_prob = next_entry_lp + next_hold_lp
            q_target = self.critic_target.min_q(next_obs, next_actions)
            backup = rewards + self.cfg.gamma * (1 - dones) * (q_target - self.alpha * next_log_prob)

        q1, q2 = self.critic(obs, actions)
        td1 = (q1 - backup).abs().detach().cpu().numpy().squeeze()
        td2 = (q2 - backup).abs().detach().cpu().numpy().squeeze()
        td_errors = (td1 + td2) / 2

        critic_loss = ((is_weights * F.mse_loss(q1, backup, reduction="none")).mean() +
                       (is_weights * F.mse_loss(q2, backup, reduction="none")).mean())
        self.critic_opt.zero_grad()
        critic_loss.backward()
        nn.utils.clip_grad_norm_(self.critic.parameters(), 1.0)
        self.critic_opt.step()

        # ── Actor update ──
        new_entry, new_entry_lp = self.cont_actor.sample(obs)
        new_hold, new_hold_lp = self.disc_actor.sample(obs)
        new_actions = self._encode_action(new_entry, new_hold)
        new_log_prob = new_entry_lp + new_hold_lp
        q_val = self.critic.min_q(obs, new_actions)
        actor_loss = (self.alpha * new_log_prob - q_val).mean()
        self.actor_opt.zero_grad()
        actor_loss.backward()
        nn.utils.clip_grad_norm_(list(self.cont_actor.parameters()) + list(self.disc_actor.parameters()), 1.0)
        self.actor_opt.step()

        # ── Alpha update ──
        alpha_loss = -(self.log_alpha * (new_log_prob.detach() + self.target_entropy)).mean()
        self.alpha_opt.zero_grad()
        alpha_loss.backward()
        self.alpha_opt.step()

        # ── Soft target update ──
        for p, tp in zip(self.critic.parameters(), self.critic_target.parameters()):
            tp.data.mul_(1 - self.cfg.tau).add_(p.data * self.cfg.tau)

        return SACUpdate(
            actor_loss=float(actor_loss),
            critic_loss=float(critic_loss),
            alpha_loss=float(alpha_loss),
            alpha=self.alpha,
            td_errors=td_errors,
        )


def _perturb_cfg(base_cfg: SACConfig, seed: int) -> SACConfig:
    """Per-agent +-30% perturbation on lr/gamma/tau. FR-5.1."""
    rng = np.random.default_rng(seed)
    cfg_dict = dataclasses.asdict(base_cfg)
    for key in PERTURB_KEYS:
        factor = 1.0 + float(rng.uniform(-PERTURB_RANGE, PERTURB_RANGE))
        cfg_dict[key] = cfg_dict[key] * factor
    # gamma must stay < 1.0 strictly
    cfg_dict["gamma"] = min(cfg_dict["gamma"], 0.9999)
    return SACConfig(**cfg_dict)


# ── Ensemble ─────────────────────────────────────────────────────────────────

class SACEnsemble:
    """
    5 independent SAC agents with a shared PER buffer.
    Actions are averaged across agents; each agent updates independently.
    """

    def __init__(
        self,
        obs_dim: int,
        cfg: SACConfig,
        encoder: Optional[TransformerStateEncoder] = None,
        device: str = "cpu",
    ) -> None:
        self.cfg = cfg
        self.device = device
        self.encoder = encoder
        enc_out = cfg.transformer_d_model if encoder is not None else 0
        agent_obs_dim = obs_dim + enc_out

        if cfg.n_agents != len(BASE_SEEDS):
            raise ValueError(
                f"FR-5.1: SACConfig.n_agents must be {len(BASE_SEEDS)} "
                f"(got {cfg.n_agents}). Update BASE_SEEDS to match."
            )
        self.agents: list[SACAgent] = []
        for seed in BASE_SEEDS:
            torch.manual_seed(seed)
            np.random.seed(seed)
            agent_cfg = _perturb_cfg(cfg, seed)
            self.agents.append(SACAgent(agent_obs_dim, agent_cfg, device))
        # Reset global RNG state so caller is unaffected by per-agent seeding
        torch.manual_seed(int(np.random.default_rng().integers(2**31)))
        self.buffer = PERBuffer(
            maxlen=cfg.per_buffer_size,
            alpha=cfg.per_alpha,
            beta_start=cfg.per_beta_start,
            beta_end=cfg.per_beta_end,
            beta_anneal_steps=cfg.per_beta_anneal_steps,
            decay_lambda=cfg.per_decay_lambda,
        )

    def _augment_obs(self, obs: np.ndarray) -> np.ndarray:
        if self.encoder is None:
            return obs
        obs_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            enc = self.encoder(obs_t).squeeze(0).cpu().numpy()
        return np.concatenate([obs, enc])

    def select_action(self, obs: np.ndarray, deterministic: bool = False) -> tuple[float, int]:
        aug = self._augment_obs(obs)
        entries, holds = zip(*[a.select_action(aug, deterministic) for a in self.agents])
        return float(np.mean(entries)), int(round(np.mean(holds)))

    def select_action_per_agent(
        self,
        obs: np.ndarray,
        deterministic: bool = False,
    ) -> list[tuple[float, int]]:
        """Return raw per-agent (entry_size, hold_bin) tuples for MoE blending (FR-5.5).

        The MoEController consumes this list (length == n_agents == 5) and produces
        a single blended action via regime-weighted projection.

        Order is stable: tuple at index i corresponds to self.agents[i], which
        matches the fixed _AGENT_TO_REGIME_BUCKET assignment in MoEController.
        """
        aug = self._augment_obs(obs)
        outputs: list[tuple[float, int]] = []
        for agent in self.agents:
            entry, hold = agent.select_action(aug, deterministic)
            outputs.append((float(entry), int(hold)))
        return outputs

    def push(self, transition: Transition, td_error: float | None = None) -> None:
        self.buffer.add(transition, td_error)

    def state_dict_bundle(self, agent_id: int) -> dict:
        """Bundle one agent's tensors for checkpoint serialization (FR-5.7)."""
        agent = self.agents[agent_id]
        return {
            "cont_actor": agent.cont_actor.state_dict(),
            "disc_actor": agent.disc_actor.state_dict(),
            "critic": agent.critic.state_dict(),
            "critic_target": agent.critic_target.state_dict(),
            "log_alpha": agent.log_alpha.detach().cpu(),
        }

    def update_all(self) -> list[SACUpdate] | None:
        if len(self.buffer) < self.cfg.online_batch_size:
            return None

        batch = self.buffer.sample(self.cfg.online_batch_size)
        obs_arr = np.array([t.state for t in batch.transitions])
        act_arr = np.array([t.action for t in batch.transitions])
        rew_arr = np.array([t.reward for t in batch.transitions], dtype=np.float32)
        nobs_arr = np.array([t.next_state for t in batch.transitions])
        done_arr = np.array([float(t.done) for t in batch.transitions], dtype=np.float32)

        updates: list[SACUpdate] = []
        all_td = np.zeros(len(batch.transitions))
        for agent in self.agents:
            upd = agent.update(obs_arr, act_arr, rew_arr, nobs_arr, done_arr, batch.weights)
            updates.append(upd)
            all_td += upd.td_errors

        # Update priorities with mean TD error across agents
        self.buffer.update_priorities(batch.indices, all_td / len(self.agents))
        return updates
