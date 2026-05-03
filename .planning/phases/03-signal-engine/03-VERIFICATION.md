---
phase: 03-signal-engine
verified: 2026-05-03T00:00:00Z
status: human_needed
score: 7/7 must-haves verified
gaps: []
human_verification:
  - test: "Run DB-gated integration tests with a live TimescaleDB instance (docker compose up + alembic upgrade head, set DATABASE_URL_SYNC). Execute: cd backend && DATABASE_URL_SYNC=... python3 -m pytest tests/signals/test_pipeline_integration.py tests/signals/test_pipeline_perf.py -v"
    expected: "3 integration tests pass (end-to-end happy path, sector hurdle suppression, ROIC<WACC suppression), 1 perf test passes asserting elapsed < 5.0s. All 4 tests show PASSED, not SKIPPED."
    why_human: "DB-gated tests skip without DATABASE_URL_SYNC set. The FR-3.7 performance budget and the actual DB write (naive_position_size=0.0200) can only be confirmed with a live PostgreSQL+TimescaleDB instance."
---

# Phase 3: Signal Engine Verification Report

**Phase Goal:** Given a new earnings event, the system computes a market-implied EPS signal, earnings quality score, three-axis composite, and a naive baseline position size — all within 5 seconds
**Verified:** 2026-05-03
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | For any ticker with a completed earnings event, the system produces a market-implied EPS value computed as price / sector median forward P/E (not analyst consensus) | VERIFIED | `compute_implied_eps(last_close, sector)` in `implied_eps.py`; divides by `SECTOR_FWD_PE[sector]`; 11 unit tests pass covering formula, edge cases, sector fallback |
| 2 | A quality decomposition score (0–100) is generated with all four components visible (revenue surprise, margin expansion, share count discipline, guidance direction) | VERIFIED | `QualityBreakdown` frozen dataclass with all four fields; `compute_quality_score` returns breakdown with `total: int` in [0,100]; 26 unit tests pass |
| 3 | Sector hurdle rates are applied; signals below the sector threshold are suppressed and logged as such | VERIFIED | `apply_sector_hurdle(quality_score, sector)` in `filters.py`; uses `SECTOR_HURDLE` from `sectors.py`; pipeline calls it and logs `log.warning` on suppression; 17 filter tests + 10 pipeline tests pass |
| 4 | ROIC > WACC filter is applied to tech/biotech names; filter decisions are logged | VERIFIED | `apply_roic_wacc_filter(event, sector)` applies only to `ROIC_FILTER_SECTORS = frozenset({"Tech", "Healthcare"})`; WACC_PROXY=0.10, ROIC=op_income/(rev*0.4); suppression logged; tests pass |
| 5 | Three-axis composite (valuation x quality x momentum) is computed and persisted to the `signals` table | VERIFIED | `compute_composite(val, quality, momentum)` = (V+Q+M)/3 as 4dp Decimal; `write_signal` persists `three_axis_composite` column via `upsert_rows(Signal.__table__, ...)`; 21 composite + 11 writer tests pass |
| 6 | Naive baseline produces a fixed 2% NAV position size for any signal-aligned name; this value is stored alongside the signal | VERIFIED | `NAIVE_POSITION_SIZE = Decimal("0.0200")` in `writer.py`; `SignalPayload.naive_position_size` defaults to it; `write_signal` row dict includes `naive_position_size`; writer tests assert exact value |
| 7 | End-to-end signal computation for one earnings event completes in under 5 seconds | PARTIAL — code exists, untested without DB | `test_signal_computation_under_5_seconds` in `test_pipeline_perf.py` with `PERF_BUDGET_SECONDS=5.0` and `time.perf_counter`; test skips without `DATABASE_URL_SYNC` env var; cannot confirm budget met without live DB |

