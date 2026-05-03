-- PEAD Trading System — PostgreSQL + TimescaleDB schema

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------
-- Prices (TimescaleDB hypertable)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prices (
    ticker      TEXT        NOT NULL,
    time        TIMESTAMPTZ NOT NULL,
    open        NUMERIC(12,4),
    high        NUMERIC(12,4),
    low         NUMERIC(12,4),
    close       NUMERIC(12,4),
    volume      BIGINT,
    PRIMARY KEY (ticker, time)
);
SELECT create_hypertable('prices', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices (ticker, time DESC);

-- ----------------------------------------------------------------
-- FF5 Factor Returns (TimescaleDB hypertable)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ff5_factors (
    time        TIMESTAMPTZ NOT NULL PRIMARY KEY,
    mkt_rf      NUMERIC(8,6),
    smb         NUMERIC(8,6),
    hml         NUMERIC(8,6),
    rmw         NUMERIC(8,6),
    cma         NUMERIC(8,6),
    rf          NUMERIC(8,6)
);
SELECT create_hypertable('ff5_factors', 'time', if_not_exists => TRUE);

-- ----------------------------------------------------------------
-- Macro State (TimescaleDB hypertable)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS macro_state (
    time              TIMESTAMPTZ NOT NULL PRIMARY KEY,
    t10y2y            NUMERIC(6,4),
    core_pce_yoy      NUMERIC(6,4),
    gdp_qoq_ann       NUMERIC(6,4),
    hy_oas            NUMERIC(8,4),
    vix               NUMERIC(8,4),
    sahm_rule         NUMERIC(6,4),
    carry_crash_flag  BOOLEAN DEFAULT FALSE,
    composite_score   INTEGER,
    size_multiplier   NUMERIC(4,2),
    is_halted         BOOLEAN DEFAULT FALSE,
    earnings_yield    NUMERIC(8,6),
    real_10y_yield    NUMERIC(8,6),
    erp_spread        NUMERIC(8,6),
    erp_compressed    BOOLEAN DEFAULT FALSE,
    vug_pe            NUMERIC(8,4),
    vtv_pe            NUMERIC(8,4),
    gv_ratio          NUMERIC(8,4),
    gv_stretched      BOOLEAN DEFAULT FALSE
);
SELECT create_hypertable('macro_state', 'time', if_not_exists => TRUE);

-- ----------------------------------------------------------------
-- Earnings Events
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS earnings_events (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker            TEXT        NOT NULL,
    announcement_ts   TIMESTAMPTZ NOT NULL,
    actual_eps        NUMERIC(10,4),
    consensus_eps     NUMERIC(10,4),
    implied_eps       NUMERIC(10,4),
    actual_rev        NUMERIC(16,4),
    implied_rev       NUMERIC(16,4),
    actual_margin     NUMERIC(8,6),
    prior_margin      NUMERIC(8,6),
    guidance          TEXT        CHECK (guidance IN ('raised','maintained','lowered','none')),
    surprise_score    NUMERIC(8,4),
    intangible_mult   NUMERIC(4,2),
    roic_mult         NUMERIC(4,2),
    quality_score     NUMERIC(5,4),
    revenue_surprise  NUMERIC(8,6),
    margin_surprise   NUMERIC(8,6),
    guidance_delta    NUMERIC(4,2),
    signal_composite  NUMERIC(8,4),
    direction         TEXT        CHECK (direction IN ('long','short','none')),
    gics_sector       TEXT,
    is_cyclical       BOOLEAN,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_earnings_ticker_ts ON earnings_events (ticker, announcement_ts DESC);
CREATE INDEX IF NOT EXISTS idx_earnings_ts ON earnings_events (announcement_ts DESC);

-- ----------------------------------------------------------------
-- Positions
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker              TEXT        NOT NULL,
    signal_id           UUID        REFERENCES earnings_events(id),
    entry_ts            TIMESTAMPTZ NOT NULL,
    entry_price         NUMERIC(12,4),
    shares              INTEGER,
    direction           TEXT        NOT NULL CHECK (direction IN ('long','short')),
    stop_price          NUMERIC(12,4),
    holding_days_target INTEGER,
    hold_bin            INTEGER,
    sac_entry_size      NUMERIC(5,4),
    rl_action_size      NUMERIC(5,4),
    moe_regime          TEXT,
    macro_score_at_entry INTEGER,
    gics_sector         TEXT,
    exit_ts             TIMESTAMPTZ,
    exit_price          NUMERIC(12,4),
    exit_reason         TEXT        CHECK (exit_reason IN ('stop','expiry','reversal','manual')),
    realized_pnl        NUMERIC(12,4),
    ff5_alpha           NUMERIC(8,6),
    alpaca_order_id     TEXT,
    status              TEXT        NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status, entry_ts DESC);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions (ticker, status);

-- ----------------------------------------------------------------
-- RL Episodes
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rl_episodes (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id   UUID        REFERENCES positions(id),
    state_vector  JSONB       NOT NULL,
    action        NUMERIC(5,4) NOT NULL,
    reward        NUMERIC(8,6) NOT NULL,
    done          BOOLEAN     DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rl_episodes_created ON rl_episodes (created_at DESC);

-- ----------------------------------------------------------------
-- RL Checkpoints
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rl_checkpoints (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    model_path      TEXT        NOT NULL,
    total_episodes  INTEGER,
    mean_reward_20  NUMERIC(8,6),
    factor_betas    JSONB,
    ir_vs_naive     NUMERIC(8,4),
    is_active       BOOLEAN     DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------
-- Company Meta (intangible / ROIC fundamentals)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS company_meta (
    ticker              TEXT        PRIMARY KEY,
    gics_sector         TEXT,
    intangible_pct      NUMERIC(6,4),
    intangible_tercile  INTEGER     CHECK (intangible_tercile IN (1,2,3)),
    roic_ttm            NUMERIC(8,4),
    wacc                NUMERIC(8,4),
    days_to_cover       NUMERIC(6,2),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------
-- Completion Portfolio (weekly FF5 neutralization snapshots)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS completion_portfolio (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    active_betas    JSONB       NOT NULL,
    deviations      JSONB       NOT NULL,
    recommended_etf TEXT,
    sleeve_pct_nav  NUMERIC(5,4),
    max_deviation   NUMERIC(6,4),
    computed_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_completion_computed ON completion_portfolio (computed_at DESC);

-- ----------------------------------------------------------------
-- Backtest Runs
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_runs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    label           TEXT,
    start_date      TEXT        NOT NULL,
    end_date        TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','running','done','error')),
    config          JSONB,
    total_return    NUMERIC(10,6),
    sharpe_ratio    NUMERIC(8,4),
    max_drawdown    NUMERIC(8,4),
    win_rate        NUMERIC(5,4),
    ir_vs_naive     NUMERIC(8,4),
    total_trades    INTEGER,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_backtest_created ON backtest_runs (created_at DESC);

-- ----------------------------------------------------------------
-- Backtest Trades
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_trades (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID        NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    ticker          TEXT        NOT NULL,
    direction       TEXT        NOT NULL CHECK (direction IN ('long','short')),
    entry_date      TIMESTAMPTZ NOT NULL,
    exit_date       TIMESTAMPTZ,
    entry_price     NUMERIC(12,4),
    exit_price      NUMERIC(12,4),
    position_size   NUMERIC(6,4),
    realized_pnl    NUMERIC(12,4),
    ff5_alpha       NUMERIC(8,6),
    hold_days       INTEGER,
    exit_reason     TEXT
);
CREATE INDEX IF NOT EXISTS idx_bt_trades_run ON backtest_trades (run_id, entry_date);

-- ----------------------------------------------------------------
-- Alert Log
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alert_log (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  TEXT        NOT NULL,
    ticker      TEXT,
    title       TEXT        NOT NULL,
    body        TEXT,
    priority    TEXT        NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('high','medium','low')),
    channels    JSONB       DEFAULT '[]'::jsonb,
    delivered   BOOLEAN     DEFAULT FALSE,
    error       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alert_log_created ON alert_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_log_type ON alert_log (event_type, created_at DESC);

-- ----------------------------------------------------------------
-- Alert Rules
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alert_rules (
    event_type  TEXT        PRIMARY KEY,
    enabled     BOOLEAN     DEFAULT TRUE,
    channels    JSONB       DEFAULT '["slack"]'::jsonb,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO alert_rules (event_type, enabled, channels) VALUES
    ('signal_generated',    TRUE, '["slack"]'),
    ('entry_executed',      TRUE, '["slack","email"]'),
    ('exit_executed',       TRUE, '["slack","email"]'),
    ('stop_loss_triggered', TRUE, '["slack","email"]'),
    ('macro_halt',          TRUE, '["slack","email"]'),
    ('macro_score_change',  TRUE, '["slack"]'),
    ('arch_check_blocked',  TRUE, '["slack"]'),
    ('rl_checkpoint_saved', FALSE,'["slack"]'),
    ('backtest_complete',   TRUE, '["slack"]')
ON CONFLICT (event_type) DO NOTHING;

-- ----------------------------------------------------------------
-- System Settings
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_settings (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO system_settings (key, value) VALUES
    ('risk', '{"hard_stop_pct": 0.08, "max_position_pct": 0.05, "max_sector_pct": 0.30, "macro_halt_threshold": -4}'),
    ('signal', '{"min_signal_threshold": 0.5, "intangible_tiers": [1.0, 1.15, 1.30], "roic_multiplier": 1.20}')
ON CONFLICT (key) DO NOTHING;

-- ----------------------------------------------------------------
-- Useful view: open position P&L (joined with latest price)
-- ----------------------------------------------------------------
CREATE OR REPLACE VIEW open_positions_pnl AS
SELECT
    p.id,
    p.ticker,
    p.entry_ts,
    p.entry_price,
    p.shares,
    p.direction,
    p.stop_price,
    p.holding_days_target,
    p.rl_action_size,
    p.macro_score_at_entry,
    p.gics_sector,
    lp.close AS current_price,
    CASE
        WHEN p.direction = 'long'
            THEN (lp.close - p.entry_price) * p.shares
        ELSE
            (p.entry_price - lp.close) * p.shares
    END AS unrealized_pnl,
    EXTRACT(DAY FROM NOW() - p.entry_ts) AS days_held,
    e.signal_composite,
    e.surprise_score
FROM positions p
LEFT JOIN LATERAL (
    SELECT close FROM prices
    WHERE ticker = p.ticker
    ORDER BY time DESC LIMIT 1
) lp ON TRUE
LEFT JOIN earnings_events e ON e.id = p.signal_id
WHERE p.status = 'open';
