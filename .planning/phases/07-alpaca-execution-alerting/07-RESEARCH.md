# Phase 7: Alpaca Execution + Alerting - Research

**Researched:** 2026-05-13
**Domain:** Alpaca paper trading execution, Redis rate limiting, SendGrid + Slack alerting, PostgreSQL alerts table
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Bracket Order Parameters**
- Stop-loss leg: 2% below entry, configurable via `STOP_LOSS_PCT=0.02` in config
- Take-profit ceiling: 4% above entry (`TAKE_PROFIT_PCT=0.04`), 2:1 R/R ratio
- Entry order type: limit order at ask + 0.5 tick to reduce slippage vs market orders
- Partial fill handling: accept partial fill, update DB position size to the filled quantity

**Alerting Implementation**
- Rate limit storage: Redis (already in stack) - key `alert_rate:{event_type}`, TTL-based counting, max 3 per hour
- Alert persistence: new `alerts` table (clean separation from RL alerts in `rl_diversity_alerts`)
- Delivery mode: fire-and-forget async (log on failure, do not block trade execution)
- SendGrid format: minimal HTML (`<p>` tags, no CSS framework) - per CLAUDE.md global rule

**Service Architecture**
- Order placement trigger: FastAPI `POST /api/v1/orders` endpoint called by signal engine (follows existing router pattern in `backend/app/routers/`)
- Startup gate check: hard block - raise `RuntimeError` if no `backtest_gate_pass` row found in `backtest_runs`; Phase 7 service cannot start in degraded mode
- Position sync cadence: startup reconciliation + 15-minute polling via existing task infrastructure

### Claude's Discretion
- Alert table schema column names and indexing strategy
- Exact Alpaca API error handling (retry count and backoff timing within the "immediate retry 3x" envelope)
- Orphan detection query implementation details
- Celery task vs asyncio for the 15-minute polling heartbeat (whichever is cleaner given existing infrastructure)

### Deferred Ideas (OUT OF SCOPE)
- Alpaca websocket-based live position events (Phase 7 uses polling; websocket is a future enhancement)
- Live trading (ALPACA_PAPER stays True for Phase 7 scope)
- Multi-account support
- Rich HTML email templates with CSS styling (deferred; minimal HTML is sufficient for Phase 7)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR-7.1 | Bracket orders (limit entry + stop-loss + take-profit) submitted via alpaca-py | alpaca-py 0.43.4 TradingClient.submit_order with LimitOrderRequest + OrderClass.BRACKET |
| FR-7.2 | Position sync with Alpaca live state on startup and 15-minute polling | TradingClient.get_all_positions(); Celery beat or asyncio periodic task |
| FR-7.3 | Orphan detector: open exit orders with no matching position are cancelled and alerted | TradingClient.get_orders(GetOrdersRequest(status=OPEN)) + cancel_order_by_id(); compare against portfolio_positions |
| FR-7.4 | 9 event types delivered via SendGrid email + Slack webhook | sendgrid 6.12.5 Mail + SendGridAPIClient; httpx POST to SLACK_WEBHOOK_URL |
| FR-7.5 | Rate limiting: max 3 per event type per hour; burst of 10 in 5 min = exactly 3 deliveries | Redis INCR + EXPIRE on key `alert_rate:{event_type}:{window}`, TTL = 3600 |
| FR-7.6 | Short-side feature flag `ENABLE_SHORT_SIDE` defaults to false | Add to Settings in config.py; gate order submission |
| FR-8.1 | Alerts persisted to PostgreSQL `alerts` table | New Alembic migration 0007_alerts.py |
| FR-8.2 | Alerts visible in Phase 8 dashboard Alerting view | Schema must include columns Phase 8 needs: event_type, payload, created_at, delivered_sendgrid, delivered_slack |
| FR-8.3 | Redis pub/sub `alerts` channel already subscribed by SSE stream | `backend/app/routers/stream.py` already subscribes to "alerts" channel |
| FR-8.4 | All alert events published to Redis for live dashboard updates | Publish JSON to Redis `alerts` channel after persistence |
</phase_requirements>

---

## Summary

