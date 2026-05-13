"""Tests for app.tasks.execution — Celery sync_positions_task."""
import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("SKIP_GATE_CHECK", "1")


def test_task_is_registered():
    """sync_positions_task is registered in celery_app.tasks."""
    from app.worker import celery_app
    # Import the task to register it
    import app.tasks.execution  # noqa: F401
    assert "app.tasks.execution.sync_positions_task" in celery_app.tasks


def test_task_routes_to_portfolio_queue():
    """execution.* tasks route to portfolio queue."""
    from app.worker import celery_app
    routes = celery_app.conf.task_routes
    assert routes.get("app.tasks.execution.*") == {"queue": "portfolio"}


def test_beat_schedule_has_sync_positions():
    """beat_schedule includes sync-positions-every-15min at 900s."""
    from app.worker import celery_app
    sched = celery_app.conf.beat_schedule
    assert "sync-positions-every-15min" in sched
    entry = sched["sync-positions-every-15min"]
    assert entry["task"] == "app.tasks.execution.sync_positions_task"
    assert entry["schedule"] == 900.0


@patch("app.tasks.execution.reconcile_positions_with_alpaca")
@patch("app.tasks.execution.sync_session")
def test_sync_positions_task_returns_count(mock_session_cm, mock_reconcile):
    """sync_positions_task returns discrepancy count from reconcile function."""
    mock_session = MagicMock()
    mock_session_cm.return_value.__enter__.return_value = mock_session
    mock_reconcile.return_value = 3

    from app.tasks.execution import sync_positions_task
    result = sync_positions_task.run()

    assert result == 3
    mock_reconcile.assert_called_once_with(mock_session)
