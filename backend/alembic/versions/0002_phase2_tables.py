"""Phase 2 tables: sp500_constituents + ff5_factors

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sp500_constituents (
            id                  BIGSERIAL NOT NULL,
            symbol              TEXT NOT NULL,
            company_name        TEXT,
            added_date          DATE NOT NULL,
            removed_date        DATE,
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sp500_symbol_added "
        "ON sp500_constituents (symbol, added_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sp500_active "
        "ON sp500_constituents (symbol) WHERE removed_date IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sp500_ingestion "
        "ON sp500_constituents (ingestion_timestamp)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ff5_factors (
            date                DATE NOT NULL,
            mkt_rf              NUMERIC(10, 6),
            smb                 NUMERIC(10, 6),
            hml                 NUMERIC(10, 6),
            rmw                 NUMERIC(10, 6),
            cma                 NUMERIC(10, 6),
            rf                  NUMERIC(10, 6),
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (date)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ff5_ingestion "
        "ON ff5_factors (ingestion_timestamp)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ff5_factors CASCADE")
    op.execute("DROP TABLE IF EXISTS sp500_constituents CASCADE")