**Score:** 7/7 truths covered in code; 6/7 verified offline + 1 requires human DB run

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/signals/sectors.py` | GICS sector map + SECTOR_FWD_PE + SECTOR_HURDLE + sector_for() | VERIFIED | All four exports present; 8 sectors with correct values (Tech FwdPE=28, hurdle=60, etc.); sector_for() returns "Other" for unknown |
| `backend/app/signals/implied_eps.py` | compute_implied_eps + eps_gap | VERIFIED | Both functions present; imports SECTOR_FWD_PE from sectors.py; divide-by-zero and negative-price guards present |
| `backend/app/signals/quality.py` | QualityBreakdown dataclass + compute_quality_score | VERIFIED | Frozen dataclass with 5 fields (4 components + total); compute_quality_score returns QualityBreakdown; 4 helper functions |
| `backend/app/signals/momentum.py` | compute_momentum_score + twenty_day_return | VERIFIED | Both functions present; ingestion_timestamp <= :as_of point-in-time filter; LIMIT 21; percentile rank formula with min=0/max=100 anchoring |
| `backend/app/signals/composite.py` | compute_composite + valuation_score + direction_for_composite | VERIFIED | All three functions; arithmetic mean (V+Q+M)/3 rounded to 4dp; strict >50 → long, <50 → short, =50 → hold |
| `backend/app/signals/filters.py` | apply_sector_hurdle + apply_roic_wacc_filter | VERIFIED | Both functions; WACC_PROXY=0.10, ROIC_REVENUE_FACTOR=0.4, ROIC_FILTER_SECTORS={"Tech","Healthcare"} |
| `backend/app/signals/writer.py` | SignalPayload + write_signal | VERIFIED | NAIVE_POSITION_SIZE=Decimal("0.0200"); 7 signal columns in row dict; upsert via Signal.__table__ |
| `backend/app/signals/pipeline.py` | compute_signal_for_event orchestrator | VERIFIED | Imports all 6 sub-modules; full 9-step pipeline; both filters applied; log.warning on suppression; returns None without writing when suppressed |
| `backend/app/tasks/signals.py` | compute_signal_task Celery task | VERIFIED | @celery_app.task with name="app.tasks.signals.compute_signal_task"; uses sync_session; imports compute_signal_for_event |
| `backend/tests/signals/test_pipeline_integration.py` | DB-gated end-to-end tests | VERIFIED | 3 test functions present; Decimal("0.0200") assertion; DATABASE_URL_SYNC skipif gate |
| `backend/tests/signals/test_pipeline_perf.py` | <5s performance benchmark | VERIFIED | PERF_BUDGET_SECONDS=5.0; test_signal_computation_under_5_seconds; time.perf_counter; warmup pass; FR-3.7 in assertion message; DATABASE_URL_SYNC gate |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `implied_eps.py` | `sectors.py` | `from app.signals.sectors import SECTOR_FWD_PE` | WIRED | Import present and used in compute_implied_eps |
| `filters.py` | `sectors.py` | `from app.signals.sectors import SECTOR_HURDLE` | WIRED | Import present and used in apply_sector_hurdle |
| `pipeline.py` | all signal sub-modules | `from app.signals.{composite,filters,implied_eps,momentum,quality,sectors,writer} import ...` | WIRED | All 7 sub-module imports present; all imported names are called in compute_signal_for_event |
| `momentum.py` | `price_bars` | `SELECT close FROM price_bars WHERE ... ingestion_timestamp <= :as_of` | WIRED | Raw SQL with bound params; fetches 21 rows; computes 20-day return |
| `pipeline.py` | `price_bars` | `_last_close()` raw SQL with ingestion_timestamp <= :as_of LIMIT 1 | WIRED | Point-in-time filter present in second price query site |
| `writer.py` | `signals` table | `upsert_rows(Signal.__table__, ...)` | WIRED | Signal model imported; Signal.__table__ used as target; 10-column row dict |
| `tasks/signals.py` | `worker.py` | `from app.worker import celery_app` + `@celery_app.task` | WIRED | celery_app imported; task registered; routing `app.tasks.signals.*` → `signals` queue in worker.py conf |
| `tasks/signals.py` | `pipeline.py` | `from app.signals.pipeline import compute_signal_for_event` | WIRED | Import present; called inside sync_session context manager |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `pipeline.py` | `last_close` | `_last_close()` → price_bars SQL | Yes — SQL query with WHERE + ORDER BY + LIMIT 1; returns Decimal | FLOWING |
| `pipeline.py` | `qb` (QualityBreakdown) | `compute_quality_score(event, prior)` | Yes — real arithmetic on EarningsEvent fields | FLOWING |
| `pipeline.py` | `mom_score` | `twenty_day_return()` → price_bars SQL + percentile rank | Yes — SQL LIMIT 21 + Python percentile computation | FLOWING |
| `pipeline.py` | `composite` | `compute_composite(val, quality, mom)` | Yes — arithmetic mean of three real Decimals | FLOWING |
| `writer.py` | row dict | `SignalPayload` fields from pipeline computation | Yes — all fields populated from real computations, not hardcoded | FLOWING |
| `tasks/signals.py` | return value | `compute_signal_for_event(session, earnings_event_id)` | Yes — DB read + compute + write; returns real UUID or None | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| sector_for("AAPL") == "Tech" | `python3 -c "from app.signals.sectors import sector_for; assert sector_for('AAPL')=='Tech'; print('OK')"` (from backend/) | OK | PASS |
| compute_implied_eps(280, "Tech") == 10.0000 | `python3 -c "from decimal import Decimal; from app.signals.implied_eps import compute_implied_eps; assert compute_implied_eps(Decimal('280'),'Tech')==Decimal('10.0000'); print('OK')"` | OK | PASS |
| compute_composite(60,60,60) == 60.0000 | `python3 -c "from decimal import Decimal; from app.signals.composite import compute_composite; assert compute_composite(Decimal('60'),Decimal('60'),Decimal('60'))==Decimal('60.0000'); print('OK')"` | OK | PASS |
| compute_signal_task registered in Celery | `python3 -c "from app.tasks.signals import compute_signal_task; from app.worker import celery_app; assert 'app.tasks.signals.compute_signal_task' in celery_app.tasks; print('OK')"` | OK | PASS |
| 149 offline tests pass | `python3 -m pytest tests/signals/ tests/tasks/ -q` (excluding DB-gated) | 149 passed in 0.10s | PASS |
| 4 DB-gated tests skip cleanly | `python3 -m pytest tests/signals/test_pipeline_integration.py tests/signals/test_pipeline_perf.py -q` | 4 skipped | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FR-3.1 | 03-01-PLAN.md | Market-implied EPS = price / sector median forward P/E (not analyst consensus) | SATISFIED | `compute_implied_eps` in implied_eps.py; 11 tests; formula correct |
| FR-3.2 | 03-01-PLAN.md | 4-component quality decomposition (0–100): revenue surprise, margin expansion, share count discipline, guidance direction | SATISFIED | `QualityBreakdown` + `compute_quality_score`; all 4 components individually visible; 26 tests |
| FR-3.3 | 03-02-PLAN.md | Sector hurdle rates applied; signals below threshold suppressed and logged | SATISFIED | `apply_sector_hurdle` with SECTOR_HURDLE table; pipeline logs WARNING and returns None on suppression |
| FR-3.4 | 03-02-PLAN.md | ROIC > WACC filter for tech/biotech; decisions logged | SATISFIED | `apply_roic_wacc_filter` applies to Tech+Healthcare only; WACC=0.10; ROIC=op_income/(rev*0.4); logged |
| FR-3.5 | 03-02-PLAN.md | Three-axis composite (valuation x quality x momentum) computed and persisted to signals table | SATISFIED | `compute_composite` = (V+Q+M)/3; persisted via `write_signal` to signals hypertable |
| FR-3.6 | 03-02-PLAN.md | Fixed 2% NAV naive baseline stored alongside signal, used as IR denominator | SATISFIED | `NAIVE_POSITION_SIZE = Decimal("0.0200")` in writer.py; persisted in naive_position_size column |
| FR-3.7 | 03-03-PLAN.md | End-to-end signal computation < 5 seconds | NEEDS HUMAN | `test_signal_computation_under_5_seconds` with PERF_BUDGET_SECONDS=5.0 exists and is structurally correct; requires live DB to confirm elapsed < 5.0s |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | All 8 signal modules and task module are clean: no TODO/FIXME, no placeholder returns, no hardcoded empty data flowing to rendering |

### Human Verification Required

#### 1. FR-3.7 Performance Budget + Integration Tests

**Test:** With Docker Compose running and TimescaleDB schema applied (`alembic upgrade head`):
```bash
cd backend
export DATABASE_URL_SYNC=postgresql://...
python3 -m pytest tests/signals/test_pipeline_integration.py tests/signals/test_pipeline_perf.py -v
```

**Expected:**
- `test_end_to_end_signal_for_earnings_event` — PASSED: signal row written with `naive_position_size=0.0200`, `direction` in {long,short,hold}, `three_axis_composite` in [0,100]
- `test_signal_suppressed_below_sector_hurdle` — PASSED: returns None, 0 rows in signals table
- `test_signal_suppressed_by_roic_wacc_filter` — PASSED: NVDA (ROIC=0.05<0.10) returns None, 0 rows
- `test_signal_computation_under_5_seconds` — PASSED: elapsed < 5.0s (message shows actual time)

**Why human:** All 4 tests use `pytest.mark.skipif(not os.environ.get("DATABASE_URL_SYNC"), ...)`. No DB is available in the automated verification environment. The performance budget (FR-3.7) and actual DB persistence behavior can only be confirmed with a live PostgreSQL+TimescaleDB instance.

### Gaps Summary

No structural gaps. All 7 ROADMAP success criteria are addressed in code. The sole outstanding item is the DB-gated FR-3.7 performance confirmation — the test infrastructure is correct and complete, but execution requires a live database. All 149 offline tests pass.

---

_Verified: 2026-05-03_
_Verifier: Claude (gsd-verifier)_