Phase 7 wires the paper trading execution layer and the system-wide alerting infrastructure. The codebase already has the Alpaca credentials in `Settings`, the `portfolio_positions` hypertable schema in place, and a stub in `backend/app/backtest/alerts.py` with `check_phase7_gate()` and `fire_gate_alert_v2()` that Phase 7 must convert from log-only to real SendGrid + Slack delivery.

The critical execution path is: signal engine calls `POST /api/v1/orders` - a new FastAPI router - which calls `TradingClient.submit_order(LimitOrderRequest(..., order_class=OrderClass.BRACKET, ...))` using alpaca-py 0.43.4 already pinned in requirements. Position state is reconciled by calling `TradingClient.get_all_positions()` on startup and every 15 minutes via a Celery periodic task (consistent with the existing Celery worker and task routing in `app/worker.py`). Orphan detection queries open orders from Alpaca and cross-references against the `portfolio_positions` DB table.

Alerting uses the sendgrid Python package (latest 6.12.5, not yet in requirements) and plain `httpx` POST for Slack (httpx is already in requirements). Rate limiting uses Redis INCR + EXPIRE, consistent with the existing `REDIS_URL` in Settings. All alerts are persisted to a new `alerts` table (migration 0007) and published to the existing Redis `alerts` pub/sub channel that `stream.py` already subscribes to.

**Primary recommendation:** Follow the established Celery task pattern for polling (not asyncio background tasks) because the worker infrastructure is already running; add `sendgrid==6.12.5` to requirements.txt; use `httpx.AsyncClient` for Slack (already available); wire `fire_gate_alert_v2()` to real delivery in the alerting module.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alpaca-py | 0.43.4 | Alpaca paper trading - bracket orders, positions, orders | Already pinned in requirements.txt [VERIFIED: requirements.txt] |
| sendgrid | 6.12.5 | SendGrid email delivery via API v3 | Official Twilio SendGrid Python SDK [VERIFIED: pypi.org/project/sendgrid] |
| httpx | 0.28.1 | Slack webhook HTTP POST | Already pinned in requirements.txt; replaces requests for async [VERIFIED: requirements.txt] |
| redis | 7.4.0 | Rate limiting (INCR/EXPIRE), pub/sub publish | Already pinned in requirements.txt [VERIFIED: requirements.txt] |
| celery[redis] | 5.6.3 | 15-minute polling heartbeat task | Already running in worker.py with broker=REDIS_URL [VERIFIED: requirements.txt] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlalchemy[asyncio] | 2.0.49 | Async ORM for alerts table persistence | All FastAPI router handlers use async sessions [VERIFIED: requirements.txt] |
| alembic | 1.18.4 | Migration 0007_alerts.py | Existing migration chain, next is 0007 [VERIFIED: migration files 0001-0006] |
| pydantic-settings | 2.14.0 | SENDGRID_API_KEY, SLACK_WEBHOOK_URL, ENABLE_SHORT_SIDE, STOP_LOSS_PCT, TAKE_PROFIT_PCT in Settings | All env config flows through Settings in config.py [VERIFIED: config.py] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sendgrid (6.x) | plain httpx POST to SendGrid v3 API | SDK handles auth, retry logic, and envelope construction; sendgrid SDK is the standard approach [ASSUMED] |
| Celery periodic for polling | asyncio background task in lifespan | Celery already has a worker running; asyncio background task would require changes to lifespan and has no retry semantics [VERIFIED: worker.py] |

**Installation:**
```bash
# Add to backend/requirements.txt:
sendgrid==6.12.5
```

**Version verification:**
- `alpaca-py 0.43.4` confirmed installed [VERIFIED: pip show alpaca-py]
- `sendgrid 6.12.5` confirmed via PyPI [VERIFIED: pypi.org/project/sendgrid]
- `httpx 0.28.1`, `redis 7.4.0`, `celery 5.6.3` confirmed in requirements.txt [VERIFIED: requirements.txt]

