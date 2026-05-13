# Phase 7: Alpaca Execution + Alerting - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 delivers paper trading execution and system-wide alerting. Signal-triggered orders submit bracket orders (limit entry + stop-loss + take-profit) via alpaca-py to the Alpaca paper account. Positions stay reconciled with Alpaca state on startup and every 15 minutes. Orphaned exit orders are detected and cancelled. All 9 system event types fire alerts via SendGrid email and Slack webhook with Redis-backed rate limiting (max 3 per event type per hour). Alerts persist to a new `alerts` table and are visible in the Phase 8 dashboard Alerting view. The short-side feature flag defaults to false. Phase 7 cannot start unless `backtest_gate_pass` exists in `backtest_runs`.

</domain>

<decisions>
## Implementation Decisions

### Bracket Order Parameters
- Stop-loss leg: 2% below entry, configurable via `STOP_LOSS_PCT=0.02` in config
- Take-profit ceiling: 4% above entry (`TAKE_PROFIT_PCT=0.04`), 2:1 R/R ratio
- Entry order type: limit order at ask + 0.5 tick to reduce slippage vs market orders
- Partial fill handling: accept partial fill, update DB position size to the filled quantity

### Alerting Implementation
- Rate limit storage: Redis (already in stack) — key `alert_rate:{event_type}`, TTL-based counting, max 3 per hour
- Alert persistence: new `alerts` table (clean separation from RL alerts in `rl_diversity_alerts`)
- Delivery mode: fire-and-forget async (log on failure, do not block trade execution)
- SendGrid format: minimal HTML (`<p>` tags, no CSS framework) — per CLAUDE.md global rule

### Service Architecture
- Order placement trigger: FastAPI `POST /api/v1/orders` endpoint called by signal engine (follows existing router pattern in `backend/app/routers/`)
- Startup gate check: hard block — raise `RuntimeError` if no `backtest_gate_pass` row found in `backtest_runs`; Phase 7 service cannot start in degraded mode
- Position sync cadence: startup reconciliation + 15-minute polling via existing task infrastructure

### Claude's Discretion
- Alert table schema column names and indexing strategy
- Exact Alpaca API error handling (retry count and backoff timing within the "immediate retry 3x" envelope)
- Orphan detection query implementation details
- Celery task vs asyncio for the 15-minute polling heartbeat (whichever is cleaner given existing infrastructure)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/routers/health.py`, `stream.py` — existing FastAPI router patterns to follow
- `backend/app/config.py` — `Settings` class with `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER=True` already present
- `backend/app/database.py` — sync and async session patterns established
- `backend/app/backtest/alerts.py` — `check_phase7_gate(session)`, `fire_gate_alert_v2()`, event type constants — Phase 7 wires the real delivery to this stub
- `backend/app/models/portfolio_positions.py` — existing positions ORM model
- Redis: `REDIS_URL`, `REDIS_BACKEND_URL`, `REDIS_PUB_URL` all configured in Settings; redis-py likely available

### Established Patterns
- All SQL uses `sqlalchemy.text()` with bound parameters (no f-string SQL)
- Alembic migrations named `00XX_description.py`; next is `0007_alerts.py`
- DB-gated tests skip when `DATABASE_URL_SYNC` absent via `@requires_db` decorator
- Point-in-time semantics: `ingestion_timestamp <= :as_of` on all historical queries (not applicable to live execution)

### Integration Points
- Signal engine triggers order placement via the new `POST /api/v1/orders` router
- Phase 6 `check_phase7_gate(session)` called at startup; hard block if returns False
- `backtest_runs` table (migration 0005 + 0006) is source of truth for gate status
- Phase 8 dashboard will read from the new `alerts` table Alerting view

</code_context>

<specifics>
## Specific Ideas

- The 9 alert event types are named in FR-7.4 / Phase 6 work: `signal_generated`, `order_submitted`, `order_filled`, `stop_triggered`, `thesis_broken`, `macro_regime_change`, `backtest_gate_pass`, `backtest_gate_fail`, `rl_diversity_alert`
- `ENABLE_SHORT_SIDE` feature flag must exist in config and default to `false`; short orders are never placed when flag is off (success criterion SC7)
- Rate limiting test: a burst of 10 same-type events in 5 minutes must result in exactly 3 deliveries (SC5 wording)
- Phase 7 hard-blocks if gate fails — the check reads `backtest_runs` where `gate_status = 'pass'`; no override flag is available in Phase 7 startup (override is a Phase 6 re-run concern)

</specifics>

<deferred>
## Deferred Ideas

- Alpaca websocket-based live position events (Phase 7 uses polling; websocket is a future enhancement)
- Live trading (ALPACA_PAPER stays True for Phase 7 scope)
- Multi-account support
- Rich HTML email templates with CSS styling (deferred; minimal HTML is sufficient for Phase 7)

</deferred>
