"""DB adapter for the rl_transitions hypertable (PER persistence).

FR-5.2: Transitions stored in and sampled from PostgreSQL rl_transitions.
The in-memory SumTree (rl/per_buffer.py) remains the priority index for
O(log n) sampling; this module owns DB I/O.

Per CLAUDE.md / FR-1.5: every record carries ingestion_timestamp.

NOTE: This is a minimal stub providing get_engine for pretrain_transformer.py.
Full implementation (upsert_transition, fetch_top_priority, update_priority_in_db)
is delivered in Plan 05-03.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine(database_url: str | None = None) -> Engine:
    """Synchronous engine for the trainer process.

    The trainer uses psycopg2 (sync) -- see RESEARCH.md Standard Stack.
    """
    url = database_url or os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql://pead:pead@localhost:5432/pead",
    )
    return create_engine(url, pool_pre_ping=True)
