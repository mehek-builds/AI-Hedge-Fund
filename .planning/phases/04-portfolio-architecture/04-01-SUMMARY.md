---
phase: 04-portfolio-architecture
plan: "01"
subsystem: portfolio-risk-primitives
tags: [portfolio, macro, risk, caps, stop-loss, pure-computation, tdd]
dependency_graph:
  requires: []
  provides:
    - backend/app/portfolio/macro.py
    - backend/app/portfolio/caps.py
    - backend/app/portfolio/risk.py
  affects:
    - Phase 4 Plan 02 (position sizing pipeline consumes all three modules)
tech_stack:
  added: []
  patterns:
    - Pure-computation module with Decimal arithmetic (no float)
    - Frozen dataclass for constraint decision results (CapDecision)
    - TDD red-green cycle per task
key_files:
  created:
    - backend/app/portfolio/__init__.py
    - backend/app/portfolio/macro.py
    - backend/app/portfolio/caps.py
    - backend/app/portfolio/risk.py
    - backend/tests/portfolio/__init__.py
    - backend/tests/portfolio/test_macro.py
    - backend/tests/portfolio/test_caps.py
    - backend/tests/portfolio/test_risk.py
  modified: []
decisions:
  - "MACRO_BANDS dict uses (hi, lo) integer tuple keys matching the spec exactly"
  - "score_component treats unknown names as ValueError to prevent silent misconfiguration"
  - "apply_mag7_cap uses strict > comparison so exactly 3% NAV is not capped (boundary per spec)"
  - "apply_erp_cap uses strict < comparison so E/P == TIPS yield is not capped (boundary per spec)"
  - "stop_loss_triggered uses >= so exactly 8% drawdown triggers (FR-4.6: triggers at exactly 8%)"
  - "risk.py validates entry_price > 0 to prevent division-by-zero (Rule 2 — missing input validation)"
metrics:
  duration: "~23 minutes"
  completed: "2026-05-04T00:00:14Z"
  tasks_completed: 3
  files_created: 8
  tests_added: 49
requirements_satisfied:
  - FR-4.1
  - FR-4.2
  - FR-4.3
  - FR-4.4
  - FR-4.6
---

# Phase 4 Plan 01: Portfolio Risk Primitives Summary

Three pure-computation modules providing macro composite scoring + sizing multiplier (FR-4.1/4.2), Mag-7 concentration cap + ERP compression cap (FR-4.3/4.4), and 8% stop-loss enforcement (FR-4.6) — all Decimal-precise, DB-free, 49 tests green.

## What Was Built

### backend/app/portfolio/macro.py (FR-4.1, FR-4.2)

Macro composite scorer and sizing multiplier.

- `MACRO_BANDS: dict[tuple[int, int], Decimal]` — `{(0,-1): 1.0, (-2,-3): 0.65, (-4,-6): 0.25}`
- `COMPONENT_NAMES` — 6-series tuple: yield_curve, sahm, lei, ism_pmi, hyg_lqd_spread, jpy_aud_carry
- `score_component(name, value)` — returns 0 or -1 per published thresholds; None treated as 0 (fail-safe)
- `compute_macro_score(components)` — sums 6 components, clamped to [-6, 0]
- `apply_sizing_multiplier(score)` — band lookup returning Decimal; ValueError for out-of-range

### backend/app/portfolio/caps.py (FR-4.3, FR-4.4)

Position concentration caps returning immutable `CapDecision` dataclasses.

- `MAG7: frozenset[str]` — {"AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AMZN"}
- `MAG7_CAP = Decimal("0.03")`, `ERP_CAP_MULTIPLIER = Decimal("0.80")`
- `CapDecision(frozen=True)` — fields: `size_nav`, `was_capped`, `reason`
- `apply_mag7_cap(symbol, size_nav)` — strict `>` boundary; uppercase normalizes symbol
- `apply_erp_cap(size_nav, ep_yield, real_tips_yield)` — strict `<` on E/P vs TIPS

