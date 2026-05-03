# Architecture Patterns: PEAD Trading System

**Domain:** Quantitative trading system — PEAD signal, RL execution, real-time dashboard
**Researched:** 2026-05-02
**Confidence:** MEDIUM-HIGH (training knowledge; WebSearch unavailable for live doc verification)

---

## System Overview

Six Docker Compose services with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER CLIENT                              │
│                  Next.js 14 App Router (SSE/WS)                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────────────┐
│                    FastAPI Backend                                  │
│  REST endpoints · SSE event stream · Celery task dispatch           │
│  Alpaca REST client · SendGrid/Slack alerting                        │
└──┬──────────────────┬──────────────────────────┬────────────────────┘
   │ SQL              │ Redis PUBLISH             │ Celery task queue
   │                  │                           │
┌──▼──────────┐  ┌────▼──────────┐  ┌────────────▼───────────────────┐
│ PostgreSQL  │  │     Redis     │  │       Celery Worker             │
│ +Timescale  │  │  broker+cache │  │  PER replay · SAC training      │
│             │  │  pub/sub      │  │  Alpaca order execution         │
└──▲──────────┘  └───────────────┘  └────────────────────────────────┘
   │
┌──┴──────────────────────────────────────────────────────────────────┐
│                      Prefect Server                                 │
│  Flow scheduler (price ingest · macro · earnings · signal · RL)     │
│  Prefect worker calls back into FastAPI or writes DB directly       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Decision 1: Inter-Service Communication

### Recommended Pattern

```
FastAPI  ──[Celery task]──►  Celery Worker  (fire-and-forget async work)
FastAPI  ──[Redis PUBLISH]── Redis          (real-time event fan-out)
FastAPI  ──[SQLAlchemy]────► TimescaleDB    (persistent reads/writes)
Prefect  ──[SQLAlchemy]────► TimescaleDB    (pipeline writes)
Prefect  ──[HTTP POST]─────► FastAPI /internal/ingest  (trigger signals)
```

**Do not** have Prefect talk to Celery directly. Prefect manages scheduling; Celery manages execution parallelism. The boundary: Prefect flows handle orchestration and data ingestion writes; Celery tasks handle compute-heavy, latency-sensitive, or user-triggered work (RL training steps, order execution).

### Redis Roles (two logical databases, same instance)

| Redis DB | Purpose | Key pattern |
|----------|---------|-------------|
| db=0 | Celery broker + result backend | `celery-task-meta-*` |
| db=1 | Pub/Sub for SSE fan-out | channels: `signals`, `positions`, `rl_state`, `alerts` |

Using two DBs on one Redis instance is fine for development and small production. Split to separate instances only if Celery queue depth interferes with pub/sub latency (monitor with `redis-cli info stats`).

### docker-compose.yml service dependencies

```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg15
    ...
  redis:
    image: redis:7-alpine
    ...
  fastapi:
    depends_on: [db, redis]
    ...
  celery_worker:
    depends_on: [db, redis]
    command: celery -A app.worker worker --loglevel=info --concurrency=4
    ...
  prefect_server:
    image: prefecthq/prefect:2-latest
    depends_on: [db]   # Prefect uses its own DB or shares Postgres
    ...
  nextjs:
    depends_on: [fastapi]
    ...
```

**Confidence:** HIGH — standard Celery+Redis+FastAPI topology, well-established.

---

## Decision 2: Real-Time Dashboard — SSE vs WebSocket

### Recommendation: Server-Sent Events (SSE) over WebSocket

**Rationale:**
- Dashboard is read-mostly — browser receives updates, never sends trading commands back through the real-time channel.
- SSE works over standard HTTP/1.1, survives Railway's load balancer without sticky sessions, and requires no upgrade handshake.
- Next.js 14 App Router's `ReadableStream` response makes SSE trivial to implement server-side.
- WebSocket adds bidirectional complexity and Railway proxy configuration overhead for no gain here.

### FastAPI SSE endpoint

