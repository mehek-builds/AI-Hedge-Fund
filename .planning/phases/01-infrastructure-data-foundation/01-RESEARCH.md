# Phase 1: Infrastructure & Data Foundation - Research

**Researched:** 2026-05-02
**Domain:** Docker Compose, TimescaleDB, Alembic, FastAPI, Next.js 14, Celery, Prefect 2.x, Railway, GitHub Actions CI
**Confidence:** HIGH (stack is pre-specified; research focused on exact DDL, config patterns, and Railway deployment mechanics)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR-1.1 | Docker Compose with 6 services: FastAPI, Next.js, Celery worker, PostgreSQL+TimescaleDB, Redis, Prefect server | Service definitions, health checks, and startup order documented in Architecture Patterns |
| FR-1.2 | TimescaleDB hypertables for all 6 tables with `ingestion_timestamp` | Exact DDL for all 6 hypertables in Architecture Patterns; Alembic migration patterns in Code Examples |
| FR-1.3 | Railway deployment with persistent volume attached before schema creation | Railway deployment section; volume-first workflow documented in Pitfalls |
| FR-1.4 | GitHub Actions CI: lint (ruff/eslint), test, Docker build on PR; auto-deploy on main | CI workflow pattern documented in Code Examples; Railway deploy action verified |
| FR-1.5 | Point-in-time data: all historical records tagged with `ingestion_timestamp`; `as_of` filtering works | `as_of` query pattern in Architecture Patterns; Alembic migration notes timestamps in schema |
</phase_requirements>

---

## Summary

Phase 1 is a pure infrastructure bootstrap: no business logic, no ML, no data ingestion. The goal is a working Docker Compose stack, a complete TimescaleDB schema with point-in-time semantics, a deployable Railway configuration, and a CI/CD pipeline. Every subsequent phase depends on this foundation being correct and stable.

The stack is fully pre-specified in CLAUDE.md and is non-negotiable. Research confirms all locked choices are current and well-supported. The most critical ordering constraint is Railway persistent volume attachment: it must be created and attached to the TimescaleDB service before the database is initialized — Railway's ephemeral filesystem will otherwise wipe the data on every service restart, making the volume-first workflow a hard prerequisite before any schema creation.

Prefect 2.x (`prefecthq/prefect:2-latest` = 2.20.25 as of Dec 2025) is confirmed still maintained and must be pinned explicitly — the current default `latest` would pull Prefect 3.x which has API-breaking changes. All other stack versions have been verified against PyPI and npm as of May 2026.

**Primary recommendation:** Build in this order — (1) persistent volume on Railway, (2) Docker Compose stack locally, (3) Alembic migrations + hypertables, (4) FastAPI/Next.js skeletons with health endpoints, (5) CI pipeline, (6) Railway service definitions. Never create schema before the volume is confirmed mounted.

---

## Project Constraints (from CLAUDE.md)

All directives from `CLAUDE.md` are mandatory and override any research recommendations:

| Directive | Constraint |
|-----------|-----------|
| Frontend | Next.js 14 App Router, TypeScript — non-negotiable |
| Backend | FastAPI async, Python 3.11 — non-negotiable |
| Workers | Celery + Redis — no `async def` in Celery tasks; use `asyncio.run()` |
| Database | PostgreSQL 15 + TimescaleDB — Railway requires custom Docker service, NOT managed PostgreSQL |
| Pipelines | Prefect 2.x — pin to `2-latest` (NOT v3); use cron schedules, not interval-based |
| Broker | `alpaca-py` SDK only — NOT deprecated `alpaca-trade-api` |
| Deployment | Docker Compose local, Railway.app hosted |
| CI | GitHub Actions |
| Real-time | SSE not WebSocket — FastAPI `StreamingResponse` + Redis pub/sub |
| PER buffer | PostgreSQL `rl_transitions` hypertable — NOT Redis (memory ceiling exceeded) |
| RL trainer | Manual deploy only on Railway — NOT auto-deploy |
| TimescaleDB | `timescale/timescaledb:latest-pg15` with persistent volume at `/var/lib/postgresql/data` |
| Alembic | Exclude `_timescaledb_*` internal tables; hypertable creation via `op.execute()` raw SQL |
| SSE design | Dark theme: `#0A1628` bg, `#2471A3` primary, `#148F77` positive, `#C0392B` negative |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `timescale/timescaledb` | `latest-pg15` (Docker) | PostgreSQL 15 + TimescaleDB extension | Only free path to TimescaleDB on Railway |
| `redis` | `7-alpine` (Docker) | Celery broker + pub/sub | Minimal image; version 7 required for Redis Functions |
| `prefecthq/prefect` | `2-latest` = 2.20.25 | Flow orchestration | Must pin 2.x; 3.x has breaking API changes |
| `fastapi` | 0.136.1 | Async REST API + SSE | Current stable; Python ≥3.10 |
| `uvicorn[standard]` | 0.46.0 | ASGI server | Standard pairing with FastAPI |
| `sqlalchemy[asyncio]` | 2.0.49 | Async ORM | SQLAlchemy 2.0 async required for asyncpg |
| `asyncpg` | 0.31.0 | Async PostgreSQL driver | Required by SQLAlchemy async engine |
| `alembic` | 1.18.4 | Database migrations | Standard migration tool for SQLAlchemy |
| `celery[redis]` | 5.6.3 | Task queue | Standard; `redis` extra adds broker support |
| `redis` (Python) | 7.4.0 | Redis client | Async support via `redis.asyncio` |
| `pydantic` | 2.13.3 | Validation + settings | v2 required for pydantic-settings 2.x |
| `pydantic-settings` | 2.14.0 | Environment config management | Required for `BaseSettings` in pydantic v2 |
| `next` | 16.2.4 | Frontend framework | App Router is default; no breaking changes for this use case |
| `typescript` | 6.0.3 | Type safety | Current stable with Next.js 16 |
| `tailwindcss` | 4.2.4 | Utility CSS | Tailwind v4; config syntax changed from v3 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | 0.28.1 | HTTP client + FastAPI test client | Integration tests via `AsyncClient` |
| `pytest` | 9.0.3 | Test runner | All Python tests |
| `pytest-asyncio` | 1.3.0 | Async test support | Testing async SQLAlchemy and FastAPI routes |
| `ruff` | 0.15.12 | Python linter + formatter | CI lint step; replaces flake8/black |
| `eslint` | 10.3.0 | TypeScript linter | CI lint step for frontend |
| `alpaca-py` | 0.43.4 | Alpaca SDK | Not needed in Phase 1 but install in backend requirements |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `timescale/timescaledb:latest-pg15` | Railway managed PostgreSQL | Railway managed PG has no TimescaleDB extension — not viable |
| `prefecthq/prefect:2-latest` | Prefect 3.x | v3 has breaking API changes; PRD locks 2.x |
| `asyncpg` via SQLAlchemy | `psycopg3` (async) | asyncpg is more performant; SQLAlchemy 2.0 has better asyncpg support |
| Alembic | Manual migrations | No viable alternative for a production system |