---

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
├── routers/
│   └── orders.py          # NEW: POST /api/v1/orders (bracket order submission)
├── execution/             # NEW module
│   ├── __init__.py
│   ├── broker.py          # TradingClient singleton, submit_bracket_order()
│   ├── position_sync.py   # reconcile_positions_with_alpaca()
│   └── orphan_detector.py # detect_and_cancel_orphans()
├── alerting/              # NEW module
│   ├── __init__.py
│   ├── dispatcher.py      # dispatch_alert(event_type, payload) - sends SendGrid + Slack
│   ├── rate_limiter.py    # is_rate_limited(event_type) using Redis INCR/EXPIRE
│   └── templates.py       # minimal HTML email bodies for each event type
├── models/
│   └── alerts.py          # NEW: Alert ORM model
├── tasks/
│   └── execution.py       # NEW: Celery task for 15-min position sync heartbeat
└── backtest/
    └── alerts.py          # EXISTING stub - fire_gate_alert_v2() wired to dispatcher
alembic/versions/
└── 0007_alerts.py         # NEW: alerts table migration
```

### Pattern 1: Bracket Order Submission via alpaca-py
**What:** Submit a limit entry order with attached stop-loss and take-profit legs in a single API call.
**When to use:** Whenever a signal triggers an order placement.
**Example:**
```python
# Source: alpaca.markets/sdks/python/api_reference/trading/requests.html [VERIFIED]
# Source: forum.alpaca.markets/t/bracket-order-code-example-with-alpaca-py-library/12110 [VERIFIED]
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, StopLossRequest, TakeProfitRequest
from alpaca.trading.enums import OrderSide, OrderClass, TimeInForce

client = TradingClient(
    api_key=settings.ALPACA_API_KEY,
    secret_key=settings.ALPACA_SECRET_KEY,
    paper=settings.ALPACA_PAPER,  # True in Phase 7
)

order = client.submit_order(LimitOrderRequest(
    symbol="AAPL",
    qty=10,
    side=OrderSide.BUY,
    limit_price=150.50,          # ask + 0.5 tick
    time_in_force=TimeInForce.DAY,
    order_class=OrderClass.BRACKET,
    stop_loss=StopLossRequest(stop_price=147.49),    # entry * (1 - STOP_LOSS_PCT)
    take_profit=TakeProfitRequest(limit_price=156.52),  # entry * (1 + TAKE_PROFIT_PCT)
))
```

### Pattern 2: Position Reconciliation
**What:** On startup and every 15 minutes, fetch Alpaca live positions and reconcile against `portfolio_positions` DB.
**When to use:** Startup lifespan and Celery periodic task.
**Example:**
```python
# Source: alpaca.markets/sdks/python/trading.html [VERIFIED]
positions = client.get_all_positions()
# Returns list of alpaca.trading.models.Position objects
# Each has: symbol, qty, avg_entry_price, current_price, unrealized_pl, etc.
```

### Pattern 3: Orphan Detection
**What:** Get all open orders from Alpaca; for each exit order (sell side), check if a matching position exists in DB. Cancel if no match.
**When to use:** Called after position reconciliation.
**Example:**
```python
# Source: alpaca.markets/sdks/python/api_reference/trading/orders.html [VERIFIED]
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

open_orders = client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
# cancel_order_by_id(order_id: Union[UUID, str]) -> None
client.cancel_order_by_id(order.id)
```

### Pattern 4: Redis Rate Limiting (Fixed Window)
**What:** Atomic INCR on a key per event_type per hour window; EXPIRE on first write; reject delivery if count > 3.
**When to use:** Every alert dispatch, before sending SendGrid/Slack.
**Example:**
```python
# Source: redis.io/tutorials/howtos/ratelimiting [CITED]
# Pattern: INCR + conditional EXPIRE (fixed window, resets at top of each hour)
import redis
import time

def is_rate_limited(r: redis.Redis, event_type: str, max_per_hour: int = 3) -> bool:
    # Key resets each hour using integer epoch-hour as window
    window = int(time.time()) // 3600
    key = f"alert_rate:{event_type}:{window}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 3600)
    return count > max_per_hour
```

### Pattern 5: SendGrid Email Dispatch
**What:** Send minimal HTML email using sendgrid Python SDK v6.
**When to use:** For every non-rate-limited alert.
**Example:**
```python
# Source: twilio.com/docs/sendgrid/for-developers/sending-email/quickstart-python [CITED]
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email="alerts@your-domain.com",
    to_emails="recipient@example.com",
    subject="[PEAD] order_filled: AAPL",
    html_content="<p>Order filled: AAPL 10 shares @ $150.50</p>",
)
sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
sg.send(message)
```

### Pattern 6: Slack Webhook Dispatch
**What:** Plain httpx POST to SLACK_WEBHOOK_URL with JSON payload. No Slack SDK needed.
**When to use:** For every non-rate-limited alert.
**Example:**
```python
# Source: api.slack.com/incoming-webhooks [CITED]
# httpx already in requirements at 0.28.1
import httpx