```python
# app/routers/stream.py
import asyncio, json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

router = APIRouter()
r = aioredis.from_url("redis://redis:6379/1")

CHANNELS = ["signals", "positions", "rl_state", "alerts"]

async def event_generator():
    pubsub = r.pubsub()
    await pubsub.subscribe(*CHANNELS)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"].decode()
                data = message["data"].decode()
                yield f"event: {channel}\ndata: {data}\n\n"
    finally:
        await pubsub.unsubscribe(*CHANNELS)

@router.get("/stream/events")
async def stream_events():
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables Nginx proxy buffering
        },
    )
```

### Publishing from anywhere in the stack

```python
# Publish from FastAPI route, Celery task, or Prefect flow
import redis, json

r = redis.Redis(host="redis", port=6379, db=1)

def publish_signal(signal_dict: dict):
    r.publish("signals", json.dumps(signal_dict))

def publish_position_update(position_dict: dict):
    r.publish("positions", json.dumps(position_dict))
```

### Next.js 14 client hook

```typescript
// hooks/useTradeStream.ts
"use client";
import { useEffect } from "react";

export function useTradeStream(handlers: {
  onSignal?: (d: any) => void;
  onPosition?: (d: any) => void;
  onRlState?: (d: any) => void;
  onAlert?: (d: any) => void;
}) {
  useEffect(() => {
    const es = new EventSource("/api/stream/events");  // proxied via Next.js rewrites
    es.addEventListener("signals",   e => handlers.onSignal?.(JSON.parse(e.data)));
    es.addEventListener("positions", e => handlers.onPosition?.(JSON.parse(e.data)));
    es.addEventListener("rl_state",  e => handlers.onRlState?.(JSON.parse(e.data)));
    es.addEventListener("alerts",    e => handlers.onAlert?.(JSON.parse(e.data)));
    return () => es.close();
  }, []);
}
```

Add a Next.js rewrite in `next.config.js` to proxy `/api/stream/*` to `http://fastapi:8000/stream/*` so the SSE connection respects CORS and shares the same origin.

**Confidence:** HIGH — SSE + Redis pub/sub is the standard pattern for this topology.

---

## Decision 3: Prefect 2.0 Flow Structure

### Recommendation: Self-hosted Prefect Server (not Prefect Cloud) for initial deployment

Railway can run the `prefecthq/prefect:2-latest` container. Prefect Cloud adds cost and network latency for no benefit at this stage. Use `PREFECT_API_URL=http://prefect_server:4200/api` in all workers.

### Flow Registry

| Flow | Trigger | Schedule | What it does |
|------|---------|----------|-------------|
| `ingest_daily_prices` | Cron `0 18 * * 1-5` (after market close) | Daily | Pulls OHLCV from Alpaca/yfinance → TimescaleDB `price_bars` hypertable |
| `ingest_macro_indicators` | Cron `0 6 * * 1` | Weekly | FRED API → `macro_indicators` table |
| `ingest_ff5_factors` | Cron `0 7 1 * *` | Monthly | Kenneth French data library → `ff5_factors` table |
| `poll_earnings_calendar` | Cron `*/30 9-16 * * 1-5` | Every 30 min market hours | Polygon/Alpaca earnings endpoint → `earnings_events`; triggers signal flow on new events |
| `compute_pead_signal` | Event-triggered by `poll_earnings_calendar` | On new earnings surprise | Runs PEAD regression + FF5 alpha computation → `signals` table → publishes to Redis |
| `reoptimize_portfolio` | Cron `0 9 1 1,4,7,10 *` | Quarterly | Mean-variance or Black-Litterman reallocation using latest RL weights |
| `train_rl_agent_online` | Cron `30 18 * * 1-5` | Daily after ingest | Pulls today's transitions from DB → runs SAC update steps → saves checkpoint |

### Flow structure pattern

