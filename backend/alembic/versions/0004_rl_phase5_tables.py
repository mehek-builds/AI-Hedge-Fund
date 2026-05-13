"""Phase 5: rl_checkpoints + rl_diversity_alerts tables.

FR-5.7: Trainer must write checkpoints (state_dict bytes) to PostgreSQL
        every 1,000 training steps so they survive Railway service restarts.
FR-5.6: Diversity alerts (max pairwise cosine similarity > 0.9) must persist
        for audit and the dashboard Alerting view (Phase 7+).

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rl_checkpoints (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            step            INTEGER NOT NULL,
            agent_id        SMALLINT NOT NULL,
            model_bytes     BYTEA,
            total_steps     INTEGER,
            mean_reward_20  NUMERIC(10, 6),
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_rl_checkpoints_agent_id CHECK (agent_id >= 0 AND agent_id < 5)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rl_checkpoints_active "
        "ON rl_checkpoints (agent_id, step DESC) WHERE is_active = TRUE"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rl_diversity_alerts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            max_similarity  NUMERIC(6, 4) NOT NULL,
            agent_pair      TEXT,
            epoch           INTEGER,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_diversity_sim_range CHECK (max_similarity >= -1.0 AND max_similarity <= 1.0)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rl_diversity_alerts_created "
        "ON rl_diversity_alerts (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rl_diversity_alerts_created")
    op.execute("DROP TABLE IF EXISTS rl_diversity_alerts")
    op.execute("DROP INDEX IF EXISTS ix_rl_checkpoints_active")
    op.execute("DROP TABLE IF EXISTS rl_checkpoints")