async def send_slack(webhook_url: str, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={"text": text})
```

### Pattern 7: FastAPI Router (following existing health.py pattern)
**What:** New `orders.py` router registered in `main.py` with `/api/v1` prefix.
**When to use:** Phase 7 adds `orders` router; main.py imports and includes it.
**Example:**
```python
# Source: backend/app/routers/health.py [VERIFIED: existing codebase]
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

router = APIRouter()

@router.post("/orders")
async def submit_order(payload: OrderRequest, db: AsyncSession = Depends(get_db)):
    ...
```
Then in `main.py`:
```python
from app.routers import health, stream, orders
app.include_router(orders.router, prefix="/api/v1")
```

### Pattern 8: Celery Periodic Task for Position Sync
**What:** `sync_positions_task` registered in `app/tasks/execution.py` using the existing `celery_app`. Beat schedule set to 15 minutes.
**When to use:** Polling heartbeat for position reconciliation.
**Example:**
```python
# Source: backend/app/tasks/signals.py [VERIFIED: existing codebase pattern]
from app.worker import celery_app

@celery_app.task(name="app.tasks.execution.sync_positions_task")
def sync_positions_task() -> int:
    """Reconcile portfolio_positions with Alpaca live state. Returns count of discrepancies."""
    from app.execution.position_sync import reconcile_positions_with_alpaca
    from app.flows._base import sync_session
    with sync_session() as session:
        return reconcile_positions_with_alpaca(session)
```
Beat schedule in `celery_app.conf.update()`:
```python
beat_schedule={
    "sync-positions-every-15min": {
        "task": "app.tasks.execution.sync_positions_task",
        "schedule": 900.0,  # 15 minutes in seconds
    },
}
```

### Anti-Patterns to Avoid
- **f-string SQL:** All SQL uses `sqlalchemy.text()` with bound parameters - established pattern across all migrations and queries [VERIFIED: codebase-wide]
- **Blocking alert delivery:** Fire-and-forget is locked decision; never `await` SendGrid/Slack inside the order submission hot path - use `asyncio.create_task()` or dispatch to Celery
- **Asyncio background task for polling:** Using `asyncio` background task in lifespan for 15-min sync would bypass Celery's retry/visibility infrastructure; use Celery beat instead [ASSUMED - based on existing Celery pattern]
- **Rate limit key without window:** Key `alert_rate:{event_type}` without a time window means the counter never resets; always include `:{epoch_hour}` or use EXPIRE

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Email delivery | Custom SMTP client | sendgrid 6.x SDK | Handles auth headers, retry on transient errors, envelope construction [ASSUMED] |
| Slack notification | Custom webhook client | httpx POST to webhook URL | Slack incoming webhooks are a plain HTTP POST; no SDK needed [CITED: api.slack.com] |
| Rate limiting logic | Custom in-memory counter | Redis INCR + EXPIRE | Redis is already in stack; in-memory counters don't survive restarts and aren't shared across workers [CITED: redis.io] |
| Bracket order legs | Manual separate stop/limit orders | alpaca-py OrderClass.BRACKET | Alpaca handles leg linkage and cancellation atomically; separate orders create orphan risk [VERIFIED: forum.alpaca.markets] |
| Position sync query | Complex SQL diff logic | TradingClient.get_all_positions() + upsert | Alpaca returns authoritative live state; DB is the mirror [VERIFIED: alpaca docs] |

**Key insight:** The hardest problems here (bracket order atomicity, email delivery reliability, rate limiting across workers) all have well-maintained library solutions already compatible with the existing stack.

---

## Alerts Table Schema

The `alerts` table is the primary output consumed by Phase 8 dashboard Alerting view. The schema must support:
- Filtering by `event_type` (9 types)
- Time-range queries for dashboard pagination
- Delivery status (did SendGrid/Slack succeed?) for operational monitoring
- Payload storage for rich event data

### Recommended Schema (migration 0007_alerts.py)
```sql
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL,          -- one of the 9 event types
    payload         JSONB,                  -- event-specific data (symbol, order_id, etc.)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_sendgrid  BOOLEAN NOT NULL DEFAULT FALSE,
    delivered_slack     BOOLEAN NOT NULL DEFAULT FALSE,
    rate_limited    BOOLEAN NOT NULL DEFAULT FALSE,  -- true when suppressed by rate limiter
    ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Phase 8 dashboard: most recent alerts by type
