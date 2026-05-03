"""Unit tests for compute_signal_task — no Celery broker, no DB."""
from unittest.mock import patch, MagicMock

import pytest


def test_task_is_registered():
    from app.tasks.signals import compute_signal_task
    from app.worker import celery_app
    assert "app.tasks.signals.compute_signal_task" in celery_app.tasks


def test_task_routes_to_signals_queue():
    from app.worker import celery_app
    routes = celery_app.conf.task_routes
    # task_routes is a dict; signals.* should route to 'signals' queue
    assert routes.get("app.tasks.signals.*") == {"queue": "signals"}


@patch("app.tasks.signals.compute_signal_for_event")
@patch("app.tasks.signals.sync_session")
def test_task_returns_signal_id_on_success(mock_session_cm, mock_compute):
    mock_session = MagicMock()
    mock_session_cm.return_value.__enter__.return_value = mock_session
    mock_compute.return_value = "abc-123"
    from app.tasks.signals import compute_signal_task
    result = compute_signal_task.run(42)
    assert result == "abc-123"
    mock_compute.assert_called_once_with(mock_session, 42)


@patch("app.tasks.signals.compute_signal_for_event")
@patch("app.tasks.signals.sync_session")
def test_task_returns_none_when_suppressed(mock_session_cm, mock_compute):
    mock_session_cm.return_value.__enter__.return_value = MagicMock()
    mock_compute.return_value = None
    from app.tasks.signals import compute_signal_task
    assert compute_signal_task.run(99) is None


@patch("app.tasks.signals.compute_signal_for_event", side_effect=ValueError("boom"))
@patch("app.tasks.signals.sync_session")
def test_task_propagates_exception(mock_session_cm, mock_compute):
    mock_session_cm.return_value.__enter__.return_value = MagicMock()
    from app.tasks.signals import compute_signal_task
    with pytest.raises(ValueError, match="boom"):
        compute_signal_task.run(1)
