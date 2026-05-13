"""Performance statistics for backtest results.

FR-6.3: compute Sharpe ratio, max drawdown, IR vs. naive baseline,
Calmar ratio, and monthly returns breakdown from a daily returns series.

All formulas use numpy only (no additional dependencies).
Risk-free rate sourced from ff5_factors.rf (point-in-time, daily).
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Annualization factor for daily returns
_TRADING_DAYS = 252


def get_risk_free_rate_daily(
    session: Session,
    as_of: date,
) -> float:
    """Return daily risk-free rate (rf) from ff5_factors as of as_of.

    FR-6.1: filters ingestion_timestamp <= as_of (point-in-time).
    Falls back to daily equivalent of 5.25% annual if no row found.
    """
    row = session.execute(
        text(
            """
            SELECT rf
            FROM ff5_factors
            WHERE date <= :as_of
              AND ingestion_timestamp <= :as_of
            ORDER BY date DESC
            LIMIT 1
            """
        ),
        {"as_of": as_of},
    ).fetchone()
    if row and row[0] is not None:
        return float(row[0])
    # Fallback: 5.25% annual -> daily (2018-2023 average)
    return (1.0 + 0.0525) ** (1.0 / _TRADING_DAYS) - 1.0


def sharpe_ratio(
    daily_returns: list[float],
    daily_rf: float = 0.0,
) -> float:
    """Annualized Sharpe ratio.

    Returns 0.0 if fewer than 2 returns or zero volatility.
    """
    if len(daily_returns) < 2:
        return 0.0
    r = np.array(daily_returns, dtype=float)
    excess = r - daily_rf
    std = excess.std(ddof=1)
    if std < 1e-10:
        return 0.0
    return float(excess.mean() / std * np.sqrt(_TRADING_DAYS))


def max_drawdown(daily_returns: list[float]) -> float:
    """Maximum drawdown as a positive fraction (e.g., 0.15 = 15% drawdown).

    Returns 0.0 if fewer than 1 return.
    """
    if not daily_returns:
        return 0.0
    r = np.array(daily_returns, dtype=float)
    cumulative = np.cumprod(1.0 + r)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (running_max - cumulative) / running_max
    return float(drawdowns.max())


def calmar_ratio(daily_returns: list[float]) -> float:
    """Calmar ratio: annualized return / max drawdown.

    Returns 0.0 if max drawdown is 0 or fewer than 2 returns.
    """
    if len(daily_returns) < 2:
        return 0.0
    r = np.array(daily_returns, dtype=float)
    annual_return = float((1.0 + r.mean()) ** _TRADING_DAYS - 1.0)
    mdd = max_drawdown(daily_returns)
    if mdd == 0.0:
        return 0.0
    return annual_return / mdd


def information_ratio(
    strategy_returns: list[float],
    naive_returns: list[float],
) -> float:
    """Information ratio: (mean active return) / (std of active return).

    Active return = strategy daily return - naive baseline daily return.
    Returns 0.0 if fewer than 2 returns or zero tracking error.
    """
    min_len = min(len(strategy_returns), len(naive_returns))
    if min_len < 2:
        return 0.0
    s = np.array(strategy_returns[:min_len], dtype=float)
    n = np.array(naive_returns[:min_len], dtype=float)
    active = s - n
    std = active.std(ddof=1)
    if std == 0.0:
        return 0.0
    return float(active.mean() / std * np.sqrt(_TRADING_DAYS))


def monthly_returns_breakdown(
    daily_returns: list[float],
    start_date: date,
) -> dict:
    """Compute monthly return totals as a dict keyed by YYYY-MM.

    Each value is the compounded return for that calendar month.
    """
    if not daily_returns:
        return {}

    import pandas as pd

    idx = pd.bdate_range(start=start_date, periods=len(daily_returns), freq="B")
    series = pd.Series(daily_returns, index=idx)
    monthly = (1.0 + series).resample("ME").prod() - 1.0
    return {str(k)[:7]: round(float(v), 8) for k, v in monthly.items()}


def compute_all_stats(
    daily_returns: list[float],
    naive_returns: Optional[list[float]],
    start_date: date,
    daily_rf: float = 0.0,
) -> dict:
    """Compute all FR-6.3 statistics and return a dict.

    Args:
        daily_returns: strategy daily return series
        naive_returns: naive baseline daily returns (same length or None)
        start_date: first date of the return series (for monthly breakdown)
        daily_rf: daily risk-free rate (from ff5_factors.rf or fallback)

    Returns dict with keys: sharpe, max_drawdown, calmar, ir_vs_baseline, monthly_returns.
    """
    result = {
        "sharpe": sharpe_ratio(daily_returns, daily_rf),
        "max_drawdown": max_drawdown(daily_returns),
        "calmar": calmar_ratio(daily_returns),
        "ir_vs_baseline": (
            information_ratio(daily_returns, naive_returns) if naive_returns else None
        ),
        "monthly_returns": monthly_returns_breakdown(daily_returns, start_date),
    }
    logger.info(
        "Stats: sharpe=%.3f, max_dd=%.3f, calmar=%.3f, IR=%.3f",
        result["sharpe"],
        result["max_drawdown"],
        result["calmar"],
        result["ir_vs_baseline"] or 0.0,
    )
    return result