```python
# flows/ingest_prices.py
from prefect import flow, task
from prefect.schedules import CronSchedule
import httpx, pandas as pd
from app.db import engine   # shared SQLAlchemy engine

@task(retries=3, retry_delay_seconds=60)
def fetch_ohlcv(symbol: str, date: str) -> pd.DataFrame:
    ...

@task
def upsert_price_bars(df: pd.DataFrame):
    df.to_sql("price_bars", engine, if_exists="append", index=False,
              method="multi")

@flow(name="ingest-daily-prices")
def ingest_daily_prices(symbols: list[str] = UNIVERSE):
    for symbol in symbols:
        df = fetch_ohlcv(symbol, today())
        upsert_price_bars(df)
```

**Event-triggered sub-flow pattern (earnings → signal):**

```python
# flows/poll_earnings.py
from prefect import flow, task
from prefect.deployments import run_deployment

@task
def check_new_earnings() -> list[dict]:
    # query earnings API, compare with DB, return novel events
    ...

@flow(name="poll-earnings-calendar")
def poll_earnings_calendar():
    new_events = check_new_earnings()
    for event in new_events:
        # trigger compute_pead_signal as child run, non-blocking
        run_deployment(
            name="compute-pead-signal/production",
            parameters={"event": event},
        )
```

### Prefect Infrastructure Decision

Use `Process` work pool (not Kubernetes) for Railway. Each Prefect flow run spins up as a subprocess inside the `prefect_server` container or a dedicated `prefect_worker` service. For Railway, a single `prefect_worker` service suffices:

```yaml
# docker-compose.yml
prefect_worker:
  image: prefecthq/prefect:2-latest
  command: prefect worker start --pool "default-process-pool"
  environment:
    PREFECT_API_URL: http://prefect_server:4200/api
  depends_on: [prefect_server, db, redis]
```

**Confidence:** MEDIUM-HIGH — Prefect 2.0 patterns from training data; verify `run_deployment` API against current Prefect 2/3 docs as the API changed between 2.x minor versions.

---

## Decision 4: PostgreSQL + TimescaleDB Schema

### TimescaleDB Hypertable Strategy

Convert time-series tables to hypertables; leave relational/reference tables as standard Postgres tables.

| Table | Type | Partition by |
|-------|------|-------------|
| `price_bars` | hypertable | `time` (daily, 1 month chunks) |
| `signals` | hypertable | `created_at` (1 month chunks) |
| `rl_transitions` | hypertable | `ts` (1 week chunks — high volume) |
| `macro_indicators` | hypertable | `date` (3 month chunks) |
| `alerts_log` | hypertable | `fired_at` (1 month chunks) |
| `positions` | standard | — (low cardinality, frequently updated) |
| `earnings_events` | standard | — (append-only but low volume, index on `announced_at`) |
| `ff5_factors` | standard | — (monthly, tiny) |
| `rl_agent_state` | standard | — (one row per agent version) |

### DDL

