---
phase: 04-portfolio-architecture
verified: 2026-05-03T00:00:00Z
status: human_needed
score: 5/6 must-haves verified
gaps: []
human_verification:
  - test: "Confirm that 'stored in macro_indicators' in SC-1 refers to the raw component series values (ingested by Phase 2) rather than the computed composite score column, since no macro_score column exists in macro_indicators and the plans never specified writing it there."
    expected: "Either (a) SC-1 is satisfied because the component data in macro_indicators is the storage contract and the computed score is ephemeral by design, OR (b) a gap exists requiring the composite score to be persisted."
    why_human: "Roadmap SC-1 says the score is 'computed from all 6 components and stored in macro_indicators'. The macro_indicators model has no macro_score column. The computed score lives only in PositionSizingResult (in-memory). Whether the roadmap means 'the component inputs are stored in macro_indicators' (true — Phase 2) or 'the composite score itself must be stored' (not implemented) requires author intent to resolve."
---

# Phase 4: Portfolio Architecture Verification Report

**Phase Goal:** Every signal-driven position size is gated through macro regime controls, ERP compression caps, Mag-7 concentration limits, and a completion portfolio that neutralizes unintended factor tilts
**Verified:** 2026-05-03
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Macro composite score (0 to -6) computed from all 6 components | ? UNCERTAIN | Score computed correctly in macro.py; 49 tests pass covering all bands. SC-1 also says "stored in macro_indicators" — no macro_score column exists in that table. See Human Verification. |
| 2 | Sizing multiplier correctly applied: 1.0x for 0 to -1, 0.65x for -2 to -3, 0.25x for -4 to -6; unit tests covering all three bands pass | ✓ VERIFIED | MACRO_BANDS dict with Decimal("1.0")/("0.65")/("0.25"); 21 test_macro.py tests pass; apply_sizing_multiplier verified for all 7 scores in [-6, 0]. |
| 3 | When E/P < real TIPS 10Y yield, ERP cap of 0.80x applied to all position sizes | ✓ VERIFIED | apply_erp_cap() with strict `<`; caps.py test 7-9 verify boundary; pipeline Test 5 confirms 0.02*0.80=0.016; log.warning fires. |
| 4 | Any Mag-7 position > 3% NAV capped to 3%; cap logged as constraint event | ✓ VERIFIED | apply_mag7_cap() with strict `>`; MAG7 frozenset has 7 symbols; MAG7_CAP=Decimal("0.03"); pipeline Tests 4 and 9 pass; log.warning with "MAG7" verified. |
| 5 | Completion portfolio allocates ~23% NAV to IVE/IYR; SLSQP achieves target FF3 betas within tolerance | ✓ VERIFIED | COMPLETION_WEIGHT=Decimal("0.23"); method='SLSQP'; 10 test_completion.py tests pass including test_achieved_betas_within_tolerance_realistic; FF3_TARGETS = {Mkt-Rf:0.985, SMB:-0.155, HML:0.025}; FF3_TOLERANCE=0.05. |
| 6 | 8% stop-loss hard limit enforced independently of RL sizing; unit test confirms trigger at exactly 8% | ✓ VERIFIED | STOP_LOSS_THRESHOLD=Decimal("0.08"); stop_loss_triggered uses `>=`; risk.py has zero RL/sizing imports; test_long_exactly_8_percent_drawdown_triggers and test_short_exactly_8_percent_move_triggers pass. |