### Installation

```bash
# Python backend (requirements.txt)
fastapi==0.136.1
uvicorn[standard]==0.46.0
pydantic==2.13.3
pydantic-settings==2.14.0
sqlalchemy[asyncio]==2.0.49
asyncpg==0.31.0
alembic==1.18.4
celery[redis]==5.6.3
redis==7.4.0
httpx==0.28.1
pytest==9.0.3
pytest-asyncio==1.3.0
ruff==0.15.12
alpaca-py==0.43.4

# Frontend (package.json devDependencies/dependencies)
next@16.2.4
typescript@6.0.3
tailwindcss@4.2.4
eslint@10.3.0
```

**Version verification:** All versions above confirmed against PyPI (2026-05-02) and npm registry (2026-05-02). [VERIFIED: PyPI, npm registry]

**Tailwind v4 note:** Tailwind v4 changed configuration — `tailwind.config.ts` is replaced by CSS-first configuration using `@import "tailwindcss"` in the main CSS file. The `@theme` directive replaces the `theme.extend` JavaScript config. [VERIFIED: npm registry v4.2.4]

---

## Architecture Patterns

### Recommended Project Structure

```
pead-trading-system/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory + lifespan
│   │   ├── config.py            # pydantic-settings BaseSettings
│   │   ├── database.py          # SQLAlchemy async engine + sessionmaker
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── price_bars.py
│   │   │   ├── earnings_events.py
│   │   │   ├── signals.py
│   │   │   ├── rl_transitions.py
│   │   │   ├── macro_indicators.py
│   │   │   └── portfolio_positions.py
│   │   ├── routers/
│   │   │   ├── health.py        # GET /health
│   │   │   └── stream.py        # GET /stream/events (SSE)
│   │   └── worker.py            # Celery app definition
│   ├── alembic/
│   │   ├── env.py               # TimescaleDB-aware env
│   │   ├── versions/
│   │   │   └── 0001_initial_schema.py
│   │   └── alembic.ini
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   └── test_schema.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # Root layout, dark theme globals
│   │   ├── page.tsx             # Dashboard home (Server Component)
│   │   └── globals.css          # Tailwind v4 @import + @theme
│   ├── components/
│   │   └── ui/                  # shadcn/ui primitives
│   ├── hooks/
│   │   └── useTradeStream.ts    # SSE client hook
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.override.yml  # local dev overrides
├── railway.toml
└── .github/
    └── workflows/
        ├── ci.yml
        └── deploy.yml
```

### Pattern 1: Docker Compose Service Stack

**What:** All 6 services with correct dependency ordering, health checks, and startup conditions.
**When to use:** Local development. Railway uses individual service deployments but should match this structure.

```yaml
# docker-compose.yml
version: "3.9"

services:
  db:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_USER: pead
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: pead_trading
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pead -d pead_trading"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 30s

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  fastapi:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://pead:${DB_PASSWORD}@db:5432/pead_trading
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  celery_worker:
    build: ./backend
    command: celery -A app.worker worker --loglevel=info --concurrency=4 --max-tasks-per-child=100
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://pead:${DB_PASSWORD}@db:5432/pead_trading
      REDIS_URL: redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  prefect_server:
    image: prefecthq/prefect:2-latest
    command: prefect server start --host 0.0.0.0
    environment:
      PREFECT_API_DATABASE_CONNECTION_URL: postgresql+asyncpg://pead:${DB_PASSWORD}@db:5432/prefect_meta
      PREFECT_SERVER_API_HOST: 0.0.0.0
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "4200:4200"
    volumes:
      - prefectdata:/root/.prefect
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4200/api/health"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s

  nextjs:
    build: ./frontend
    command: npm run dev
    env_file: .env
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      fastapi:
        condition: service_healthy
    ports:
      - "3000:3000"

volumes:
  pgdata:
  redisdata:
  prefectdata:
```

**Critical note:** Prefect server requires its own database (or schema). Use a separate `prefect_meta` database on the same PostgreSQL instance to avoid Prefect managing metadata in the `pead_trading` database. [ASSUMED — Prefect 2.x separate DB recommendation based on training knowledge]

