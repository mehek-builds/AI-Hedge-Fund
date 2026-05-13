"""FR-8.1 integration test: alerts table schema after migration 0007.

DB-gated: requires DATABASE_URL_SYNC set and `alembic upgrade head` run.
"""
import pytest
from sqlalchemy import text

from tests.conftest import requires_db


@requires_db
@pytest.mark.asyncio
async def test_alerts_table_exists(db):
    """alerts table exists and has the correct columns after migration 0007."""
    result = await db.execute(
        text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'alerts'
            ORDER BY ordinal_position
        """)
    )
    rows = result.fetchall()
    col_names = [r[0] for r in rows]
    assert "id" in col_names
    assert "event_type" in col_names
    assert "payload" in col_names
    assert "created_at" in col_names
    assert "delivered_sendgrid" in col_names
    assert "delivered_slack" in col_names
    assert "rate_limited" in col_names
    assert "ingestion_timestamp" in col_names


@requires_db
@pytest.mark.asyncio
async def test_alerts_check_constraint(db):
    """alerts.event_type CHECK constraint rejects invalid values."""
    with pytest.raises(Exception, match="chk_alert_event_type|check constraint"):
        await db.execute(
            text("""
                INSERT INTO alerts (event_type) VALUES (:event_type)
            """),
            {"event_type": "invalid_event_type"},
        )
        await db.commit()


@requires_db
@pytest.mark.asyncio
async def test_alerts_indexes_exist(db):
    """ix_alerts_event_type_created and ix_alerts_created_at indexes exist."""
    result = await db.execute(
        text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'alerts'
        """)
    )
    index_names = [r[0] for r in result.fetchall()]
    assert "ix_alerts_event_type_created" in index_names
    assert "ix_alerts_created_at" in index_names
