"""Wave 0 stubs -- FR-5.7 (Training loop + checkpoint cadence)."""
import os
import sys
import importlib.util
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from tests.conftest import requires_db


def test_trainer_module_exists():
    """FR-5.7: worker/flows/rl_trainer.py must be importable."""
    spec = importlib.util.find_spec("worker.flows.rl_trainer") or \
           importlib.util.find_spec("flows.rl_trainer")
    assert spec is not None, "worker/flows/rl_trainer.py must exist (Wave 4)"


@requires_db
def test_checkpoint_at_1000_steps():
    """FR-5.7: Trainer writes a row to rl_checkpoints every 1000 steps."""
    # This is a contract assertion -- Wave 4 implementation will satisfy.
    from sqlalchemy import create_engine, text
    url = os.environ.get("DATABASE_URL_SYNC", "postgresql://pead:pead@localhost:5432/pead")
    engine = create_engine(url)
    with engine.connect() as conn:
        # Table must exist after migration 0004
        result = conn.execute(text(
            "SELECT to_regclass('public.rl_checkpoints')"
        )).scalar()
        assert result == "rl_checkpoints", "rl_checkpoints table missing -- run alembic upgrade head"


@requires_db
def test_diversity_alerts_table_exists():
    """FR-5.6 schema: rl_diversity_alerts table must exist after migration 0004."""
    from sqlalchemy import create_engine, text
    url = os.environ.get("DATABASE_URL_SYNC", "postgresql://pead:pead@localhost:5432/pead")
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT to_regclass('public.rl_diversity_alerts')"
        )).scalar()
        assert result == "rl_diversity_alerts"
