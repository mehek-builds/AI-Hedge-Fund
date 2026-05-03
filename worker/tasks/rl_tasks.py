"""SAC Ensemble training Celery task — replaces SB3 PPO."""

from __future__ import annotations

import json
import os
import pickle
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text

from worker.celery_app import celery_app

DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://postgres:postgres@db:5432/pead",
)
MODEL_DIR = os.environ.get("MODEL_DIR", "models")

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
    return _engine


@celery_app.task(name="worker.tasks.rl_tasks.train_rl_model", bind=True, max_retries=1)
def train_rl_model(self) -> dict:
    """
    Load rl_episodes from DB, run online SAC Ensemble updates from the
    PER buffer, save ensemble checkpoint, and log to rl_checkpoints.
    """
    engine = _get_engine()

    # ------------------------------------------------------------------
    # 1. Load training episodes
    # ------------------------------------------------------------------
    with engine.connect() as conn:
        episode_rows = conn.execute(
            text(
                """
                SELECT e.id, e.position_id, e.state_vector, e.action, e.reward, e.done,
                       p.ticker, p.entry_ts, p.exit_ts, p.direction, p.gics_sector
                FROM rl_episodes e
                LEFT JOIN positions p ON p.id = e.position_id
                ORDER BY e.created_at ASC
                """
            )
        ).fetchall()

    if len(episode_rows) < 50:
        logger.warning(f"Only {len(episode_rows)} episodes — need at least 50 to train")
        return {"status": "insufficient_data", "episodes": len(episode_rows)}

    # ------------------------------------------------------------------
    # 2. Build or load SAC Ensemble
    # ------------------------------------------------------------------
    from rl.sac_agent import SACEnsemble
    from rl.per_buffer import Transition
    from rl.transformer_encoder import TransformerStateEncoder
    from config import CONFIG

    model_dir = Path(MODEL_DIR)
    model_dir.mkdir(exist_ok=True)
    ensemble_path = model_dir / "sac_ensemble.pkl"

    if ensemble_path.exists():
        with open(ensemble_path, "rb") as f:
            ensemble: SACEnsemble = pickle.load(f)
        logger.info(f"Loaded existing SAC ensemble from {ensemble_path}")
    else:
        encoder = None
        encoder_path = model_dir / "transformer_encoder.pt"
        if encoder_path.exists():
            try:
                encoder = TransformerStateEncoder.from_pretrained(
                    str(encoder_path),
                    input_dim=CONFIG.rl.observation_dim,
                    d_model=CONFIG.sac.transformer_d_model,
                    n_heads=CONFIG.sac.transformer_heads,
                    n_layers=CONFIG.sac.transformer_layers,
                )
                logger.info("Loaded pre-trained transformer encoder")
            except Exception as exc:
                logger.warning(f"Could not load transformer encoder: {exc}")

        ensemble = SACEnsemble(
            obs_dim=CONFIG.rl.observation_dim,
            cfg=CONFIG.sac,
            encoder=encoder,
            device="cpu",
        )
        logger.info("Created fresh SAC Ensemble")

    # ------------------------------------------------------------------
    # 3. Fill PER buffer from DB episodes
    # ------------------------------------------------------------------
    episodes_df_list = []
    for row in episode_rows:
        r = dict(row._mapping)
        state = r["state_vector"]
        if isinstance(state, str):
            state = json.loads(state)
        state = np.array(state, dtype=np.float32)

        action_val = float(r["action"])
        action_arr = np.array([action_val, 4.0], dtype=np.float32)  # default hold_bin=4

        reward = float(r["reward"])
        episodes_df_list.append({"reward": reward})

        transition = Transition(
            state=state,
            action=action_arr,
            reward=reward,
            next_state=state,    # terminal state — next_state = state
            done=True,
        )
        ensemble.push(transition)

    episodes_df = pd.DataFrame(episodes_df_list)

    # ------------------------------------------------------------------
    # 4. Run SAC online updates
    # ------------------------------------------------------------------
    n_update_steps = min(len(episode_rows) * 2, 2000)
    total_actor_loss = 0.0
    n_updates = 0

    try:
        for _ in range(n_update_steps):
            updates = ensemble.update_all()
            if updates:
                total_actor_loss += float(np.mean([u.actor_loss for u in updates]))
                n_updates += 1
    except Exception as exc:
        logger.error(f"SAC update failed: {exc}")
        raise self.retry(exc=exc, countdown=60)

    avg_actor_loss = total_actor_loss / max(n_updates, 1)
    logger.info(f"SAC training: {n_updates} update steps | avg_actor_loss={avg_actor_loss:.4f}")

    # ------------------------------------------------------------------
    # 5. Save ensemble checkpoint
    # ------------------------------------------------------------------
    try:
        with open(ensemble_path, "wb") as f:
            pickle.dump(ensemble, f)
        logger.info(f"SAC ensemble saved to {ensemble_path}")
    except Exception as exc:
        logger.error(f"Failed to save ensemble: {exc}")
        raise self.retry(exc=exc, countdown=30)

    # ------------------------------------------------------------------
    # 6. Compute metrics
    # ------------------------------------------------------------------
    recent_rewards = episodes_df["reward"].tail(20).tolist()
    mean_reward_20 = float(np.mean(recent_rewards)) if recent_rewards else None

    # IR vs naive baseline (3% NAV / 1.0 SD fixed policy)
    all_rewards = episodes_df["reward"].tolist()
    naive_baseline_mean = 0.0   # naive policy expected alpha ≈ 0
    ir_vs_naive: Optional[float] = None
    if len(all_rewards) >= 20:
        rolling = pd.Series(all_rewards).rolling(60).mean().dropna()
        if len(rolling) >= 1:
            excess = rolling - naive_baseline_mean
            ir_vs_naive = float(excess.mean() / max(excess.std(), 1e-6))

    # Factor betas
    factor_betas: Optional[dict] = None
    try:
        from rl.reward import FF5RewardFunction
        reward_fn = FF5RewardFunction()
        if reward_fn._current_betas:
            factor_betas = reward_fn._current_betas.betas
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 7. Save checkpoint to DB
    # ------------------------------------------------------------------
    checkpoint_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    total_episodes = len(episode_rows)

    with engine.begin() as conn:
        conn.execute(text("UPDATE rl_checkpoints SET is_active = FALSE"))
        conn.execute(
            text(
                """
                INSERT INTO rl_checkpoints
                    (id, model_path, total_episodes, mean_reward_20, factor_betas,
                     ir_vs_naive, is_active, created_at)
                VALUES
                    (:id, :model_path, :total_episodes, :mean_reward_20,
                     :factor_betas::jsonb, :ir_vs_naive, TRUE, :created_at)
                """
            ),
            {
                "id": checkpoint_id,
                "model_path": str(ensemble_path),
                "total_episodes": total_episodes,
                "mean_reward_20": mean_reward_20,
                "factor_betas": json.dumps(factor_betas) if factor_betas else None,
                "ir_vs_naive": ir_vs_naive,
                "created_at": now,
            },
        )

    # Alert on checkpoint
    try:
        from worker.tasks.alerts import dispatch_alert
        dispatch_alert.delay(
            event_type="rl_checkpoint_saved",
            title="SAC Ensemble checkpoint saved",
            message=f"episodes={total_episodes} mean_reward_20={mean_reward_20:.4f} ir_vs_naive={ir_vs_naive}",
            priority="low",
        )
    except Exception:
        pass

    logger.info(
        f"SAC training complete: {total_episodes} episodes | "
        f"mean_reward_20={mean_reward_20} | ir_vs_naive={ir_vs_naive} | checkpoint={checkpoint_id}"
    )
    return {
        "status": "ok",
        "checkpoint_id": checkpoint_id,
        "total_episodes": total_episodes,
        "mean_reward_20": mean_reward_20,
        "ir_vs_naive": ir_vs_naive,
    }
