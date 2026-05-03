"""RL Agent wrapper using Stable-Baselines3 PPO.

Wraps SB3's PPO with PEAD-specific defaults and evaluation utilities.
PPO chosen per PRD §8 (stable, continuous action space).
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    from stable_baselines3 import PPO, SAC
    from stable_baselines3.common.env_checker import check_env
    from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnNoModelImprovement
    from stable_baselines3.common.monitor import Monitor
    _SB3_AVAILABLE = True
except ImportError:
    _SB3_AVAILABLE = False
    logger.warning("stable-baselines3 not installed — agent training disabled")

from config import CONFIG
from rl.environment import PEADTradingEnv


class RLAgent:
    """PEAD RL Agent supporting PPO and SAC algorithms."""

    def __init__(
        self,
        algorithm: str = "PPO",
        model_dir: str = "models",
    ):
        self._algorithm = algorithm.upper()
        self._model_dir = Path(model_dir)
        self._model_dir.mkdir(exist_ok=True)
        self._model = None

    def train(
        self,
        env: PEADTradingEnv,
        total_timesteps: int | None = None,
        eval_env: Optional[PEADTradingEnv] = None,
        tensorboard_log: str | None = None,
    ) -> None:
        """Train the RL agent on the given environment."""
        if not _SB3_AVAILABLE:
            raise RuntimeError("stable-baselines3 not installed")

        total_timesteps = total_timesteps or CONFIG.rl.total_timesteps

        # Validate env
        logger.info("Validating environment...")
        check_env(env, warn=True)

        train_env = Monitor(env)

        cfg = CONFIG.rl
        if self._algorithm == "PPO":
            self._model = PPO(
                policy="MlpPolicy",
                env=train_env,
                learning_rate=cfg.learning_rate,
                n_steps=cfg.n_steps,
                batch_size=cfg.batch_size,
                n_epochs=cfg.n_epochs,
                gamma=cfg.gamma,
                verbose=1,
                tensorboard_log=tensorboard_log,
            )
        elif self._algorithm == "SAC":
            self._model = SAC(
                policy="MlpPolicy",
                env=train_env,
                learning_rate=cfg.learning_rate,
                gamma=cfg.gamma,
                verbose=1,
                tensorboard_log=tensorboard_log,
            )
        else:
            raise ValueError(f"Unsupported algorithm: {self._algorithm}")

        callbacks = []
        if eval_env is not None:
            eval_callback = EvalCallback(
                Monitor(eval_env),
                best_model_save_path=str(self._model_dir / "best"),
                log_path=str(self._model_dir / "logs"),
                eval_freq=10_000,
                n_eval_episodes=50,
                deterministic=True,
            )
            callbacks.append(eval_callback)

        logger.info(f"Training {self._algorithm} for {total_timesteps:,} timesteps")
        self._model.learn(total_timesteps=total_timesteps, callback=callbacks or None)
        logger.info("Training complete")

    def predict(
        self, obs: np.ndarray, deterministic: bool = True
    ) -> tuple[np.ndarray, Any]:
        """Run inference on a single observation."""
        if self._model is None:
            # Naive baseline: size proportional to signal strength (obs[1])
            signal = float(obs[1]) if len(obs) > 1 else 0.0
            action = np.clip(signal / 5.0, -1.0, 1.0)
            return np.array([action], dtype=np.float32), None
        return self._model.predict(obs, deterministic=deterministic)

    def save(self, name: str = "pead_agent") -> Path:
        if self._model is None:
            raise RuntimeError("No model to save")
        path = self._model_dir / name
        self._model.save(str(path))
        logger.info(f"Model saved to {path}")
        return path

    def load(self, name: str = "pead_agent") -> None:
        if not _SB3_AVAILABLE:
            raise RuntimeError("stable-baselines3 not installed")
        path = self._model_dir / f"{name}.zip"
        if not path.exists():
            raise FileNotFoundError(f"No model at {path}")
        AlgoCls = PPO if self._algorithm == "PPO" else SAC
        self._model = AlgoCls.load(str(path))
        logger.info(f"Model loaded from {path}")

    # ------------------------------------------------------------------
    # Naive baseline for comparison (PRD §6: RL must beat this)
    # ------------------------------------------------------------------

    @staticmethod
    def naive_baseline_action(obs: np.ndarray) -> np.ndarray:
        """Full-size in direction of signal strength — no RL learning."""
        signal = float(obs[1]) if len(obs) > 1 else 0.0
        # Direction from signal sign, fixed size = 1.0
        action = float(np.sign(signal))
        return np.array([action], dtype=np.float32)


# Avoid 'Any' import at module level for cleanliness
from typing import Any