```sql
-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ── REFERENCE / CONFIG TABLES ────────────────────────────────────────

CREATE TABLE symbols (
    symbol          TEXT PRIMARY KEY,
    name            TEXT,
    sector          TEXT,
    market_cap_tier TEXT,   -- 'large', 'mid', 'small'
    active          BOOLEAN DEFAULT TRUE
);

-- ── TIME-SERIES TABLES ───────────────────────────────────────────────

CREATE TABLE price_bars (
    time            TIMESTAMPTZ NOT NULL,
    symbol          TEXT        NOT NULL REFERENCES symbols(symbol),
    open            NUMERIC(12,4),
    high            NUMERIC(12,4),
    low             NUMERIC(12,4),
    close           NUMERIC(12,4),
    volume          BIGINT,
    vwap            NUMERIC(12,4),
    PRIMARY KEY (time, symbol)
);
SELECT create_hypertable('price_bars', 'time', chunk_time_interval => INTERVAL '1 month');
CREATE INDEX ON price_bars (symbol, time DESC);

CREATE TABLE macro_indicators (
    date            DATE        NOT NULL,
    series_id       TEXT        NOT NULL,   -- e.g. 'FEDFUNDS', 'UNRATE'
    value           NUMERIC(16,6),
    source          TEXT,
    PRIMARY KEY (date, series_id)
);
SELECT create_hypertable('macro_indicators', 'date',
    chunk_time_interval => INTERVAL '3 months');

CREATE TABLE ff5_factors (
    date            DATE    NOT NULL,
    mkt_rf          NUMERIC(10,6),
    smb             NUMERIC(10,6),
    hml             NUMERIC(10,6),
    rmw             NUMERIC(10,6),
    cma             NUMERIC(10,6),
    rf              NUMERIC(10,6),
    PRIMARY KEY (date)
);

-- ── EARNINGS & SIGNALS ───────────────────────────────────────────────

CREATE TABLE earnings_events (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT        NOT NULL REFERENCES symbols(symbol),
    announced_at    TIMESTAMPTZ NOT NULL,
    fiscal_quarter  TEXT,                   -- e.g. '2024Q3'
    eps_actual      NUMERIC(10,4),
    eps_estimate    NUMERIC(10,4),
    eps_surprise    NUMERIC(10,4),          -- actual - estimate
    eps_surprise_pct NUMERIC(8,4),
    revenue_actual  NUMERIC(18,2),
    revenue_estimate NUMERIC(18,2),
    source          TEXT,
    UNIQUE (symbol, fiscal_quarter)
);
CREATE INDEX ON earnings_events (announced_at DESC);
CREATE INDEX ON earnings_events (symbol, announced_at DESC);

CREATE TABLE signals (
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_id           UUID        NOT NULL DEFAULT gen_random_uuid(),
    symbol              TEXT        NOT NULL REFERENCES symbols(symbol),
    earnings_event_id   BIGINT      REFERENCES earnings_events(id),
    -- PEAD components
    eps_surprise_pct    NUMERIC(8,4),
    standardized_ue     NUMERIC(8,4),    -- unexpected earnings (standardized)
    pead_score          NUMERIC(8,4),    -- raw PEAD drift score
    -- FF5 alpha
    alpha_30d           NUMERIC(8,4),
    alpha_t_stat        NUMERIC(8,4),
    -- RL agent decision
    rl_action           SMALLINT,        -- 0=hold, 1=long, 2=short
    rl_confidence       NUMERIC(6,4),
    rl_agent_version    TEXT,
    -- Signal metadata
    direction           TEXT CHECK (direction IN ('long','short','hold')),
    target_weight       NUMERIC(6,4),    -- portfolio weight [0,1]
    entry_price         NUMERIC(12,4),
    stop_loss_price     NUMERIC(12,4),
    take_profit_price   NUMERIC(12,4),
    status              TEXT DEFAULT 'pending' CHECK (status IN
                            ('pending','executed','cancelled','expired')),
    PRIMARY KEY (created_at, signal_id)
);
SELECT create_hypertable('signals', 'created_at',
    chunk_time_interval => INTERVAL '1 month');
CREATE INDEX ON signals (symbol, created_at DESC);
CREATE INDEX ON signals (status, created_at DESC);

-- ── POSITIONS ────────────────────────────────────────────────────────

CREATE TABLE positions (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT        NOT NULL REFERENCES symbols(symbol),
    signal_id           UUID,
    alpaca_order_id     TEXT,
    alpaca_position_id  TEXT,
    side                TEXT CHECK (side IN ('long','short')),
    qty                 NUMERIC(12,4),
    avg_entry_price     NUMERIC(12,4),
    current_price       NUMERIC(12,4),
    unrealized_pnl      NUMERIC(14,4),
    realized_pnl        NUMERIC(14,4),
    stop_loss_price     NUMERIC(12,4),
    take_profit_price   NUMERIC(12,4),
    status              TEXT DEFAULT 'open' CHECK (status IN
                            ('open','closed','partial')),
    opened_at           TIMESTAMPTZ DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX ON positions (symbol) WHERE status = 'open';
CREATE INDEX ON positions (status, opened_at DESC);

-- ── RL TRAINING TABLES ───────────────────────────────────────────────

CREATE TABLE rl_transitions (
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    episode_id      UUID        NOT NULL,
    step            INTEGER,
    symbol          TEXT        REFERENCES symbols(symbol),
    state_vec       JSONB,          -- feature vector snapshot
    action          SMALLINT,
    reward          NUMERIC(10,6),
    next_state_vec  JSONB,
    done            BOOLEAN,
    priority        NUMERIC(10,6) DEFAULT 1.0,  -- PER priority weight
    PRIMARY KEY (ts, episode_id, step)
);
SELECT create_hypertable('rl_transitions', 'ts',
    chunk_time_interval => INTERVAL '1 week');
CREATE INDEX ON rl_transitions (priority DESC, ts DESC);  -- PER sampling

CREATE TABLE rl_agent_state (
    version         TEXT        PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN     DEFAULT TRUE,
    -- SAC hyperparameters
    alpha           NUMERIC(8,6),    -- entropy temperature
    gamma           NUMERIC(8,6),    -- discount factor
    lr_actor        NUMERIC(10,8),
    lr_critic       NUMERIC(10,8),
    -- Training metadata
    total_steps     BIGINT DEFAULT 0,
    total_episodes  INTEGER DEFAULT 0,
    mean_reward_30d NUMERIC(10,6),
    sharpe_30d      NUMERIC(8,4),
    -- Checkpoint
    checkpoint_path TEXT,            -- S3/Railway volume path to .pt file
    ensemble_size   SMALLINT DEFAULT 5
);

-- ── ALERTING ─────────────────────────────────────────────────────────

CREATE TABLE alerts_log (
    fired_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_id        UUID        NOT NULL DEFAULT gen_random_uuid(),
    event_type      TEXT        NOT NULL,   -- see 9 event types below
    channel         TEXT        NOT NULL CHECK (channel IN ('email','slack','both')),
    symbol          TEXT        REFERENCES symbols(symbol),
    payload         JSONB,
    delivered       BOOLEAN     DEFAULT FALSE,
    delivery_error  TEXT,
    PRIMARY KEY (fired_at, alert_id)
);
SELECT create_hypertable('alerts_log', 'fired_at',
    chunk_time_interval => INTERVAL '1 month');
CREATE INDEX ON alerts_log (event_type, fired_at DESC);
```

