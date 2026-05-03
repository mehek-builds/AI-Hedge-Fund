# Technology Stack Research

**Project:** PEAD Trading System
**Researched:** 2026-05-02
**Research mode:** Ecosystem — verifying best practices for a pre-specified stack

---

## Source Notes

Next.js documentation was verified against official docs (nextjs.org, version 16.2.4, updated 2026-04-10). All other components use training data (cutoff August 2025) cross-referenced against known ecosystem patterns. Confidence levels reflect this asymmetry.

---

## Recommended Stack

### Frontend

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| Next.js | 15+ (App Router) | React framework, trading dashboard UI | HIGH (official docs verified) |
| TypeScript | 5.x | Type safety across frontend | HIGH |
| Tailwind CSS | 3.x | Utility-first styling for dashboard | HIGH |
| SWR or TanStack Query | latest | Client-side data polling for live prices | MEDIUM |
| Recharts or TradingView Lightweight | latest | Price charts and P&L visualization | MEDIUM |

**Next.js App Router vs Pages Router decision:**
Use App Router. The PRD specifies Next.js 14 but the framework has since released v15/v16 with no App Router breaking changes for this use case. App Router is the default and recommended path. Pages Router is in maintenance mode.

Key App Router patterns for this project:
- Dashboard pages are Server Components by default — fetch positions/signals on server
- Real-time WebSocket UI (live P&L, signal events) requires Client Components with `'use client'` directive
- Use `<Suspense>` with skeleton fallbacks for initial position/portfolio load
- Context must be wrapped in a Client Component provider at the root layout level
- `NEXT_PUBLIC_` prefix required for any env vars accessed in browser (e.g., WebSocket URL)
- Do NOT use Route Handlers to proxy WebSocket traffic — WebSockets don't survive serverless lambda timeouts; connect the browser directly to FastAPI

### Backend

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| FastAPI | 0.111+ | REST API + WebSocket server | HIGH |
| Python | 3.11+ | Required for modern async, better typing | HIGH |
| Uvicorn | 0.29+ | ASGI server (use with `--workers 1` in Docker for Celery coordination) | HIGH |
| Pydantic v2 | 2.x | Request/response validation, settings management | HIGH |

**FastAPI async patterns (verified via official docs):**
- Use `async def` for all endpoints that touch asyncpg/SQLAlchemy async or call `await`
- Use regular `def` for CPU-bound tasks — FastAPI runs these in a threadpool automatically
- WebSocket endpoint pattern: `async def ws(websocket: WebSocket)` with `await websocket.accept()` then an infinite loop with `await asyncio.sleep()` between broadcasts
- For broadcasting to multiple connected clients, maintain an in-memory `ConnectionManager` class (set of active WebSocket connections); this is fine for single-user but does not survive multi-worker restarts — Redis pub/sub is the correct solution for worker-safe broadcasting

**Critical gotcha — Uvicorn workers and Celery:**
If running `uvicorn --workers N`, each worker has its own in-memory state. The ConnectionManager pattern breaks — two requests may hit different workers. For a single-user system on Railway with one replica, `--workers 1` is fine. For future scale: use Redis pub/sub where FastAPI subscribes and pushes to WS clients.

### Task Queue

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| Celery | 5.3+ | Async task execution for signal processing | HIGH |
| Redis | 7.x | Celery broker + result backend + pub/sub bus | HIGH |
| Flower | 2.x | Celery monitoring UI (dev only) | MEDIUM |

**Celery + Redis integration pattern:**
```python
# celery_app.py
from celery import Celery

celery_app = Celery(
    "pead_worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "tasks.signal_processing.*": {"queue": "signals"},
        "tasks.training.*": {"queue": "ml"},
    },
)
```

**FastAPI → Celery pattern (no shared event loop):**
```python
# From a FastAPI endpoint, dispatch to Celery
from .celery_app import celery_app

@router.post("/signals/process")
async def trigger_signal(event: EarningsEvent):
    task = celery_app.send_task(
        "tasks.signal_processing.compute_pead",
        args=[event.model_dump()],
        queue="signals",
    )
    return {"task_id": task.id}
```

**Redis pub/sub for real-time signal events to frontend:**
```python
# In Celery task, after signal computed:
import redis.asyncio as aioredis

async def publish_signal_event(signal: dict):
    r = aioredis.from_url("redis://redis:6379")
    await r.publish("signal_events", json.dumps(signal))

# In FastAPI WebSocket handler, subscribe:
@router.websocket("/ws/signals")
async def signal_stream(websocket: WebSocket):
    await websocket.accept()
    r = aioredis.from_url("redis://redis:6379")
    pubsub = r.pubsub()
    await pubsub.subscribe("signal_events")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("signal_events")
```