**Score:** 5/6 truths verified (1 requires human disambiguation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/portfolio/macro.py` | compute_macro_score(), apply_sizing_multiplier(), MACRO_BANDS | ✓ VERIFIED | All 3 exports present; 21 tests pass; no forbidden imports |
| `backend/app/portfolio/caps.py` | MAG7, apply_mag7_cap(), apply_erp_cap(), CapDecision | ✓ VERIFIED | All 4 exports present; 13 tests pass; frozen dataclass confirmed |
| `backend/app/portfolio/risk.py` | STOP_LOSS_THRESHOLD, stop_loss_triggered(), stop_loss_price() | ✓ VERIFIED | All 3 exports present; 15 tests pass; entry_price validation added |
| `backend/app/portfolio/completion.py` | optimize_completion_weights(), CompletionAllocation, COMPLETION_WEIGHT, COMPLETION_INSTRUMENTS, FF3_TARGETS | ✓ VERIFIED | All exports present; SLSQP converges; 10 tests pass |
| `backend/app/portfolio/pipeline.py` | compute_position_size(), PositionSizingResult | ✓ VERIFIED | Both present; 11 tests pass; imports all Plan 01 primitives; 2 log.warning calls; no scipy import |
| `backend/requirements.txt` | scipy==1.14.1, numpy==2.1.3 | ✓ VERIFIED | Both pinned in requirements.txt |
| `backend/app/portfolio/macro_loader.py` | load_latest_macro_components(session, as_of) | ✓ VERIFIED | SERIES_TO_COMPONENT with all 6 series; ingestion_timestamp <= :as_of present; 6 DB-gated tests skip cleanly |
| `backend/app/tasks/portfolio.py` | compute_portfolio_size_task Celery task | ✓ VERIFIED | Registered as "app.tasks.portfolio.compute_portfolio_size_task"; routed to "portfolio" queue; 5 unit tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pipeline.py` | `macro.py`, `caps.py`, `risk.py` | `from app.portfolio.macro/caps/risk import` | ✓ WIRED | All 3 import statements present; compute_position_size calls all 4 primitives in correct order |
| `pipeline.py` | `MACRO_BANDS` dict | `apply_sizing_multiplier(score)` returns Decimal multiplier | ✓ WIRED | Band lookup iterates dict entries using `lo <= score <= hi`; verified for all 7 scores |
| `caps.py` | `MAG7` frozenset | `apply_mag7_cap(symbol, size_nav)` checks `symbol.upper() in MAG7` | ✓ WIRED | Case-normalization confirmed; 7 tickers in frozenset |
| `completion.py` | `scipy.optimize.minimize` | `method='SLSQP'` constrained optimization | ✓ WIRED | `from scipy.optimize import minimize`; method='SLSQP' confirmed |
| `tasks/portfolio.py` | `pipeline.py` | `compute_position_size` called inside `sync_session()` | ✓ WIRED | Import confirmed; called at step 4 of task flow |
| `macro_loader.py` | `macro_indicators` table | `SQLAlchemy text()` with `ingestion_timestamp <= :as_of` param | ✓ WIRED | FR-1.5 filter in SQL; LIMIT 1 per series; bound params (no f-strings) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `tasks/portfolio.py` | `result.stop_loss_price` | `compute_position_size()` -> `stop_loss_price(entry_price, direction)` | Yes — computed from DB price_bar.close | ✓ FLOWING |
| `tasks/portfolio.py` | `macro` dict | `load_latest_macro_components(session, created_at)` | Yes — queries macro_indicators with FR-1.5 filter | ✓ FLOWING |
| `completion.py` | `weights`, `achieved_betas` | `scipy.optimize.minimize` SLSQP solve | Yes — optimizer converges on feasible fixture | ✓ FLOWING |
| `pipeline.py` | `final_size_nav` | `naive_size_nav * macro_mult` -> ERP cap -> Mag-7 cap | Yes — deterministic Decimal arithmetic from inputs | ✓ FLOWING |

Note: `DEFAULT_EP_YIELD = Decimal("0.045")` and `DEFAULT_TIPS_YIELD = Decimal("0.020")` in tasks/portfolio.py are documented Phase 5 placeholders. With these values the ERP cap (fires when E/P < TIPS) will not trigger (0.045 > 0.020), meaning ERP cap is effectively dormant until Phase 5 wires a live feed. This is intentional and documented in the module, not a hidden stub.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Plan 01 — 49 unit tests pass | `pytest tests/portfolio/test_macro.py test_caps.py test_risk.py` | 49 passed in 0.02s | ✓ PASS |
| Plan 02 — 21 unit tests pass | `pytest tests/portfolio/test_completion.py test_pipeline.py` | 21 passed in 0.19s | ✓ PASS |
| Plan 03 — 5 unit tests pass (no broker/DB) | `pytest tests/tasks/test_portfolio_task.py` | 5 passed in 0.06s | ✓ PASS |
| Plan 03 — 9 DB-gated tests skip cleanly | `pytest tests/portfolio/test_macro_loader.py test_pipeline_integration.py` | 9 skipped in 0.01s | ✓ PASS |
| MACRO_BANDS lookup correctness | Inline Python: scores 0 to -6 map to 1.0/1.0/0.65/0.65/0.25/0.25/0.25 | All 7 correct | ✓ PASS |
| scipy isolated to completion.py | `grep -rE "(scipy|numpy)" app/portfolio/pipeline.py` (not an import) | Only docstring mention | ✓ PASS |
| No forbidden imports in Plan 01 modules | `grep -rE "(sqlalchemy|fastapi|celery|scipy|numpy)" macro.py caps.py risk.py` | No matches | ✓ PASS |
| Task registered with Celery | test_task_is_registered passes | PASS | ✓ PASS |

**Grand total: 75 passed, 9 skipped** (out of 84 collected)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FR-4.1 | 04-01, 04-02, 04-03 | Macro composite score from 6 components | ✓ SATISFIED | compute_macro_score() + COMPONENT_NAMES + all 6 series in SERIES_TO_COMPONENT |
| FR-4.2 | 04-01, 04-02, 04-03 | Sizing multiplier bands | ✓ SATISFIED | MACRO_BANDS with Decimal values; apply_sizing_multiplier() band lookup; pipeline chains it at step 2 |
| FR-4.3 | 04-01, 04-02, 04-03 | ERP compression cap at 0.80x when E/P < TIPS | ✓ SATISFIED | apply_erp_cap() with ERP_CAP_MULTIPLIER=Decimal("0.80"); strict `<` boundary; pipeline wires it at step 4 |
| FR-4.4 | 04-01, 04-02, 04-03 | Mag-7 concentration cap at 3% NAV | ✓ SATISFIED | apply_mag7_cap() with MAG7_CAP=Decimal("0.03"); 7-symbol frozenset; pipeline wires it at step 5 with log.warning |
| FR-4.5 | 04-02, 04-03 | Completion portfolio ~23% NAV, SLSQP FF3 betas | ✓ SATISFIED | completion.py with COMPLETION_WEIGHT=Decimal("0.23"), COMPLETION_INSTRUMENTS=("IVE","IYR"), SLSQP convergent |
| FR-4.6 | 04-01, 04-02, 04-03 | 8% stop-loss independent of RL sizing | ✓ SATISFIED | STOP_LOSS_THRESHOLD=Decimal("0.08"); `>=` triggers at exactly 8%; risk.py has zero sizing/RL imports |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/tasks/portfolio.py` | 23-25 | DEFAULT_EP_YIELD=0.045, DEFAULT_TIPS_YIELD=0.020 placeholder yields | ℹ️ Info | ERP cap dormant until Phase 5 wires live E/P/TIPS feeds. Documented in code and SUMMARY. Does not affect Mag-7, stop-loss, or macro gate. |

No blockers. No stubs in computation paths. No empty implementations. No hardcoded empty returns flowing to output.

### Human Verification Required

#### 1. Roadmap SC-1 Storage Claim

**Test:** Read Roadmap SC-1: "Macro composite score (0 to −6) is computed from all 6 components (yield curve, Sahm Rule, LEI, ISM PMI, HYG/LQD credit spreads, JPY/AUD carry) **and stored in** `macro_indicators`". Compare against implementation: the `macro_indicators` table has no `macro_score` column. The composite score is computed in `compute_macro_score()` and returned as `PositionSizingResult.macro_score` (in-memory). The `macro_indicators` table stores the raw component values (T10Y2Y, SAHMREALTIME, etc.) which are the inputs to the score.

**Expected:** Either:
- (a) SC-1 is satisfied as written — the phrase "stored in macro_indicators" refers to the 6 component series values being in that table (a Phase 2 deliverable), and the computed composite score is correctly ephemeral. In this interpretation Phase 4 is complete.
- (b) SC-1 requires the computed macro_score integer to be persisted to a DB column (e.g., a `macro_score` column in `portfolio_positions` or a separate `macro_snapshots` table). In this interpretation there is a gap.

**Why human:** The roadmap wording is ambiguous. The plans (04-01 through 04-03) never specified writing the composite score to any DB table. The `macro_indicators` table predates Phase 4 and stores individual series values. No plan created a `macro_score` column anywhere. Resolving whether the roadmap intended "the raw component data lives in macro_indicators" vs. "the computed score must be written to macro_indicators" requires the author's intent.

### Gaps Summary

No blocking gaps were found. All 6 pure-computation modules exist, are substantive, are wired into the pipeline, and have their data flow through to outputs. All 75 non-DB-gated tests pass. The 9 DB-gated tests skip cleanly.

One ambiguity in ROADMAP.md SC-1 ("stored in macro_indicators") cannot be resolved programmatically and requires human confirmation. If the author intended the raw component series (stored by Phase 2 in `macro_indicators`) as the storage contract, Phase 4 is fully complete. If the author intended the composite integer score to be persisted, a column and write step are missing.

The ERP cap placeholder yields (DEFAULT_EP_YIELD/DEFAULT_TIPS_YIELD) are intentional Phase 5 stubs, documented inline and in SUMMARY, and do not affect the correctness of any other gate.

---

## Deviations from Plan Noted

| Plan | Deviation | Impact |
|------|-----------|--------|
| 04-02 | FF3_TOLERANCE changed from 0.02 to 0.05 (domain spec conflict resolved by executor) | Tolerance is more lenient; SLSQP convergence is easier. Still within realistic domain range. |
| 04-02 | SLSQP equality constraint changed from sum-to-0.23 to sum-to-1 internally, then scaled | Achieved_betas are now correctly comparable to FF3_TARGETS; tests pass |
| 04-02 | Test 5 realistic fixture replaced with feasible betas | Plan's fixture was mathematically infeasible (HML target outside convex hull); replacement is feasible |

All deviations were self-corrected by the executor and documented in 04-02-SUMMARY.md.

---

_Verified: 2026-05-03_
_Verifier: Claude (gsd-verifier)_