### 9 Alert Event Types

```python
class AlertEventType(str, Enum):
    SIGNAL_GENERATED    = "signal_generated"
    ORDER_FILLED        = "order_filled"
    ORDER_REJECTED      = "order_rejected"
    STOP_LOSS_HIT       = "stop_loss_hit"
    TAKE_PROFIT_HIT     = "take_profit_hit"
    POSITION_OPENED     = "position_opened"
    POSITION_CLOSED     = "position_closed"
    DRAWDOWN_THRESHOLD  = "drawdown_threshold"
    PIPELINE_FAILURE    = "pipeline_failure"
```

**Confidence:** HIGH — schema follows TimescaleDB best practices; hypertable chunk intervals are conservative and can be tuned.

---

## Decision 5: RL Training Loop Architecture

### Online Learning on Live Data (Recommended Pattern)

For a PEAD system trading a handful of positions per week, pure online RL is preferred over large batch replay. The training loop should be:

```
Daily close → Prefect: ingest_daily_prices
           → Prefect: train_rl_agent_online
               ├── Pull last N=10,000 transitions from DB (PER-weighted)
               ├── Run K=100 SAC gradient steps (CPU is sufficient)
               ├── Update priorities in rl_transitions table
               └── Checkpoint new weights → rl_agent_state
```

### PER (Prioritized Experience Replay) with PostgreSQL

Avoid storing the full replay buffer in memory (Celery worker restarts lose state). Instead, use `rl_transitions` as the persistent buffer:

```python
# app/rl/per_sampler.py
import numpy as np
from sqlalchemy import text

def sample_per_batch(conn, batch_size: int = 256) -> tuple:
    """
    Proportional PER sampling using DB priorities.
    Not as efficient as a segment tree but correct and restart-safe.
    """
    # Fetch top candidates (oversample, then stochastic select)
    rows = conn.execute(text("""
        SELECT episode_id, step, state_vec, action, reward,
               next_state_vec, done, priority, ts
        FROM rl_transitions
        WHERE ts >= NOW() - INTERVAL '90 days'
        ORDER BY priority DESC
        LIMIT :pool
    """), {"pool": batch_size * 8}).fetchall()

    priorities = np.array([r.priority for r in rows], dtype=np.float32)
    probs = priorities / priorities.sum()
    indices = np.random.choice(len(rows), size=batch_size, replace=False, p=probs)
    batch = [rows[i] for i in indices]

    # IS weights
    n = len(rows)
    weights = (n * probs[indices]) ** -0.4   # beta=0.4 initially
    weights /= weights.max()
    return batch, weights

def update_priorities(conn, episode_ids: list, steps: list, new_priorities: list):
    for eid, step, p in zip(episode_ids, steps, new_priorities):
        conn.execute(text("""
            UPDATE rl_transitions SET priority = :p
            WHERE episode_id = :eid AND step = :step
        """), {"p": float(p), "eid": str(eid), "step": step})
```

### Celery Task for RL Training

```python
# app/tasks/rl_tasks.py
from celery import shared_task
from app.rl.sac_ensemble import SACEnsemble
from app.rl.per_sampler import sample_per_batch, update_priorities

@shared_task(bind=True, max_retries=2, soft_time_limit=3600)
def run_daily_rl_training(self, agent_version: str, n_steps: int = 100):
    agent = SACEnsemble.load(agent_version)   # load from checkpoint
    with db_session() as conn:
        for _ in range(n_steps):
            batch, weights = sample_per_batch(conn)
            td_errors = agent.update(batch, weights)
            update_priorities(conn, ...)
        agent.checkpoint(conn)   # writes new row to rl_agent_state
```

### GPU vs CPU Decision

CPU is correct for this workload. SAC on a feature vector of ~50-100 dims with 5-ensemble, batch=256, 100 steps/day: this runs in under 60 seconds on a single CPU core. GPU overhead (data transfer, process isolation in Docker) would make it slower. Use GPU only if ensemble size > 20 or state includes image/time-series tensors.

**Confidence:** MEDIUM — PER-in-Postgres pattern is non-standard (usually in-memory segment tree); functional but has O(N log N) sampling overhead. For buffer sizes under 100K transitions, acceptable. Flag for profiling in Phase 3-4.

---

## Decision 6: Alpaca Integration Patterns

### Bracket Order Execution

```python
# app/services/alpaca_service.py
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

client = TradingClient(api_key=ALPACA_KEY, secret_key=ALPACA_SECRET, paper=True)

def submit_bracket_order(
    symbol: str,
    qty: float,
    side: str,          # 'buy' or 'sell'
    take_profit_pct: float,
    stop_loss_pct: float,
    current_price: float,
) -> dict:
    direction = OrderSide.BUY if side == "buy" else OrderSide.SELL
    if side == "buy":
        tp_price = round(current_price * (1 + take_profit_pct), 2)
        sl_price = round(current_price * (1 - stop_loss_pct), 2)
    else:
        tp_price = round(current_price * (1 - take_profit_pct), 2)
        sl_price = round(current_price * (1 + stop_loss_pct), 2)

    request = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=direction,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=tp_price),
        stop_loss=StopLossRequest(stop_price=sl_price),
    )
    order = client.submit_order(request)
    return {"alpaca_order_id": str(order.id), "status": order.status}
```

### Stop-Loss Monitoring: Webhook (Recommended) over Polling

Alpaca supports trade update webhooks via their streaming API. For Railway deployment, use Alpaca's streaming WebSocket client in a Celery long-running task rather than a polling loop:

```python
# app/tasks/alpaca_stream.py
from alpaca.trading.stream import TradingStream

@shared_task(bind=True)
def monitor_trade_updates(self):
    """Long-running Celery task that listens to Alpaca trade updates."""
    stream = TradingStream(ALPACA_KEY, ALPACA_SECRET, paper=True)

    @stream.on("trade_updates")
    async def on_trade_update(data):
        event = data.event   # 'fill', 'partial_fill', 'canceled', 'expired'
        if event in ("fill", "partial_fill"):
            await handle_fill(data.order)
        elif event == "canceled":
            await handle_cancel(data.order)

    stream.run()
```

