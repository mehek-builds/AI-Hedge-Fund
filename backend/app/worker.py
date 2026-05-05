"""Celery app. Tasks MUST be synchronous (sync functions only). Use asyncio.run() inside tasks if you need async helpers."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "pead_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_BACKEND_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.signals.*": {"queue": "signals"},
        "app.tasks.portfolio.*": {"queue": "portfolio"},
        "app.tasks.rl.*": {"queue": "ml"},
    },
)
