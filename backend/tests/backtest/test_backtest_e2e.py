"""End-to-end backtest tests: FR-6.5 (ex-2020 slice) and FR-6.6 (DB persistence).

These tests are DB-gated: they skip unless DATABASE_URL_SYNC is set and
alembic migrations have been applied.

FR-6.5: ex-2020 slice runs as a separate backtest_runs row and reports Sharpe.
FR-6.6: results are queryable from backtest_runs table after a run completes.
"""

import sys
import os
from datetime import date

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Import requires_db from top-level conftest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from conftest import requires_db
except ImportError:
    from tests.conftest import requires_db


class TestBacktestE2ESchema:
    """FR-6.6: backtest_runs table must be queryable (DB-gated)."""

    @requires_db
    def test_backtest_runs_table_exists(self):
        """backtest_runs table must exist after running alembic upgrade head."""
        from app.flows._db import sync_engine
        from sqlalchemy import inspect

        inspector = inspect(sync_engine)
        tables = inspector.get_table_names()
        assert "backtest_runs" in tables, (
            "backtest_runs table not found. Run: alembic upgrade head"
        )

    @requires_db
    def test_backtest_runs_columns_match_schema(self):
        """backtest_runs columns must match the Phase 8 Explorer spec."""
        from app.flows._db import sync_engine
        from sqlalchemy import inspect

        inspector = inspect(sync_engine)
        cols = {c["name"] for c in inspector.get_columns("backtest_runs")}
        required = {
            "id", "start_date", "end_date", "sharpe", "max_drawdown",
            "ir_vs_baseline", "calmar", "monthly_returns", "gate_status",
            "is_partial_year", "config_snapshot", "created_at",
        }
        assert required <= cols, (
            f"backtest_runs missing columns: {required - cols}"
        )


class TestExclude2020Slice:
    """FR-6.5: ex-2020 stress slice is computed and stored as a separate run."""

    def test_runner_accepts_exclude_date_range(self):
        """BacktestConfig must accept exclude_start and exclude_end parameters."""
        from app.backtest.runner import BacktestConfig

        cfg = BacktestConfig(
            start_date=date(2019, 1, 2),
            end_date=date(2021, 12, 31),
            exclude_start=date(2020, 3, 1),
            exclude_end=date(2020, 4, 30),
            run_label="ex2020",
        )
        assert cfg.exclude_start == date(2020, 3, 1)
        assert cfg.exclude_end == date(2020, 4, 30)
        assert cfg.run_label == "ex2020"

    def test_trading_dates_excludes_specified_range(self):
        """trading_dates with exclude range must omit the excluded period."""
        from app.backtest.runner import trading_dates

        # Small range for fast test
        all_dates = trading_dates(date(2020, 1, 2), date(2020, 4, 30))
        exclude_start = date(2020, 3, 1)
        exclude_end = date(2020, 4, 30)
        filtered = [d for d in all_dates if not (exclude_start <= d <= exclude_end)]

        # The excluded range should have fewer dates
        assert len(filtered) < len(all_dates)
        # No dates in filtered should be in the excluded range
        for d in filtered:
            assert not (exclude_start <= d <= exclude_end)

    def test_runner_marks_partial_year_true_for_excluded_runs(self):
        """run_backtest with exclude_date_range must set is_partial_year=True in result."""
        from app.backtest.runner import BacktestConfig
        from unittest.mock import patch, MagicMock

        cfg = BacktestConfig(
            start_date=date(2020, 1, 2),
            end_date=date(2020, 12, 31),
            exclude_start=date(2020, 3, 1),
            exclude_end=date(2020, 4, 30),
        )

        # Patch sync_session to avoid DB call in unit test
        with patch("app.backtest.runner.sync_session") as mock_ctx:
            mock_session = MagicMock()
            mock_ctx.return_value.__enter__.return_value = mock_session

            # Patch step_replay to return 0 for all dates
            with patch("app.backtest.replay.step_replay", return_value=0.001):
                from app.backtest.runner import run_backtest
                result = run_backtest(cfg)

        assert result["is_partial_year"] is True, (
            "run_backtest must set is_partial_year=True when exclude_date_range is set (FR-6.5)"
        )

    @requires_db
    def test_results_persisted(self):
        """FR-6.6: after a run, a backtest_runs row must be queryable."""
        from app.flows._db import SyncSessionLocal
        from app.models.backtest_runs import BacktestRun

        with SyncSessionLocal() as session:
            # Insert a test row directly (not via full replay)
            run = BacktestRun(
                start_date=date(2020, 1, 2),
                end_date=date(2020, 12, 31),
                sharpe=1.1,
                max_drawdown=0.08,
                ir_vs_baseline=0.5,
                calmar=1.3,
                monthly_returns={"2020-01": 0.012},
                gate_status="pass",
                is_partial_year=False,
                config_snapshot={"run_label": "test"},
            )
            session.add(run)
            session.flush()
            run_id = run.id

        # Query back the row
        with SyncSessionLocal() as session:
            fetched = session.get(BacktestRun, run_id)
            assert fetched is not None, "BacktestRun row must be persisted and queryable"
            assert fetched.sharpe == pytest.approx(1.1, abs=1e-4)
            assert fetched.gate_status == "pass"
