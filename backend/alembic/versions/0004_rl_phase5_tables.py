"""Add rl_transitions, rl_checkpoints, and rl_diversity_alerts tables for Phase 5.

FR-5.2: rl_transitions - DB-backed PER buffer (TimescaleDB hypertable)
FR-5.7: rl_checkpoints - serialized SAC agent state_dicts (BYTEA)
FR-5.6: rl_diversity_alerts - pairwise cosine similarity alert log

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # rl_transitions: DB-backed PER buffer (FR-5.2)
    op.execute("""
        CREATE TABLE IF NOT EXISTS rl_transitions (
            id              BIGSERIAL,
            agent_id        INTEGER NOT NULL,
            episode_id      TEXT NOT NULL,
            step            INTEGER NOT NULL,
            symbol          TEXT NOT NULL DEFAULT '',
            state           FLOAT4[] NOT NULL,
            action          FLOAT4[] NOT NULL,
            reward          FLOAT4 NOT NULL,
            next_state      FLOAT4[] NOT NULL,
            done            BOOLEAN NOT NULL DEFAULT FALSE,
            td_error        FLOAT4,
            ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, ingested_at)
        )
    """)

    # Try to create TimescaleDB hypertable; silently skip if extension not available
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable(
                    'rl_transitions', 'ingested_at',
                    if_not_exists => TRUE,
                    migrate_data  => TRUE
                );
            END IF;
        END
        $$;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rl_transitions_agent_ingested
            ON rl_transitions (agent_id, ingested_at DESC)
    """)

    # rl_checkpoints: serialized SAC agent weights (FR-5.7)
    op.execute("""
        CREATE TABLE IF NOT EXISTS rl_checkpoints (
            id              BIGSERIAL PRIMARY KEY,
            step            INTEGER NOT NULL,
            agent_id        INTEGER NOT NULL,
            model_bytes     BYTEA NOT NULL,
            total_steps     INTEGER,
            mean_reward_20  FLOAT4,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rl_checkpoints_agent_active
            ON rl_checkpoints (agent_id, is_active)
    """)

    # rl_diversity_alerts: pairwise cosine similarity log (FR-5.6)
    op.execute("""
        CREATE TABLE IF NOT EXISTS rl_diversity_alerts (
            id              BIGSERIAL PRIMARY KEY,
            max_similarity  NUMERIC(6, 5) NOT NULL,
            agent_pair      TEXT NOT NULL,
            epoch           INTEGER NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rl_diversity_alerts")
    op.execute("DROP TABLE IF EXISTS rl_checkpoints")
    op.execute("DROP TABLE IF EXISTS rl_transitions")
