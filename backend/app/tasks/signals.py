"""Celery tasks for signal computation (FR-3.7).

The `compute_signal_task` is dispatched by Phase 7 (FMP earnings ingestion) and
during the Phase 6 backtest to compute one signal per earnings event. Routing to
the 'signals' queue is configured in app.worker.celery_app.task_routes.
"""
from typing import Optional

from app.flows._base import sync_session
from app.signals.pipeline import compute_signal_for_event
from app.worker import celery_app


@celery_app.task(name="app.tasks.signals.compute_signal_task")
def compute_signal_task(earnings_event_id: int) -> Optional[str]:
    """Compute and persist a signal for one earnings event.

    Returns the signal_id (str UUID) when both filters pass, else None.
    Uses a sync session that commits on success and rolls back on exception.
    """
    with sync_session() as session:
        return compute_signal_for_event(session, earnings_event_id)
