"""L1 Reward Function: FF5-Adjusted Alpha with asymmetric shaping.

Terminal reward:
  alpha = r_position − Σ(β_f · F_f)
  if alpha < 0: alpha *= 1.5  (asymmetric loss penalty)
  + CVaR tail penalty (5th pct of last 200 episodes, weight 0.1)

Intermediate reward:
  daily FF5 alpha contribution × 0.1 (prevents sparse reward problem)

Factor betas estimated via rolling 60-month OLS on the active portfolio
vs. Ken French data library factor returns. Recalibrated quarterly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger
import statsmodels.api as sm

from data.factor_data import FactorDataClient
from config import CONFIG


_FACTOR_COLS = ["MKT-RF", "SMB", "HML", "RMW", "CMA"]


@dataclass
class FactorBetas:
    betas: dict[str, float]     # factor → beta estimate
    r_squared: float
    estimation_end: pd.Timestamp

    def alpha_for_return(self, r: float, factors: dict[str, float]) -> float:
        """Compute FF5-adjusted alpha for a single return observation."""
        factor_return = sum(
            self.betas.get(f, 0.0) * factors.get(f, 0.0)
            for f in _FACTOR_COLS
        )
        return r - factor_return


class FF5RewardFunction:
    """Computes FF5-adjusted alpha reward for RL training.

    Maintains a rolling 60-month portfolio return history and re-estimates
    betas each quarter. At position exit, computes alpha net of factor
    exposures.
    """

    def __init__(self, factor_client: FactorDataClient | None = None):
        self._factors = factor_client or FactorDataClient()
        self._cfg = CONFIG.rl
        self._beta_window_months = CONFIG.rl.beta_rolling_months   # 60

        # Rolling portfolio return history {month_str: portfolio_return}
        self._portfolio_returns: dict[str, float] = {}
        self._current_betas: Optional[FactorBetas] = None
        self._last_recalibration: Optional[pd.Timestamp] = None
        # CVaR tail tracking: last 200 episode alphas (pre-shaping)
        self._episode_alphas: deque[float] = deque(maxlen=200)

        # Load factors once
        self._factor_df = self._factors.get_factors(start="2005-01-01")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def compute_reward(
        self,
        entry_date: pd.Timestamp,
        exit_date: pd.Timestamp,
        position_return: float,
        transaction_cost: float = 0.0,
    ) -> float:
        """Return shaped FF5-adjusted alpha for a closed position.

        Shaping:
          1. Asymmetric loss penalty: losses multiplied by 1.5×
          2. CVaR tail penalty: subtract 0.1 × CVaR(5%) over last 200 episodes
        """
        net_return = position_return - transaction_cost
        self._maybe_recalibrate(exit_date)

        if self._current_betas is None:
            logger.warning("Betas not yet calibrated — returning raw return as reward")
            alpha = net_return
        else:
            factor_returns = self._cumulative_factor_returns(entry_date, exit_date)
            alpha = self._current_betas.alpha_for_return(net_return, factor_returns)

        # Asymmetric loss penalty
        if alpha < 0:
            alpha *= 1.5

        # CVaR tail penalty
        self._episode_alphas.append(alpha)
        cvar_penalty = self._cvar_penalty()
        shaped = alpha - 0.1 * cvar_penalty

        return shaped

    def compute_intermediate(
        self,
        entry_date: pd.Timestamp,
        current_date: pd.Timestamp,
        position_return: float,
    ) -> float:
        """Daily FF5 alpha contribution for intermediate reward signal."""
        if self._current_betas is None:
            return 0.0
        factor_returns = self._cumulative_factor_returns(entry_date, current_date)
        daily_alpha = self._current_betas.alpha_for_return(position_return, factor_returns)
        # Asymmetric penalty applies to intermediate too
        if daily_alpha < 0:
            daily_alpha *= 1.5
        return daily_alpha

    def record_portfolio_return(self, month: pd.Timestamp, r: float) -> None:
        """Register a monthly portfolio return for future beta estimation."""
        self._portfolio_returns[month.strftime("%Y-%m")] = r

    def get_current_betas(self) -> Optional[FactorBetas]:
        return self._current_betas

    # ------------------------------------------------------------------
    # CVaR tail penalty
    # ------------------------------------------------------------------

    def _cvar_penalty(self) -> float:
        """CVaR at 5th percentile of last 200 episode alphas (expected shortfall)."""
        if len(self._episode_alphas) < 10:
            return 0.0
        arr = np.array(self._episode_alphas)
        cutoff = np.percentile(arr, 5)
        tail = arr[arr <= cutoff]
        if len(tail) == 0:
            return 0.0
        return float(np.mean(tail))   # negative number; caller subtracts 0.1 × this

    # ------------------------------------------------------------------
    # Beta estimation
    # ------------------------------------------------------------------

    def _maybe_recalibrate(self, current_date: pd.Timestamp) -> None:
        """Re-estimate betas if a quarter has passed or first run."""
        if self._last_recalibration is None:
            self._recalibrate(current_date)
            return

        months_since = (
            (current_date.year - self._last_recalibration.year) * 12
            + (current_date.month - self._last_recalibration.month)
        )
        # Recalibrate every quarter (3 months)
        if months_since >= 3:
            self._recalibrate(current_date)

    def _recalibrate(self, as_of: pd.Timestamp) -> None:
        """Run rolling 60-month OLS to estimate factor betas."""
        if len(self._portfolio_returns) < 12:
            # Not enough history
            return

        # Build portfolio return series aligned with factor data
        port_series = pd.Series(self._portfolio_returns)
        port_series.index = pd.to_datetime(port_series.index)
        port_series = port_series.sort_index()

        # Use last 60 months
        cutoff = as_of - pd.DateOffset(months=self._beta_window_months)
        port_series = port_series[port_series.index >= cutoff]

        # Align with factor returns
        factors = self._factor_df.copy()
        factors.index = pd.to_datetime(factors.index)
        factors = factors.loc[
            (factors.index >= port_series.index.min())
            & (factors.index <= as_of)
        ]
        factors = factors[_FACTOR_COLS]

        # Inner join on month
        merged = port_series.rename("port").to_frame().join(factors, how="inner")
        if len(merged) < 12:
            return

        # OLS: port ~ MKT-RF + SMB + HML + RMW + CMA
        X = sm.add_constant(merged[_FACTOR_COLS])
        y = merged["port"]
        try:
            result = sm.OLS(y, X).fit()
            betas = {f: float(result.params.get(f, 0.0)) for f in _FACTOR_COLS}
            self._current_betas = FactorBetas(
                betas=betas,
                r_squared=float(result.rsquared),
                estimation_end=as_of,
            )
            self._last_recalibration = as_of
            logger.debug(
                f"FF5 betas recalibrated at {as_of.date()} | R²={result.rsquared:.3f} | "
                f"β_MKT={betas['MKT-RF']:.2f}"
            )
        except Exception as exc:
            logger.warning(f"OLS recalibration failed: {exc}")

    # ------------------------------------------------------------------
    # Factor return accumulation over holding period
    # ------------------------------------------------------------------

    def _cumulative_factor_returns(
        self, entry: pd.Timestamp, exit: pd.Timestamp
    ) -> dict[str, float]:
        """Compound monthly factor returns over a holding period."""
        factors = self._factor_df.copy()
        factors.index = pd.to_datetime(factors.index)
        window = factors.loc[
            (factors.index >= entry) & (factors.index <= exit)
        ][_FACTOR_COLS]

        if window.empty:
            return {f: 0.0 for f in _FACTOR_COLS}

        # Compound: (1+r1)(1+r2)... - 1
        cumulative = (1 + window).prod() - 1
        return cumulative.to_dict()

    # ------------------------------------------------------------------
    # Bootstrap: seed portfolio returns from factor data for initial betas
    # ------------------------------------------------------------------

    def bootstrap_from_history(
        self, start: str = "2005-01-01", market_beta: float = 0.8
    ) -> None:
        """Pre-seed portfolio return history using a synthetic market-like portfolio."""
        factors = self._factor_df.copy()
        factors.index = pd.to_datetime(factors.index)
        factors = factors[factors.index >= pd.Timestamp(start)]

        for month, row in factors.iterrows():
            synthetic_port = (
                market_beta * row["MKT-RF"]
                + 0.1 * row["SMB"]
                + 0.05 * row["RMW"]
                + row["RF"]
            )
            self._portfolio_returns[month.strftime("%Y-%m")] = float(synthetic_port)
        logger.info(f"Bootstrapped {len(self._portfolio_returns)} months of portfolio history")
