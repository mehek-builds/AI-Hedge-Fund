"""FR-6.5 + FR-6.6: end-to-end DB-gated smoke test on a 1-month slice."""

import sys
import os
from datetime import date

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from conftest import requires_db
except ImportError:
    from tests.conftest import requires_db


# ---------------------------------------------------------------------------
# DB-gated smoke tests (skipped without DATABASE_URL_SYNC)
# ---------------------------------------------------------------------------


@requires_db
def test_e2e_writes_backtest_runs_row(sync_engine):
    from app.backtest.runner import run_backtest
    from sqlalchemy import text

    result = run_backtest(date(2022, 6, 1), date(2022, 6, 30), slice_type="main")
    assert result["run_id"] is not None
    with sync_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT run_id, start_date, end_date, slice_type, gate_status "
                "FROM backtest_runs WHERE run_id = :rid"
            ),
            {"rid": result["run_id"]},
        ).fetchone()
    assert row is not None, "row not persisted"
    assert str(row[0]) == result["run_id"]
    assert row[1] == date(2022, 6, 1)
    assert row[2] == date(2022, 6, 30)
    assert row[3] == "main"
    assert row[4] == "pending"  # gate evaluated externally


@requires_db
def test_results_persisted(sync_engine):
    from app.backtest.runner import run_backtest
    from sqlalchemy import text

    result = run_backtest(date(2022, 6, 1), date(2022, 6, 30), slice_type="main")
    with sync_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT sharpe, max_drawdown, ir_vs_baseline, calmar, monthly_returns, "
                "config_snapshot, is_partial_year, total_trades "
                "FROM backtest_runs WHERE run_id = :rid"
            ),
            {"rid": result["run_id"]},
        ).fetchone()
    assert row is not None
    # is_partial_year True since < 200 trading days
    assert row[6] is True
    # monthly_returns is JSONB dict
    assert isinstance(row[4], dict)
    # config_snapshot is JSONB dict
    assert isinstance(row[5], dict)


@requires_db
def test_ex2020_slice_persists_separate_row(sync_engine):
    """FR-6.5: ex-2020 slice is a separate backtest_runs row with slice_type='ex_2020'."""
    from app.backtest.runner import run_backtest
    from sqlalchemy import text

    main = run_backtest(date(2022, 6, 1), date(2022, 6, 30), slice_type="main")
    ex2020 = run_backtest(
        date(2020, 1, 1),
        date(2020, 6, 30),
        slice_type="ex_2020",
        exclude_date_range=(date(2020, 3, 1), date(2020, 4, 30)),
    )
    assert main["run_id"] != ex2020["run_id"]
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT slice_type FROM backtest_runs WHERE run_id IN (:m, :x)"),
            {"m": main["run_id"], "x": ex2020["run_id"]},
        ).fetchall()
    slice_types = {r[0] for r in rows}
    assert slice_types == {"main", "ex_2020"}, slice_types


# ---------------------------------------------------------------------------
# Non-DB validation tests (always run)
# ---------------------------------------------------------------------------


def test_validates_future_end_date():
    """T-6-01: end_date in the future must raise ValueError."""
    from app.backtest.runner import run_backtest

    with pytest.raises(ValueError, match="future"):
        run_backtest(date(2030, 1, 1), date(2030, 12, 31))


def test_validates_inverted_range():
    from app.backtest.runner import run_backtest

    with pytest.raises(ValueError):
        run_backtest(date(2022, 12, 31), date(2022, 1, 1))