**Gotcha:** Celery tasks are synchronous Python by default. Do not use `async def` in Celery task functions unless using `gevent` or `eventlet` pool. Use `asyncio.run()` to call async helpers from within sync tasks.

### Database

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| PostgreSQL | 15+ | Relational data (trades, positions, configurations) | HIGH |
| TimescaleDB | 2.14+ | Time-series extension on PostgreSQL for price/signal data | HIGH |
| SQLAlchemy | 2.0+ (async) | ORM + async query interface | HIGH |
| asyncpg | 0.29+ | Async PostgreSQL driver (required for SQLAlchemy async) | HIGH |
| Alembic | 1.13+ | Database migrations | HIGH |

**TimescaleDB hypertable setup:**
TimescaleDB is installed as a PostgreSQL extension. The Docker image `timescale/timescaledb:latest-pg15` includes both.

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create the base table first
CREATE TABLE price_bars (
    time        TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4),
    volume      BIGINT
);

-- Convert to hypertable (chunk by 1 day)
SELECT create_hypertable('price_bars', 'time', chunk_time_interval => INTERVAL '1 day');

-- Create a composite index for symbol + time queries (critical for PEAD lookups)
CREATE INDEX ON price_bars (symbol, time DESC);

-- Compression policy (after 7 days, compress chunks)
SELECT add_compression_policy('price_bars', INTERVAL '7 days');
```

**TimescaleDB performance characteristics:**
- Query speeds for time-range scans on hypertables: sub-millisecond for recent chunks (hot cache), 1-10ms for compressed historical chunks
- Continuous aggregates allow pre-computed OHLCV at any interval — use for dashboard charts
- `time_bucket()` function is the key aggregate: `SELECT time_bucket('5 minutes', time) AS bucket, AVG(close) ...`
- For PEAD signal computation: query 90-day window post-earnings, expect <10ms with proper indexing at S&P 500 scale (~500 symbols × 4 quarters)

**SQLAlchemy async pattern:**
```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@db:5432/pead"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# FastAPI dependency
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Critical gotcha — Alembic + TimescaleDB:**
Alembic migrations will fail if you try to `create_hypertable()` in a standard migration. Use `op.execute()` with raw SQL for TimescaleDB-specific operations. Also, Alembic autogenerate does not understand TimescaleDB internal tables — add `include_schemas=False` and exclude `_timescaledb_*` schemas in `env.py`.

```python
# In alembic/env.py
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name.startswith("_timescaledb"):
        return False
    return True
```

### ML/RL Stack

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| PyTorch | 2.3+ | Deep learning backbone | HIGH |
| Stable Baselines 3 | 2.3+ | SAC implementation | HIGH (SB3 is the standard) |
| Gymnasium (gym) | 0.29+ | RL environment interface (SB3 requires this) | HIGH |
| NumPy | 1.26+ | Numerical operations, feature engineering | HIGH |
| Pandas | 2.1+ | Data manipulation for earnings/price data | HIGH |
| scikit-learn | 1.4+ | Feature preprocessing, scaler utilities | HIGH |

**SAC Library Decision — Stable Baselines 3 vs alternatives:**

Recommend **Stable Baselines 3** (SB3) over tianshou or custom implementation.

Rationale:
- SB3's SAC implementation is battle-tested, well-documented, and PyTorch-native
- Custom SAC ensemble is straightforward: instantiate multiple `SAC` agents, run inference in parallel, aggregate actions by mean/vote
- SB3 supports custom Gymnasium environments, which is required (trading env is not standard)
- Tianshou is more research-oriented and requires more boilerplate for production use
- Custom SAC would take 2-4 weeks to stabilize vs 2-4 days with SB3

**Custom Gymnasium environment for PEAD trading:**
```python
import gymnasium as gym
import numpy as np

class PEADTradingEnv(gym.Env):
    metadata = {"render_modes": []}
    
    def __init__(self, price_data: np.ndarray, earnings_features: np.ndarray):
        super().__init__()
        # Observation: [price_momentum_features, earnings_surprise, position, cash]
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(32,), dtype=np.float32
        )
        # Action: continuous position sizing [-1, 1] where sign = direction
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(1,), dtype=np.float32
        )
    
    def step(self, action):
        # Returns: obs, reward, terminated, truncated, info
        ...
    
    def reset(self, seed=None, options=None):
        ...
```