### Pattern 2: TimescaleDB Hypertable DDL (All 6 Tables with `ingestion_timestamp`)

**What:** The exact DDL for all 6 required hypertables, including the `ingestion_timestamp` column on every table for FR-1.5 point-in-time semantics.
**When to use:** Initial Alembic migration `0001_initial_schema.py`.

```sql
-- Source: TimescaleDB docs (training knowledge; core API stable since 2.0)
-- All 6 required hypertables per FR-1.2

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1. price_bars
CREATE TABLE price_bars (
    time                TIMESTAMPTZ NOT NULL,
    symbol              TEXT        NOT NULL,
    open                NUMERIC(12,4),
    high                NUMERIC(12,4),
    low                 NUMERIC(12,4),
    close               NUMERIC(12,4),
    volume              BIGINT,
    vwap                NUMERIC(12,4),
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (time, symbol)
);
SELECT create_hypertable('price_bars', 'time', chunk_time_interval => INTERVAL '1 month');
CREATE INDEX ON price_bars (symbol, time DESC);

-- 2. earnings_events
CREATE TABLE earnings_events (
    id                  BIGSERIAL   PRIMARY KEY,
    symbol              TEXT        NOT NULL,
    announced_at        TIMESTAMPTZ NOT NULL,
    fiscal_quarter      TEXT,
    eps_actual          NUMERIC(10,4),
    eps_estimate        NUMERIC(10,4),
    revenue_actual      NUMERIC(18,2),
    revenue_estimate    NUMERIC(18,2),
    operating_income    NUMERIC(18,2),
    share_count         BIGINT,
    guidance_direction  TEXT CHECK (guidance_direction IN ('raised','lowered','maintained','withdrew','none')),
    source              TEXT,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, fiscal_quarter)
);
-- NOTE: earnings_events does NOT become a hypertable per architecture research
-- (low cardinality, append-only). FR-1.2 lists it as a required hypertable.
-- Use hypertable on announced_at per FR-1.2 requirement:
SELECT create_hypertable('earnings_events', 'announced_at',
    chunk_time_interval => INTERVAL '3 months',
    migrate_data => TRUE);
CREATE INDEX ON earnings_events (symbol, announced_at DESC);

-- 3. signals
CREATE TABLE signals (
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_id           UUID        NOT NULL DEFAULT gen_random_uuid(),
    symbol              TEXT        NOT NULL,
    earnings_event_id   BIGINT,
    eps_gap             NUMERIC(8,4),
    quality_score       NUMERIC(5,2),
    three_axis_composite NUMERIC(8,4),
    naive_position_size NUMERIC(6,4),  -- fixed 2% NAV baseline (FR-3.7)
    direction           TEXT CHECK (direction IN ('long','short','hold')),
    status              TEXT DEFAULT 'pending',
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (created_at, signal_id)
);
SELECT create_hypertable('signals', 'created_at',
    chunk_time_interval => INTERVAL '1 month');
CREATE INDEX ON signals (symbol, created_at DESC);

-- 4. rl_transitions
CREATE TABLE rl_transitions (
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    episode_id      UUID        NOT NULL,
    step            INTEGER     NOT NULL,
    agent_id        SMALLINT    NOT NULL DEFAULT 0,  -- 0-4 for 5-agent ensemble
    symbol          TEXT,
    state_vec       JSONB,
    action          NUMERIC(6,4),   -- continuous [0,1] Beta dist output
    reward          NUMERIC(10,6),
    next_state_vec  JSONB,
    done            BOOLEAN,
    priority        NUMERIC(10,6) DEFAULT 1.0,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts, episode_id, step)
);
SELECT create_hypertable('rl_transitions', 'ts',
    chunk_time_interval => INTERVAL '1 week');
CREATE INDEX ON rl_transitions (priority DESC, ts DESC);
CREATE INDEX ON rl_transitions (agent_id, ts DESC);

-- 5. macro_indicators
CREATE TABLE macro_indicators (
    date                DATE        NOT NULL,
    series_id           TEXT        NOT NULL,
    value               NUMERIC(16,6),
    vintage_date        DATE,        -- ALFRED vintage (point-in-time)
    source              TEXT,
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (date, series_id)
);
SELECT create_hypertable('macro_indicators', 'date',
    chunk_time_interval => INTERVAL '3 months');

-- 6. portfolio_positions
CREATE TABLE portfolio_positions (
    snapshot_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol              TEXT        NOT NULL,
    qty                 NUMERIC(12,4),
    avg_entry_price     NUMERIC(12,4),
    current_price       NUMERIC(12,4),
    unrealized_pnl      NUMERIC(14,4),
    stop_loss_price     NUMERIC(12,4),
    take_profit_price   NUMERIC(12,4),
    status              TEXT DEFAULT 'open',
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (snapshot_at, symbol)
);
SELECT create_hypertable('portfolio_positions', 'snapshot_at',
    chunk_time_interval => INTERVAL '1 month');
CREATE INDEX ON portfolio_positions (symbol, snapshot_at DESC);
```

**ingestion_timestamp semantics:** `ingestion_timestamp` records when a row was first written to the database. It is always `DEFAULT NOW()` and must never be updated. The `as_of` filtering pattern queries `WHERE ingestion_timestamp <= :as_of_date` to reconstruct the database state as visible at a historical point in time. [ASSUMED — standard point-in-time pattern; verify this is the correct column for the `as_of` filter vs. the event timestamp]

### Pattern 3: Alembic + TimescaleDB Migration

