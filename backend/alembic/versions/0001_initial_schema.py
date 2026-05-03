"""Initial schema: 6 TimescaleDB hypertables with point-in-time ingestion_timestamp.

Revision ID: 0001
Revises:
Create Date: 2026-05-03
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # ── price_bars ────────────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS price_bars (
            time                TIMESTAMPTZ NOT NULL,
            symbol              TEXT NOT NULL,
            open                NUMERIC(12, 4),
            high                NUMERIC(12, 4),
            low                 NUMERIC(12, 4),
            close               NUMERIC(12, 4),
            vwap                NUMERIC(12, 4),
            volume              BIGINT,
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (time, symbol)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('price_bars', 'time', "
        "chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_price_bars_symbol_time "
        "ON price_bars (symbol, time DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_price_bars_ingestion "
        "ON price_bars (ingestion_timestamp)"
    )

    # ── earnings_events ───────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS earnings_events (
            id                  BIGSERIAL NOT NULL,
            symbol              TEXT,
            announced_at        TIMESTAMPTZ NOT NULL,
            fiscal_quarter      TEXT,
            eps_actual          NUMERIC(10, 4),
            eps_estimate        NUMERIC(10, 4),
            revenue_actual      NUMERIC(18, 2),
            revenue_estimate    NUMERIC(18, 2),
            operating_income    NUMERIC(18, 2),
            share_count         BIGINT,
            guidance_direction  TEXT CHECK (guidance_direction IN
                                    ('up', 'down', 'flat', 'none', 'withdrawn')),
            source              TEXT,
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id),
            UNIQUE (symbol, fiscal_quarter)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('earnings_events', 'announced_at', "
        "chunk_time_interval => INTERVAL '3 months', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_earnings_symbol "
        "ON earnings_events (symbol, announced_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_earnings_ingestion "
        "ON earnings_events (ingestion_timestamp)"
    )

    # ── signals ───────────────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            signal_id             UUID          NOT NULL DEFAULT gen_random_uuid(),
            symbol                TEXT,
            earnings_event_id     BIGINT,
            eps_gap               NUMERIC(8, 4),
            quality_score         NUMERIC(5, 2),
            three_axis_composite  NUMERIC(8, 4),
            naive_position_size   NUMERIC(6, 4),
            direction             TEXT CHECK (direction IN ('long', 'short', 'hold')),
            status                TEXT DEFAULT 'pending',
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (created_at, signal_id)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('signals', 'created_at', "
        "chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_symbol "
        "ON signals (symbol, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_signals_ingestion "
        "ON signals (ingestion_timestamp)"
    )

    # ── rl_transitions ────────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rl_transitions (
            ts                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            episode_id          UUID          NOT NULL DEFAULT gen_random_uuid(),
            step                INTEGER       NOT NULL,
            agent_id            SMALLINT      NOT NULL DEFAULT 0,
            symbol              TEXT,
            state_vec           JSONB,
            action              NUMERIC(6, 4),
            reward              NUMERIC(10, 6),
            next_state_vec      JSONB,
            done                BOOLEAN,
            priority            NUMERIC(10, 6) DEFAULT 1.0,
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (ts, episode_id, step)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('rl_transitions', 'ts', "
        "chunk_time_interval => INTERVAL '1 week', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rl_agent_priority "
        "ON rl_transitions (agent_id, priority DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rl_ingestion "
        "ON rl_transitions (ingestion_timestamp)"
    )

    # ── macro_indicators ──────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS macro_indicators (
            date                DATE          NOT NULL,
            series_id           TEXT NOT NULL,
            value               NUMERIC(16, 6),
            vintage_date        DATE,
            source              TEXT,
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (date, series_id)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('macro_indicators', 'date', "
        "chunk_time_interval => INTERVAL '3 months', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_macro_series "
        "ON macro_indicators (series_id, date DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_macro_ingestion "
        "ON macro_indicators (ingestion_timestamp)"
    )

    # ── portfolio_positions ───────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            snapshot_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            symbol              TEXT NOT NULL,
            qty                 NUMERIC(12, 4),
            avg_entry_price     NUMERIC(12, 4),
            current_price       NUMERIC(12, 4),
            unrealized_pnl      NUMERIC(14, 4),
            stop_loss_price     NUMERIC(12, 4),
            take_profit_price   NUMERIC(12, 4),
            status              TEXT DEFAULT 'open',
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (snapshot_at, symbol)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('portfolio_positions', 'snapshot_at', "
        "chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_positions_symbol "
        "ON portfolio_positions (symbol, snapshot_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_positions_ingestion "
        "ON portfolio_positions (ingestion_timestamp)"
    )


def downgrade() -> None:
    for table in [
        "portfolio_positions",
        "macro_indicators",
        "rl_transitions",
        "signals",
        "earnings_events",
        "price_bars",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")  # noqa: S608
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
