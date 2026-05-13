"""Celery tasks for execution layer (FR-7.2: 15-minute position sync heartbeat)."""
import logging

from app.execution.position_sync import reconcile_positions_with_alpaca
from app.flows._base import sync_session
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.execution.sync_positions_task")
def sync_positions_task() -> int:
    """Reconcile portfolio_positions with Alpaca live state.

    Runs every 15 minutes via Celery beat schedule (900 seconds).
    Returns count of discrepancies resolved.
    """
    logger.info("sync_positions_task: starting position reconciliation")
    with sync_session() as session:
        count = reconcile_positions_with_alpaca(session)
    logger.info("sync_positions_task: resolved %d discrepancies", count)
    return count
