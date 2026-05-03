---
phase: 02-data-pipelines
plan: "02"
subsystem: price-ingestion
tags: [prefect, alpaca, ohlcv, price_bars, hypertable, upsert, cron]
dependency_graph:
  requires: [02-01]
  provides: [flows.prices.ingest_prices_daily, flows._universe.current_sp500_universe]
  affects: [02-05, phase-3-signals, phase-6-backtest]
tech_stack:
  added: []
  patterns: [prefect-flow-inner-function-testability, alpaca-py-batch-200, postgres-upsert-on-conflict, sp500-fallback-universe]
key_files:
  created:
    - backend/app/flows/_universe.py
    - backend/app/flows/prices.py
    - backend/tests/test_flow_prices.py
  modified: []
decisions:
  - "Extracted _run_ingestion() as a plain function wrapping the @flow decorator to allow unit tests to bypass Prefect runtime server requirement"
  - "Used test_client (not _client) as injection parameter name — Prefect 3.x rejects leading-underscore parameter names in @flow signatures"
  - "FALLBACK_SP500 list (~100 tickers) used when sp500_constituents table is empty (Wave 2 race with plan 02-04)"
  - "current_sp500_universe() catches all DB exceptions and falls back gracefully — ensures prices flow can run even before 02-04 populates constituents"
  - "Batching at BATCH_SIZE=200 matches alpaca-py per-request limit"
metrics:
  duration_seconds: 900
  completed_date: "2026-05-03"
  tasks_completed: 2
  files_changed: 3
---

# Phase 02 Plan 02: Price Bar Ingestion Flow Summary

**One-liner:** Prefect flow `ingest_prices_daily` batches S&P 500 tickers in groups of 200, fetches daily OHLCV from alpaca-py, upserts into `price_bars` with conflict resolution on (time, symbol), and registers a weekday 22:00 UTC cron via `deploy()`.

## What Was Built

### `backend/app/flows/_universe.py`

`current_sp500_universe() -> list[str]` — queries `sp500_constituents` for active tickers (removed_date IS NULL). Falls back to `FALLBACK_SP500` (~100 tickers) when the table is empty or the DB is unreachable. This fallback is intentional: plan 02-04 populates the constituents table; until then, the prices flow can still run using the hard-coded fallback.

### `backend/app/flows/prices.py`

Key components:

- **`_build_client()`** — lazy-imports `StockHistoricalDataClient` from alpaca-py using `settings.ALPACA_API_KEY` / `settings.ALPACA_SECRET_KEY`
- **`_fetch_batch(client, symbols, start, end)`** — issues a `StockBarsRequest(timeframe=TimeFrame.Day)` for up to 200 symbols
- **`_process_batch(symbols, start, end, client) -> int`** — core batch logic: fetches bars, builds row dicts, calls `upsert_rows(..., conflict_cols=["time", "symbol"], update_cols=[open,high,low,close,vwap,volume])`, logs warnings for empty symbol responses
- **`_run_ingestion(lookback_days, test_client) -> int`** — orchestrates batching loop over the S&P 500 universe, accumulates total row count
- **`ingest_prices_daily`** — `@flow(name="ingest_prices_daily", retries=2, retry_delay_seconds=60)` wrapper around `_run_ingestion`; thin wrapper enables Prefect scheduling/retry without coupling test code to Prefect server
- **`deploy()`** — calls `ingest_prices_daily.serve(name="ingest-prices-daily", schedule=CronSchedule(cron="0 22 * * 1-5", timezone="UTC"), tags=["phase-2", "prices"])`. Cron fires every weekday at 22:00 UTC (~30 min after US equity close at 16:00 ET / 21:00 UTC in DST)
- **`__main__` entrypoint** — `python -m app.flows.prices` runs ingestion; `python -m app.flows.prices deploy` registers the schedule

### `backend/tests/test_flow_prices.py`

5 unit tests, fully offline (no Prefect server, no DB, no Alpaca API key):

| Test | What it verifies |
|------|-----------------|
| `test_universe_fallback_when_table_empty` | Returns FALLBACK_SP500 when DB returns empty rows |
| `test_ingest_prices_writes_to_db` | `_run_ingestion` calls `upsert_rows` with correct row count |
| `test_ingest_prices_idempotent` | Running twice does not error |
| `test_empty_response_does_not_raise` | Empty Alpaca response → 0 rows, no exception |
| `test_flow_importable_and_callable` | `ingest_prices_daily` and `deploy` are callable |

## Integration Notes for Plan 02-05

Plan 02-05 (integration tests) should verify:

1. With a running DB and valid Alpaca paper key, `_run_ingestion(lookback_days=5)` inserts rows into `price_bars` with correct schema
2. `SELECT count(*) FROM price_bars WHERE symbol = 'AAPL'` returns > 0
3. Re-running the flow for the same date window does not duplicate rows (ON CONFLICT DO UPDATE)
4. `current_sp500_universe()` returns DB-backed tickers once 02-04 has populated `sp500_constituents`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Renamed `_client` parameter to `test_client` in flow signature**
- **Found during:** Task 1 GREEN phase — first pytest run
- **Issue:** Prefect 3.x raises `NameError: Fields must not use names with leading underscores` when a `@flow`-decorated function has a parameter starting with `_`
- **Fix:** Renamed `_client` → `test_client` in both `prices.py` and `test_flow_prices.py`
- **Files modified:** `backend/app/flows/prices.py`, `backend/tests/test_flow_prices.py`
- **Commit:** 2368e10b

**2. [Rule 1 - Bug] Extracted `_run_ingestion()` to bypass Prefect ephemeral server**
- **Found during:** Task 1 GREEN phase — second pytest run
- **Issue:** Prefect 3.x tries to start an ephemeral Prefect API server when any `@flow` is called without `PREFECT_API_URL` pointing at a running server. This fails in CI (no Prefect server) with `RuntimeError: Timed out while attempting to connect to ephemeral Prefect API server`
- **Fix:** Extracted all flow logic into `_run_ingestion()` (plain function). The `@flow` decorator wraps it as a thin pass-through. Tests call `_run_ingestion()` directly. Production `ingest_prices_daily()` call goes through Prefect normally.
- **Files modified:** `backend/app/flows/prices.py`, `backend/tests/test_flow_prices.py`
- **Commit:** 2368e10b

## Known Stubs

None — `current_sp500_universe()` is wired to the real DB with a graceful fallback. `ingest_prices_daily` is wired to the real Alpaca client in production.

## Threat Flags

None — no new network endpoints or auth paths introduced. Alpaca API key usage is read-only (market data), already tracked in `settings.ALPACA_API_KEY`.

## Self-Check: PASSED
