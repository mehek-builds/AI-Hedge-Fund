"""SAC ensemble training loop entrypoint (FR-5.7).

Runs as a Railway service with `deployTrigger = "manual"` (railway.toml).
Never auto-deployed -- `python -m worker.flows.rl_trainer`.

Per CLAUDE.md:
  - Manual deploy only (CI excludes rl/ profile from auto-deploy)
  - Checkpoints persisted to PostgreSQL `rl_checkpoints` (Railway filesystem is ephemeral)
  - Diversity monitoring fires alerts via existing Celery dispatch_alert task

Cadence:
  - Every step:                ensemble.update_all() if buffer ready
  - Every 1000 steps (FR-5.7): save checkpoints + diversity check
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import time
from typing import Optional

import numpy as np
import torch
from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import SACConfig
from rl.db_per import get_engine
from rl.diversity_monitor import (
    compute_pairwise_diversity,
    fire_diversity_alert,
    should_fire_alert,
)
from rl.per_buffer import PERBuffer
from rl.sac_agent import SACEnsemble

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

CHECKPOINT_INTERVAL: int = 1000  # FR-5.7: checkpoints every 1000 steps
DEFAULT_OBS_DIM: int = 31         # config.RLConfig.observation_dim
DEFAULT_DIVERSITY_BATCH: int = 100


def save_checkpoints_to_db(
    engine: Engine,
    ensemble: SACEnsemble,
    *,
    step: int,
    mean_reward_20: Optional[float] = None,
) -> None:
    """Serialize each agent's tensors and persist to rl_checkpoints (FR-5.7).

    Single active row per agent: deactivates prior rows with is_active=FALSE,
    then inserts new row with is_active=TRUE.
    """
    with engine.begin() as conn:
        for agent_id in range(len(ensemble.agents)):
            buf = io.BytesIO()
            torch.save(ensemble.state_dict_bundle(agent_id), buf)
            model_bytes = buf.getvalue()

            # Single active row per agent -- deactivate prior, then insert new
            conn.execute(
                text(
                    "UPDATE rl_checkpoints SET is_active = FALSE "
                    "WHERE agent_id = :agent_id AND is_active = TRUE"
                ),
                {"agent_id": agent_id},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO rl_checkpoints
                        (step, agent_id, model_bytes, total_steps, mean_reward_20, is_active)
                    VALUES
                        (:step, :agent_id, :mb, :total, :mr20, TRUE)
                    """
                ),
                {
                    "step": step,
                    "agent_id": agent_id,
                    "mb": model_bytes,
                    "total": step,
                    "mr20": float(mean_reward_20) if mean_reward_20 is not None else None,
                },
            )
            logger.info(
                "checkpoint agent=%d step=%d bytes=%d", agent_id, step, len(model_bytes)
            )


def _build_canonical_obs(
    buffer: PERBuffer, batch: int = DEFAULT_DIVERSITY_BATCH
) -> torch.Tensor:
    """Sample a fixed observation batch for stable diversity comparison."""
    if len(buffer) < batch:
        # Fallback: random observations of the right shape
        return torch.randn(batch, DEFAULT_OBS_DIM)
    sample = buffer.sample(batch)
    obs = np.array([t.state for t in sample.transitions], dtype=np.float32)
    return torch.tensor(obs)


def main(
    total_steps: int = 10_000,
    checkpoint_interval: int = CHECKPOINT_INTERVAL,
    obs_dim: int = DEFAULT_OBS_DIM,
    database_url: Optional[str] = None,
) -> int:
    """Run the SAC ensemble training loop. Returns total steps executed."""
    cfg = SACConfig()
    engine = get_engine(database_url)

    buffer = PERBuffer(
        maxlen=cfg.per_buffer_size,
        alpha=cfg.per_alpha,
        beta_start=cfg.per_beta_start,
        beta_end=cfg.per_beta_end,
        beta_anneal_steps=cfg.per_beta_anneal_steps,
        decay_lambda=cfg.per_decay_lambda,
        engine=engine,
    )
    # FR-5.2: hydrate from DB so training survives restarts
    n_loaded = buffer.hydrate_from_db(agent_id=0, limit=cfg.per_buffer_size)
    logger.info("hydrated %d transitions from rl_transitions", n_loaded)

    ensemble = SACEnsemble(obs_dim, cfg, encoder=None, device="cpu")
    # Replace the auto-created in-memory buffer with our DB-backed one
    ensemble.buffer = buffer

    canonical_obs = _build_canonical_obs(buffer)
    epoch = 0
    rewards_window: list[float] = []

    for step in range(1, total_steps + 1):
        updates = ensemble.update_all()
        if updates is None:
            # Buffer not yet full enough -- wait briefly, no busy loop
            if step % 100 == 0:
                logger.info("step=%d buffer=%d (waiting for batch)", step, len(buffer))
            time.sleep(0.1)
            continue

        rewards_window.append(float(np.mean([u.actor_loss for u in updates])))
        if len(rewards_window) > 20:
            rewards_window.pop(0)

        if step % checkpoint_interval == 0:
            epoch += 1
            mean_reward_20 = float(np.mean(rewards_window)) if rewards_window else None
            save_checkpoints_to_db(
                engine, ensemble, step=step, mean_reward_20=mean_reward_20
            )

            max_sim, pair = compute_pairwise_diversity(ensemble.agents, canonical_obs)
            logger.info("diversity step=%d max_sim=%.4f pair=%s", step, max_sim, pair)
            if should_fire_alert(max_sim):
                fire_diversity_alert(engine, max_sim=max_sim, agent_pair=pair, epoch=epoch)

    logger.info("training complete: total_steps=%d", total_steps)
    return total_steps


def _cli() -> int:
    p = argparse.ArgumentParser(description="SAC ensemble training loop (FR-5.7)")
    p.add_argument(
        "--total-steps",
        type=int,
        default=int(os.environ.get("RL_TOTAL_STEPS", 10_000)),
    )
    p.add_argument("--checkpoint-interval", type=int, default=CHECKPOINT_INTERVAL)
    p.add_argument("--database-url", type=str, default=None)
    args = p.parse_args()
    return main(
        total_steps=args.total_steps,
        checkpoint_interval=args.checkpoint_interval,
        database_url=args.database_url,
    )


if __name__ == "__main__":
    sys.exit(0 if _cli() else 1)