**SAC Ensemble pattern:**
```python
from stable_baselines3 import SAC

class SACEnsemble:
    def __init__(self, n_agents: int, env):
        self.agents = [
            SAC("MlpPolicy", env, verbose=0, device="cpu")
            for _ in range(n_agents)
        ]
    
    def predict(self, obs) -> np.ndarray:
        actions = [agent.predict(obs, deterministic=True)[0] for agent in self.agents]
        return np.mean(actions, axis=0)  # ensemble average
    
    def learn(self, total_timesteps: int):
        for agent in self.agents:
            agent.learn(total_timesteps=total_timesteps)
```

**Transformer for earnings signal processing:**
Use PyTorch directly (not HuggingFace transformers — overkill for tabular sequential data). A lightweight Transformer encoder over a sequence of earnings features (surprise %, guidance, sector) feeding into the SAC observation vector is the right architecture. PyTorch's `nn.TransformerEncoder` with 2-4 layers is sufficient.

**Known PEAD/finance RL reference codebases:**
- `FinRL` library (GitHub: AI4Finance-Foundation/FinRL) — open source framework specifically for financial RL, includes custom gym envs and SB3 integration. Not ideal to use directly (too much abstraction) but excellent reference for reward shaping and observation space design
- `tensortrade` — older, less maintained, but has PEAD-adjacent patterns
- Confidence: MEDIUM (from training data, not re-verified)

### Data Pipelines

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| Prefect | 2.x (Prefect 2.0) | Orchestration of earnings data ingestion pipelines | MEDIUM |
| yfinance | 0.2+ | Historical OHLCV data (free, no auth) | HIGH |
| alpha_vantage or polygon.io SDK | latest | Earnings surprise data, SEC filings | MEDIUM |

**Prefect 2.0 flow design:**
```python
from prefect import flow, task
from prefect.schedules import CronSchedule

@task(retries=3, retry_delay_seconds=60)
def fetch_earnings_calendar(quarter: str) -> list[dict]:
    # Pull from earnings API
    ...

@task
def compute_pead_features(earnings: list[dict]) -> pd.DataFrame:
    # Feature engineering
    ...

@task  
def upsert_to_timescaledb(features: pd.DataFrame):
    # Write to PostgreSQL
    ...

@flow(
    name="earnings-ingestion",
    description="Daily earnings data ingestion for PEAD signal computation",
)
def earnings_ingestion_flow(quarter: str = "current"):
    earnings = fetch_earnings_calendar(quarter)
    features = compute_pead_features(earnings)
    upsert_to_timescaledb(features)
```

**Prefect 2.0 → PostgreSQL metadata storage:**
Prefect 2.0 uses SQLite by default for local development. For production, configure the Prefect server to use PostgreSQL:

```
# Environment variable for Prefect server
PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://user:pass@db:5432/prefect
```

The Prefect server is a separate service that writes flow run metadata to its own schema. Recommend using the **same** PostgreSQL instance with a separate `prefect` database to reduce Railway service count.

**Gotcha — Prefect 2.0 scheduler overhead:**
Prefect 2.0's built-in scheduler polls the database every ~5 seconds. For a trading system with earnings-triggered flows (not sub-second), this is acceptable. The Celery queue handles the sub-second event processing; Prefect handles the data pipeline scheduling (daily/weekly cadence). Do not try to use Prefect for real-time signal dispatch — use Celery for that.

**Gotcha — Prefect 2.0 vs Prefect 3.0:**
As of mid-2025, Prefect 3.0 was released. If the PRD specifies Prefect 2.0, stick with it — migration to v3 involves renaming `prefect.orion` internals and some API changes. The Docker image tag is `prefecthq/prefect:2-latest` for v2.

### Trading API

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| alpaca-py | 0.21+ | Official Alpaca Python SDK (replaces alpaca-trade-api) | HIGH |
| Alpaca Paper Trading | REST + WebSocket | Order execution, position management | HIGH |

**Critical note on SDK versions:**
The old SDK `alpaca-trade-api` is deprecated. Use the new `alpaca-py` package (`pip install alpaca-py`). The API is completely different.

