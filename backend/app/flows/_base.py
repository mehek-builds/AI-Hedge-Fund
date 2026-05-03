from contextlib import contextmanager
from typing import Iterable, Sequence

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Table

from app.flows._db import SyncSessionLocal


@contextmanager
def sync_session():
    """Yield a sync SQLAlchemy session, committing on success, rolling back on error."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert_rows(
    session,
    table: Table,
    rows: Iterable[dict],
    conflict_cols: Sequence[str],
    update_cols: Sequence[str] | None = None,
) -> int:
    """Bulk INSERT ... ON CONFLICT (conflict_cols) DO UPDATE for Postgres.

    Returns number of rows submitted (postgres rowcount may differ).
    Always sets ingestion_timestamp = NOW() on update so point-in-time
    semantics record the latest write.
    """
    rows = list(rows)
    if not rows:
        return 0
    stmt = pg_insert(table).values(rows)
    if update_cols is None:
        update_cols = [c.name for c in table.columns
                       if c.name not in conflict_cols and c.name != "id"]
    set_map = {c: getattr(stmt.excluded, c) for c in update_cols}
    # Bump ingestion_timestamp on every update path
    if "ingestion_timestamp" in [c.name for c in table.columns]:
        from sqlalchemy import func
        set_map["ingestion_timestamp"] = func.now()
    stmt = stmt.on_conflict_do_update(
        index_elements=list(conflict_cols),
        set_=set_map,
    )
    session.execute(stmt)
    return len(rows)
