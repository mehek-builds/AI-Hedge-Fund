---
phase: 02-data-pipelines
plan: "05"
subsystem: integration-test-and-deployment
tags: [prefect, integration-test, deploy, hyg-lqd-spread, derived-macro, phase2-gate]
dependency_graph:
  requires: [02-02, 02-03, 02-04]
  provides: [compute_hyg_lqd_daily-flow, test_phase2_integration, deploy_all_flows]
  affects: [phase-3-signals, phase-4-macro, phase-6-backtest]
tech_stack:
  added: []
  patterns: [prefect-flow-inner-function-testability, multiprocessing-serve-launcher, derived-indicator-from-price-bars]
key_files:
  created:
    - backend/app/flows/derived_macro.py
    - backend/tests/test_phase2_integration.py
    - backend/scripts/deploy_all_flows.py
    - backend/scripts/__init__.py
  modified:
    - backend/app/flows/constituents.py
    - backend/app/flows/macro.py
    - backend/app/flows/ff5.py
    - backend/app/flows/earnings.py
decisions:
  - "Extracted _run_X() inner plain-function helpers from all flows that lacked them (constituents, macro, ff5, earnings, derived_macro) to match the prices._run_ingestion() pattern — Prefect 3.x ephemeral server is triggered by any @flow or @task call without PREFECT_API_URL set"
  - "deploy_all_flows.py uses multiprocessing (not threading) because flow.serve() is blocking and cannot be sequential"
  - "Integration tests call _run_X() inner helpers directly, not @flow wrappers — DB-gated (CI only)"
  - "HYG_LQD_SPREAD computed from price_bars not FRED — LQD_close / HYG_close is the credit-spread proxy"
metrics:
  duration_seconds: 467
  completed_date: "2026-05-03"
  tasks_completed: 2
  files_changed: 8
---

# Phase 02 Plan 05: Phase 2 Integration Test + Deployment Registration Summary

**One-liner:** Integration test drives all 6 Phase 2 flows end-to-end with mocked sources asserting per-table row counts; deploy_all_flows.py registers all 6 cron-scheduled Prefect deployments via multiprocessing; HYG/LQD credit-spread computed as 6th derived flow.

## What Was Built

### `backend/app/flows/derived_macro.py`

`compute_hyg_lqd_daily` — Prefect flow (daily 22:30 UTC Mon-Fri) that:
1. Queries `price_bars` for HYG and LQD close prices within `lookback_days`
2. Computes `HYG_LQD_SPREAD = LQD_close / HYG_close` for each overlapping date
3. Upserts rows into `macro_indicators` with `series_id = "HYG_LQD_SPREAD"`
4. Returns 0 (no error) when no overlapping HYG/LQD bars exist

This is the 6th scheduled flow — the credit-spread proxy used by the Phase 4 macro composite scorer.

### `backend/tests/test_phase2_integration.py`

Three integration tests requiring live PostgreSQL + Phase 2 schema:

| Test | What it verifies |
|------|-----------------|
| `test_all_six_flows_write_to_their_tables` | All 6 flows run in order; each table has >= 1 row |
| `test_sequence_is_idempotent` | Running the full sequence twice does not error |
| `test_derived_handles_missing_prices_gracefully` | `_run_derived_macro(lookback_days=0)` returns 0, no exception |

All three are CI-gated (need `docker compose up` + `alembic upgrade head`). They call `_run_X()` inner helpers directly to bypass Prefect's ephemeral server requirement.

### `backend/scripts/deploy_all_flows.py`

One-shot deployment registration script. The 6 flows registered:

| Flow name | Cron | Source |
|-----------|------|--------|
| ingest-prices-daily | `0 22 * * 1-5` | Alpaca |
| ingest-macro-daily | `0 13 * * 1-5` | FRED |
| ingest-ff5-weekly | `0 6 * * 6` | Ken French |
| ingest-earnings-daily | `30 23 * * 1-5` | FMP |
| sync-sp500-constituents-weekly | `0 12 * * 0` | Wikipedia |
| compute-hyg-lqd-daily | `30 22 * * 1-5` | Derived (price_bars) |

