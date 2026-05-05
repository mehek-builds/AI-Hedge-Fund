"""Unit tests for compute_portfolio_size_task — no Celery broker, no DB.

All DB and compute calls are mocked. Tests exercise task routing, early-exit
paths, and the success path verifying upsert_rows is called with stop_loss_price.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: Task is registered with Celery under the expected name
# ---------------------------------------------------------------------------


def test_task_is_registered():
    from app.worker import celery_app
    assert "app.tasks.portfolio.compute_portfolio_size_task" in celery_app.tasks


# ---------------------------------------------------------------------------
# Test 2: Returns None when signal_id is not found in DB
# ---------------------------------------------------------------------------


@patch("app.tasks.portfolio.upsert_rows")
@patch("app.tasks.portfolio.load_latest_macro_components")
@patch("app.tasks.portfolio.compute_position_size")
@patch("app.tasks.portfolio.sync_session")
def test_task_returns_none_when_signal_missing(
    mock_sync_session, mock_compute_ps, mock_load_macro, mock_upsert
):
    mock_session = MagicMock()
    # Signal lookup returns None
    mock_session.execute.return_value.fetchone.return_value = None
    mock_sync_session.return_value.__enter__.return_value = mock_session

    from app.tasks.portfolio import compute_portfolio_size_task
    result = compute_portfolio_size_task.run("nonexistent-signal-id")

    assert result is None
    mock_compute_ps.assert_not_called()
    mock_upsert.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Returns None when direction is "hold"
# ---------------------------------------------------------------------------


@patch("app.tasks.portfolio.upsert_rows")
@patch("app.tasks.portfolio.load_latest_macro_components")
@patch("app.tasks.portfolio.compute_position_size")
@patch("app.tasks.portfolio.sync_session")
def test_task_returns_none_for_hold_direction(
    mock_sync_session, mock_compute_ps, mock_load_macro, mock_upsert
):
    mock_session = MagicMock()
    # Signal row: (symbol, naive_size, direction, created_at)
    from datetime import datetime, timezone
    mock_session.execute.return_value.fetchone.return_value = (
        "AAPL", Decimal("0.02"), "hold", datetime.now(timezone.utc)
    )
    mock_sync_session.return_value.__enter__.return_value = mock_session

    from app.tasks.portfolio import compute_portfolio_size_task
    result = compute_portfolio_size_task.run("some-signal-id")

    assert result is None
    mock_compute_ps.assert_not_called()
    mock_upsert.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: Returns symbol on success; upsert_rows called with stop_loss_price
# ---------------------------------------------------------------------------


@patch("app.tasks.portfolio.upsert_rows")
@patch("app.tasks.portfolio.load_latest_macro_components")
@patch("app.tasks.portfolio.compute_position_size")
@patch("app.tasks.portfolio.sync_session")
def test_task_returns_symbol_on_success(
    mock_sync_session, mock_compute_ps, mock_load_macro, mock_upsert
):
    from datetime import datetime, timezone
    from app.portfolio.pipeline import PositionSizingResult

    mock_session = MagicMock()
    now = datetime.now(timezone.utc)

    # First execute call: signal row
    signal_row = ("AAPL", Decimal("0.02"), "long", now)
    # Second execute call: price bar row
    price_row = (Decimal("150.00"),)

    call_count = [0]

    def side_effect(*args, **kwargs):
        result = MagicMock()
        if call_count[0] == 0:
            result.fetchone.return_value = signal_row
        else:
            result.fetchone.return_value = price_row
        call_count[0] += 1
        return result

    mock_session.execute.side_effect = side_effect
    mock_sync_session.return_value.__enter__.return_value = mock_session

    mock_load_macro.return_value = {
        "yield_curve": Decimal("0.5"),
        "sahm": Decimal("0.1"),
        "lei": Decimal("0.2"),
        "ism_pmi": Decimal("0.1"),
        "hyg_lqd_spread": Decimal("3.5"),
        "jpy_aud_carry": Decimal("0.05"),
    }

    stop_price = Decimal("138.00")  # 150 * 0.92
    mock_result = PositionSizingResult(
        symbol="AAPL",
        direction="long",
        final_size_nav=Decimal("0.02"),
        macro_score=0,
        macro_multiplier=Decimal("1.0"),
        erp_capped=False,
        mag7_capped=False,
        stop_loss_price=stop_price,
        constraint_events=(),
    )
    mock_compute_ps.return_value = mock_result

    from app.tasks.portfolio import compute_portfolio_size_task
    result = compute_portfolio_size_task.run("valid-signal-id")

    assert result == "AAPL"
    mock_upsert.assert_called_once()

    # Verify upsert was called with stop_loss_price in the row dict
    call_args = mock_upsert.call_args
    rows_passed = call_args[0][2]  # positional arg: rows list
    assert len(rows_passed) == 1
    assert rows_passed[0]["stop_loss_price"] == stop_price
    assert rows_passed[0]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Test 5: Exceptions from compute_position_size are NOT swallowed (T-04-14)
# ---------------------------------------------------------------------------


@patch("app.tasks.portfolio.upsert_rows")
@patch("app.tasks.portfolio.load_latest_macro_components")
@patch("app.tasks.portfolio.compute_position_size", side_effect=ValueError("compute exploded"))
@patch("app.tasks.portfolio.sync_session")
def test_task_propagates_exception(
    mock_sync_session, mock_compute_ps, mock_load_macro, mock_upsert
):
    from datetime import datetime, timezone

    mock_session = MagicMock()
    now = datetime.now(timezone.utc)

    signal_row = ("AAPL", Decimal("0.02"), "long", now)
    price_row = (Decimal("150.00"),)

    call_count = [0]

    def side_effect(*args, **kwargs):
        result = MagicMock()
        if call_count[0] == 0:
            result.fetchone.return_value = signal_row
        else:
            result.fetchone.return_value = price_row
        call_count[0] += 1
        return result

    mock_session.execute.side_effect = side_effect
    mock_sync_session.return_value.__enter__.return_value = mock_session

    mock_load_macro.return_value = {}

    from app.tasks.portfolio import compute_portfolio_size_task
    with pytest.raises(ValueError, match="compute exploded"):
        compute_portfolio_size_task.run("any-signal-id")

    mock_upsert.assert_not_called()
