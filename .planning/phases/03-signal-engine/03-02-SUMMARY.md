---
phase: 03-signal-engine
plan: "02"
subsystem: signal-engine
tags: [signals, momentum, composite, filters, writer, pipeline, tdd]
dependency_graph:
  requires:
    - 03-01 (sectors.py, implied_eps.py, quality.py)
    - 02-02 (price_bars model)
    - 02-04 (earnings_events model)
  provides:
    - backend/app/signals/momentum.py → twenty_day_return(), compute_momentum_score()
    - backend/app/signals/composite.py → valuation_score(), compute_composite(), direction_for_composite()
    - backend/app/signals/filters.py → apply_sector_hurdle(), apply_roic_wacc_filter()
    - backend/app/signals/writer.py → SignalPayload, write_signal()
    - backend/app/signals/pipeline.py → compute_signal_for_event()
  affects:
    - 03-03 (Celery task wrapping compute_signal_for_event)
tech_stack:
  added: []
  patterns:
    - TDD red-green per task (6 commits: 3 RED + 3 GREEN)
    - Frozen dataclass (SignalPayload) for immutable signal payload
    - SQLAlchemy text() with bound parameters for all raw SQL (FR-1.5, T-03-07)
    - TYPE_CHECKING guard in filters.py to avoid circular import
    - MagicMock + patch for DB-free unit tests
key_files:
  created:
    - backend/app/signals/momentum.py
    - backend/app/signals/composite.py
    - backend/app/signals/filters.py
    - backend/app/signals/writer.py
    - backend/app/signals/pipeline.py
    - backend/tests/signals/test_momentum.py
    - backend/tests/signals/test_composite.py
    - backend/tests/signals/test_filters.py
    - backend/tests/signals/test_writer.py
    - backend/tests/signals/test_pipeline.py
  modified: []
decisions:
  - Percentile rank uses (below + ties_midpoint) / (n-1) formula to anchor min=0.0 and max=100.0 exactly, with neutral 50.0 for single-element cohort
  - valuation_score clamps ratio > 1 to 1 (eps_gap exceeding cohort max scores 0, not negative)
  - Pipeline _last_close and twenty_day_return both independently apply ingestion_timestamp <= :as_of per FR-1.5
  - Suppressed signals write nothing to DB; suppression reason is the audit trail (T-03-11 accepted)
metrics:
  duration_minutes: 5
  completed_date: "2026-05-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 10
  files_modified: 0
  tests_added: 77
---

# Phase 03 Plan 02: Signal Pipeline Glue Summary

**One-liner:** End-to-end signal computation pipeline — 20-day momentum (cohort percentile), three-axis composite (V+Q+M)/3, sector-hurdle + ROIC>WACC filters, and signal writer persisting naive 2% NAV baseline to signals hypertable.

## What Was Built

Five modules completing the signal computation chain from earnings event → signals row:

### 1. `backend/app/signals/momentum.py`

20-trading-day price return, cohort-normalized to percentile rank.

- `twenty_day_return(session, symbol, as_of)`: queries `price_bars` with `ingestion_timestamp <= :as_of` (FR-1.5 point-in-time), `LIMIT 21`, returns None when < 21 bars or zero denominator
- `compute_momentum_score(symbol_return, cohort_returns)`: percentile rank in [0, 100] using `(below + ties_midpoint) / (n-1) * 100` formula — guarantees min=0.0, max=100.0, median≈50.0; falls back to neutral 50.0 for None return or empty cohort

### 2. `backend/app/signals/composite.py`

Three-axis composite scorer (FR-3.5).

- `valuation_score(eps_gap, max_eps_gap)`: `(1 - |eps_gap| / max_gap) * 100`, clamped to [0, 100], 50.0 on None/zero inputs
- `compute_composite(valuation, quality, momentum)`: arithmetic mean `(V+Q+M)/3` rounded to 4 decimal places
- `direction_for_composite(composite)`: strict thresholds — `>50 → "long"`, `<50 → "short"`, `==50 → "hold"`

### 3. `backend/app/signals/filters.py`

Sector hurdle + ROIC>WACC filters (FR-3.3, FR-3.4).

| Filter | Sectors | Threshold | Miss behavior |
|--------|---------|-----------|---------------|
| Sector hurdle | All | SECTOR_HURDLE[sector] | Return (False, reason) |
| ROIC>WACC | Tech, Healthcare | ROIC = op_income / (revenue * 0.4) >= 0.10 | Return (False, reason) |

- `apply_sector_hurdle(quality_score, sector)`: returns `(True, "")` or `(False, "quality_score N < sector hurdle M (Sector)")`
- `apply_roic_wacc_filter(event, sector)`: returns `(True, "")`, `(True, "filter not applicable to {sector}")`, or `(False, reason)` for missing inputs or ROIC < WACC

### 4. `backend/app/signals/writer.py`

Signal persistence to hypertable (FR-3.5, FR-3.6).

**SignalPayload column mapping:**