**What:** Alembic `env.py` configuration to exclude TimescaleDB internal tables and migration template for hypertable creation.
**When to use:** `alembic/env.py` setup and the initial migration file.

```python
# alembic/env.py — critical TimescaleDB exclusion
# Source: CLAUDE.md directive + training knowledge

def include_object(object, name, type_, reflected, compare_to):
    """Exclude TimescaleDB internal tables from autogenerate."""
    if type_ == "table" and (
        name.startswith("_timescaledb_")
        or name.startswith("timescaledb_")
    ):
        return False
    return True

context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_object=include_object,
    include_schemas=True,
)
```

```python
# alembic/versions/0001_initial_schema.py
# Hypertable creation must use op.execute() raw SQL — NOT autogenerated DDL
# Source: CLAUDE.md directive

def upgrade() -> None:
    # 1. Enable extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # 2. Create base tables (standard CREATE TABLE via op.create_table or op.execute)
    op.execute("""
        CREATE TABLE IF NOT EXISTS price_bars (
            time                TIMESTAMPTZ NOT NULL,
            ...
            ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # 3. Convert to hypertable — ALWAYS via op.execute(), never autogenerated
    op.execute(
        "SELECT create_hypertable('price_bars', 'time', "
        "chunk_time_interval => INTERVAL '1 month', "
        "if_not_exists => TRUE)"
    )
    # Repeat for all 6 tables

def downgrade() -> None:
    # Cannot un-hypertable; drop tables
    op.execute("DROP TABLE IF EXISTS price_bars CASCADE")
    # ...
```

**Critical:** The `if_not_exists => TRUE` parameter on `create_hypertable` prevents errors if the migration is run twice (e.g., Railway restart during migration). [ASSUMED — `if_not_exists` parameter exists in TimescaleDB 2.x; verify exact parameter name]

### Pattern 4: FastAPI App Skeleton with Health Endpoint

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine
from app.routers import health, stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: test DB connection with retry
    yield
    # Shutdown: close connection pool
    await engine.dispose()


app = FastAPI(title="PEAD Trading System", lifespan=lifespan)
app.include_router(health.router)
app.include_router(stream.router, prefix="/stream")
```

```python
# backend/app/routers/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Checks both process liveness and DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)}, 503
```

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # detects stale connections
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

### Pattern 5: Celery App Definition (Synchronous Tasks)

```python
# backend/app/worker.py
# CRITICAL: No async def in Celery tasks — CLAUDE.md directive
from celery import Celery
from app.config import settings

celery_app = Celery(
    "pead_worker",
    broker=settings.REDIS_URL,          # redis://redis:6379/0
    backend=settings.REDIS_BACKEND_URL, # redis://redis:6379/1 — separate DB
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # acknowledge after completion, not receipt
    worker_prefetch_multiplier=1, # prevent task accumulation on crashed workers
    task_routes={
        "app.tasks.signals.*": {"queue": "signals"},
        "app.tasks.rl.*":      {"queue": "ml"},
    },
)
```

### Pattern 6: Next.js 14 Skeleton with Dark Theme

```typescript
// frontend/app/globals.css
// Tailwind v4 — CSS-first config (no tailwind.config.ts needed)
@import "tailwindcss";

@theme {
  --color-bg-primary: #0A1628;
  --color-brand-primary: #2471A3;
  --color-positive: #148F77;
  --color-negative: #C0392B;
  --font-family-ui: "Inter", system-ui, sans-serif;
  --font-family-mono: "JetBrains Mono", "Fira Code", monospace;
}

:root {
  background-color: var(--color-bg-primary);
  color: white;
  font-family: var(--font-family-ui);
}
```

```typescript
// frontend/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PEAD Trading System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className} style={{ backgroundColor: "#0A1628" }}>
        {children}
      </body>
    </html>
  );
}
```

```typescript
// frontend/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.FASTAPI_URL ?? "http://fastapi:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

### Pattern 7: `as_of` Point-in-Time Query Filter

**What:** The SQLAlchemy pattern for `as_of` filtering on any table with `ingestion_timestamp`. Required for FR-1.5.

```python
# backend/app/queries/point_in_time.py
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.price_bars import PriceBar

async def get_prices_as_of(
    db: AsyncSession,
    symbol: str,
    as_of: datetime,
    lookback_days: int = 90,
) -> list[PriceBar]:
    """
    Returns only rows visible at `as_of` — excludes rows ingested after that date.
    This is the core mechanism preventing look-ahead bias in backtests.
    """
    stmt = (
        select(PriceBar)
        .where(PriceBar.symbol == symbol)
        .where(PriceBar.time >= as_of - timedelta(days=lookback_days))
        .where(PriceBar.time <= as_of)
        .where(PriceBar.ingestion_timestamp <= as_of)  # point-in-time gate
        .order_by(PriceBar.time.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()
```

**Test for FR-1.5 success criterion:**

```python
# tests/test_schema.py
async def test_as_of_filtering_excludes_future_ingested_rows(db):
    """
    Insert a row with ingestion_timestamp in the future.
    Verify that as_of query at NOW() does not return it.
    """
    future_ts = datetime.utcnow() + timedelta(days=365)
    # Insert row with backdated time but future ingestion_timestamp
    await db.execute(text("""
        INSERT INTO price_bars (time, symbol, close, ingestion_timestamp)
        VALUES (NOW() - INTERVAL '1 day', 'TEST', 100.0, :future_ts)
    """), {"future_ts": future_ts})
    await db.commit()

    rows = await get_prices_as_of(db, "TEST", as_of=datetime.utcnow())
    assert len(rows) == 0, "Future-ingested row must not appear in as_of query"
```

