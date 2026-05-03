---
plan: 01-02
phase: 01-infrastructure-data-foundation
status: complete
completed: 2026-05-03
commits:
  - f7d3327f feat(01-02): initialize Alembic with TimescaleDB-aware env and 6 ORM models
  - 84fcfa60 test(01-02): add failing tests for hypertables and as_of filtering
  - 594e5db1 feat(01-02): create initial schema with 6 hypertables and as_of filter
---

# Plan 01-02 Summary — Alembic + TimescaleDB Hypertables + TDD Tests

## What was built

**Task 1 — Alembic + ORM Models:**
- `backend/alembic.ini` — script_location + DATABASE_URL override via env
- `backend/alembic/env.py` — async migration runner, `include_object` filter excluding `_timescaledb_*` and `_hyper_*` tables, `compare_type=True`
- `backend/alembic/script.py.mako` — standard Alembic template
- 6 SQLAlchemy 2.0 ORM models (Mapped[...] / mapped_column()) — all with `ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()`:
  - `PriceBar` (price_bars) — time+symbol PK, OHLCV+vwap+volume
  - `EarningsEvent` (earnings_events) — BIGSERIAL PK, UNIQUE(symbol, fiscal_quarter), guidance_direction CHECK
  - `Signal` (signals) — created_at+UUID PK, direction CHECK, status default 'pending'
  - `RlTransition` (rl_transitions) — ts+episode_id+step PK, agent_id, JSONB state vectors, priority
  - `MacroIndicator` (macro_indicators) — date+series_id PK, vintage_date (ALFRED point-in-time)
  - `PortfolioPosition` (portfolio_positions) — snapshot_at+symbol PK, position fields, status

**Task 2 — Migration + Tests (TDD):**
- `backend/alembic/versions/0001_initial_schema.py` — CREATE EXTENSION timescaledb + 6 CREATE TABLE IF NOT EXISTS + 6 create_hypertable() calls + 12 indexes. Idempotent via `if_not_exists => TRUE`.
- `backend/app/queries/point_in_time.py` — `get_prices_as_of()` enforces `ingestion_timestamp <= as_of` (FR-1.5)
- `backend/pytest.ini` — asyncio_mode=auto, testpaths=tests
- `backend/tests/conftest.py` — session-scoped event_loop + db_engine, per-test db with rollback, httpx AsyncClient
- `backend/tests/test_health.py` — GET /health → 200, status=ok, db=connected
- `backend/tests/test_schema.py` — hypertable existence, ingestion_timestamp column presence + NOT NULL, insert round-trips, migration idempotency
- `backend/tests/test_as_of.py` — future-ingested row excluded (FR-1.5 proof), past-ingested row included

## Requirements satisfied

- **FR-1.2** — 6 TimescaleDB hypertables exist and accept writes after `alembic upgrade head`
- **FR-1.5** — Every table has `ingestion_timestamp NOT NULL DEFAULT NOW()`; `get_prices_as_of` filters `ingestion_timestamp <= as_of`; `test_future_ingested_row_excluded` enforces the filter

## Key decisions

- Hypertables created via `op.execute()` raw SQL only (CLAUDE.md directive) — Alembic autogenerate cannot handle TimescaleDB DDL
- `include_object` filter prevents autogenerate from seeing `_timescaledb_*` catalog tables and `_hyper_*` chunks as diffs
- `if_not_exists => TRUE` on both CREATE TABLE and create_hypertable makes the migration fully idempotent (run `upgrade head` twice = safe)
- `.gitignore` updated: `/models/` (root-only) instead of `models/` (any depth) to un-block `backend/app/models/`
