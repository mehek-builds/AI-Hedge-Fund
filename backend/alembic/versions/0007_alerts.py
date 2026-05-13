"""Phase 7 plan 01: create alerts table with CHECK constraint and indexes.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type      TEXT NOT NULL,
            payload         JSONB,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            delivered_sendgrid  BOOLEAN NOT NULL DEFAULT FALSE,
            delivered_slack     BOOLEAN NOT NULL DEFAULT FALSE,
            rate_limited    BOOLEAN NOT NULL DEFAULT FALSE,
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_alert_event_type CHECK (event_type IN (
                'signal_generated', 'order_submitted', 'order_filled',
                'stop_triggered', 'thesis_broken', 'macro_regime_change',
                'backtest_gate_pass', 'backtest_gate_fail', 'rl_diversity_alert'
            ))
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_alerts_event_type_created
        ON alerts (event_type, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_alerts_created_at
        ON alerts (created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alerts")
