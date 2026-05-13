"""Shared fixtures for backtest tests.

Provides:
- synthetic_daily_returns: a deterministic list of 252 daily returns
- synthetic_naive_returns: naive baseline returns at NAIVE_POSITION_SIZE level
- mock_sync_session: a mock sync SQLAlchemy session for unit tests
"""

from datetime import date
from unittest.mock import MagicMock

import numpy as np
import pytest


# Seed for determinism across test runs
_RNG = np.random.default_rng(seed=42)

# Number of trading days in a standard backtest year
_N_DAYS = 252


@pytest.fixture
def synthetic_daily_returns() -> list[float]:
    """252 daily returns with Sharpe ~1.1 and max drawdown ~8%.

    Generated with fixed seed for golden-number tests.
    Mean ~0.0004, std ~0.006 (typical equity strategy).
    """
    returns = _RNG.normal(loc=0.0004, scale=0.006, size=_N_DAYS)
    return returns.tolist()


@pytest.fixture
def synthetic_naive_returns() -> list[float]:
    """252 naive baseline returns (2% NAV fixed-size long).

    Slightly lower Sharpe than strategy to ensure positive IR.
    """
    returns = _RNG.normal(loc=0.00025, scale=0.007, size=_N_DAYS)
    return returns.tolist()


@pytest.fixture
def synthetic_ex2020_returns() -> list[float]:
    """Returns excluding the March-April 2020 volatility window.

    Lower variance slice - should have Sharpe > 0.8.
    """
    returns = _RNG.normal(loc=0.0003, scale=0.005, size=_N_DAYS)
    return returns.tolist()


@pytest.fixture
def mock_sync_session() -> MagicMock:
    """Mock SQLAlchemy sync session for unit tests that do not need a real DB."""
    session = MagicMock()
    # Mock execute().fetchone() to return None by default
    session.execute.return_value.fetchone.return_value = None
    session.execute.return_value.fetchall.return_value = []
    return session


@pytest.fixture
def backtest_start_date() -> date:
    return date(2018, 1, 2)


@pytest.fixture
def backtest_end_date() -> date:
    return date(2023, 12, 29)