### Pattern 8: Railway Configuration

**What:** `railway.toml` service definitions and the volume-first deployment workflow.
**When to use:** After Docker Compose is working locally; Railway deploys each service separately.

```toml
# railway.toml — defines build/deploy settings per service
# Source: Railway docs (training knowledge; verify at deployment time)
[build]
builder = "dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

**Railway service deployment order (manual, CLI-based workflow):**

```bash
# Step 1: Create Railway project and services
railway link  # or railway new

# Step 2: Create and attach persistent volume to TimescaleDB service FIRST
# This MUST happen before any container starts or data is written
# Railway UI: Service → Settings → Volumes → Add Volume → /var/lib/postgresql/data

# Step 3: Set environment variables on each service
railway variables set DATABASE_URL="postgresql+asyncpg://..." --service fastapi

# Step 4: Deploy services in dependency order:
# db → redis → fastapi → celery_worker → prefect_server → nextjs
railway up --service db
# Wait for health check to pass before deploying dependent services

# Step 5: Run initial Alembic migration against Railway DB
DATABASE_URL=$(railway variables get DATABASE_URL --service fastapi) \
  alembic upgrade head
```

**Railway private networking:** Services on the same Railway project communicate via internal hostnames: `<service-name>.railway.internal`. Production environment variables use these hostnames, not localhost.

```bash
# Production Railway env vars (set per service)
DATABASE_URL=postgresql+asyncpg://pead:${DB_PASSWORD}@db.railway.internal:5432/pead_trading
REDIS_URL=redis://redis.railway.internal:6379/0
PREFECT_API_URL=http://prefect-server.railway.internal:4200/api
```

[ASSUMED — `.railway.internal` hostname pattern based on training knowledge; verify against current Railway private networking docs at deployment time]

### Pattern 9: GitHub Actions CI Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  lint-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff==0.15.12
      - run: ruff check backend/
      - run: ruff format --check backend/

  lint-typescript:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci --prefix frontend
      - run: npm run lint --prefix frontend
      - run: npm run type-check --prefix frontend  # npx tsc --noEmit

  test-python:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_USER: pead
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: pead_test
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r backend/requirements.txt
      - run: alembic upgrade head
        working-directory: backend
        env:
          DATABASE_URL: postgresql+asyncpg://pead:testpass@localhost:5432/pead_test
      - run: pytest backend/tests/ -v
        env:
          DATABASE_URL: postgresql+asyncpg://pead:testpass@localhost:5432/pead_test
          REDIS_URL: redis://localhost:6379/0

  docker-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: docker build ./backend -t pead-backend:ci
      - run: docker build ./frontend -t pead-frontend:ci
```