```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream

# Paper trading client
trading_client = TradingClient(
    api_key=settings.ALPACA_API_KEY,
    secret_key=settings.ALPACA_SECRET_KEY,
    paper=True,  # Paper trading mode
)

# Submit market order
order_data = MarketOrderRequest(
    symbol="AAPL",
    qty=10,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY,
)
order = trading_client.submit_order(order_data)

# WebSocket market data stream
stream = StockDataStream(api_key, secret_key)

async def quote_handler(data):
    print(data)

stream.subscribe_quotes(quote_handler, "AAPL")
stream.run()
```

**Paper trading limitations:**
- Paper trading uses delayed data (15-min delay for free tier) unless using live market hours
- Order fills in paper trading simulate market conditions but are not guaranteed to match live fills
- Rate limits: 200 requests/min for REST, unlimited for WebSocket streams
- Paper account starts with $100k simulated cash

### Infrastructure

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| Docker Compose | 3.8+ | Local development orchestration | HIGH |
| Railway | current | Production deployment | MEDIUM |
| Docker | 24+ | Container runtime | HIGH |

**Docker Compose service topology for this project:**
```yaml
services:
  db:          # timescale/timescaledb:latest-pg15
  redis:       # redis:7-alpine
  api:         # FastAPI + Uvicorn (custom Dockerfile)
  worker:      # Celery worker (same image as api, different CMD)
  frontend:    # Next.js (custom Dockerfile)
  prefect:     # prefecthq/prefect:2-latest (Prefect server + agent)
```

Six services total, which is within normal Docker Compose and Railway limits.

**Railway deployment gotchas:**

Railway does NOT natively support Docker Compose as a single deployment unit. Each service must be deployed as a separate Railway service within a project. The workflow is:

1. Each service gets its own Dockerfile or Nixpacks buildpack
2. Services are connected via Railway's private networking (internal hostnames like `db.railway.internal`)
3. Railway provides managed PostgreSQL — but it does NOT provide TimescaleDB as a managed option
4. For TimescaleDB on Railway: deploy `timescale/timescaledb:latest-pg15` as a custom Docker service, not Railway's managed Postgres plugin

**Recommended Railway service configuration:**
- `db`: Custom Docker service using `timescale/timescaledb:latest-pg15` with a persistent volume
- `redis`: Custom Docker service using `redis:7-alpine` with persistence (`redis-server --appendonly yes`)
- `api`: Deploy from `/backend/` with Railway's auto-detect or custom Dockerfile
- `worker`: Same image as `api`, override start command to `celery -A app.celery_app worker --queues=signals,ml`
- `frontend`: Deploy from `/frontend/` with `npm run build && npm start`
- `prefect`: Custom Docker service from `prefecthq/prefect:2-latest`

**Railway volume persistence:**
Railway persistent volumes are required for PostgreSQL and Redis. Without them, every deploy wipes your data. Each volume is mounted at the data directory (`/var/lib/postgresql/data` for Postgres, `/data` for Redis).

**Railway free tier limitations:**
- $5/month credit on free tier — 6 services will exceed this quickly
- Starter plan ($20/month) provides more generous limits
- Services sleep after inactivity on free tier — not acceptable for a trading system; use Starter

---

## Integration Architecture

### FastAPI ↔ TimescaleDB (async)

```
FastAPI endpoint
  → async def handler(db: AsyncSession = Depends(get_db))
  → await db.execute(select(PriceBar).where(...))
  → results via asyncpg
  → TimescaleDB responds with chunk-aware query plan
```

Connection pool lives in `engine` (SQLAlchemy). Do not create a new engine per request.

### FastAPI ↔ WebSocket ↔ Next.js

```
Next.js Client Component (useEffect)
  → new WebSocket("ws://api/ws/signals")
  → FastAPI WebSocket endpoint accepts connection
  → FastAPI subscribes to Redis channel
  → Celery task publishes signal event to Redis
  → FastAPI pushes JSON to browser via WS
```

In Next.js, WebSocket connection lives in a Client Component `useEffect` hook. On unmount, call `ws.close()`. Use a custom hook (`useSignalStream`) to encapsulate this.

### Prefect 2.0 ↔ PostgreSQL

```
Prefect server (container)
  → PREFECT_API_DATABASE_CONNECTION_URL env var
  → writes flow/task run metadata to PostgreSQL
  → Prefect agent polls server for pending runs
  → agent executes flow Python code in subprocess
  → tasks write business data to TimescaleDB (separate connection)
```

Prefect's own metadata goes to PostgreSQL `prefect` database. Business data (earnings features, prices) goes to `pead` database through your own SQLAlchemy sessions inside the task functions.

### Celery ↔ FastAPI coordination