CREATE INDEX IF NOT EXISTS ix_alerts_event_type_created
    ON alerts (event_type, created_at DESC);
-- Phase 8 dashboard: all recent alerts sorted by time
CREATE INDEX IF NOT EXISTS ix_alerts_created_at
    ON alerts (created_at DESC);
```

**event_type CHECK constraint** (9 values from FR-7.4):
```sql
CONSTRAINT chk_alert_event_type CHECK (event_type IN (
    'signal_generated', 'order_submitted', 'order_filled',
    'stop_triggered', 'thesis_broken', 'macro_regime_change',
    'backtest_gate_pass', 'backtest_gate_fail', 'rl_diversity_alert'
))
```

**Note:** `rate_limited=TRUE` rows are still persisted (success criterion SC6 says "all alerts are persisted") but have `delivered_sendgrid=FALSE` and `delivered_slack=FALSE`. This satisfies both SC5 (rate limiting enforced) and SC6 (all persisted). [ASSUMED - based on SC5 and SC6 wording interpretation]

---

## Common Pitfalls

### Pitfall 1: Startup Gate Check Timing
**What goes wrong:** `check_phase7_gate()` is called before the DB is fully connected at startup, causing it to falsely return False.
**Why it happens:** FastAPI lifespan runs immediately; DB pool may not have connections established.
**How to avoid:** Call `check_phase7_gate()` inside the lifespan `async with` block after the engine is initialized, not at module import time. Use the existing async session pattern.
**Warning signs:** Gate check fails in tests even with valid `backtest_runs` row.

### Pitfall 2: Bracket Order Partial Fill Race Condition
**What goes wrong:** Alpaca returns a partially-filled order; the position is written to DB with original qty; subsequent sync sees a qty mismatch and logs a spurious discrepancy.
**Why it happens:** The locked decision is "accept partial fill, update DB position size to the filled quantity" - this requires reading `filled_qty` from the order object, not `qty`.
**How to avoid:** On order response, write `order.filled_qty` (not `order.qty`) to the `portfolio_positions` row; handle partial fill in the order fill webhook/polling.
**Warning signs:** Position qty in DB doesn't match Alpaca.

### Pitfall 3: Rate Limiter Window Boundary Burst
**What goes wrong:** Fixed window allows a burst: 3 alerts at 59:59 of hour N and 3 more at 00:01 of hour N+1 (6 deliveries in 2 seconds).
**Why it happens:** Fixed window resets at the top of each hour; the boundary burst is inherent.
**How to avoid:** For Phase 7's use case (max 3/hr per event type), the fixed window is acceptable per the locked decision. The success criterion SC5 tests 10 events in 5 minutes - not a boundary burst - so fixed window passes SC5. Document the boundary behavior in comments.
**Warning signs:** More than 3 deliveries during boundary testing.

### Pitfall 4: Orphan Detection False Positives
**What goes wrong:** An exit order that was just submitted (pending fill) is detected as orphaned before the DB position has been written.
**Why it happens:** Timing: Alpaca accepts the exit order, it appears as OPEN in `get_orders()`, but the corresponding position write to DB hasn't committed yet.
**How to avoid:** Run orphan detection only for orders older than a configurable grace period (e.g., 60 seconds). Filter: `order.submitted_at < now - timedelta(seconds=60)`.
**Warning signs:** Orphan detector cancels valid exit orders immediately after submission.

### Pitfall 5: TradingClient.submit_order Sync vs. Async
**What goes wrong:** `TradingClient` from alpaca-py is synchronous; calling it directly inside a FastAPI async endpoint blocks the event loop.
**Why it happens:** alpaca-py's TradingClient does not have an async variant in 0.43.4.
**How to avoid:** Use `asyncio.to_thread(client.submit_order, request)` or dispatch to a Celery task. The existing pattern in `app/flows/prices.py` wraps sync Alpaca calls in sync context (Prefect task); for the FastAPI router, use `asyncio.to_thread`.
**Warning signs:** Uvicorn worker hangs during order submission under load.

### Pitfall 6: Redis Key Without Expiry on Rate Limiter
**What goes wrong:** If the `r.expire(key, 3600)` call is missed (e.g., only called when `count == 1` and that path is skipped), the key persists forever and blocks all future alerts of that type.
**Why it happens:** Race condition between INCR and EXPIRE in a non-atomic implementation.
**How to avoid:** Use Lua script to make INCR+EXPIRE atomic, or use the `count == 1` pattern consistently. Alternatively, use `r.set(key, 0, ex=3600, nx=True)` then `r.incr(key)` pattern.
**Warning signs:** Alerts of a type stop delivering permanently after a high-burst period.

---

## Code Examples

### Wiring the Existing Gate Stub to Real Delivery

The stub in `backend/app/backtest/alerts.py` defines `fire_gate_alert_v2()` that returns a dict but does not deliver. Phase 7 must wire it:

```python
# Source: backend/app/backtest/alerts.py [VERIFIED: existing codebase]
# fire_gate_alert_v2() already returns:
# {"event_type": "backtest_gate_pass"|"backtest_gate_fail", "run_id": str|None, "reason": str}
# Phase 7 calls dispatch_alert(event["event_type"], event) from the alerting module
from app.backtest.alerts import fire_gate_alert_v2
from app.alerting.dispatcher import dispatch_alert

