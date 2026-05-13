"""Phase 6: backtest_runs table for backtest engine results and validation gate.

FR-6.4: gate_status column is the go/no-go pivot for Phase 7 startup.
FR-6.6: columns match Phase 8 Backtest Explorer query needs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-13
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS backtest_runs (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            start_date          DATE NOT NULL,
            end_date            DATE NOT NULL,
            sharpe              NUMERIC(10, 6),
            max_drawdown        NUMERIC(10, 6),
            ir_vs_baseline      NUMERIC(10, 6),
            calmar              NUMERIC(10, 6),
            monthly_returns     JSONB,
            gate_status         TEXT NOT NULL DEFAULT 'pending'
                                    CONSTRAINT chk_gate_status
                                    CHECK (gate_status IN ('pending', 'pass', 'fail')),
            is_partial_year     BOOLEAN NOT NULL DEFAULT FALSE,
            config_snapshot     JSONB,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    # Lookup index for Phase 7 startup gate check and dashboard queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_backtest_runs_gate_status "
        "ON backtest_runs (gate_status, created_at DESC)"
    )
    # Index for date-range filtering in Phase 8 Backtest Explorer
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_backtest_runs_dates "
        "ON backtest_runs (start_date, end_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_backtest_runs_dates")
    op.execute("DROP INDEX IF EXISTS ix_backtest_runs_gate_status")
    op.execute("DROP TABLE IF EXISTS backtest_runs")
