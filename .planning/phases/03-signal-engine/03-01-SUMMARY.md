---
phase: 03-signal-engine
plan: "01"
subsystem: signal-engine
tags: [signals, pure-computation, sector-map, implied-eps, quality-scorer, tdd]
dependency_graph:
  requires:
    - 02-04 (EarningsEvent model from FMP earnings pipeline)
    - 02-02 (price_bars model for last_close reference)
  provides:
    - backend/app/signals/sectors.py → SECTOR_MAP, SECTOR_FWD_PE, SECTOR_HURDLE, sector_for()
    - backend/app/signals/implied_eps.py → compute_implied_eps(), eps_gap()
    - backend/app/signals/quality.py → QualityBreakdown, compute_quality_score()
  affects:
    - 03-02 (composite signal scorer will import these pure functions)
tech_stack:
  added: []
  patterns:
    - Pure computation modules (no DB, no Celery, no Prefect)
    - TDD red-green cycle for each module
    - Frozen dataclass for immutable score breakdown
    - TYPE_CHECKING guard to avoid circular SQLAlchemy import
key_files:
  created:
    - backend/app/signals/__init__.py
    - backend/app/signals/sectors.py
    - backend/app/signals/implied_eps.py
    - backend/app/signals/quality.py
    - backend/tests/signals/__init__.py
    - backend/tests/signals/test_sectors.py
    - backend/tests/signals/test_implied_eps.py
    - backend/tests/signals/test_quality.py
  modified: []
decisions:
  - Consumer sector merges Discretionary + Staples for v1 simplicity (unmerge in v2 if needed)
  - Margin expansion uses float arithmetic with pytest.approx tolerance for boundary assertions
  - TYPE_CHECKING guard on EarningsEvent import keeps quality.py DB-free at import time
metrics:
  duration_minutes: 4
  completed_date: "2026-05-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 8
  files_modified: 0
  tests_added: 67
---

# Phase 03 Plan 01: Signal Engine Building Blocks Summary

**One-liner:** Pure-computation signal building blocks — GICS sector map (67 tickers), market-implied EPS (price / sector fwd P/E), and 4-component quality scorer (0–100) with full TDD coverage.

## What Was Built

Three pure-Python modules with zero DB access, zero Prefect/Celery imports:

### 1. `backend/app/signals/sectors.py`

GICS sector lookup and plan-locked valuation tables.

- **SECTOR_MAP**: 67 S&P 500 tickers mapped to 7 sectors + `Other` fallback
- **SECTOR_FWD_PE**: median forward P/E per sector (plan-locked, not fetched from API)

| Sector | Fwd P/E | Hurdle |
|--------|---------|--------|
| Tech | 28.0 | 60 |
| Healthcare | 18.0 | 55 |
| Financials | 13.0 | 50 |
| Consumer | 22.0 | 45 |
| Energy | 12.0 | 45 |
| Industrials | 19.0 | 45 |
| Utilities | 16.0 | 45 |
| Other | 18.0 | 45 |

- **sector_for(symbol)**: case-insensitive lookup, returns `"Other"` for unknown/empty/None

### 2. `backend/app/signals/implied_eps.py`

Market-implied EPS (FR-3.1) — what EPS *must be* to justify current price at sector multiple.

```
implied_eps = last_close / SECTOR_FWD_PE[sector]
eps_gap = (eps_actual - eps_implied) / eps_implied
```

Guards: ValueError on negative price, Decimal("0") on zero price, Decimal("0") on zero implied (div-by-zero), None propagation on missing actual.

### 3. `backend/app/signals/quality.py`

4-component earnings quality decomposition (FR-3.2):

| Component | Signal | Max Pts | Formula |
|-----------|--------|---------|---------|
| Revenue surprise | Beat estimate | 25 | linear 0→25 capped at 10% beat |
| Margin expansion | Op margin vs prior | 25 | linear over ±5pp band |
| Share count discipline | Buyback | 25 | share_count < prior → 25, else 0 |
| Guidance direction | Forward look | 25 | up=25, flat=12, else=0 |

`QualityBreakdown` is a frozen dataclass exposing all four components individually. `compute_quality_score(current, prior)` returns `QualityBreakdown` with `total: int` in [0, 100].

## Test Coverage

| File | Tests | Status |
|------|-------|--------|
| tests/signals/test_sectors.py | 30 | PASS |
| tests/signals/test_implied_eps.py | 11 | PASS |
| tests/signals/test_quality.py | 26 | PASS |
| **Total** | **67** | **All green** |

All tests run offline — no DB, no network, no Docker required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Floating point boundary assertion in margin expansion test**
- **Found during:** Task 3 GREEN phase
- **Issue:** `(10/100 - 15/100) * 100` in float arithmetic produces `~3.55e-15` instead of exactly `-5.0`, causing `== 0.0` assertion to fail
- **Fix:** Changed test assertion to use `pytest.approx(0.0, abs=1e-10)` — the implementation is correct, the binary float representation has sub-femto error
- **Files modified:** backend/tests/signals/test_quality.py
- **Commit:** 0172b462

## Threat Mitigations Applied

Per plan's threat model — all `mitigate` dispositions implemented:

| Threat | Mitigation Implemented |
|--------|----------------------|
| T-03-01: Bad EarningsEvent data | All component helpers guard None, zero-divisor; revenue_estimate <= 0 → component = 0 |
| T-03-02: Negative price in implied_eps | `ValueError` raised on `last_close < 0` |

## Known Stubs

None — all functions are fully implemented and return computed values.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. All modules are pure computation only.

## Self-Check: PASSED

Files verified:
- FOUND: backend/app/signals/sectors.py
- FOUND: backend/app/signals/implied_eps.py
- FOUND: backend/app/signals/quality.py
- FOUND: backend/tests/signals/test_sectors.py
- FOUND: backend/tests/signals/test_implied_eps.py
- FOUND: backend/tests/signals/test_quality.py

Commits verified:
- c9ce69dc — feat(03-01): implement GICS sector map
- 6ce1cfd5 — feat(03-01): implement market-implied EPS formula
- 0172b462 — feat(03-01): implement 4-component quality scorer
