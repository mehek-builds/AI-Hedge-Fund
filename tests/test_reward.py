"""Tests for L1 FF5 reward function."""

import pytest
import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rl.reward import FF5RewardFunction, FactorBetas


class TestFactorBetas:
    def test_alpha_removes_factor_return(self):
        betas = FactorBetas(
            betas={"MKT-RF": 1.0, "SMB": 0.0, "HML": 0.0, "RMW": 0.0, "CMA": 0.0},
            r_squared=0.9,
            estimation_end=pd.Timestamp("2023-01-01"),
        )
        # Portfolio return exactly equals market factor return → alpha = 0
        factors = {"MKT-RF": 0.05, "SMB": 0.0, "HML": 0.0, "RMW": 0.0, "CMA": 0.0}
        alpha = betas.alpha_for_return(r=0.05, factors=factors)
        assert alpha == pytest.approx(0.0)

    def test_positive_alpha_when_beating_factors(self):
        betas = FactorBetas(
            betas={"MKT-RF": 1.0, "SMB": 0.0, "HML": 0.0, "RMW": 0.0, "CMA": 0.0},
            r_squared=0.85,
            estimation_end=pd.Timestamp("2023-01-01"),
        )
        factors = {"MKT-RF": 0.03, "SMB": 0.0, "HML": 0.0, "RMW": 0.0, "CMA": 0.0}
        alpha = betas.alpha_for_return(r=0.05, factors=factors)
        assert alpha == pytest.approx(0.02)


class TestFF5RewardFunction:
    def test_bootstrap_seeds_history(self):
        fn = FF5RewardFunction()
        fn.bootstrap_from_history(start="2015-01-01")
        assert len(fn._portfolio_returns) > 0

    def test_reward_returns_float(self):
        fn = FF5RewardFunction()
        fn.bootstrap_from_history(start="2010-01-01")
        # Force recalibration
        fn._maybe_recalibrate(pd.Timestamp("2020-01-01"))

        reward = fn.compute_reward(
            entry_date=pd.Timestamp("2020-03-01"),
            exit_date=pd.Timestamp("2020-06-01"),
            position_return=0.08,
            transaction_cost=0.0015,
        )
        assert isinstance(reward, float)

    def test_transaction_cost_reduces_reward(self):
        fn = FF5RewardFunction()
        fn.bootstrap_from_history()
        fn._maybe_recalibrate(pd.Timestamp("2020-01-01"))

        r_no_tc = fn.compute_reward(
            pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"),
            position_return=0.05, transaction_cost=0.0,
        )
        r_with_tc = fn.compute_reward(
            pd.Timestamp("2020-03-01"), pd.Timestamp("2020-06-01"),
            position_return=0.05, transaction_cost=0.002,
        )
        assert r_with_tc < r_no_tc

    def test_recalibration_triggered_quarterly(self):
        fn = FF5RewardFunction()
        fn.bootstrap_from_history(start="2010-01-01")
        fn._maybe_recalibrate(pd.Timestamp("2018-01-01"))
        first_calibration = fn._last_recalibration

        fn._maybe_recalibrate(pd.Timestamp("2018-02-01"))  # same quarter
        assert fn._last_recalibration == first_calibration

        fn._maybe_recalibrate(pd.Timestamp("2018-04-01"))  # new quarter
        assert fn._last_recalibration > first_calibration