event = fire_gate_alert_v2(gate_status, gate_reason, run_id)
await dispatch_alert(event["event_type"], payload=event)
```

### Config Additions Required

```python
# Source: backend/app/config.py [VERIFIED: existing codebase]
# Add to Settings class:
SENDGRID_API_KEY: str = ""
SENDGRID_FROM_EMAIL: str = "alerts@pead-system.com"
SENDGRID_TO_EMAIL: str = ""
SLACK_WEBHOOK_URL: str = ""
ENABLE_SHORT_SIDE: bool = False
STOP_LOSS_PCT: float = 0.02    # 2% below entry
TAKE_PROFIT_PCT: float = 0.04  # 4% above entry
```

### Celery Beat Schedule Integration

```python
# Source: backend/app/worker.py [VERIFIED: existing codebase pattern]
# Add to celery_app.conf.update():
beat_schedule={
    "sync-positions-every-15min": {
        "task": "app.tasks.execution.sync_positions_task",
        "schedule": 900.0,
    },
},
task_routes={
    ...,
    "app.tasks.execution.*": {"queue": "portfolio"},
},
```

### main.py Router Registration

```python
# Source: backend/app/main.py [VERIFIED: existing codebase]
# Add to imports and include_router calls:
from app.routers import health, stream, orders, alerts_router

app.include_router(orders.router, prefix="/api/v1")
app.include_router(alerts_router.router, prefix="/api/v1")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| alpaca-trade-api (v1) | alpaca-py (v2+) | 2022 | Different import paths: `alpaca.trading.client`, not `alpaca_trade_api` |
| sendgrid v5 | sendgrid v6 (BREAKING) | ~2021 | v6 renamed `SendGridAPIClient`; v5 and v6 share same pip package name |
| Slack SDK `WebhookClient` | Plain httpx POST | - | For simple notifications, no SDK needed; webhook URL accepts raw JSON POST |

**Deprecated/outdated:**
- `alpaca-trade-api` (pip): This is the old v1 SDK. The project uses `alpaca-py` (the new SDK). Import from `alpaca.trading.*` not `alpaca_trade_api` [VERIFIED: prices.py uses `alpaca.data.*`]
- `sendgrid v5`: The project should install `sendgrid==6.12.5` - v5's `sgmail` helper API is different [CITED: PyPI]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Celery beat is the cleaner choice for 15-min polling over asyncio lifespan background task | Architecture Patterns (Pattern 8) | If Celery beat is not running in Railway config, the polling task never fires - planner must ensure beat worker is started |
| A2 | `asyncio.to_thread()` is the right way to call sync TradingClient in async FastAPI handlers | Common Pitfalls (Pitfall 5) | If alpaca-py adds async support in a future version, to_thread is still safe but redundant |
| A3 | `rate_limited=TRUE` rows still persisted satisfies SC6 requirement | Alerts Table Schema | If user expects `delivered` = True for rate-limited events, schema needs a `was_rate_limited` column instead |
| A4 | Fixed-window rate limiter (not sliding window) passes SC5 burst test (10 events in 5 min = exactly 3) | Common Pitfalls (Pitfall 3) | A burst mid-hour would be capped at 3; SC5 is testing within a single window, so fixed window passes |

