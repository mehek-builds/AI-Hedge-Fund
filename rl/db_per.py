"""PostgreSQL adapter for PER buffer persistence (FR-5.2).

Provides get_engine() and helpers for reading/writing rl_transitions rows.
"""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


_DEFAULT_DATABASE_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://pead:pead@localhost:5432/pead",
)


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Return a SQLAlchemy Engine for the given URL (or DATABASE_URL_SYNC env var).

    Uses pool_pre_ping so stale connections are detected automatically.
    """
    url = database_url or _DEFAULT_DATABASE_URL
    return create_engine(url, pool_pre_ping=True)
