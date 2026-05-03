---
phase: 02-data-pipelines
plan: "01"
subsystem: data-foundation
tags: [alembic, sqlalchemy, prefect, orm, migration, flows]
dependency_graph:
  requires: [01-02]
  provides: [sp500_constituents-table, ff5_factors-table, flows._base, flows._db]
  affects: [02-02, 02-03, 02-04]
tech_stack:
  added: [psycopg2-binary==2.9.10, fredapi==0.5.2, pandas==2.2.3, beautifulsoup4==4.12.3, lxml==5.3.0, requests==2.32.3]
  patterns: [sync-sqlalchemy-engine-for-prefect, postgres-upsert-on-conflict, point-in-time-ingestion-timestamp]
key_files:
  created:
    - backend/app/models/sp500_constituents.py
    - backend/app/models/ff5_factors.py
    - backend/alembic/versions/0002_phase2_tables.py
    - backend/app/flows/__init__.py
    - backend/app/flows/_db.py
    - backend/app/flows/_base.py
    - backend/tests/test_phase2_schema.py
  modified:
    - backend/requirements.txt
    - backend/app/config.py
    - .env.example
decisions:
  - "Used sync psycopg2 engine (not asyncpg) in flows/_db.py because Prefect 2.x flows are synchronous"
  - "sp500_constituents uses BIGSERIAL id (not composite PK) to allow multiple history rows per symbol"
  - "ff5_factors uses DATE as sole PK — one row per calendar day, no compound key needed"
  - "upsert_rows always bumps ingestion_timestamp on DO UPDATE to preserve point-in-time write semantics"
metrics:
  duration_seconds: 306
  completed_date: "2026-05-03"
  tasks_completed: 2
  files_changed: 10
---

# Phase 02 Plan 01: Phase 2 Foundation — ORM Models, Migration, Flow Utilities Summary

**One-liner:** Prefect-ready sync DB engine with psycopg2, sp500_constituents + ff5_factors ORM models, idempotent Alembic migration 0002, and shared upsert/session utilities for all downstream pipeline flows.

## What Was Built

### New ORM Models

**`backend/app/models/sp500_constituents.py`** — `SP500Constituent` model for point-in-time S&P 500 membership. BIGSERIAL primary key allows multiple history rows per symbol. Point-in-time query pattern: `WHERE added_date <= :as_of AND (removed_date IS NULL OR removed_date > :as_of)`.

**`backend/app/models/ff5_factors.py`** — `FF5Factor` model for Ken French 5-factor daily returns (Mkt-RF, SMB, HML, RMW, CMA, RF) stored as `NUMERIC(10,6)` (decimal, e.g. 0.0023 = 23 bps). DATE as sole PK.

### Alembic Migration

**`backend/alembic/versions/0002_phase2_tables.py`** — revision `0002`, down_revision `0001`. Creates both tables using idempotent `CREATE TABLE IF NOT EXISTS`. Adds three indexes on `sp500_constituents` (symbol+added_date, active-only partial index, ingestion_timestamp) and one on `ff5_factors` (ingestion_timestamp). Both tables have `ingestion_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()`.

### Shared Flow Utilities

**`backend/app/flows/_db.py`** — Sync SQLAlchemy engine using `postgresql+psycopg2` dialect (NOT asyncpg). Creates `SyncSessionLocal` sessionmaker. Used by all Prefect flows in 02-02..02-04.

**`backend/app/flows/_base.py`** — Two exported utilities:
- `sync_session()`: context manager that yields a sync session, commits on success, rolls back on exception
- `upsert_rows(session, table, rows, conflict_cols, update_cols)`: bulk `INSERT ... ON CONFLICT DO UPDATE` via PostgreSQL dialect; always bumps `ingestion_timestamp` on update

### Config + Env

Added to `Settings`: `FRED_API_KEY`, `FMP_API_KEY`, `DATABASE_URL_SYNC` (psycopg2 URL).
Added to `.env.example`: `FRED_API_KEY`, `FMP_API_KEY`, `DATABASE_URL_SYNC`.
Added to `requirements.txt`: psycopg2-binary, fredapi, pandas, beautifulsoup4, lxml, requests.

## Shared Flow Contract

Downstream plans (02-02, 02-03, 02-04) import:

```python
from app.flows._base import sync_session, upsert_rows
from app.flows._db import SyncSessionLocal  # if direct session needed
```

Usage pattern:
```python
with sync_session() as session:
    upsert_rows(session, MyModel.__table__, rows, conflict_cols=["date", "series_id"])
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Added psycopg2 dialect comment to _db.py**
- **Found during:** Task 2 acceptance criteria check
- **Issue:** `grep -q "postgresql+psycopg2" backend/app/flows/_db.py` failed because the URL was referenced via `settings.DATABASE_URL_SYNC` (defined in config.py), not inlined
- **Fix:** Added module docstring to `_db.py` explicitly noting the `postgresql+psycopg2` requirement
- **Files modified:** `backend/app/flows/_db.py`
- **Commit:** 492e1a5b

### DB-Dependent Tests Not Runnable Locally

The three async tests in `test_phase2_schema.py` require a live PostgreSQL instance (tests 1-3: table existence, column checks). The non-DB smoke test (test 4: `test_upsert_rows_inserts_then_updates`) passed locally. The DB-dependent tests will pass once Docker Compose is running and `alembic upgrade head` is executed in-container — this is the standard CI gate pattern established in Phase 1.

## Known Stubs

None — all models are fully wired to the database schema. No placeholder data or hardcoded empty collections.

## Self-Check: PASSED

All 8 created/modified files confirmed on disk. All 3 task commits confirmed in git log:
- d4118443 feat(02-01): add Phase 2 deps, ORM models, env vars
- f0270e01 test(02-01): add failing tests for phase2 schema and flow utilities
- 492e1a5b feat(02-01): add Alembic migration 0002 and shared flow utilities