---

## Open Questions

1. **Celery Beat Worker Configuration**
   - What we know: Celery worker is configured in `docker-compose.yml` and Railway
   - What's unclear: Whether the Railway deployment runs `celery beat` alongside the worker
   - Recommendation: Planner should verify the docker-compose Celery service command includes `--beat` or adds a separate beat service

2. **ALPACA_FROM_EMAIL Domain Verification**
   - What we know: SendGrid requires the from-address domain to be verified in SendGrid account
   - What's unclear: Whether the project has a verified domain configured
   - Recommendation: Planner should flag this as a manual setup step before Phase 7 tests run (domain verification in SendGrid dashboard)

3. **Position Write Strategy on Reconciliation**
   - What we know: `portfolio_positions` is a TimescaleDB hypertable - it appends snapshots (immutable history via `snapshot_at` primary key)
   - What's unclear: Whether reconciliation should INSERT a new snapshot or UPDATE the latest row
   - Recommendation: INSERT a new snapshot (consistent with hypertable append semantics); "latest position" is always the most recent `snapshot_at` for a symbol. Orphan check and sync both read `MAX(snapshot_at)` per symbol.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | All services | Yes | 29.4.1 | None needed |
| alpaca-py | Execution layer | Yes (installed) | 0.43.4 | None - required |
| sendgrid Python pkg | Alert delivery | No (not installed) | - | Install `sendgrid==6.12.5` |
| Redis | Rate limiting, pub/sub | Via Docker Compose only | 7.x (in compose) | None - required service |
| PostgreSQL | alerts table | Via Docker Compose only | 15.x (in compose) | None - required service |
| httpx | Slack webhook | Yes (installed) | 0.28.1 | None needed |

**Missing dependencies with no fallback:**
- `sendgrid==6.12.5` must be added to `backend/requirements.txt` before Wave 1 execution

