"""DB adapter for the rl_transitions hypertable (PER persistence).

FR-5.2: Transitions stored in and sampled from PostgreSQL `rl_transitions`.
The in-memory SumTree (rl/per_buffer.py) remains the priority index for
O(log n) sampling; this module owns DB I/O.

Per CLAUDE.md / FR-1.5: every record carries ingestion_timestamp.
Per RESEARCH.md Pitfall 2: priorities updated by PK, not SumTree leaf index.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from rl.per_buffer import Transition


def get_engine(database_url: str | None = None) -> Engine:
    """Synchronous engine for the trainer process.

    The trainer uses psycopg2 (sync) -- see RESEARCH.md Standard Stack.
    """
    url = database_url or os.environ.get(
        "DATABASE_URL_SYNC",
        "postgresql://pead:pead@localhost:5432/pead",
    )
    return create_engine(url, pool_pre_ping=True)


def upsert_transition(
    conn: Connection,
    *,
    agent_id: int,
    episode_id: str,
    step: int,
    transition: Transition,
    priority: float,
    symbol: str | None = None,
    ts: datetime | None = None,
) -> None:
    """Insert (or update on conflict) a single transition into rl_transitions.

    Uses parameterized SQL (FR security V5 + STRIDE T-05-08).
    """
    row_ts = ts or datetime.now(timezone.utc)
    state_json = json.dumps(transition.state.tolist())
    next_state_json = json.dumps(transition.next_state.tolist())
    # action is stored in NUMERIC(6,4); for [entry, hold] we persist entry only --
    # hold is recoverable from JSON state_vec downstream (kept compatible with
    # the schema's single-value action column from migration 0001).
    action_value = float(transition.action[0]) if transition.action.shape else float(transition.action)
    conn.execute(
        text(
            """
            INSERT INTO rl_transitions (
                ts, episode_id, step, agent_id, symbol,
                state_vec, action, reward, next_state_vec, done, priority,
                ingestion_timestamp
            ) VALUES (
                :ts, :episode_id, :step, :agent_id, :symbol,
                CAST(:state_vec AS JSONB), :action, :reward,
                CAST(:next_state_vec AS JSONB), :done, :priority,
                :ingestion_timestamp
            )
            ON CONFLICT (ts, episode_id, step) DO UPDATE SET
                priority = EXCLUDED.priority
            """
        ),
        {
            "ts": row_ts,
            "episode_id": episode_id,
            "step": step,
            "agent_id": agent_id,
            "symbol": symbol,
            "state_vec": state_json,
            "action": action_value,
            "reward": float(transition.reward),
            "next_state_vec": next_state_json,
            "done": bool(transition.done),
            "priority": float(priority),
            "ingestion_timestamp": row_ts,
        },
    )


def fetch_top_priority(
    conn: Connection,
    *,
    agent_id: int,
    limit: int = 50_000,
) -> list[dict[str, Any]]:
    """Pull the top-`limit` highest-priority rows for an agent (ix_rl_agent_priority)."""
    rows = conn.execute(
        text(
            """
            SELECT ts, episode_id, step, agent_id, state_vec, action,
                   reward, next_state_vec, done, priority
            FROM rl_transitions
            WHERE agent_id = :agent_id
            ORDER BY priority DESC
            LIMIT :limit
            """
        ),
        {"agent_id": agent_id, "limit": limit},
    ).mappings().all()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "ts": row["ts"],
        "episode_id": str(row["episode_id"]),
        "step": int(row["step"]),
        "agent_id": int(row["agent_id"]),
        "state": np.array(row["state_vec"] or [], dtype=np.float32),
        "action": float(row["action"]) if row["action"] is not None else 0.0,
        "reward": float(row["reward"]) if row["reward"] is not None else 0.0,
        "next_state": np.array(row["next_state_vec"] or [], dtype=np.float32),
        "done": bool(row["done"]),
        "priority": float(row["priority"]) if row["priority"] is not None else 1.0,
    }


def update_priority_in_db(
    conn: Connection,
    *,
    ts: datetime,
    episode_id: str,
    step: int,
    priority: float,
) -> None:
    """Update priority for a transition by primary key (NOT SumTree leaf index)."""
    conn.execute(
        text(
            """
            UPDATE rl_transitions
            SET priority = :priority
            WHERE ts = :ts AND episode_id = :episode_id AND step = :step
            """
        ),
        {"ts": ts, "episode_id": episode_id, "step": step, "priority": float(priority)},
    )


def new_episode_id() -> str:
    """Convenience UUID generator for episode boundaries."""
    return str(uuid4())
