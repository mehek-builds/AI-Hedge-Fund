"""SAC ensemble diversity monitoring (FR-5.6).

Computes pairwise cosine similarity between agent Beta-distribution parameter
vectors after each training epoch. Fires `rl_diversity_alert` when any pair
exceeds 0.9 -- both persisted to `rl_diversity_alerts` and dispatched via the
existing Celery alert task (Phase 4).
"""

from __future__ import annotations

import logging
from typing import Sequence

import torch
import torch.nn.functional as F
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# FR-5.6: alert when max pairwise cosine similarity strictly exceeds this.
DIVERSITY_THRESHOLD: float = 0.9


def should_fire_alert(max_sim: float) -> bool:
    """Strict threshold: 0.9 itself does NOT fire (matches FR-5.6 wording)."""
    return float(max_sim) > DIVERSITY_THRESHOLD


def compute_pairwise_diversity(
    agents: Sequence,
    sample_obs: torch.Tensor,
) -> tuple[float, tuple[int, int]]:
    """Return (max_pairwise_cosine_similarity, (agent_i, agent_j)) over all pairs.

    Each agent's "fingerprint" vector is the concatenation of mean-batch
    actor output parameters (alpha/mu and beta/log_std) at `sample_obs`.

    Args:
        agents: Sequence of SACAgent instances (typically SACEnsemble.agents)
        sample_obs: shape (batch, obs_dim) -- canonical observation batch held
                    constant across epochs for stable comparison.
    """
    if len(agents) < 2:
        return 0.0, (0, 0)

    param_vecs: list[torch.Tensor] = []
    for agent in agents:
        with torch.no_grad():
            alpha, beta = agent.cont_actor(sample_obs)  # each (batch, 1)
        # Mean across batch -> (1,) for each, then concat -> (2,)
        vec = torch.cat([alpha.mean(0), beta.mean(0)])
        param_vecs.append(vec)

    max_sim = -1.0
    pair: tuple[int, int] = (0, 1)
    for i in range(len(param_vecs)):
        for j in range(i + 1, len(param_vecs)):
            sim = float(
                F.cosine_similarity(
                    param_vecs[i].unsqueeze(0),
                    param_vecs[j].unsqueeze(0),
                )
            )
            if sim > max_sim:
                max_sim = sim
                pair = (i, j)
    return float(max_sim), pair


def persist_diversity_alert(
    engine: Engine,
    *,
    max_sim: float,
    agent_pair: tuple[int, int],
    epoch: int,
) -> None:
    """Insert a row into rl_diversity_alerts (parameterized SQL)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO rl_diversity_alerts (max_similarity, agent_pair, epoch)
                VALUES (:max_sim, :pair, :epoch)
                """
            ),
            {
                "max_sim": float(max_sim),
                "pair": f"{agent_pair[0]},{agent_pair[1]}",
                "epoch": int(epoch),
            },
        )


def fire_diversity_alert(
    engine: Engine,
    *,
    max_sim: float,
    agent_pair: tuple[int, int],
    epoch: int,
) -> None:
    """Persist + best-effort Celery dispatch for an `rl_diversity_alert` event."""
    persist_diversity_alert(engine, max_sim=max_sim, agent_pair=agent_pair, epoch=epoch)
    try:
        from app.tasks.alerts import dispatch_alert  # type: ignore[import-not-found]
        dispatch_alert.delay(
            event_type="rl_diversity_alert",
            title="SAC ensemble collapse detected",
            message=(
                f"max_pairwise_cosine_sim={max_sim:.4f} > {DIVERSITY_THRESHOLD} "
                f"between agents {agent_pair[0]} and {agent_pair[1]} at epoch {epoch}"
            ),
            priority="high",
        )
    except Exception as exc:  # pragma: no cover -- Celery unavailable in unit tests
        logger.warning("dispatch_alert unavailable, skipping Celery enqueue: %s", exc)