### backend/app/portfolio/risk.py (FR-4.6)

Stop-loss enforcement independent of any RL or sizing logic.

- `STOP_LOSS_THRESHOLD = Decimal("0.08")`
- `stop_loss_price(entry_price, direction)` — computes trigger price level
- `stop_loss_triggered(entry_price, current_price, direction)` — uses `>=` so exactly 8% triggers
- Validates `entry_price > 0` and direction in {"long", "short"}

## Test Counts

| Module | Tests | Method |
|--------|-------|--------|
| test_macro.py | 21 | TDD red-green |
| test_caps.py | 13 | TDD red-green |
| test_risk.py | 15 | TDD red-green |
| **Total** | **49** | |

All 49 tests pass. Zero skipped. Zero failures.

## Decisions Made

1. **MACRO_BANDS tuple keys** — Using `(hi, lo)` integer tuples exactly as specified in the plan. Band lookup iterates dict entries and uses `lo <= score <= hi`, which correctly handles the asymmetric ranges.

2. **Unknown component names raise ValueError** — Prevents silent misconfiguration where a typo in a component name would quietly contribute 0 rather than fail fast.

3. **Mag-7 strict `>` boundary** — Position exactly at 3% NAV passes through uncapped. This matches the spec ("Mag-7 position > 3% NAV is capped") and the test plan's Test 3.

4. **ERP strict `<` boundary** — E/P equal to TIPS yield is not compressed. Matches spec and Test 9.

5. **Stop-loss `>=` boundary** — Exactly 8% drawdown triggers. This is the FR-4.6 requirement ("triggers at exactly 8%") and is confirmed by Tests 1 and 4.

6. **Entry price validation in risk.py (Rule 2)** — Added `entry_price > 0` guard to prevent division-by-zero in drawdown calculation. Not in original plan but required for correctness.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added entry_price > 0 validation in risk.py**

- **Found during:** Task 3 implementation
- **Issue:** `stop_loss_triggered` performs `(entry - current) / entry` — a zero or negative entry price would cause ZeroDivisionError or silently wrong results
- **Fix:** Added `_validate_entry_price(entry_price)` helper that raises `ValueError` for `entry_price <= 0`; exposed via Tests 12 and 13 in test_risk.py
- **Files modified:** `backend/app/portfolio/risk.py`, `backend/tests/portfolio/test_risk.py`
- **Commit:** 0c74ef6b

All other plan steps executed as written.

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-04-01 | `compute_macro_score` treats missing components as 0 (fail-safe, not -1); score clamped to [-6, 0] |
| T-04-02 | `apply_mag7_cap` and `apply_erp_cap` return `CapDecision(was_capped=True/False)` — caller cannot bypass silently |
| T-04-04 | `risk.py` has zero imports from sizing, RL, or signal modules — verified by grep |

## Commit History

| Task | Phase | Hash | Message |
|------|-------|------|---------|
| 1 RED | Task 1 | 61422462 | test(04-01): add failing tests for macro composite scorer |
| 1 GREEN | Task 1 | fa79929a | feat(04-01): implement macro score and sizing multiplier (FR-4.1, FR-4.2) |
| 2 RED | Task 2 | 32acdadf | test(04-01): add failing tests for Mag-7 and ERP caps |
| 2 GREEN | Task 2 | 56ef3b40 | feat(04-01): implement Mag-7 concentration cap and ERP compression cap (FR-4.3, FR-4.4) |
| 3 RED | Task 3 | 936a7a06 | test(04-01): add failing tests for 8% stop-loss enforcement |
| 3 GREEN | Task 3 | 0c74ef6b | feat(04-01): implement 8% stop-loss enforcement (FR-4.6) |

## Known Stubs

None. All modules are fully implemented with no placeholders, TODO comments, or hardcoded empty returns that flow to UI.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

All 9 files verified present. All 6 commits verified in git log.