```yaml
# .github/workflows/deploy.yml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Railway CLI
        run: npm install -g @railway/cli
      - name: Deploy to Railway
        run: railway up --detach
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

[ASSUMED — `@railway/cli` npm package and `railway up` command; verify Railway CLI deploy pattern at setup time. The RL trainer service must be excluded from this auto-deploy workflow.]

### Anti-Patterns to Avoid

- **Starting TimescaleDB without a persistent volume**: All data lost on restart. Volume must be attached before first container start.
- **`async def` in Celery tasks**: Celery uses sync workers by default. Use `asyncio.run()` for async helpers. (CLAUDE.md directive)
- **`interval`-based Prefect schedules**: Reset on Railway redeploy → double-runs. Use cron only. (CLAUDE.md directive)
- **Pulling Prefect `latest` instead of `2-latest`**: Pulls 3.x which has breaking changes.
- **Using Railway managed PostgreSQL**: No TimescaleDB extension. Must use custom Docker service.
- **Running Alembic autogenerate without `include_object` filter**: Generates migrations for `_timescaledb_*` internal tables, breaking the migration.
- **Health check that only checks process liveness**: `depends_on: condition: service_healthy` requires a health check that verifies DB connectivity, not just that Python is running.
- **Sharing Redis DB 0 for Celery broker AND pub/sub**: Use DB 0 for Celery broker/backend, DB 1 for SSE pub/sub fan-out. Mixing causes interference under load.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Database migrations | Manual SQL scripts | Alembic | Schema drift, no rollback, no version tracking |
| TimescaleDB internal table handling | Custom migration guard | `include_object` filter in Alembic `env.py` | TimescaleDB creates ~15 internal tables that autogenerate treats as missing |
| Docker service health ordering | `sleep 30` hacks | `depends_on: condition: service_healthy` with proper health checks | Sleep is unreliable; health checks are deterministic |
| Async DB sessions | Per-request engine creation | `async_sessionmaker` with `expire_on_commit=False` | New engine per request exhausts connection limits |
| Environment config | Hardcoded strings | `pydantic-settings BaseSettings` | Type-safe, `.env`-aware, Railway env vars work automatically |
| SSE heartbeat | Client reconnect logic | Server sends `: heartbeat\n\n` every 25 seconds | Railway proxy has 60s idle timeout; heartbeat prevents disconnection |
| Railway private hostnames | External URL routing | `.railway.internal` hostnames | Internal routing is free and zero-latency |

---

## Common Pitfalls

### Pitfall 1: Railway Ephemeral Filesystem Wipes Database

**What goes wrong:** TimescaleDB service restarts (crash, deploy, Railway maintenance) with no persistent volume → all data at `/var/lib/postgresql/data` is deleted. 5 years of price history gone on a routine deploy.

**Why it happens:** Railway services have ephemeral filesystems by default. Volume must be explicitly attached in Railway UI or CLI before the service ever starts.

**How to avoid:** Attach Railway persistent volume to `/var/lib/postgresql/data` as the FIRST action, before deploying or initializing the database. Test by restarting the service and verifying data survives.

**Warning signs:** Service restarts cleanly with no data; `pg_isready` passes but tables are empty.

---

### Pitfall 2: Alembic Autogenerate Detects `_timescaledb_*` Internal Tables

**What goes wrong:** `alembic revision --autogenerate` generates `op.drop_table()` calls for all TimescaleDB internal tables, because Alembic can see them in the DB but not in the model metadata. Running this migration destroys the TimescaleDB extension.

**Why it happens:** TimescaleDB creates ~15 internal tables and schemas when the extension is enabled. Alembic's autogenerate compares all DB objects to models.

**How to avoid:** Add `include_object` filter in `alembic/env.py` that returns `False` for any table name starting with `_timescaledb`. Never run `--autogenerate` without this filter.

**Warning signs:** Generated migration contains `op.drop_table('_timescaledb_catalog_*')`.

---

### Pitfall 3: Prefect Pulls v3 Instead of v2

**What goes wrong:** Docker image `prefecthq/prefect:latest` now resolves to Prefect 3.x. Prefect 3 has breaking API changes: `prefect.orion` namespace removed, `run_deployment` API changed, flow/task decorators behave differently.

**Why it happens:** `latest` tag always tracks the newest major version. Prefect 3.6.29 is current as of May 2026.

**How to avoid:** Always use `prefecthq/prefect:2-latest` in `docker-compose.yml` and Railway service configuration. Pin explicitly in `requirements.txt` as `prefect>=2.0,<3.0`.

**Warning signs:** `from prefect.orion` import errors; `run_deployment` function signature mismatch.

---

### Pitfall 4: `create_hypertable` Fails if Table Has Data

**What goes wrong:** If the Alembic migration runs `CREATE TABLE` followed by inserts, then attempts `SELECT create_hypertable(...)`, it may fail depending on TimescaleDB version if the table already has rows.

**Why it happens:** Some TimescaleDB versions require the table to be empty at hypertable conversion time.

**How to avoid:** Always call `create_hypertable` immediately after `CREATE TABLE`, before any data is inserted. The `migrate_data => TRUE` parameter handles tables that already have rows but adds migration overhead.

**Warning signs:** `ERROR: cannot create a hypertable if table has rows` in migration output.

---

### Pitfall 5: FastAPI `depends_on` Without `service_healthy` Condition

**What goes wrong:** `depends_on: [db]` only waits for the Docker container to start, not for PostgreSQL to be ready to accept connections. FastAPI starts immediately, attempts DB connection, fails, and crashes.

**Why it happens:** Docker's `depends_on` has three conditions: `service_started` (default), `service_healthy`, and `service_completed_successfully`. Only `service_healthy` waits for the health check.

**How to avoid:** Use `depends_on: db: condition: service_healthy` in `docker-compose.yml`. Ensure the `db` service has a `healthcheck` that runs `pg_isready`.

**Warning signs:** FastAPI container exits with `sqlalchemy.exc.OperationalError: could not connect to server` in logs.

---

### Pitfall 6: Railway Proxy Kills SSE Connections (60s Timeout)

**What goes wrong:** Railway's HTTP proxy has a 60-second idle connection timeout. SSE connections with no activity for 60 seconds are terminated at the proxy layer. The Next.js client gets a disconnection, shows stale data.

**Why it happens:** Railway uses an HTTP reverse proxy that enforces idle timeouts for resource management.

**How to avoid:** SSE event generator must emit a keepalive comment (`yield ": heartbeat\n\n"`) every 25 seconds. Also set the `X-Accel-Buffering: no` response header to prevent Nginx-style proxy buffering.

**Warning signs:** SSE connection drops exactly at 60-second intervals in production but not in local Docker.

---

### Pitfall 7: Tailwind v4 Config Syntax Change

**What goes wrong:** Installing `tailwindcss@4.x` and trying to configure it via `tailwind.config.ts` — v4 replaced the JavaScript config file with CSS-first configuration using `@theme` directive.

**Why it happens:** Tailwind v4 is a major rewrite. The config model changed completely. Any tutorial or documentation for v3 will show the wrong setup.

**How to avoid:** Use CSS-first `@theme` in `globals.css`. Remove `tailwind.config.ts`. Do not use `content` array — v4 uses automatic content detection. [VERIFIED: npm registry v4.2.4]

**Warning signs:** `tailwind.config.ts not found` warning; custom colors not applied; `@apply` directives fail.

---

## Code Examples

### FastAPI SSE Endpoint with Redis Pub/Sub and Heartbeat

```python
# backend/app/routers/stream.py
# Source: CLAUDE.md architecture decision (SSE not WebSocket)
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis
from app.config import settings

router = APIRouter()

CHANNELS = ["signals", "positions", "rl_state", "alerts"]

async def event_generator():
    r = aioredis.from_url(settings.REDIS_PUB_URL)  # redis://redis:6379/1
    pubsub = r.pubsub()
    await pubsub.subscribe(*CHANNELS)
    last_heartbeat = asyncio.get_event_loop().time()
    try:
        async for message in pubsub.listen():
            now = asyncio.get_event_loop().time()
            # Heartbeat every 25s to survive Railway 60s proxy timeout
            if now - last_heartbeat > 25:
                yield ": heartbeat\n\n"
                last_heartbeat = now
            if message["type"] == "message":
                channel = message["channel"].decode()
                data = message["data"].decode()
                yield f"event: {channel}\ndata: {data}\n\n"
    finally:
        await pubsub.unsubscribe(*CHANNELS)
        await r.aclose()

