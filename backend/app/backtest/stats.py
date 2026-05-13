"""Performance statistics for backtest results.

FR-6.3: compute Sharpe ratio, max drawdown, IR vs. naive baseline,
Calmar ratio, and monthly returns breakdown from a daily returns series.

All formulas use numpy only (no additional dependencies).
Risk-free rate sourced from ff5_factors.rf (point-in-time, daily).

Plan 06-03 adds vectorized compute_* functions alongside the original helpers.
All math runs on numpy arrays in a single pass; no Python-for-loop accumulation
of floating-point sums (per RESEARCH Pitfall 5).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
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


def compute_all_stats_v1(
    daily_returns: list[float],
    naive_returns: Optional[list[float]],
    start_date: date,
    daily_rf: float = 0.0,
) -> dict:
    """Compute all FR-6.3 statistics (legacy list-based API).

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


# ---------------------------------------------------------------------------
# Plan 06-03 vectorized API (compute_* functions)
# All math runs on numpy arrays in a single pass; no Python loop accumulation.
# ---------------------------------------------------------------------------

TRADING_DAYS_PER_YEAR = 252


def compute_sharpe(daily_returns: np.ndarray, daily_rf) -> float:
    """Annualized Sharpe = mean(excess) / std(excess) * sqrt(252).

    daily_rf may be a scalar or an array of the same length as daily_returns.
    Returns 0.0 if len < 2 or std(excess) == 0.
    """
    r = np.asarray(daily_returns, dtype=np.float64)
    if r.size < 2:
        return 0.0
    rf = (
        np.asarray(daily_rf, dtype=np.float64)
        if hasattr(daily_rf, "__len__")
        else float(daily_rf)
    )
    excess = r - rf
    sd = float(excess.std(ddof=0))
    if sd < 1e-10:
        return 0.0
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS_PER_YEAR))


def compute_max_drawdown(daily_returns: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction.

    Returns 0.0 if array has fewer than 2 elements or is empty.
    """
    r = np.asarray(daily_returns, dtype=np.float64)
    if r.size < 2:
        return 0.0
    cumulative = np.cumprod(1.0 + r)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    return float(abs(drawdowns.min()))


def compute_ir_vs_baseline(
    strategy_returns: np.ndarray, naive_returns: np.ndarray
) -> float:
    """Information Ratio vs naive baseline = mean(diff) / std(diff) * sqrt(252).

    Returns 0.0 if fewer than 2 elements or arrays differ in length or std == 0.
    """
    s = np.asarray(strategy_returns, dtype=np.float64)
    n = np.asarray(naive_returns, dtype=np.float64)
    if s.size < 2 or s.size != n.size:
        return 0.0
    diff = s - n
    sd = float(diff.std(ddof=0))
    if sd == 0.0:
        return 0.0
    return float(diff.mean() / sd * np.sqrt(TRADING_DAYS_PER_YEAR))


def compute_calmar(annualized_return: float, max_drawdown_val: float) -> float:
    """Calmar = annualized_return / max_drawdown. Returns 0.0 if drawdown == 0."""
    if max_drawdown_val == 0:
        return 0.0
    return float(annualized_return / max_drawdown_val)


def compute_annualized_return(daily_returns: np.ndarray) -> float:
    """Geometric annualized return from daily return array."""
    r = np.asarray(daily_returns, dtype=np.float64)
    if r.size < 1:
        return 0.0
    total = float(np.prod(1.0 + r))
    years = r.size / TRADING_DAYS_PER_YEAR
    if years <= 0:
        return 0.0
    return total ** (1.0 / years) - 1.0


def compute_monthly_returns(dates, daily_returns: np.ndarray) -> dict[str, float]:
    """Group daily returns by YYYY-MM and return compounded monthly returns.

    dates: list of date objects, same length as daily_returns.
    Returns dict {YYYY-MM: float}.
    """
    r = np.asarray(daily_returns, dtype=np.float64)
    if r.size == 0 or len(dates) != r.size:
        return {}
    buckets: dict[str, list[float]] = {}
    for d, val in zip(dates, r):
        key = f"{d.year:04d}-{d.month:02d}"
        buckets.setdefault(key, []).append(float(val))
    return {
        k: float(np.prod(1.0 + np.asarray(v, dtype=np.float64)) - 1.0)
        for k, v in buckets.items()
    }


def load_daily_rf_as_of(session, as_of: datetime) -> float:
    """Return daily risk-free rate (decimal fraction) from ff5_factors visible at as_of.

    Pattern: SELECT rf FROM ff5_factors WHERE date <= :as_of
             AND ingestion_timestamp <= :as_of ORDER BY date DESC LIMIT 1.
    Fallback: 0.0 if no row visible.
    """
    row = session.execute(
        text(
            """
            SELECT rf FROM ff5_factors
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
    return 0.0


def compute_all_stats(  # type: ignore[override]
    dates,
    daily_returns,
    naive_returns,
    daily_rf_array,
) -> dict:
    """Compute all FR-6.3 stats (Plan 06-03 vectorized overload).

    This overload is selected when the first argument is a list/sequence of dates
    (not a list of floats). It returns the Plan 06-03 schema with is_partial_year.

    Signature: compute_all_stats(dates, daily_returns, naive_returns, daily_rf_array)
    """
    r = np.asarray(daily_returns, dtype=np.float64)
    ann = compute_annualized_return(r)
    mdd = compute_max_drawdown(r)
    return {
        "sharpe": compute_sharpe(r, daily_rf_array),
        "max_drawdown": mdd,
        "ir_vs_baseline": compute_ir_vs_baseline(r, naive_returns),
        "calmar": compute_calmar(ann, mdd),
        "annualized_return": ann,
        "monthly_returns": compute_monthly_returns(dates, r),
        "is_partial_year": bool(r.size < 200),
    }