Register this task as a Celery beat singleton at startup. On Railway restart, call `client.get_all_positions()` to sync position state before re-registering the stream.

### Position Sync on Startup

```python
# app/startup.py — called in FastAPI lifespan
async def sync_positions_from_alpaca():
    """Reconcile DB positions table with live Alpaca positions."""
    alpaca_positions = client.get_all_positions()
    alpaca_symbols = {p.symbol for p in alpaca_positions}

    with db_session() as conn:
        # Mark positions closed if Alpaca no longer holds them
        conn.execute(text("""
            UPDATE positions
            SET status = 'closed', closed_at = NOW()
            WHERE status = 'open' AND symbol NOT IN :symbols
        """), {"symbols": tuple(alpaca_symbols) or ('__none__',)})

        # Upsert current Alpaca positions
        for pos in alpaca_positions:
            conn.execute(text("""
                INSERT INTO positions (symbol, side, qty, avg_entry_price,
                    current_price, unrealized_pnl, alpaca_position_id, status)
                VALUES (:symbol, :side, :qty, :entry, :current, :pnl, :apid, 'open')
                ON CONFLICT (symbol) WHERE status = 'open'
                DO UPDATE SET qty = EXCLUDED.qty,
                              current_price = EXCLUDED.current_price,
                              unrealized_pnl = EXCLUDED.unrealized_pnl,
                              updated_at = NOW()
            """), {...})
```

**Confidence:** MEDIUM-HIGH — Alpaca SDK patterns from training data; verify `OrderClass.BRACKET` enum name and `TradingStream` API against current alpaca-py SDK docs (SDK had breaking changes in 0.8→0.9).

---

## Decision 7: Backtest Engine Architecture

### Core Principle: Single Code Path

The backtest harness must reuse the identical signal engine and RL agent code that runs in production. Separate backtest codebases inevitably diverge and produce misleading results.

### Replay Harness Pattern

```
BacktestRunner
    ├── HistoricalDataProvider  (reads from price_bars hypertable, filtered by date range)
    ├── EarningsReplayProvider  (reads from earnings_events, replay in chronological order)
    ├── SignalEngine             ← SAME class as production
    ├── RLAgent                  ← SAME class as production (loaded at backtest_start_date weights)
    ├── SimulatedBroker          ← replaces AlpacaService, uses OHLCV for fill simulation
    └── PortfolioLedger          ← tracks positions, PnL, drawdown
```

```python
# app/backtest/runner.py
from app.signals.pead import compute_pead_signal   # production code
from app.rl.sac_ensemble import SACEnsemble          # production code
from app.backtest.simulated_broker import SimulatedBroker

def run_backtest(
    start_date: str,        # "2018-01-01"
    end_date:   str,        # "2023-12-31"
    agent_checkpoint: str,  # load weights from this date (or None for untrained)
    initial_capital: float = 100_000,
):
    broker = SimulatedBroker(initial_capital=initial_capital)
    agent = SACEnsemble.load(agent_checkpoint) if agent_checkpoint else SACEnsemble()

    # Replay earnings events in chronological order
    for event in iter_earnings_events(start_date, end_date):
        # Get historical price data available as of event date (no lookahead)
        prices = get_prices_as_of(event.symbol, as_of=event.announced_at)
        ff5 = get_ff5_as_of(event.announced_at)
        macro = get_macro_as_of(event.announced_at)

        # Identical to production signal path
        signal = compute_pead_signal(event, prices, ff5, macro)
        action = agent.act(signal.state_vector())

        if action != "hold":
            broker.submit_order(event.symbol, action, signal, prices)

        # Optional: online RL update during replay (realistic simulation)
        if broker.has_closed_position_today():
            transition = broker.get_last_transition()
            agent.update_single(transition)   # online learning during backtest

    return broker.get_results()   # DataFrame of daily PnL, positions, metrics
```

### SimulatedBroker Fill Assumptions

