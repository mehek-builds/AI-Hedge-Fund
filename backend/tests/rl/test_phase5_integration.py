"""DB-gated integration tests for Phase 5 (FR-5.1..FR-5.7).

These tests skip automatically when DATABASE_URL_SYNC is not set. They run
in CI's PostgreSQL service and locally when:

    DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest tests/rl/

Pre-req: alembic upgrade head must have been run so migration 0004 is applied.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pytest
import torch
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tests.conftest import requires_db


SYNC_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://pead:pead@localhost:5432/pead",
)


@pytest.fixture
def sync_engine():
    eng = create_engine(SYNC_URL, pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL not reachable for DB-gated tests")
    yield eng
    eng.dispose()


_TABLE_EXISTS_QUERIES = {
    "rl_checkpoints": text(
        "SELECT to_regclass('public.rl_checkpoints')"
    ),
    "rl_diversity_alerts": text(
        "SELECT to_regclass('public.rl_diversity_alerts')"
    ),
}


@requires_db
def test_migration_0004_tables_exist(sync_engine):
    """FR-5.6 + FR-5.7: rl_checkpoints and rl_diversity_alerts must exist after `alembic upgrade head`."""
    with sync_engine.connect() as conn:
        for tbl, query in _TABLE_EXISTS_QUERIES.items():
            result = conn.execute(query).scalar()
            assert result == tbl, f"{tbl} missing - run `cd backend && alembic upgrade head`"


@requires_db
def test_per_buffer_db_round_trip(sync_engine):
    """FR-5.2: push to DB then hydrate restores transitions into a fresh buffer."""
    from rl.per_buffer import PERBuffer, Transition

    # Clean slate for this agent_id
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM rl_transitions WHERE agent_id = 99"))

    buf = PERBuffer(maxlen=100, engine=sync_engine)
    ep = str(uuid4())
    for i in range(10):
        t = Transition(
            state=np.full(31, i, dtype=np.float32),
            action=np.array([0.5, 3], dtype=np.float32),
            reward=float(i),
            next_state=np.full(31, i + 1, dtype=np.float32),
            done=(i == 9),
        )
        buf.push_to_db(t, agent_id=99, episode_id=ep, step=i, td_error=float(i))

    # Fresh buffer hydrates from DB
    buf2 = PERBuffer(maxlen=100, engine=sync_engine)
    n = buf2.hydrate_from_db(agent_id=99, limit=100)
    assert n == 10, f"expected 10 hydrated rows, got {n}"
    assert len(buf2) == 10

    # Cleanup
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM rl_transitions WHERE agent_id = 99"))


@requires_db
def test_diversity_alert_persisted(sync_engine):
    """FR-5.6: fire_diversity_alert writes a row into rl_diversity_alerts."""
    from rl.diversity_monitor import fire_diversity_alert

    before = _count(sync_engine, "rl_diversity_alerts")
    fire_diversity_alert(sync_engine, max_sim=0.97, agent_pair=(0, 3), epoch=42)
    after = _count(sync_engine, "rl_diversity_alerts")
    assert after == before + 1

    with sync_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT max_similarity, agent_pair, epoch FROM rl_diversity_alerts "
                "ORDER BY created_at DESC LIMIT 1"
            )
        ).first()
    assert float(row.max_similarity) == pytest.approx(0.97, abs=1e-4)
    assert row.agent_pair == "0,3"
    assert row.epoch == 42


@requires_db
def test_full_loop_writes_checkpoints(sync_engine):
    """FR-5.7: trainer.main with total_steps=1100, interval=1000 writes 1 checkpoint per agent.

    Uses a small buffer pre-seeded with synthetic transitions so update_all() can run.
    """
    from rl.per_buffer import PERBuffer, Transition
    from worker.flows.rl_trainer import main

    # Pre-seed: clear and insert enough transitions to exceed online_batch_size=64
    ep = str(uuid4())
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM rl_transitions WHERE agent_id = 0 AND symbol = :s"),
                     {"s": "TEST_SEED"})
    # 80 transitions > batch_size=64, so update_all() always returns a loss in the
    # trainer loop - the `time.sleep(0.1)` empty-buffer path in worker.flows.rl_trainer
    # is never hit during this test. (WARNING-2 from revision-1.)
    seeder = PERBuffer(maxlen=200, engine=sync_engine)
    for i in range(80):
        t = Transition(
            state=np.random.randn(31).astype(np.float32),
            action=np.array([0.5, 3], dtype=np.float32),
            reward=float(np.random.randn()),
            next_state=np.random.randn(31).astype(np.float32),
            done=False,
        )
        seeder.push_to_db(t, agent_id=0, episode_id=ep, step=i, symbol="TEST_SEED",
                          td_error=float(np.random.uniform(0.1, 1.0)))

    before_ckpts = _count(sync_engine, "rl_checkpoints")
    # total_steps=1100, checkpoint_interval=1000 -> exactly 1 checkpoint event,
    # writing 5 rows (one per agent)
    main(total_steps=1100, checkpoint_interval=1000, database_url=SYNC_URL)
    after_ckpts = _count(sync_engine, "rl_checkpoints")

    assert after_ckpts >= before_ckpts + 5, (
        f"Expected >=5 new rl_checkpoints rows, got {after_ckpts - before_ckpts}"
    )

    # Verify one active row per agent
    with sync_engine.connect() as conn:
        active_per_agent = conn.execute(
            text("SELECT agent_id, COUNT(*) AS n FROM rl_checkpoints "
                 "WHERE is_active = TRUE GROUP BY agent_id ORDER BY agent_id")
        ).all()
    active_map = {int(r.agent_id): int(r.n) for r in active_per_agent}
    for agent_id in range(5):
        assert active_map.get(agent_id, 0) == 1, (
            f"agent {agent_id} should have exactly 1 active checkpoint, got {active_map.get(agent_id, 0)}"
        )

    # Cleanup seed transitions
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM rl_transitions WHERE symbol = :s"), {"s": "TEST_SEED"})


_COUNT_QUERIES = {
    "rl_checkpoints": text("SELECT COUNT(*) FROM rl_checkpoints"),
    "rl_diversity_alerts": text("SELECT COUNT(*) FROM rl_diversity_alerts"),
    "rl_transitions": text("SELECT COUNT(*) FROM rl_transitions"),
}


def _count(engine, table: str) -> int:
    """Hardcoded per-table COUNT queries - never f-string SQL (WARNING-3 from revision-1).

    Using a fixed mapping prevents accidental SQL injection if a future caller
    passes user input as `table`. Each query is a pre-built sqlalchemy text() with
    no interpolation surface.
    """
    query = _COUNT_QUERIES.get(table)
    if query is None:
        raise ValueError(f"_count: unsupported table {table!r}; add it to _COUNT_QUERIES")
    with engine.connect() as conn:
        return int(conn.execute(query).scalar())