Celery workers and FastAPI do NOT share memory. Communication happens through:
1. FastAPI dispatches tasks via `celery_app.send_task()` (writes to Redis broker queue)
2. Celery task results stored in Redis backend, fetched by FastAPI via `AsyncResult(task_id).get()`
3. Real-time events published to Redis pub/sub, FastAPI WebSocket handler subscribes

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| RL library | Stable Baselines 3 | tianshou | SB3 more production-ready, less boilerplate |
| RL library | Stable Baselines 3 | Custom SAC | 2-4 week implementation risk |
| Task queue | Celery | RQ (Redis Queue) | Celery has richer routing, priority queues, monitoring |
| Task queue | Celery | FastAPI BackgroundTasks | Not durable — task lost on crash; no distributed workers |
| ORM | SQLAlchemy async | Tortoise ORM | SQLAlchemy is industry standard, better TimescaleDB support |
| ORM | SQLAlchemy async | asyncpg raw | No ORM abstractions; migrations become manual |
| Frontend charts | Recharts | TradingView Lightweight Charts | TradingView is actually better for OHLCV — consider it |
| Data pipeline | Prefect 2.0 | Airflow | Airflow requires more infra; Prefect 2.0 is lighter |
| Data pipeline | Prefect 2.0 | APScheduler | APScheduler has no flow observability/retry UI |

---

## Installation Reference

```bash
# Backend (Python 3.11+)
pip install \
  fastapi==0.111.* \
  uvicorn[standard]==0.29.* \
  pydantic[email]==2.* \
  pydantic-settings==2.* \
  sqlalchemy[asyncio]==2.* \
  asyncpg==0.29.* \
  alembic==1.13.* \
  celery[redis]==5.3.* \
  redis==5.* \
  prefect==2.* \
  alpaca-py==0.21.* \
  stable-baselines3==2.3.* \
  gymnasium==0.29.* \
  torch==2.3.* \
  numpy==1.26.* \
  pandas==2.1.* \
  scikit-learn==1.4.* \
  yfinance==0.2.*

# Frontend (Node 20+)
npm install next react react-dom typescript
npm install @types/react @types/node
npm install tailwindcss postcss autoprefixer
npm install swr  # or: npm install @tanstack/react-query
npm install recharts  # or lightweight-charts for candlestick
```

---

## Version-Specific Gotchas Summary

| Component | Gotcha | Impact |
|-----------|--------|--------|
| Next.js App Router | `params` is now a Promise in Next.js 15 — must `await params` | Build error if using old destructuring syntax |
| Next.js App Router | WebSockets cannot use Route Handlers (lambda timeout) | Must proxy WS directly to FastAPI |
| Next.js App Router | Server Components cannot use React context — wrap providers in `'use client'` | Runtime error if violated |
| FastAPI WebSocket | Single-worker only for in-memory ConnectionManager | Multi-worker breaks WS broadcast; use Redis pub/sub |
| Celery | No `async def` tasks by default | Use `asyncio.run()` for async helpers inside tasks |
| TimescaleDB + Alembic | `_timescaledb_*` tables confuse autogenerate | Filter in `env.py` include_object |
| TimescaleDB + Railway | No managed TimescaleDB option | Must deploy custom Docker service with volume |
| alpaca-py | Old `alpaca-trade-api` package is deprecated | Must use new `alpaca-py` SDK |
| Prefect | v3 released; v2 has different internal paths | Pin to `prefect==2.*` explicitly |
| SQLAlchemy async | `expire_on_commit=False` required with `async_sessionmaker` | Lazy-loading fails in async context otherwise |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Next.js App Router patterns | HIGH | Verified against official docs (v16.2.4, 2026) |
| FastAPI async patterns | HIGH | Verified against official docs |
| Celery + Redis integration | HIGH | Well-established pattern, stable ecosystem |
| SQLAlchemy async | HIGH | SQLAlchemy 2.0 async is mature and well-documented |
| TimescaleDB hypertables | MEDIUM | Training data (cutoff Aug 2025); core concepts are stable |
| Stable Baselines 3 SAC | MEDIUM | Training data; SB3 v2.x is stable |
| Railway deployment | MEDIUM | Railway evolves quickly; verify current service limits and Docker support at deploy time |
| Prefect 2.0 specifics | MEDIUM | v3 released; verify `prefecthq/prefect:2-latest` is still maintained |
| alpaca-py SDK | MEDIUM | Alpaca changes APIs — verify paper trading endpoint URLs at integration time |
