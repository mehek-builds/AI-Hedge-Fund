"""Celery application configuration."""

from __future__ import annotations

import os

from celery import Celery
from loguru import logger

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "pead_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "worker.tasks.ingest",
        "worker.tasks.signal",
        "worker.tasks.execution",
        "worker.tasks.rl_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/New_York",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 24h
)

logger.info(f"Celery app configured with broker: {REDIS_URL}")