**Missing dependencies with fallback:**
- Redis and PostgreSQL are only accessible when `docker compose up` is running locally or via Railway in production; integration tests require `DATABASE_URL_SYNC` set (consistent with existing `@requires_db` pattern)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none - run via `cd backend && pytest tests/ -v --tb=short` |
| Quick run command | `cd backend && pytest tests/ -v --tb=short -k "not integration"` |
| Full suite command | `DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-7.1 | Bracket order submitted with correct limit/stop/take-profit prices | unit (mock TradingClient) | `pytest tests/execution/test_broker.py -x` | No - Wave 0 |
| FR-7.2 | Reconciliation writes new portfolio_positions snapshot on discrepancy | unit (mock TradingClient + mock DB) | `pytest tests/execution/test_position_sync.py -x` | No - Wave 0 |
| FR-7.3 | Orphan order detected and cancel_order_by_id called | unit (mock TradingClient + mock session) | `pytest tests/execution/test_orphan_detector.py -x` | No - Wave 0 |
| FR-7.4 | SendGrid send() called for each of 9 event types | unit (mock SendGridAPIClient) | `pytest tests/alerting/test_dispatcher.py -x` | No - Wave 0 |
| FR-7.5 | Burst of 10 events results in exactly 3 deliveries | unit (mock Redis) | `pytest tests/alerting/test_rate_limiter.py -x` | No - Wave 0 |
| FR-7.6 | Short order not placed when ENABLE_SHORT_SIDE=False | unit | `pytest tests/execution/test_broker.py::test_short_blocked_by_flag -x` | No - Wave 0 |
| FR-8.1 | alerts table exists with correct schema after migration | integration (DB-gated) | `DATABASE_URL_SYNC=... pytest tests/test_alerts_schema.py -x` | No - Wave 0 |
| FR-8.3/8.4 | Alert published to Redis alerts channel after dispatch | unit (mock Redis) | `pytest tests/alerting/test_dispatcher.py::test_redis_publish -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/ -v --tb=short -k "not integration"`
- **Per wave merge:** `DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/execution/__init__.py` - execution test package
- [ ] `tests/execution/test_broker.py` - covers FR-7.1, FR-7.6
- [ ] `tests/execution/test_position_sync.py` - covers FR-7.2
- [ ] `tests/execution/test_orphan_detector.py` - covers FR-7.3
- [ ] `tests/alerting/__init__.py` - alerting test package
- [ ] `tests/alerting/test_dispatcher.py` - covers FR-7.4, FR-8.3, FR-8.4
- [ ] `tests/alerting/test_rate_limiter.py` - covers FR-7.5
- [ ] `tests/test_alerts_schema.py` - covers FR-8.1 (DB-gated)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No - internal services communicate within Docker network | N/A |
| V3 Session Management | No | N/A |
| V4 Access Control | Partial - ENABLE_SHORT_SIDE feature flag gates short order placement | Feature flag in Settings; gate checked before order submission |
| V5 Input Validation | Yes - order payload from signal engine must be validated | pydantic model for OrderRequest in FastAPI router |
| V6 Cryptography | No - ALPACA_API_KEY and SENDGRID_API_KEY transmitted over TLS by SDK | SDK handles transport security |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leakage in logs | Information Disclosure | Never log ALPACA_API_KEY or SENDGRID_API_KEY; Settings already has `extra="ignore"` to prevent accidental exposure |
| Order injection via signal engine | Tampering | Validate OrderRequest with pydantic; reject orders with qty < 0 or missing symbol |
| Redis rate limiter key collision | Tampering | Key format `alert_rate:{event_type}:{window}` is scoped by event_type; no cross-type collision possible |
| SLACK_WEBHOOK_URL logged accidentally | Information Disclosure | Treat SLACK_WEBHOOK_URL as a secret; exclude from health check responses |

---

## Sources

### Primary (HIGH confidence)
- alpaca-py 0.43.4 installed (`pip show alpaca-py`) - confirmed version in project venv
- `backend/requirements.txt` - all pinned versions verified by direct file read
- `backend/app/backtest/alerts.py` - existing stub interface verified by direct file read
- `backend/app/config.py` - existing Settings class verified by direct file read
- `backend/app/models/portfolio_positions.py` - existing ORM model verified by direct file read
- `backend/app/worker.py` - Celery configuration and task routing verified by direct file read
- `backend/app/routers/stream.py` - Redis pub/sub "alerts" channel already subscribed verified by direct file read
- `backend/alembic/versions/` - migration chain 0001-0006 verified, next is 0007

### Secondary (MEDIUM confidence)
- [alpaca-py bracket order forum example](https://forum.alpaca.markets/t/bracket-order-code-example-with-alpaca-py-library/12110) - verified against official SDK docs
- [alpaca-py trading requests docs](https://alpaca.markets/sdks/python/api_reference/trading/requests.html) - official SDK reference
- [alpaca-py trading client docs](https://alpaca.markets/sdks/python/trading.html) - get_all_positions, get_orders, cancel_order_by_id confirmed
- [SendGrid Python quickstart](https://www.twilio.com/docs/sendgrid/for-developers/sending-email/quickstart-python) - SendGridAPIClient + Mail pattern confirmed
- [PyPI sendgrid](https://pypi.org/project/sendgrid/) - version 6.12.5 confirmed

### Tertiary (LOW confidence)
- [Redis rate limiting tutorial](https://redis.io/tutorials/howtos/ratelimiting/) - INCR+EXPIRE fixed window pattern; cross-referenced with multiple sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all versions verified against installed packages and PyPI
- Architecture: HIGH - based on verified existing codebase patterns
- Pitfalls: MEDIUM - most from direct codebase analysis; Pitfall 5 (sync TradingClient) from alpaca-py docs analysis
- Alerts table schema: MEDIUM - design is Claude's discretion (per CONTEXT.md); schema choices are well-reasoned but not user-confirmed

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (30 days - stable libraries)