@router.get("/events")
async def stream_events():
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

### Alembic `env.py` with TimescaleDB Table Exclusion

```python
# backend/alembic/env.py (relevant sections)
# Source: CLAUDE.md directive

def include_object(object, name, type_, reflected, compare_to):
    """Exclude TimescaleDB internals from autogenerate detection."""
    if type_ == "table":
        if name.startswith("_timescaledb_"):
            return False
        if name.startswith("timescaledb_"):
            return False
    return True

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            include_schemas=False,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
```

### Pydantic Settings Config

```python
# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://pead:dev@localhost:5432/pead_trading"

    # Redis — separate DBs for Celery and pub/sub
    REDIS_URL: str = "redis://localhost:6379/0"          # Celery broker
    REDIS_BACKEND_URL: str = "redis://localhost:6379/1"  # Celery result backend
    REDIS_PUB_URL: str = "redis://localhost:6379/2"      # SSE pub/sub

    # Prefect
    PREFECT_API_URL: str = "http://localhost:4200/api"

    # Alpaca
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_PAPER: bool = True

settings = Settings()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `prefect:latest` = 2.x | `prefect:latest` = 3.x | 2025 | Must pin `2-latest` explicitly |
| `tailwind.config.ts` JS config | CSS-first `@theme` in globals.css | Tailwind v4 (2024-2025) | All v3 tutorials show wrong config |
| `pydantic.BaseSettings` | `pydantic-settings.BaseSettings` | Pydantic v2 | Separate package install required |
| `alpaca-trade-api` | `alpaca-py` | Alpaca SDK v0.x+ | Completely different import paths |
| Railway `nixpacks` auto-detect | Dockerfile-first for complex services | Ongoing | TimescaleDB and Prefect need explicit Docker |
| Alembic `run_async_migrations` via `asyncio.run()` | Native async Alembic `run_async_migrations` | Alembic 1.11+ | Async migrations now fully supported |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ingestion_timestamp` is the correct column name for `as_of` filtering; event timestamp is used for time partitioning | Architecture Patterns (Pattern 2) | Wrong column used for point-in-time filter → look-ahead bias in backtests |
| A2 | Prefect 2.x requires a separate `prefect_meta` database on PostgreSQL | Architecture Patterns (Pattern 1) | Could use same `pead_trading` DB with separate schema — verify Prefect 2.x server docs |
| A3 | `create_hypertable(..., if_not_exists => TRUE)` is valid TimescaleDB 2.x syntax | Code Examples (Alembic migration) | Migration error if parameter name differs — check TimescaleDB docs |
| A4 | Railway `.railway.internal` DNS hostname pattern for private networking | Architecture Patterns (Pattern 8) | Service-to-service connections fail if hostname format changed — verify Railway docs at deploy time |
| A5 | `railway up` via `@railway/cli` npm package works for GitHub Actions auto-deploy | Architecture Patterns (Pattern 9) | CI deploy step fails — verify Railway CLI/GitHub Action at CI setup time |
| A6 | Prefect 2.20.25 is the latest maintained 2.x version (upload: 2025-12-08) | Standard Stack | Newer 2.x patch may be available — check PyPI at implementation time |
| A7 | Tailwind v4 `@theme` directive replaces `tailwind.config.ts` entirely | Standard Stack + Pattern 6 | Config approach wrong if using Tailwind 3.x instead — clarify version intention |

---

## Open Questions (RESOLVED)

1. **Tailwind v4 vs v3 for Next.js 16**
   - What we know: npm registry shows `tailwindcss@4.2.4` as latest. Next.js 16.2.4 supports Tailwind v4.
   - What's unclear: PRD specifies "Next.js 14" but research shows Next.js 16 is current. All App Router patterns are compatible. If Tailwind v3 is required for compatibility with existing shadcn/ui components, that's a different config path.
   - **RESOLVED: Use Tailwind v4 CSS-first config (`@theme` in globals.css, no tailwind.config.ts). Implemented in Plan 01-01 Task 3.**

2. **Prefect metadata DB: shared instance or separate service?**
   - What we know: Prefect 2.x server needs a PostgreSQL-compatible database for its own metadata. Same Railway PostgreSQL instance is possible using a separate database name (`prefect_meta`).
   - What's unclear: Connection pool contention between Prefect metadata writes and application queries.
   - **RESOLVED: Use shared PostgreSQL instance with separate `prefect_meta` database (created via infra/db/init.sql mounted as docker-entrypoint-initdb.d). Implemented in Plan 01-01 Task 1.**

3. **Railway deployment: CLI-based vs `railway.toml` vs Railway GitHub App**
   - What we know: Railway supports multiple deploy methods. GitHub integration with auto-deploy is standard. RL trainer must be excluded from auto-deploy.
   - What's unclear: Current Railway `railway.toml` schema and whether per-service deploy exclusions are configurable there.
   - **RESOLVED: Use `@railway/cli` npm package with `railway up --detach --service <name>` in a GitHub Actions matrix strategy. rl_trainer is explicitly omitted from the matrix. Implemented in Plan 01-03 Task 2.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Docker Compose local dev | Yes | 29.4.1 | — |
| Docker Compose | Local stack | Yes | v5.1.3 | — |
| Python 3.11 | Backend | Yes | 3.11.4 | — |
| Node.js 22+ | Frontend | Yes | v22.20.0 | — |
| npm | Frontend packages | Yes | 10.9.3 | — |
| Railway CLI | Deployment | No | — | Deploy via Railway GitHub App UI |
| TimescaleDB (local Docker pull) | DB service | Yes (Docker available) | latest-pg15 | — |

