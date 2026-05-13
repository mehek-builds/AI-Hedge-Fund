"""Database adapter for Prioritized Experience Replay (FR-5.2).

Provides the get_engine helper and DB-backed PER operations.
Full implementation created in Plan 03; this module provides the interface
used by worker/flows/rl_trainer.py (Plan 05).
"""

from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    _SQLALCHEMY_AVAILABLE = True
except ImportError:
    _SQLALCHEMY_AVAILABLE = False
    Engine = object  # type: ignore[misc,assignment]


def get_engine(database_url: Optional[str] = None) -> "Engine":
    """Return a SQLAlchemy engine using DATABASE_URL env var or explicit url.

    Args:
        database_url: Optional explicit connection string. Falls back to
                      DATABASE_URL_SYNC or DATABASE_URL env vars.
    """
    if not _SQLALCHEMY_AVAILABLE:
        raise ImportError("sqlalchemy is required for DB-backed PER. Install it.")

    url = (
        database_url
        or os.environ.get("DATABASE_URL_SYNC")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        raise ValueError(
            "No database URL provided. Set DATABASE_URL_SYNC or DATABASE_URL env var, "
            "or pass database_url= to get_engine()."
        )
    return create_engine(url, pool_pre_ping=True)


def upsert_transition(engine: "Engine", transition, agent_id: int = 0) -> None:
    """Upsert a Transition row into rl_transitions hypertable (FR-5.2).

    No-op stub -- full implementation in Plan 03.
    """
    logger.debug("upsert_transition: stub (Plan 03 not yet executed)")


def fetch_top_priority(engine: "Engine", agent_id: int = 0, limit: int = 1000) -> list:
    """Fetch top-N priority transitions from rl_transitions (FR-5.2).

    Returns empty list stub -- full implementation in Plan 03.
    """
    logger.debug("fetch_top_priority: stub (Plan 03 not yet executed)")
    return []


def update_priority_in_db(engine: "Engine", pk: tuple, td_error: float) -> None:
    """Update priority for a transition row by primary key (FR-5.2).

    No-op stub -- full implementation in Plan 03.
    """
    logger.debug("update_priority_in_db: stub (Plan 03 not yet executed)")
