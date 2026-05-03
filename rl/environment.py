"""PEAD Trading Gymnasium Environment — v3.

Observation space (31-dim):
  Scalars (20):
    [0]  std_surprise           — standardized EPS gap signal
    [1]  signal_composite       — raw_signal × quality_score
    [2]  quality_score          — earnings quality [0.5, 1.5]
    [3]  revenue_surprise       — actual vs implied rev, normalized
    [4]  margin_surprise        — actual vs prior margin
    [5]  guidance_delta         — +1 raised / 0 maintained / -1 lowered
    [6]  macro_composite_score  — normalised to [-1, 0]
    [7]  macro_sizing_mult      — [0, 1]
    [8]  holding_day_pct        — days held / max_hold, [0, 1]
    [9]  current_position_ret   — unrealised return, clipped [-0.15, 0.15]
    [10] is_cyclical            — 0 or 1
    [11] is_mag7                — 0 or 1
    [12] erp_spread             — earnings_yield − real_10y_yield
    [13] erp_compressed         — 1 if spread < 0
    [14] gv_ratio               — VUG P/E / VTV P/E
    [15] gv_stretched           — 1 if ratio > 2.0
    [16] sector_nav_pct         — sector exposure / total NAV
    [17] is_short               — 1 for short position
    [18] completion_sleeve_pct  — completion portfolio sleeve size
    [19] days_to_cover_norm     — days_to_cover / 5, clipped [0, 1]
  One-hot (11):
    [20:31] sector_one_hot      — GICS sector (11 classes)

Action space: Box([0., 0.], [1., 6.]) — (entry_size, hold_bin_float)
  entry_size ∈ [0, 1]  — fraction of position cap
  hold_bin   ∈ [0, 6]  — index into {10,20,30,45,60,75,90}; rounded at use
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional
from loguru import logger

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    import gym
    from gym import spaces

from config import CONFIG
from rl.reward import FF5RewardFunction
from risk.controls import RiskControls
from portfolio.architecture import MAG7


_SECTORS = CONFIG.gics_sectors
_SECTOR_TO_IDX = {s: i for i, s in enumerate(_SECTORS)}
_N_SECTORS = len(_SECTORS)
_HOLD_BINS = [10, 20, 30, 45, 60, 75, 90]
_N_SCALAR = 20
_OBS_DIM = _N_SCALAR + _N_SECTORS   # 31


class Position:
    """Tracks a single open PEAD position."""

    def __init__(
        self,
        ticker: str,
        entry_date: pd.Timestamp,
        entry_price: float,
        size: float,
        sector: str,
        is_cyclical: bool,
        max_hold: int,
        is_short: bool = False,
    ):
        self.ticker = ticker
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.size = size
        self.sector = sector
        self.is_cyclical = is_cyclical
        self.max_hold = max_hold
        self.is_short = is_short
        self.days_held = 0
        self.current_price: float = entry_price

    @property
    def unrealised_return(self) -> float:
        if self.entry_price == 0:
            return 0.0
        raw = (self.current_price - self.entry_price) / self.entry_price
        return raw * (-1.0 if self.is_short else 1.0)

    @property
    def holding_day_pct(self) -> float:
        return min(self.days_held / self.max_hold, 1.0)

    def is_expired(self) -> bool:
        return self.days_held >= self.max_hold

    def should_stop(self) -> bool:
        stop_pct = CONFIG.portfolio_arch.short_stop_pct if self.is_short else abs(CONFIG.risk.hard_stop_pct)
        return self.unrealised_return < -stop_pct


class PEADTradingEnv(gym.Env):
    """Gymnasium environment for PEAD trading — v3 (SAC Ensemble compatible).

    Episodes cover one earnings event entry → exit. The agent selects
    (entry_size, hold_bin) at entry; environment steps daily until exit.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        events_df: pd.DataFrame,
        prices_df: pd.DataFrame,
        regime_df: pd.DataFrame,
        reward_fn: FF5RewardFunction | None = None,
        risk_controls: RiskControls | None = None,
        allow_short: bool = False,
        seed: int = 42,
    ):
        super().__init__()
        self._events = events_df.sort_values("announce_date").reset_index(drop=True)
        self._prices = prices_df
        self._regime = regime_df
        self._reward_fn = reward_fn or FF5RewardFunction()
        self._risk = risk_controls or RiskControls()
        self._allow_short = allow_short

        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(_OBS_DIM,), dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=np.array([0.0, 0.0], dtype=np.float32),
            high=np.array([1.0, float(len(_HOLD_BINS) - 1)], dtype=np.float32),
        )

        self._rng = np.random.default_rng(seed)
        self._event_idx: int = 0
        self._position: Optional[Position] = None
        self._nav: float = 1.0
        self._sector_nav: dict[str, float] = {}
        self._erp_spread: float = 0.0
        self._erp_compressed: bool = False
        self._gv_ratio: float = 1.0
        self._gv_stretched: bool = False
        self._completion_sleeve_pct: float = 0.0

    # ── Context setters (called by worker before each episode batch) ────────

    def set_arch_state(
        self,
        erp_spread: float,
        erp_compressed: bool,
        gv_ratio: float,
        gv_stretched: bool,
        completion_sleeve_pct: float,
        sector_nav: dict[str, float] | None = None,
    ) -> None:
        self._erp_spread = erp_spread
        self._erp_compressed = erp_compressed
        self._gv_ratio = gv_ratio
        self._gv_stretched = gv_stretched
        self._completion_sleeve_pct = completion_sleeve_pct
        if sector_nav is not None:
            self._sector_nav = sector_nav

    # ── Gymnasium API ───────────────────────────────────────────────────────

    def reset(self, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        if self._event_idx >= len(self._events):
            self._event_idx = 0
        self._current_event = self._events.iloc[self._event_idx]
        self._event_idx += 1
        self._position = None
        obs = self._build_obs()
        return obs.astype(np.float32), {}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        entry_size = float(np.clip(action[0], 0.0, 1.0))
        hold_bin = int(np.clip(round(float(action[1])), 0, len(_HOLD_BINS) - 1))

        if self._position is None:
            reward, terminated, truncated = self._enter_position(entry_size, hold_bin)
        else:
            reward, terminated, truncated = self._step_position()

        obs = self._build_obs()
        return obs.astype(np.float32), reward, terminated, truncated, {}

    # ── Entry / step / exit ─────────────────────────────────────────────────

    def _enter_position(self, entry_size: float, hold_bin: int) -> tuple[float, bool, bool]:
        event = self._current_event
        announce = pd.Timestamp(event["announce_date"])
        regime = self._get_regime(announce)

        if regime["is_halted"]:
            return 0.0, True, False

        signal = float(event.get("signal_composite", event.get("signal_strength", 0.0)))
        is_short = signal < 0 and self._allow_short

        if not self._allow_short and signal < 0:
            return 0.0, True, False
        if abs(entry_size) < 0.01:
            return 0.0, True, False

        effective_size = entry_size * regime["sizing_multiplier"]
        effective_size = self._risk.clip_position_size(effective_size)
        if self._erp_compressed:
            effective_size *= CONFIG.portfolio_arch.erp_compression_cap

        entry_price = self._get_price(event["ticker"], announce)
        if np.isnan(entry_price):
            return 0.0, True, False

        max_hold = _HOLD_BINS[hold_bin]

        self._position = Position(
            ticker=event["ticker"],
            entry_date=announce,
            entry_price=entry_price,
            size=effective_size,
            sector=event["sector"],
            is_cyclical=bool(event.get("is_cyclical", False)),
            max_hold=max_hold,
            is_short=is_short,
        )
        return 0.0, False, False

    def _step_position(self) -> tuple[float, bool, bool]:
        pos = self._position
        pos.days_held += 1
        step_date = pos.entry_date + pd.Timedelta(days=pos.days_held)
        new_price = self._get_price(pos.ticker, step_date)
        if not np.isnan(new_price):
            pos.current_price = new_price

        # Intermediate FF5 alpha reward (scaled ×0.1 to prevent sparse reward issue)
        intermediate = self._reward_fn.compute_intermediate(
            pos.entry_date, step_date, pos.unrealised_return * abs(pos.size)
        ) * 0.1

        if pos.should_stop() or pos.is_expired():
            terminal = self._close_position(pos.should_stop())
            return terminal + intermediate, True, False

        return intermediate, False, False

    def _close_position(self, stop: bool = False) -> float:
        pos = self._position
        exit_date = pos.entry_date + pd.Timedelta(days=pos.days_held)
        tc = CONFIG.risk.transaction_cost_bps / 10_000
        alpha = self._reward_fn.compute_reward(
            entry_date=pos.entry_date,
            exit_date=exit_date,
            position_return=pos.unrealised_return * abs(pos.size),
            transaction_cost=tc,
        )
        month = exit_date.to_period("M").to_timestamp()
        self._reward_fn.record_portfolio_return(month, pos.unrealised_return * abs(pos.size))
        self._position = None
        return float(alpha)

    # ── Observation builder ─────────────────────────────────────────────────

    def _build_obs(self) -> np.ndarray:
        event = self._current_event
        pos = self._position
        announce = pd.Timestamp(event["announce_date"])
        regime = self._get_regime(announce)

        sector = str(event.get("sector", ""))
        ticker = str(event.get("ticker", ""))
        dtc = float(event.get("days_to_cover", 0.0))

        scalars = np.array([
            float(event.get("std_surprise", 0.0)),
            float(event.get("signal_composite", event.get("signal_strength", 0.0))),
            float(event.get("quality_score", 1.0)),
            float(event.get("revenue_surprise", 0.0)),
            float(event.get("margin_surprise", 0.0)),
            float(event.get("guidance_delta", 0.0)),
            float(regime["composite_score"]) / 6.0,
            float(regime["sizing_multiplier"]),
            float(pos.holding_day_pct) if pos else 0.0,
            float(np.clip(pos.unrealised_return, -0.15, 0.15)) if pos else 0.0,
            float(bool(event.get("is_cyclical", False))),
            float(ticker in MAG7),
            float(self._erp_spread),
            float(self._erp_compressed),
            float(self._gv_ratio),
            float(self._gv_stretched),
            float(self._sector_nav.get(sector, 0.0) / max(self._nav, 1e-6)),
            float(pos.is_short) if pos else 0.0,
            float(self._completion_sleeve_pct),
            float(np.clip(dtc / 5.0, 0.0, 1.0)),
        ], dtype=np.float32)

        sector_oh = np.zeros(_N_SECTORS, dtype=np.float32)
        if sector in _SECTOR_TO_IDX:
            sector_oh[_SECTOR_TO_IDX[sector]] = 1.0

        return np.concatenate([scalars, sector_oh])

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _get_price(self, ticker: str, date: pd.Timestamp) -> float:
        if ticker not in self._prices.columns:
            return float("nan")
        series = self._prices[ticker].dropna()
        idx = series.index.get_indexer([date], method="ffill")[0]
        if idx < 0:
            return float("nan")
        return float(series.iloc[idx])

    def _get_regime(self, date: pd.Timestamp) -> dict:
        if self._regime is None or self._regime.empty:
            return {"composite_score": 0, "sizing_multiplier": 1.0, "is_halted": False}
        idx = self._regime.index.get_indexer([date], method="ffill")[0]
        if idx < 0:
            return {"composite_score": 0, "sizing_multiplier": 1.0, "is_halted": False}
        row = self._regime.iloc[idx]
        return {
            "composite_score":   int(row.get("composite_score", 0)),
            "sizing_multiplier": float(row.get("sizing_multiplier", 1.0)),
            "is_halted":         bool(row.get("is_halted", False)),
        }