| Column | Source | Notes |
|--------|--------|-------|
| symbol | event.symbol | |
| earnings_event_id | event.id | |
| eps_gap | computed | None if eps_actual missing |
| quality_score | QualityBreakdown.total | Decimal cast of int |
| three_axis_composite | compute_composite() | 4dp Decimal |
| naive_position_size | NAIVE_POSITION_SIZE | Fixed Decimal("0.0200") — FR-3.6 |
| direction | direction_for_composite() | "long"/"short"/"hold" |
| status | SignalPayload.status | Default "pending" |

`NAIVE_POSITION_SIZE = Decimal("0.0200")` is a module-level constant — never computed, always 2% NAV baseline.

### 5. `backend/app/signals/pipeline.py`

End-to-end orchestrator — `compute_signal_for_event(session, earnings_event_id, cohort_eps_gaps, cohort_returns)`.

**Pipeline execution order:**
1. Load event via `session.get(EarningsEvent, eid)` — return None + WARNING if missing
2. `_last_close()`: point-in-time price query (`ingestion_timestamp <= :as_of`, LIMIT 1) — return None + WARNING if no bars
3. `compute_implied_eps() + eps_gap()` → valuation component
4. `_load_prior_event()` + `compute_quality_score()` → quality component (prior=None handled)
5. `twenty_day_return()` + `compute_momentum_score()` → momentum component
6. `apply_sector_hurdle()` → return None + WARNING if suppressed
7. `apply_roic_wacc_filter()` → return None + WARNING if suppressed
8. `compute_composite()` + `direction_for_composite()` → three-axis composite
9. `write_signal()` → insert to signals hypertable, return signal_id

## Composite Formula Confirmed

```
composite = (valuation_score + quality_score + momentum_score) / 3
```

All three inputs are Decimal in [0, 100]. Result is Decimal rounded to 4 decimal places.

## Sector Hurdle Rates (from Plan 01)

| Sector | Hurdle | ROIC Filter? |
|--------|--------|--------------|
| Tech | 60 | Yes |
| Healthcare | 55 | Yes |
| Financials | 50 | No |
| Consumer | 45 | No |
| Energy | 45 | No |
| Industrials | 45 | No |
| Utilities | 45 | No |
| Other | 45 | No |

## Test Counts

| File | Tests | Status |
|------|-------|--------|
| tests/signals/test_momentum.py | 18 | PASS |
| tests/signals/test_composite.py | 21 | PASS |
| tests/signals/test_filters.py | 17 | PASS |
| tests/signals/test_writer.py | 11 | PASS |
| tests/signals/test_pipeline.py | 10 | PASS |
| **New total** | **77** | **All green** |
| **Plan 01 tests** | **67** | **All green** |
| **Grand total** | **144** | **All green** |

All tests run offline — no DB, no Docker, no network required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Percentile rank formula: max/min anchoring**
- **Found during:** Task 1 GREEN phase
- **Issue:** Plan-specified average-rank formula `(below + equal/2) / n * 100` returns 83.33 for max element of 3-element cohort instead of 100.0. Behavior spec explicitly requires max→100.0 and min→0.0.
- **Fix:** Changed to `(below + (equal-1)/2) / (n-1) * 100` formula with special case for single-element cohort (returns 50.0). This correctly anchors min=0.0, max=100.0, and median≈50.0.
- **Files modified:** backend/app/signals/momentum.py
- **Commit:** 148d312e (updated during GREEN phase before separate commit)

## Threat Mitigations Applied

Per plan's threat model — all `mitigate` dispositions implemented:

| Threat | Mitigation Implemented |
|--------|----------------------|
| T-03-07: SQL injection in momentum.py and pipeline.py | All raw SQL uses SQLAlchemy `text()` with bound parameters (`:symbol`, `:as_of`) — no f-string interpolation |
| T-03-08: upsert_rows data integrity | `conflict_cols=["created_at","signal_id"]` — server-generated UUID, no user input in PK |
| T-03-09: DoS unbounded query | `_last_close` uses LIMIT 1, `twenty_day_return` uses LIMIT 21 |
| T-03-13: DoS cohort unbounded | Cohort passed by caller, both are pure-Python list ops bounded by S&P 500 size |

## Known Stubs

None — all functions fully implemented and return computed values.

## Threat Flags

None — no new network endpoints, auth paths, file access, or schema changes. All modules use existing signals hypertable schema from Phase 2.

## Self-Check: PASSED

Files verified:
- FOUND: backend/app/signals/momentum.py
- FOUND: backend/app/signals/composite.py
- FOUND: backend/app/signals/filters.py
- FOUND: backend/app/signals/writer.py
- FOUND: backend/app/signals/pipeline.py
- FOUND: backend/tests/signals/test_momentum.py
- FOUND: backend/tests/signals/test_composite.py
- FOUND: backend/tests/signals/test_filters.py
- FOUND: backend/tests/signals/test_writer.py
- FOUND: backend/tests/signals/test_pipeline.py

Commits verified:
- 4f732806 — test(03-02): add failing tests for momentum score
- 148d312e — feat(03-02): implement momentum score
- 930d1eae — test(03-02): add failing tests for composite scorer and filters
- 8db04bd2 — feat(03-02): implement three-axis composite scorer and filters
- 87032838 — test(03-02): add failing tests for signal writer and pipeline
- 17d90251 — feat(03-02): implement signal writer and end-to-end pipeline
