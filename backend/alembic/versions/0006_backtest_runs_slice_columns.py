"""Phase 6 plan 04: add slice_type, gate_reason, total_trades columns to backtest_runs.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # slice_type distinguishes 'main' vs 'ex_2020' slices (FR-6.5)
    op.execute(
        "ALTER TABLE backtest_runs "
        "ADD COLUMN IF NOT EXISTS slice_type TEXT NOT NULL DEFAULT 'main'"
    )
    # gate_reason stores the human-readable reason from evaluate_gate
    op.execute(
        "ALTER TABLE backtest_runs "
        "ADD COLUMN IF NOT EXISTS gate_reason TEXT"
    )
    # total_trades: count of non-None replay_step results
    op.execute(
        "ALTER TABLE backtest_runs "
        "ADD COLUMN IF NOT EXISTS total_trades INTEGER"
    )
    # Index for slice_type lookups (Phase 8 Explorer filtering)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_backtest_runs_slice_type "
        "ON backtest_runs (slice_type, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_backtest_runs_slice_type")
    op.execute("ALTER TABLE backtest_runs DROP COLUMN IF EXISTS total_trades")
    op.execute("ALTER TABLE backtest_runs DROP COLUMN IF EXISTS gate_reason")
    op.execute("ALTER TABLE backtest_runs DROP COLUMN IF EXISTS slice_type")