```python
class SimulatedBroker:
    """
    Fill at next-day open price + slippage factor.
    Bracket stops/TPs trigger at high/low of day.
    """
    SLIPPAGE_BPS = 5      # 5 basis points
    COMMISSION_PER_SHARE = 0.005

    def fill_price(self, symbol: str, side: str, date: str) -> float:
        bar = get_next_open(symbol, date)   # no lookahead
        slip = bar.open * (self.SLIPPAGE_BPS / 10_000)
        return bar.open + slip if side == "buy" else bar.open - slip
```

**Confidence:** HIGH — replay-harness pattern with shared production code is the standard quantitative approach. PnL calculation details need domain validation.

---

## Railway.app Deployment Patterns

### Service Configuration

Railway runs each `docker-compose.yml` service as a separate Railway service. Key constraints:

1. **Persistent volumes** — TimescaleDB data and Prefect flow storage need Railway volumes. Attach a volume to the `db` service at `/var/lib/postgresql/data`.
2. **Private networking** — Services on the same Railway project communicate via internal hostnames (e.g., `db.railway.internal`, `redis.railway.internal`). Update all service URLs to use `.railway.internal` hostnames in production env vars.
3. **SSE keepalive** — Railway's proxy has a 60-second idle timeout. The SSE endpoint must emit a keepalive comment every 30 seconds:

```python
async def event_generator():
    pubsub = r.pubsub()
    await pubsub.subscribe(*CHANNELS)
    last_heartbeat = asyncio.get_event_loop().time()
    async for message in pubsub.listen():
        now = asyncio.get_event_loop().time()
        if now - last_heartbeat > 25:
            yield ": heartbeat\n\n"
            last_heartbeat = now
        if message["type"] == "message":
            ...
```

4. **Celery worker** — Railway will restart crashed workers. Use `--max-tasks-per-child=100` to prevent memory leaks in long-running RL training tasks.
5. **Prefect server** — Set `PREFECT_HOME=/data` and mount a Railway volume at `/data` so flow run history persists across deploys.

**Confidence:** MEDIUM — Railway internal networking and timeout behaviors from training data. Verify `.railway.internal` DNS pattern against current Railway docs.

---

## Component Boundaries Summary

| Component | Owns | Does NOT own |
|-----------|------|-------------|
| FastAPI | REST API, SSE stream, auth, alert dispatch | Data ingestion, RL training |
| Celery Worker | RL training, order execution, Alpaca stream monitoring | HTTP routing, scheduling |
| Prefect Server/Worker | Flow scheduling, data pipeline orchestration | Business logic, order execution |
| TimescaleDB | All persistent state | In-flight task state |
| Redis | Celery broker, real-time pub/sub | Persistent data |
| Next.js | Dashboard UI, SSE client | Any server-side data computation |

---

## Critical Architecture Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| PER sampling O(N log N) at scale | Medium | Segment tree in Redis if buffer > 500K rows |
| Celery worker restart loses RL model in memory | High | Always load from DB checkpoint at task start |
| Alpaca stream disconnect (Railway restart) | High | Startup reconciliation + dead-letter retry in beat schedule |
| SSE connection drop on Railway proxy timeout | Medium | 25s heartbeat comment |
| TimescaleDB `rl_transitions` unbounded growth | Medium | retention policy: `add_retention_policy('rl_transitions', INTERVAL '180 days')` |
| Lookahead bias in backtest | Critical | Strict `as_of` filtering on all data queries; never read `price_bars` beyond event date |

---

## Sources

- TimescaleDB documentation (training data, Aug 2025 cutoff) — HIGH confidence for hypertable DDL
- Prefect 2.0 documentation (training data) — MEDIUM confidence; verify `run_deployment` API
- FastAPI SSE patterns (training data + established community patterns) — HIGH confidence
- Alpaca alpaca-py SDK (training data, v0.8-0.9 era) — MEDIUM confidence; verify `OrderClass.BRACKET`
- Railway.app Docker networking (training data) — MEDIUM confidence; verify `.railway.internal` DNS
- SAC/PER academic literature — HIGH confidence (algorithmic correctness)
- WebSearch: UNAVAILABLE (permission denied); all findings from training knowledge
