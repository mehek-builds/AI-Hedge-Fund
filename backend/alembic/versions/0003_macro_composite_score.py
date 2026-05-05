"""Add composite_score + score_components to macro_indicators.

Gap SC-1b (Phase 4 UAT): the computed macro composite score must be persisted
alongside the raw series readings so the RL state builder and MoE meta-controller
can replay sizing decisions without re-running the scoring algorithm.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-03
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE macro_indicators
            ADD COLUMN IF NOT EXISTS composite_score  INTEGER,
            ADD COLUMN IF NOT EXISTS score_components JSONB
        """
    )
    # Index lets the RL state builder find the latest snapshot quickly.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_macro_composite "
        "ON macro_indicators (date DESC) WHERE composite_score IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_macro_composite")
    op.execute(
        """
        ALTER TABLE macro_indicators
            DROP COLUMN IF EXISTS composite_score,
            DROP COLUMN IF EXISTS score_components
        """
    )