`--once` flag smoke-tests all deploy() callables without starting blocking workers. Verified: `python -m scripts.deploy_all_flows --once` exits 0 and prints all 6 names.

### Inner `_run_X` helpers added to existing flow modules

To fix the Prefect ephemeral server issue for integration tests (same bug fixed in 02-02 for prices):

- `constituents.py` → `_run_constituents(fetcher)`
- `macro.py` → `_run_macro(lookback_days, fred_client)` (inlines FRED fetch loop, bypasses `@task fetch_one_series`)
- `ff5.py` → `_run_ff5(downloader)`
- `earnings.py` → `_run_earnings(quarters, http_override)`
- `derived_macro.py` → `_run_derived_macro(lookback_days)` (primary logic in inner function, `@flow` wraps it)

## Task 3: Human Verification (Checkpoint — Not Yet Executed)

Task 3 is a `checkpoint:human-verify` gate. To verify:

1. Ensure `.env` has `FRED_API_KEY`, `FMP_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`.
2. `docker compose up -d`
3. Wait ~20s for `prefect_server` healthy.
4. `docker compose exec fastapi alembic upgrade head`
5. `docker compose exec fastapi python -m scripts.deploy_all_flows` (leave running)
6. Open Prefect dashboard at http://localhost:4200 → Deployments view.
7. Confirm all 6 deployments visible with correct cron schedules.
8. Click "Run" on `sync-sp500-constituents-weekly` → verify completes successfully.
9. `docker compose exec db psql -U pead -d pead_trading -c "SELECT count(*) FROM sp500_constituents"` must be > 400.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Prefect ephemeral server triggered by all @flow/@task calls in tests**
- **Found during:** Task 1 GREEN phase — first test run
- **Issue:** The plan's integration test called `@flow`-decorated functions directly (`sync_sp500_constituents_weekly`, `ingest_macro_daily`, etc.). Prefect 3.x raises `RuntimeError: Timed out while attempting to connect to ephemeral Prefect API server` when any `@flow` is called outside a running Prefect environment.
- **Fix:** Extracted `_run_X()` inner plain functions from all 5 flow modules that lacked them (constituents, macro, ff5, earnings, derived_macro). Integration test calls `_run_X()` directly. Same pattern as `prices._run_ingestion()` established in 02-02.
- **Files modified:** `constituents.py`, `macro.py`, `ff5.py`, `earnings.py`, `derived_macro.py`, `test_phase2_integration.py`
- **Commits:** b67162a7

**2. [Rule 1 - Bug] Parameter names in test did not match actual flow signatures**
- **Found during:** Task 1 planning (reading actual flow code vs. plan's test template)
- **Issue:** Plan's test used `_fetcher=`, `_client=`, `_fred=`, `_http=` — all leading-underscore names. Actual flows use `fetcher=`, `test_client=`, `fred_client=`, `http_override=` (fixed in 02-02..02-04 summaries).
- **Fix:** Integration test uses correct parameter names throughout.
- **Commits:** b67162a7

## Known Stubs

None — `derived_macro.py` is fully wired to real `price_bars` and `macro_indicators` tables. `deploy_all_flows.py` imports real `deploy()` functions.

## Threat Flags

None — no new network endpoints or auth paths. `derived_macro.py` reads from existing `price_bars` table (intra-DB) and writes to `macro_indicators` (existing table). No new external API dependencies.

## Self-Check

Files confirmed:
- `backend/app/flows/derived_macro.py` — exists
- `backend/tests/test_phase2_integration.py` — exists
- `backend/scripts/deploy_all_flows.py` — exists
- `backend/scripts/__init__.py` — exists

Commits confirmed:
- db1bb574 test(02-05): add failing integration tests for all 6 Phase 2 flows
- b67162a7 feat(02-05): derived HYG/LQD flow + inner _run_X helpers for integration testability
- ee08e339 feat(02-05): deploy_all_flows.py registers all 6 Phase 2 Prefect cron deployments

## Self-Check: PASSED