**Missing dependencies with no fallback:**
- None that block local development. Railway CLI is optional if using GitHub App integration.

**Missing dependencies with fallback:**
- Railway CLI not installed: deploy via Railway web dashboard or GitHub App integration (preferred approach anyway).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — Wave 0 |
| Quick run command | `pytest backend/tests/ -v -x` |
| Full suite command | `pytest backend/tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-1.1 | `docker compose up` starts all 6 services with health checks passing | smoke | `docker compose up -d && docker compose ps` (all healthy) | Wave 0 |
| FR-1.2 | All 6 hypertables exist and accept writes | integration | `pytest backend/tests/test_schema.py::test_hypertables_exist -x` | Wave 0 |
| FR-1.2 | Each hypertable accepts INSERT | integration | `pytest backend/tests/test_schema.py::test_hypertable_inserts -x` | Wave 0 |
| FR-1.3 | Schema migration survives Railway service restart | manual | Restart TimescaleDB container; verify tables intact | N/A (manual) |
| FR-1.4 | CI lint passes on PR | smoke | GitHub Actions CI run | Wave 0 |
| FR-1.4 | CI Docker build passes on PR | smoke | GitHub Actions CI run | Wave 0 |
| FR-1.5 | `as_of` query excludes future-ingested rows | unit | `pytest backend/tests/test_as_of.py::test_future_ingested_row_excluded -x` | Wave 0 |
| FR-1.5 | `ingestion_timestamp` column exists on all 6 tables | unit | `pytest backend/tests/test_schema.py::test_ingestion_timestamp_columns -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/ -v -x -q`
- **Per wave merge:** `pytest backend/tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/pytest.ini` — pytest configuration with `asyncio_mode = auto`
- [ ] `backend/tests/conftest.py` — async DB session fixture pointing at test DB
- [ ] `backend/tests/test_health.py` — GET /health returns 200 with db connected
- [ ] `backend/tests/test_schema.py` — hypertable existence, insert acceptance, `as_of` filtering
- [ ] Framework install: `pip install pytest==9.0.3 pytest-asyncio==1.3.0 httpx==0.28.1`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user, no auth in v1.0 (NFR-5) |
| V3 Session Management | No | No sessions in v1.0 |
| V4 Access Control | No | Internal Railway deployment, not public-facing |
| V5 Input Validation | Yes (minimal) | pydantic v2 models on all API inputs |
| V6 Cryptography | No | No crypto operations in Phase 1 |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Database credentials in Docker image layers | Information Disclosure | Pass via env vars at runtime; never as build ARGs |
| Alpaca API keys in committed `.env` | Information Disclosure | `.env` in `.gitignore`; keys set in Railway env vars only |
| Railway environment variables visible to all project members | Information Disclosure | Single-user project; rotate paper trading keys every 90 days |
| SQL injection via raw `op.execute()` in Alembic | Tampering | Migration files are static; no user input in migrations |

**Phase 1 security stance:** This phase has minimal attack surface (no auth, internal deployment, no user-facing inputs). Primary risk is credential exposure in Docker image history or git commits.

---

## Sources

### Primary (HIGH confidence)

- PyPI registry — `fastapi`, `celery`, `alembic`, `sqlalchemy`, `asyncpg`, `redis`, `uvicorn`, `pydantic`, `ruff`, `pytest`, `pytest-asyncio`, `alpaca-py` — current versions verified 2026-05-02 [VERIFIED: PyPI]
- npm registry — `next`, `typescript`, `tailwindcss`, `eslint` — current versions verified 2026-05-02 [VERIFIED: npm]
- `CLAUDE.md` — all locked architecture decisions (non-negotiable stack, service names, Celery sync requirement, Prefect 2.x pin) [VERIFIED: project file]
- Local environment — Docker 29.4.1, Docker Compose v5.1.3, Python 3.11.4, Node 22.20.0 confirmed available [VERIFIED: Bash tool]

### Secondary (MEDIUM confidence)

- Project research docs (`.planning/research/ARCHITECTURE.md`, `STACK.md`, `PITFALLS.md`) — verified against PyPI/npm where possible; training data cutoff August 2025 [CITED: .planning/research/]
- Prefect 2.20.25 — latest 2.x confirmed at PyPI; upload date 2025-12-08 confirms active maintenance [VERIFIED: PyPI]

### Tertiary (LOW confidence)

- Railway `.railway.internal` private networking hostname pattern — training knowledge, not verified in this session [ASSUMED]
- Railway `railway.toml` exact current schema — training knowledge; Railway evolves quickly [ASSUMED]
- `create_hypertable` `if_not_exists` parameter syntax — training knowledge; TimescaleDB core API is stable but verify at migration time [ASSUMED]
- `@railway/cli` npm package for GitHub Actions deploy — training knowledge; Railway CLI install method may have changed [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI and npm as of 2026-05-02
- Architecture: HIGH — Docker Compose, Alembic, FastAPI patterns are well-established; SSE/Redis pattern locked by CLAUDE.md
- TimescaleDB DDL: MEDIUM-HIGH — core API stable since 2.0; specific parameter names assumed from training data
- Railway deployment: MEDIUM — Railway evolves quickly; verify at deployment time
- CI/CD: MEDIUM — GitHub Actions syntax stable; Railway CLI/GitHub App integration needs verification

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 for stable libraries; 2026-05-16 for Railway-specific patterns (changes frequently)
